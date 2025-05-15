import asyncio
import functools
from dataclasses import dataclass
from hashlib import blake2b
from typing import List, Tuple
import re
import aiohttp
from bs4 import BeautifulSoup
from ebooklib import epub
from ebooklib.epub import EpubHtml, EpubImage, EpubBook
from tqdm.asyncio import tqdm

from lparchive2epub.style import get_style_item


@dataclass(order=True)
class Chapters:
    num: int
    original_href: str
    txt: BeautifulSoup
    new_href: str
    original_href_slug: str

    def __hash__(self):
        return hash((self.original_href, str(self.txt.text)))

    def __post_init__(self):
        self.sort_index = self.num


@dataclass(order=True)
class Image:
    num: int
    src: str
    media_type: str
    tag: BeautifulSoup

    def __post_init__(self):
        self.sort_index = self.num


@dataclass(order=True)
class IndexedEpubImage:
    num: int
    hash: str
    old_name: str
    new_name: str
    data: EpubImage

    def __post_init__(self):
        self.sort_index = self.num


@dataclass
class Intro:
    title: str
    language: str
    author: str
    intro: BeautifulSoup
    images: List[Image]
    chapters: List[Chapters]


@dataclass
class Update:
    content: BeautifulSoup
    images: List[Image]


LP_SPECIFIC_NAMES = {
    "Dwarf-Fortress-Boatmurdered": ["Introduction"],
    "Arcanum": ["Intro", "Epilogue"],
}

FIND_FILES = re.compile(r"([.])[^/.]+$")
FIND_ANCHOR_LINKS = re.compile(r"(#)[^/.]+$")


class Extractor:

    @staticmethod
    def get_known_update_names(url: str) -> List[str]:
        knownUpdateNames = ["Update"]
        extension = next((x for x in LP_SPECIFIC_NAMES.keys() if x in url), None)
        if extension:
            knownUpdateNames.extend(LP_SPECIFIC_NAMES[extension])
        return knownUpdateNames

    @staticmethod
    def intro(url: str, p: BeautifulSoup) -> Intro:
        title = p.title.text
        author = next(x for x in p.find_all("meta") if x.get("name", None) == "author").get("content", None)
        language = "en"
        content = p.find("div", id="content")
        chapters = Extractor.all_chapters(url, p)
        for c in chapters:
            links = content.find_all("a", href=re.compile(c.original_href_slug))
            to_update = (x for x in links if not FIND_FILES.search(x.get("href")))
            for link_to_update in to_update:
                link_to_update["href"] = link_to_update["href"].replace(c.original_href_slug, c.new_href + "/")
            asset_links = (x for x in links if FIND_FILES.search(x.get("href")))
            for link_to_asset in asset_links:
                link_to_asset["href"] = link_to_asset["href"].replace(c.original_href_slug, c.original_href + "/")

        images = Extractor.all_images(content)

        return Intro(
            title=title, language=language, author=author, intro=content, images=images, chapters=chapters
        )

    @staticmethod
    def all_chapters(root_url: str, p: BeautifulSoup) -> List[Chapters]:
        content = p.find("div", id="content")

        chapters = content.find_all("a")
        known_update_names = Extractor.get_known_update_names(root_url)
        chapters = (x for x in chapters if any(a in x.get("href", None) for a in known_update_names))
        chapters = (x for x in chapters if not FIND_FILES.search(x.get("href")))
        chapters = (x for x in chapters if not FIND_ANCHOR_LINKS.search(x.get("href")))

        def build_chapter(chap: Tuple[int, BeautifulSoup]) -> Chapters:
            i, c = chap
            original_href_slug = c.get("href", None)
            original_href = f"{root_url}/{original_href_slug}"
            if original_href.endswith("/"):
                original_href = original_href[:-1]
            return Chapters(
                num=i,
                original_href=original_href,
                txt=c.text,
                new_href=f"update_{i}.xhtml",
                original_href_slug=original_href_slug,
            )

        chapters = list(map(build_chapter, enumerate(chapters)))

        return chapters

    @staticmethod
    def all_images(content: BeautifulSoup) -> List[Image]:
        # Get direct image tags
        images = content.find_all("img")
        r = []

        # Add direct images
        for i, x in enumerate(images):
            r.append(Image(
                num=i,
                src=x['src'],
                media_type=x["src"][-3:],
                tag=x
            ))

        # Find image links - typically "Click here for full image" links
        image_links = content.find_all("a", href=lambda x: x and (
                    x.endswith('.jpg') or x.endswith('.png') or x.endswith('.gif')))

        # Add linked images to be saved, but don't modify the HTML structure
        for i, link in enumerate(image_links, start=len(r)):
            r.append(Image(
                num=i,
                src=link['href'],
                media_type=link['href'][-3:],
                tag=link  # Use the link tag itself
            ))

        return r

    @staticmethod
    def get_update(prefix: str, p: BeautifulSoup) -> Update:
        content = p.find("div", id="content")
        images = Extractor.all_images(content)
        return Update(content=content, images=images)


@dataclass(order=True)
class Page:
    num: int
    chapter: EpubHtml
    images: List[IndexedEpubImage]

    def __post_init__(self):
        self.sort_index = self.num


async def _get_image(session: aiohttp.ClientSession, url_root: str, img: Image) -> IndexedEpubImage:
    # Get the image URL from either src (for img tags) or href (for a tags)
    img_url = img.tag.get('src') or img.tag.get('href')
    async with session.get(f"{url_root}/{img_url}") as r:
        media_type = img.media_type
        content = await r.content.read()
        hasher = blake2b()
        hasher.update(content)
        img_hash = hasher.hexdigest()
        new_name = f"images/{img_hash}.{media_type}"
        return IndexedEpubImage(
            img.num,
            img_hash,
            img_url,  # Use the original URL as old_name
            new_name,
            EpubImage(
                uid=f"i{img_hash}",
                file_name=new_name,
                media_type=f"image/{media_type}",
                content=content)
        )


async def build_intro(session: aiohttp.ClientSession, url_root: str, intro: Intro) -> Page:
    intro_chapter = epub.EpubHtml(title="Introduction", file_name="introduction.xhtml", lang=intro.language)
    intro_chapter.add_item(get_style_item())
    tasks = []
    for image in intro.images:
        task = asyncio.ensure_future(_get_image(session, url_root, image))
        tasks.append(task)

    images = await asyncio.gather(*tasks)

    for image in images:
        intro.intro = replace_img_name(intro.intro, image)

    intro_chapter.content = str(intro.intro)

    return Page(0, intro_chapter, images)


def replace_img_name(content: BeautifulSoup, image: IndexedEpubImage) -> BeautifulSoup:
    # Handle img tags
    to_change_imgs = (x for x in content.find_all("img") if x["src"] == image.old_name)
    for item in to_change_imgs:
        item["src"] = image.new_name

    # Handle linked images
    to_change_links = (x for x in content.find_all("a") if x.get("href", "") == image.old_name)
    for item in to_change_links:
        item["href"] = image.new_name

    return content


async def build_update(session: aiohttp.ClientSession, chapter: Chapters, data: Update, intro: Intro) -> Page:
    update_chapter = epub.EpubHtml(title=str(chapter.txt), file_name=chapter.new_href,
                                   lang=intro.language)  # TODO: fix language
    update_chapter.add_item(get_style_item())

    img_builder = functools.partial(_get_image, session, chapter.original_href)

    tasks = []
    for image in data.images:
        task = asyncio.ensure_future(img_builder(image))
        tasks.append(task)

    images = await asyncio.gather(*tasks)

    for image in images:
        data.content = replace_img_name(data.content, image)

    update_chapter.content = str(data.content)

    return Page(chapter.num, update_chapter, images)


def add_page(known_images: dict, book: EpubBook, toc: List, spine: List, page: Page):
    book.add_item(page.chapter)
    for img in page.images:
        if img.hash not in known_images["hashes"]:
            book.add_item(img.data)
            known_images["hashes"].append(img.hash)
    toc.append(epub.Link(page.chapter.file_name, page.chapter.title, page.chapter.id))
    spine.append(page.chapter)


async def build_single_page(session: aiohttp.ClientSession, intro: Intro, chapter: Chapters) -> Page:
    chapter_page = await session.get(chapter.original_href)
    chapter_bs = get_cleaned_html(await chapter_page.text())
    update = Extractor.get_update(str(chapter.num), chapter_bs)
    return await build_update(session, chapter, update, intro)


class DummyUpdater:

    def __init__(self, *args, **kwargs):
        pass

    #todo: everything


async def lparchive2epub(url: str, file: str, root_session: aiohttp.ClientSession | None = None, writer=tqdm.write):
    if url.endswith("/"):
        url = url[:-1]
    if root_session is None:
        root_session = aiohttp.ClientSession()
    async with root_session as session:
        await do(url, file, session, writer)


tags_to_clean = [
    "st1:place",
    "st1:city",
    "st1:country-region",
    "st1:placename",
    "st1:placetype",
    "st1:state",
    "o:p"
]


def get_cleaned_html(page: str) -> BeautifulSoup:
    xml_version = BeautifulSoup(page, "html.parser")
    for tag in tags_to_clean:
        while found := xml_version.find(tag):
            found.unwrap()
    return BeautifulSoup(str(xml_version), "html.parser")


async def do(url: str, file: str, session: aiohttp.ClientSession, writer):
    writer(f"extracting lp from {url}")
    writer("getting landing page")
    page = await session.get(url)

    landing = get_cleaned_html(await page.text())

    book = epub.EpubBook()
    intro = Extractor.intro(url, landing)

    toc = []
    spine = ["nav"]

    writer("building intro")
    epub_intro = await build_intro(session, url, intro)

    known_images = {
        "hashes": [],
    }

    add_page(known_images, book, toc, spine, epub_intro)

    # pages takes a vastly inequal times to get, so it's faster to gather and sort
    # gotta go fast, but also keep the page order.

    tasks = []

    writer("building chapters / updates")
    for chapter in intro.chapters:
        task = asyncio.ensure_future(build_single_page(session, intro, chapter))
        tasks.append(task)

    pages = await tqdm.gather(*tasks, desc="Gathering and building pages")
    pages = sorted(pages)

    tasks = []

    for p in tqdm(pages, desc="Adding pages to book"):
        add_page(known_images, book, toc, spine, p)

    writer("preparing book structure")
    book.toc = toc

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    book.spine = spine

    book.add_item(get_style_item())

    book.add_author(intro.author)
    book.set_title(intro.title)
    book.set_language(intro.language)
    book.add_metadata("DC", "source", url)
    book.set_identifier(f"lparchive2epub-{hash(intro.title)}-{hash(intro.author)}-{hash(url)}")

    writer("Writing book file")
    epub.write_epub(file, book)
