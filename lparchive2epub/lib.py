import functools
from dataclasses import dataclass
from typing import List, Tuple

import aiohttp
from bs4 import BeautifulSoup
from ebooklib import epub
from ebooklib.epub import EpubHtml, EpubImage, EpubBook
import urllib.parse
import os
import asyncio

from tqdm.asyncio import tqdm

from contextlib import nullcontext


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


async def _get_image(session: aiohttp.ClientSession, url_root: str, img: Image) -> IndexedEpubImage:
    async with session.get(f"{url_root}/{img.src}") as r:
        return IndexedEpubImage(img.num, EpubImage(
            uid=img.file_name,
            file_name=img.file_name,
            media_type=img.media_type,
            content=await r.content.read()))


async def build_intro(session: aiohttp.ClientSession, url_root: str, intro: Intro) -> Page:
    intro_chapter = epub.EpubHtml(title="Introduction", file_name="introduction.xhtml", lang=intro.language)
    intro_chapter.content = intro.intro

    tasks = []
    for image in intro.images:
        task = asyncio.ensure_future(_get_image(session, url_root, image))
        tasks.append(task)

    images = await asyncio.gather(*tasks)

    return Page(0, intro_chapter, images)


async def build_update(session: aiohttp.ClientSession, chapter: Chapters, data: Update, intro: Intro) -> Page:
    update_chapter = epub.EpubHtml(title=chapter.txt, file_name=chapter.new_href,
                                   lang=intro.language)  # TODO: fix language
    update_chapter.content = data.content

    img_builder = functools.partial(_get_image, session, chapter.original_href)

    tasks = []
    for image in data.images:
        task = asyncio.ensure_future(img_builder(image))
        tasks.append(task)

    images = await asyncio.gather(*tasks)

    return Page(chapter.num, update_chapter, images)


def add_page(book: EpubBook, toc: List, spine: List, page: Page):
    book.add_item(page.chapter)
    for img in page.images:
        book.add_item(img.data)
    toc.append(epub.Link(page.chapter.file_name, page.chapter.title, page.chapter.id))
    spine.append(page.chapter)


async def build_single_page(session: aiohttp.ClientSession(), intro: Intro, chapter: Chapters) -> Page:
    chapter_page = await session.get(chapter.original_href)
    chapter_bs = BeautifulSoup(await chapter_page.text(), 'html.parser')
    update = Extractor.get_update(str(chapter.num), chapter_bs)
    return await build_update(session, chapter, update, intro)


class DummyUpdater:

    def __init__(self, *args, **kwargs):
        pass

    #todo: everything


async def lparchive2epub(url: str, file: str, root_session: [aiohttp.ClientSession | None] = None, with_pbar: bool = True):
    if root_session is None:
        root_session = aiohttp.ClientSession()
    async with root_session as session:
        await do(url, file, session, with_pbar)


async def do(url: str, file: str, session: aiohttp.ClientSession, with_pbar: bool):
    page = await session.get(url)
    landing = BeautifulSoup(await page.text(), 'html.parser')

    book = epub.EpubBook()
    intro = Extractor.intro(url, landing)

    book.add_author(intro.author)
    book.set_title(intro.title)
    book.set_language(intro.language)
    book.add_metadata("DC", "source", url)
    book.set_identifier(f"lparchive2epub-{hash(intro.title)}-{hash(intro.author)}-{hash(url)}")

    toc = []
    spine = ["nav"]

    epub_intro = await build_intro(session, url, intro)

    add_page(book, toc, spine, epub_intro)

    # pages takes a vastly inequal times to get, so it's faster to imap_unordered and do a simple bisect.insort
    # gotta go fast, but also keep the page order.

    tasks = []

    for chapter in intro.chapters:
        task = asyncio.ensure_future(build_single_page(session, intro, chapter))
        tasks.append(task)

    gatherer = tqdm.gather if with_pbar else asyncio.gather

    pages = await gatherer(*tasks)
    pages = sorted(pages)

    for p in pages:
        add_page(book, toc, spine, p)

    book.toc = toc

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    book.spine = spine

    epub.write_epub(file, book)

# todo: check for links like in headshoots
# todo: deduplicate images when possible.
