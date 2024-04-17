import functools
from dataclasses import dataclass
from multiprocessing import Pool
from typing import List, Tuple

import requests
from bs4 import BeautifulSoup
from ebooklib import epub
from ebooklib.epub import EpubHtml, EpubImage, EpubBook
from requests import Session
import bisect
import urllib.parse
import os


@dataclass(order=True)
class Chapters:
    num: int
    original_href: str
    txt: str
    new_href: str

    def __hash__(self):
        return hash((self.original_href, self.txt))

    def __post_init__(self):
        self.sort_index = self.num


@dataclass(order=True)
class Image:
    num: int
    src: str
    media_type: str
    file_name: str

    def __post_init__(self):
        self.sort_index = self.num


@dataclass(order=True)
class IndexedEpubImage:
    num: int
    data: EpubImage

    def __post_init__(self):
        self.sort_index = self.num


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

        images = Extractor.all_images("introduction", content)

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
                num=i,
                original_href=original_href,
                txt=str(c.string),
                new_href=f"update_{i}.xhtml"
            )

        chapters = list(map(build_chapter, enumerate(chapters)))

        return chapters

    @staticmethod
    def all_images(prefix: str, content: BeautifulSoup) -> List[Image]:
        images = content.find_all("img")
        r = []
        for i, x in enumerate(images):
            base_name = os.path.split(urllib.parse.urlparse(x['src']).path)[1]
            new_filename = f"images/{prefix}/{i}_{base_name}"
            r.append(Image(
                num=i,
                src=x['src'],
                media_type=x["src"][-3:],
                file_name=new_filename
            ))
            x['src'] = new_filename
        return r

    @staticmethod
    def get_update(prefix: str, p: BeautifulSoup) -> Update:
        content = p.find("div", id="content")
        images = Extractor.all_images(prefix, content)
        return Update(content=str(content), images=images)


@dataclass(order=True)
class Page:
    num: int
    chapter: EpubHtml
    images: List[IndexedEpubImage]

    def __post_init__(self):
        self.sort_index = self.num


def _get_image(session: Session, url_root: str, img: Image) -> IndexedEpubImage:
    r = session.get(f"{url_root}/{img.src}")
    return IndexedEpubImage(img.num, EpubImage(uid=img.file_name, file_name=img.file_name, media_type=img.media_type,
                                               content=r.content))


def build_intro(pool: Pool, session: Session, url_root: str, intro: Intro) -> Page:
    intro_chapter = epub.EpubHtml(title="Introduction", file_name="introduction.xhtml", lang=intro.language)
    intro_chapter.content = intro.intro
    images = []

    builder = functools.partial(_get_image, session, url_root)

    for i in pool.imap_unordered(builder, intro.images):
        bisect.insort(images, i)

    return Page(0, intro_chapter, images)


def build_update(session: Session, chapter: Chapters, data: Update, intro: Intro) -> Page:
    update_chapter = epub.EpubHtml(title=chapter.txt, file_name=chapter.new_href,
                                   lang=intro.language)  # TODO: fix language
    update_chapter.content = data.content

    img_builder = functools.partial(_get_image, session, chapter.original_href)

    images: List[IndexedEpubImage] = list(map(img_builder, data.images))

    return Page(chapter.num, update_chapter, images)


def add_page(book: EpubBook, toc: List, spine: List, page: Page):
    book.add_item(page.chapter)
    for img in page.images:
        book.add_item(img.data)
    toc.append(epub.Link(page.chapter.file_name, page.chapter.title, page.chapter.id))
    spine.append(page.chapter)


def build_single_page(session: Session, intro: Intro, chapter: Chapters) -> Page:
    chapter_page = session.get(chapter.original_href)
    chapter_bs = BeautifulSoup(chapter_page.content, 'html.parser')
    update = Extractor.get_update(str(chapter.num), chapter_bs)
    return build_update(session, chapter, update, intro)


class DummyUpdater:

    def __init__(self, *args, **kwargs):
        pass


def lparchive2epub(update_manager, url: str, file: str):
    if update_manager is None:
        update_manager = DummyUpdater

    session = requests.Session()

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
    with Pool() as pool:

        epub_intro = build_intro(pool, session, url, intro)

        add_page(book, toc, spine, epub_intro)

        page_builder = functools.partial(build_single_page, session)
        page_builder = functools.partial(page_builder, intro)

        pages_iterator = pool.imap_unordered(page_builder, intro.chapters)
        pages = []
        with update_manager(total=len(intro.chapters)) as pbar:
            for p in pages_iterator:
                bisect.insort(pages, p)
                pbar.update()

    for p in pages:
        add_page(book, toc, spine, p)

    book.toc = toc

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    book.spine = spine

    epub.write_epub(file, book)

# todo: add ongoing treatment to show that it's working
# todo: add style imported from page?
