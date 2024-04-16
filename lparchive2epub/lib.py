import functools
from dataclasses import dataclass
from typing import List, Tuple

import requests
from bs4 import BeautifulSoup
from ebooklib import epub
from ebooklib.epub import EpubHtml, EpubImage, EpubBook
from multiprocessing import Pool

session = requests.Session()

@dataclass(order=True)
class Chapters:
    original_href: str
    txt: str
    new_href: str

    def __hash__(self):
        return hash((self.original_href, self.txt))

    def __post_init__(self):
        self.sort_index = self.original_href


@dataclass
class Image:
    src: str
    media_type: str


@dataclass
class Intro:
    title: str
    language: str
    author: str
    intro: str
    images: List[Image]
    chapters: List[Chapters]


@dataclass
class Update:
    content: str
    images: List[Image]


class Extractor:

    @staticmethod
    def intro(url: str, p: BeautifulSoup) -> Intro:
        title = p.title.text
        author = next(x for x in p.find_all("meta") if x.get("name", None) == "author").get("content", None)
        language = "en"
        content = p.find("div", id="content")
        chapters = Extractor.all_chapters(url, p)
        for c in chapters:
            a = content.find("a", text=c.txt)
            a['href'] = c.new_href

        images = Extractor.all_images(content)

        return Intro(
            title=title, language=language, author=author, intro=str(content), images=images, chapters=chapters
        )

    @staticmethod
    def all_chapters(root_url: str, p: BeautifulSoup) -> List[Chapters]:
        content = p.find("div", id="content")

        chapters = content.find_all("a")
        chapters = (x for x in chapters if "Update" in x.get("href", None))

        def build_chapter(chap: Tuple[int, BeautifulSoup]) -> Chapters:
            i, c = chap
            original_href = c.get("href", None)
            if original_href.startswith("Update"):
                original_href = f"{root_url}/{original_href}"
            return Chapters(
                original_href=original_href,
                txt=str(c.string),
                new_href=f"update_{i}.xhtml")

        chapters = list(map(build_chapter, enumerate(chapters)))

        return chapters

    @staticmethod
    def all_images(content: BeautifulSoup) -> List[Image]:
        images = content.find_all("img")
        return [Image(src=x['src'], media_type=x["src"][-3:]) for x in images]

    @staticmethod
    def get_update(p: BeautifulSoup) -> Update:
        content = p.find("div", id="content")
        images = Extractor.all_images(content)
        return Update(content=str(content), images=images)


@dataclass
class Page:
    chapter: EpubHtml
    images: List[EpubImage]


def build_intro(url_root: str, intro: Intro) -> Page:
    intro_chapter = epub.EpubHtml(title="Introduction", file_name="introduction.xhtml", lang=intro.language)
    intro_chapter.content = intro.intro
    images = []
    for img in intro.images:
        r = session.get(f"{url_root}/{img.src}")
        epub_img = EpubImage(uid=img.src, file_name=img.src, media_type=img.media_type, content=r.content)
        images.append(epub_img)
    return Page(intro_chapter, images)


def build_update(chapter: Chapters, data: Update, intro: Intro) -> Page:
    update_chapter = epub.EpubHtml(title=chapter.txt, file_name=chapter.new_href,
                                   lang=intro.language)  # TODO: fix language
    update_chapter.content = data.content

    def img_builder(img: Image) -> EpubImage:
        r = session.get(f"{chapter.original_href}/{img.src}")
        return EpubImage(uid=img.src, file_name=img.src, media_type=img.media_type, content=r.content)

    images: List[EpubImage] = list(map(img_builder, data.images))

    return Page(update_chapter, images)


def add_page(book: EpubBook, toc: List, spine: List, page: Page):
    book.add_item(page.chapter)
    for img in page.images:
        book.add_item(img)
    toc.append(epub.Link(page.chapter.file_name, page.chapter.title, page.chapter.id))
    spine.append(page.chapter)

def build_single_page(intro: Intro, chapter: Chapters) -> Page:
    chapter_page = session.get(chapter.original_href)
    chapter_bs = BeautifulSoup(chapter_page.content, 'html.parser')
    update = Extractor.get_update(chapter_bs)
    return build_update(chapter, update, intro)

def lparchive2epub(url: str, file: str):
    page = session.get(url)
    landing = BeautifulSoup(page.content, 'html.parser')
    book = epub.EpubBook()
    intro = Extractor.intro(url, landing)

    book.add_author(intro.author)
    book.set_title(intro.title)
    book.set_language(intro.language)
    book.set_identifier(f"lparchive2epub-{hash(intro.title)}-{hash(intro.author)}-{hash(url)}")

    toc = []
    spine = ["nav"]
    epub_intro = build_intro(url, intro)

    add_page(book, toc, spine, epub_intro)

    builder = functools.partial(build_single_page, intro)

    with Pool() as pool:
        pages = pool.map(builder, intro.chapters)

    for page in pages:
        add_page(book, toc, spine, page)

    book.toc = toc

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    book.spine = spine

    epub.write_epub(file, book)

# todo: add ongoing treatment to show that it's working
# todo: add prefix to images (intro, chapter_{num})
# todo: add style imported from page?
