import asyncio
import datetime
import functools
import mimetypes
import os
import re
from dataclasses import dataclass
from hashlib import blake2b
from typing import List, Tuple
from urllib.parse import urlparse, urlunparse, unquote

import aiohttp
from bs4 import BeautifulSoup
from ebooklib import epub
from ebooklib.epub import EpubHtml, EpubImage, EpubBook
from tqdm.asyncio import tqdm

from lparchive2epub.style import get_style_item

# Concurrency limit for worker queues
CONCURRENCY_LIMIT_PAGES = 25
CONCURRENCY_LIMIT_IMAGES = 10

def get_blake2b_hash(content: bytes) -> str:
    hasher = blake2b()
    hasher.update(content)
    return hasher.hexdigest()

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
    url: str
    root_url: str

    def __post_init__(self):
        self.sort_index = self.num


@dataclass(order=True)
class IndexedEpubImage:
    num: int
    hash: str
    old_name: str
    new_name: str
    root_url: str
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
    published_on: str


@dataclass
class Update:
    content: BeautifulSoup
    images: List[Image]


LP_SPECIFIC_NAMES = {
    "Dwarf-Fortress-Boatmurdered": ["Introduction"],
    "Arcanum": ["Intro", "Epilogue"],
    "Martian-Dreams": ["Cast"]
}

FIND_FILES = re.compile(r"([.])[^/.]+$")
# Links to image files, whatever the case of the extension and ignoring any query string or fragment
IMAGE_FILE_LINK = re.compile(r"\.(jpe?g|png|gif|webp|bmp|svg)(?=[?#]|$)", re.IGNORECASE)

# (media subtype, file extension) by magic number. Checked in order.
IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "png", "png"),
    (b"GIF87a", "gif", "gif"),
    (b"GIF89a", "gif", "gif"),
    (b"\xff\xd8\xff", "jpeg", "jpg"),
    (b"BM", "bmp", "bmp"),
)
IMAGE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
    "image/svg+xml": "svg",
}


def detect_image_type(content: bytes, url: str = "", content_type: str | None = None) -> tuple[str, str] | None:
    """Return (media type, file extension) for downloaded image bytes, or None if this is not an image.

    The bytes are authoritative: file extensions on image hosts are often wrong, and dead hosts
    happily answer 200 with an HTML page. The URL and Content-Type header are only fallbacks for
    formats without a simple signature."""
    head = content[:16]
    for signature, subtype, ext in IMAGE_SIGNATURES:
        if head.startswith(signature):
            return f"image/{subtype}", ext
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image/webp", "webp"
    start = content[:512].lstrip()
    if start.startswith(b"<svg") or (start.startswith(b"<?xml") and b"<svg" in content[:2048]):
        return "image/svg+xml", "svg"
    if start.startswith((b"<!DOCTYPE", b"<html", b"<HTML", b"<head", b"<body", b"<!doctype")):
        return None
    # Fallbacks: a format we have no signature for; trust the declared type, then the URL
    for candidate in (content_type.split(";")[0].strip().lower() if content_type else None,
                      mimetypes.guess_type(urlparse(url).path)[0]):
        if candidate in IMAGE_EXTENSIONS:
            return candidate, IMAGE_EXTENSIONS[candidate]
    return None
# "update_3.xhtml/" or "update_3.xhtml/#anchor" -> the slash must go
TRAILING_SLASH_AFTER_PAGE = re.compile(r"\.xhtml/(?=#|$)")
FIND_ANCHOR_LINKS = re.compile(r"(#)[^/.]+$")

# Typos in the scheme part of a URL found in some LPs: "hhttp://", "htttp://", "http:/", "http//"...
FIXABLE_SCHEME = re.compile(r"^h+t+p+(s?)\s*(?::/*|//+)", re.IGNORECASE)
HAS_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def normalize_url(url: str) -> str | None:
    """Repair common typos in an absolute URL. Returns None if the URL can't be made into a valid http(s) URL."""
    url = url.strip().replace("\\", "/")
    url = FIXABLE_SCHEME.sub(lambda m: f"http{m.group(1).lower()}://", url, count=1)
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if parsed.scheme.lower() in ("http", "https") and parsed.netloc:
        return url
    return None


class Extractor:

    @staticmethod
    def fix_links(content, chapters, current_url: str):
        if not current_url.endswith("/"):
            current_url += "/"

        all_links = [x for x in content.find_all("a") if x.get("href", None)]
        for link in all_links:
            link["href"] = link["href"].replace("../", "")

        local_assets = (x for x in all_links if FIND_FILES.search(x.get("href")) and "/" not in x.get("href"))

        for link_to_asset in local_assets:
            link_to_asset["href"] = current_url + link_to_asset["href"]

        for c in chapters:
            links = content.find_all("a", href=re.compile(c.original_href_slug))
            to_update = (x for x in links if not FIND_FILES.search(x.get("href")))
            for link_to_update in to_update:
                # The slug ends with "/" (e.g. "Update%2001/"); the file name inside the book must not.
                href = link_to_update["href"].replace(c.original_href_slug, c.new_href)
                link_to_update["href"] = TRAILING_SLASH_AFTER_PAGE.sub(".xhtml", href)
            asset_links = (x for x in links if FIND_FILES.search(x.get("href")))
            for link_to_asset in asset_links:
                # original_href already ends with "/"
                link_to_asset["href"] = link_to_asset["href"].replace(c.original_href_slug, c.original_href)

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
        Extractor.fix_links(content, chapters, url)

        images = Extractor.all_images(content, url)

        archival = p.find("li", id="archival")
        published_on = archival.find("strong").text

        return Intro(
            title=title, language=language, author=author, intro=content, images=images, chapters=chapters, published_on=published_on
        )

    @staticmethod
    def all_chapters(root_url: str, p: BeautifulSoup) -> List[Chapters]:
        content = p.find("div", id="content")

        chapters = content.find_all("a")

        known_update_names = Extractor.get_known_update_names(root_url)
        chapters = (x for x in chapters if any(a in x.get("href", "") for a in known_update_names))
        chapters = (x for x in chapters if "lparchive.org" not in x.get("href", ""))
        chapters = (x for x in chapters if not FIND_FILES.search(x.get("href", "")))
        chapters = (x for x in chapters if not FIND_ANCHOR_LINKS.search(x.get("href", "")))

        chapters = list(chapters)

        if not chapters:
            return []

        def build_chapter(chap: Tuple[int, BeautifulSoup]) -> Chapters:
            i, c = chap
            original_href_slug = c.get("href", None)
            original_href = f"{root_url}/{original_href_slug}"
            if not original_href.endswith("/"):
                original_href += "/"
            txt = c.text if c.text else unquote(original_href_slug[:-1])
            return Chapters(
                num=i,
                original_href=original_href,
                txt=txt,
                new_href=f"update_{i}.xhtml",
                original_href_slug=original_href_slug,
            )

        chapters = list(map(build_chapter, enumerate(chapters)))

        return chapters

    @staticmethod
    def get_full_url(root_url: str, src: str) -> str | None:
        def remove_extra_dots(url):
            parsed = list(urlparse(url))
            dirs = []
            for name in parsed[2].split("/"):
                if name == "..":
                    if len(dirs) > 1:
                        dirs.pop()
                else:
                    dirs.append(name)
            parsed[2] = "/".join(dirs)
            return urlunparse(parsed)

        root = str(root_url)
        if root.endswith("/"):
            root = root[:-1]

        src = src.strip()
        if FIXABLE_SCHEME.match(src) or src.startswith("//") or HAS_SCHEME.match(src):
            full = normalize_url(src)
            if full is None:
                return None
        elif root_url in src:
            full = src
        else:
            full = f"{root}/{src}"
        if ".." in full:
            full = remove_extra_dots(full)
        return full


    @staticmethod
    def all_images(content: BeautifulSoup, root_url: str) -> List[Image]:
        # Get direct image tags
        images = content.find_all("img")
        images = (x for x in images if x.get("src", None) is not None)
        r = []

        def get_media_type(src: str) -> str:
            # Only a hint from the URL; the real type is detected from the downloaded bytes.
            guessed, _ = mimetypes.guess_type(urlparse(src).path)
            return guessed or "application/octet-stream"

        # Add direct images
        for i, x in enumerate(images):
            r.append(Image(
                num=i,
                src=x['src'],
                media_type=get_media_type(x["src"]),
                tag=x,
                url=Extractor.get_full_url(root_url, x["src"]),
                root_url=root_url
            ))

        # Find image links - typically "Click here for full image" links
        image_links = content.find_all("a", href=lambda x: x and IMAGE_FILE_LINK.search(x))

        # Add linked images to be saved, but don't modify the HTML structure
        for i, link in enumerate(image_links, start=len(r)):
            r.append(Image(
                num=i,
                src=link['href'],
                media_type=get_media_type(link['href']),
                tag=link,  # Use the link tag itself
                url=Extractor.get_full_url(root_url, link['href']),
                root_url=root_url
            ))

        return r

    @staticmethod
    def get_update(chapters: List[Chapters], p: BeautifulSoup, chapter: Chapters) -> Update:
        content = p.find("div", id="content")
        images = Extractor.all_images(content, chapter.original_href)
        Extractor.fix_links(content, chapters, chapter.original_href)
        return Update(content=content, images=images)


@dataclass(order=True)
class Page:
    num: int
    chapter: EpubHtml
    images: List[IndexedEpubImage]

    def __post_init__(self):
        self.sort_index = self.num

async def _default_get(r):
    return await r.text()


CURL_HEADERS = {
    "user-agent": "curl/8.1.1",
    "accept": "*/*"
}

class NonRetryableError(RuntimeError):
    """A failure that will not go away by trying again (malformed URL, 404...)."""


@dataclass
class SkippedResource:
    page: str
    url: str
    reason: str


class ExtractionError(RuntimeError):
    """The book could not be built; the message is a full report meant to be shown to the user."""


class StrictModeError(ExtractionError):
    """Resources were skipped while --strict was requested."""


class MissingUpdatesError(ExtractionError):
    """One or more updates (chapters) could not be retrieved."""


class OutputError(ExtractionError):
    """The output file can't be written."""


def check_output_path(file: str):
    """Fail early, before any download, if the book can't possibly be written at `file`."""
    directory = os.path.dirname(os.path.abspath(file))
    if os.path.isdir(file):
        raise OutputError(f"Cannot write the book to {file}: it is a directory.")
    if not os.path.isdir(directory):
        raise OutputError(f"Cannot write the book to {file}: the directory {directory} does not exist.")
    if not os.access(directory, os.W_OK):
        raise OutputError(f"Cannot write the book to {file}: the directory {directory} is not writable.")
    if os.path.exists(file) and not os.access(file, os.W_OK):
        raise OutputError(f"Cannot write the book to {file}: the file exists and is not writable.")


def write_book(file: str, book: EpubBook, mtime: datetime.datetime):
    """Write the book through a temporary file, so a failure never leaves a truncated epub behind."""
    partial = file + ".part"
    try:
        epub.write_epub(partial, book, options={"mtime": mtime, "raise_exceptions": True})
        os.replace(partial, file)
    except OSError as e:
        try:
            os.remove(partial)
        except OSError:
            pass
        raise OutputError(f"Cannot write the book to {file}: {e.strerror or e}") from e


ISSUES_URL = "https://github.com/Arwalk/lparchive2epub/issues/new"

# Client errors that may succeed later: request timeout, too many requests
RETRYABLE_CLIENT_STATUSES = {408, 429}


async def get_resource_with_retries(session: aiohttp.ClientSession, url, action=_default_get, max_retries=5):
    retry_count = 0
    last_exception = None

    while retry_count < max_retries:
        try:
            async with session.get(url, headers=CURL_HEADERS) as r:
                if 400 <= r.status < 500 and r.status not in RETRYABLE_CLIENT_STATUSES:
                    raise NonRetryableError(f"Failed to get resource {url}, status code: {r.status}")
                if r.status != 200:
                    raise RuntimeError(f"Failed to get resource {url}, status code: {r.status}")
                return await action(r)
        except NonRetryableError:
            raise
        except aiohttp.InvalidURL as e:
            raise NonRetryableError(f"Invalid URL {url}: {e}") from e
        except Exception as e:
            last_exception = e
            retry_count += 1
            if retry_count < max_retries:
                # Exponential backoff: 2^retry_count * 1s (2s, 4s, 8s, 16s)
                wait_time = (2 ** retry_count) * 1
                await asyncio.sleep(wait_time)
    raise RuntimeError(f"Failed to get resource {url} after {max_retries} retries: {last_exception}")



async def _get_image(session: aiohttp.ClientSession, img: Image, registry: dict = None) -> IndexedEpubImage:
    # Get the image URL from either src (for img tags) or href (for a tags)
    img_url = img.url
    if img_url is None:
        raise NonRetryableError(f"Malformed URL that could not be repaired: {img.src}")

    if registry is not None:
        if img_url in registry:
            return await registry[img_url]
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        registry[img_url] = future
    else:
        future = None

    async def get(r):
        content = await r.content.read()
        content_type = r.headers.get("Content-Type") if getattr(r, "headers", None) else None
        detected = detect_image_type(content, img_url, content_type)
        if detected is None:
            declared = (content_type or "unknown type").split(";")[0].strip()
            raise NonRetryableError(f"Not an image: the server answered with {declared} ({len(content)} bytes)")
        media_type, extension = detected
        img_hash = get_blake2b_hash(content)
        new_name = f"images/{img_hash}.{extension}"
        return IndexedEpubImage(
            img.num,
            img_hash,
            img_url,  # Use the original URL as old_name
            new_name,
            img.root_url,
            EpubImage(
                uid=f"i{img_hash}",
                file_name=new_name,
                media_type=media_type,
                content=content)
        )

    try:
        res = await get_resource_with_retries(session, img_url, get)
        if future:
            future.set_result(res)
        return res
    except Exception as e:
        if future:
            future.set_exception(e)
            # Mark the exception as retrieved, so asyncio doesn't complain if nobody else awaits it
            future.exception()
            del registry[img_url]
        raise

def _skipped(img: Image, e: Exception) -> SkippedResource:
    return SkippedResource(page=img.root_url, url=img.src, reason=str(e) or type(e).__name__)


async def build_intro(session: aiohttp.ClientSession, url_root: str, intro: Intro, registry: dict = None, failures: list[SkippedResource] = None) -> Page:
    intro_chapter = epub.EpubHtml(title="Introduction", file_name="introduction.xhtml", lang=intro.language)
    intro_chapter.add_item(get_style_item())
    tasks = []
    for image in intro.images:
        task = asyncio.ensure_future(_get_image(session, image, registry))
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    images = []
    for img, res in zip(intro.images, results):
        if isinstance(res, Exception):
            if failures is not None:
                failures.append(_skipped(img, res))
        else:
            images.append(res)

    for image in images:
        intro.intro = replace_img_name(intro.intro, image)

    intro_chapter.content = str(intro.intro)

    return Page(0, intro_chapter, images)


def replace_img_name(content: BeautifulSoup, image: IndexedEpubImage) -> BeautifulSoup:
    # Handle img tags
    to_change_imgs = (x for x in content.find_all("img") if Extractor.get_full_url(image.root_url, x["src"]) == image.old_name)
    for item in to_change_imgs:
        item["src"] = image.new_name

    # Handle linked images
    to_change_links = (x for x in content.find_all("a") if x.get("href") and Extractor.get_full_url(image.root_url, x["href"]) == image.old_name)
    for item in to_change_links:
        item["href"] = image.new_name

    return content

def batch(iterable, n=1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]

async def build_update(session: aiohttp.ClientSession, chapter: Chapters, data: Update, intro: Intro, registry: dict = None, failures: list[SkippedResource] = None) -> Page:
    update_chapter = epub.EpubHtml(title=str(chapter.txt), file_name=chapter.new_href,
                                   lang=intro.language)  # TODO: fix language
    update_chapter.add_item(get_style_item())

    img_builder = functools.partial(_get_image, session, registry=registry)

    # Queue-based worker pool to cap concurrency
    q: asyncio.Queue = asyncio.Queue()
    images: list[IndexedEpubImage] = []

    async def worker():
        while True:
            try:
                img = await q.get()
                try:
                    res = await img_builder(img)
                    replace_img_name(data.content, res)
                    images.append(res)
                except Exception as e:
                    # Missing images are not worth failing the whole book: keep the original link
                    if failures is not None:
                        failures.append(_skipped(img, e))
                finally:
                    q.task_done()
            except asyncio.CancelledError:
                break

    workers = [asyncio.create_task(worker()) for _ in range(CONCURRENCY_LIMIT_IMAGES)]

    # Enqueue images with their indices
    for image in data.images:
        await q.put(image)

    # Wait for completion and shutdown workers
    await q.join()
    for w in workers:
        w.cancel()

    await asyncio.gather(*workers, return_exceptions=True)

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


async def build_single_page(session: aiohttp.ClientSession, intro: Intro, chapter: Chapters, all_chapters: List[Chapters], pbar, registry: dict = None, failures: list[SkippedResource] = None) -> Page:
    async def get(r):
        chapter_bs = get_cleaned_html(await r.text())
        update = Extractor.get_update(all_chapters, chapter_bs, chapter)
        u = await build_update(session, chapter, update, intro, registry, failures)
        pbar.update(1)
        return u

    return await get_resource_with_retries(session, chapter.original_href, get)

def build_placeholder_page(chapter: Chapters, intro: Intro, error: Exception) -> Page:
    """Stand-in for a chapter that could not be retrieved, so the book keeps its structure."""
    placeholder = epub.EpubHtml(title=str(chapter.txt), file_name=chapter.new_href, lang=intro.language)
    placeholder.add_item(get_style_item())
    content = BeautifulSoup("<div id=\"content\"></div>", "html.parser")
    div = content.div
    h = content.new_tag("h3")
    h.string = str(chapter.txt)
    div.append(h)
    p = content.new_tag("p")
    p.append("This update could not be retrieved when the book was built. It is available online at ")
    a = content.new_tag("a", href=chapter.original_href)
    a.string = chapter.original_href
    p.append(a)
    p.append(".")
    div.append(p)
    reason = content.new_tag("p")
    reason.string = f"Reason: {str(error) or type(error).__name__}"
    div.append(reason)
    placeholder.content = str(content)
    return Page(chapter.num, placeholder, [])


async def lparchive2epub(url: str, file: str, root_session: aiohttp.ClientSession | None = None, writer=tqdm.write,
                         strict: bool = False, allow_missing_updates: bool = False):
    if url.endswith("/"):
        url = url[:-1]
    if root_session is None:
        root_session = aiohttp.ClientSession()
    async with root_session as session:
        await do(url, file, session, writer, strict, allow_missing_updates)


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
    return xml_version


def format_failures_report(url: str, failures: list[SkippedResource], outcome: str, what: str = "resource(s)") -> str:
    unique = list(dict.fromkeys((f.page, f.url, f.reason) for f in failures))
    separator = "-" * 72
    lines = [
        separator,
        f"lparchive2epub: {len(unique)} {what} could not be retrieved while extracting {url}",
    ]
    for page, res_url, reason in unique:
        if page != res_url:
            lines.append(f"  - page:   {page}")
            lines.append(f"    url:    {res_url}")
        else:
            lines.append(f"  - url:    {res_url}")
        lines.append(f"    reason: {reason}")
    lines.append(separator)
    lines.append(outcome)
    lines.append(f"Please open an issue at {ISSUES_URL} and paste the output between the lines above,")
    lines.append("so these cases can be handled in a future release.")
    return "\n".join(lines)


async def do(url: str, file: str, session: aiohttp.ClientSession, writer, strict: bool = False,
             allow_missing_updates: bool = False):
    check_output_path(file)
    writer(f"extracting lp from {url}")
    writer("getting landing page")
    page_text = await get_resource_with_retries(session, url)

    landing = get_cleaned_html(page_text)

    book = epub.EpubBook()
    intro = Extractor.intro(url, landing)

    toc = []
    spine = ["nav"]

    writer("building intro")
    image_registry = {}
    failures: list[SkippedResource] = []
    missing_updates: list[tuple[int, Chapters, Exception]] = []
    epub_intro = await build_intro(session, url, intro, image_registry, failures)

    known_images = {
        "hashes": [],
    }

    add_page(known_images, book, toc, spine, epub_intro)

    # pages takes a vastly inequal times to get, so it's faster to gather and sort
    # gotta go fast, but also keep the page order.

    writer("building chapters / updates")

    pages_indexed: list[tuple[int, Page]] = []

    with tqdm(total=len(intro.chapters), desc="Gathering and building pages") as pbar:
        q: asyncio.Queue = asyncio.Queue()

        async def worker():
            while True:
                try:
                    i, chapter = await q.get()
                except asyncio.CancelledError:
                    break
                try:
                    page = await build_single_page(session, intro, chapter, intro.chapters, pbar, image_registry, failures)
                except asyncio.CancelledError:
                    q.task_done()
                    raise
                except Exception as e:
                    # A chapter that can't be retrieved must not silently vanish from the book: remember it
                    # so the run fails with a full report (or, on request, gets a placeholder page).
                    missing_updates.append((i, chapter, e))
                    pbar.update(1)
                else:
                    pages_indexed.append((i, page))
                finally:
                    q.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(CONCURRENCY_LIMIT_PAGES)]

        for i, chapter in enumerate(intro.chapters):
            await q.put((i, chapter))

        await q.join()
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    if missing_updates:
        missing_updates.sort(key=lambda x: x[0])
        missing = [SkippedResource(page=c.original_href, url=c.original_href, reason=str(e) or type(e).__name__)
                   for _, c, e in missing_updates]
        if not allow_missing_updates:
            raise MissingUpdatesError(format_failures_report(
                url, missing,
                "No book was written: it would be missing the update(s) above. "
                "Run again later, or with --allow-missing-updates to build it anyway with placeholder pages.",
                what="update(s)"))
        failures.extend(missing)
        for i, chapter, e in missing_updates:
            pages_indexed.append((i, build_placeholder_page(chapter, intro, e)))

    pages = [p for _, p in sorted(pages_indexed, key=lambda x: x[0])]

    if failures and strict:
        raise StrictModeError(format_failures_report(
            url, failures, "No book was written (--strict). Run again without --strict to build it anyway."))

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
    book.add_metadata("DC", "identifier", f"lparchive2epub-{hash(intro.title)}-{hash(intro.author)}-{hash(url)}")

    book.set_identifier(f"lparchive2epub-{get_blake2b_hash(intro.title.encode("utf-8"))}-{get_blake2b_hash(intro.author.encode("utf-8"))}-{get_blake2b_hash(url.encode("utf-8"))}")

    mtime = datetime.datetime.strptime(intro.published_on, "%b %d, %Y")

    writer("Writing book file")
    write_book(file, book, mtime)

    if failures:
        writer(format_failures_report(
            url, failures,
            "Missing images were left as external links in the book; "
            "missing updates (--allow-missing-updates) were replaced by a placeholder page linking to the original."))
