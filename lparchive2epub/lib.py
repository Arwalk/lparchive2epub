import asyncio
import contextlib
import datetime
import functools
import io
import mimetypes
import os
import re
import sqlite3
import sys
import zipfile
from dataclasses import dataclass, field
from hashlib import blake2b
from typing import List
from urllib.parse import urlparse, urljoin, urldefrag, unquote

import aiohttp
from bs4 import BeautifulSoup
from ebooklib import epub
from ebooklib.epub import EpubHtml, EpubImage, EpubBook
from tqdm.asyncio import tqdm

from lparchive2epub.cover import COVER_FILE_NAME, TITLE_PAGE_FILE_NAME, make_cover, make_title_page
from lparchive2epub.style import get_style_item

# Worker pools: how many pages are being built at once, and how many images per page. The number of
# requests actually in flight is capped separately by FetchSettings.concurrency.
CONCURRENCY_LIMIT_PAGES = 25
CONCURRENCY_LIMIT_IMAGES = 10
DEFAULT_CONCURRENCY = 32   # measured on Boatmurdered: 16 costs ~40% of wall time, 32 ~15%, 64 none
DEFAULT_RETRIES = 5
# No total timeout (a 17 MB picture on a slow link is legitimate), but connecting and each read must
# make progress: a stalled host must not park a download for minutes.
CLIENT_TIMEOUT = aiohttp.ClientTimeout(total=None, connect=15, sock_connect=15, sock_read=60)


def log(message: str):
    """Default writer for progress messages: stderr, so stdout stays free for data."""
    tqdm.write(message, file=sys.stderr)


@dataclass
class FetchSettings:
    """How downloads behave: how many at once, how many attempts, and whether to say anything."""
    concurrency: int = DEFAULT_CONCURRENCY
    retries: int = DEFAULT_RETRIES
    quiet: bool = False
    _semaphore: asyncio.Semaphore | None = field(default=None, repr=False, compare=False)

    def limit(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.concurrency)   # created inside the running loop
        return self._semaphore

@dataclass
class ImageProcessing:
    """Opt-in image reduction (--max-image-size). Counters are updated as images go through."""
    max_size: int                   # longest edge, in pixels
    jpeg_quality: int = 85
    bytes_in: int = 0
    bytes_out: int = 0
    changed: int = 0
    seen: int = 0

    def record(self, before: int, after: int):
        self.seen += 1
        self.bytes_in += before
        self.bytes_out += after
        if after != before:
            self.changed += 1

    def summary(self) -> str:
        return (f"Images: {self.changed} of {self.seen} reduced, "
                f"{self.bytes_in / 1e6:.1f} MB -> {self.bytes_out / 1e6:.1f} MB")


# Formats the optimiser may rewrite. GIF is left alone (animations), SVG is text.
REDUCIBLE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}


def reduce_image(content: bytes, media_type: str, settings: ImageProcessing) -> tuple[bytes, str, str] | None:
    """Shrink an image to at most `settings.max_size` pixels on its longest edge and re-encode it.

    JPEG stays JPEG (at `jpeg_quality`), PNG stays PNG. WebP and BMP, which many readers can't show,
    become PNG (with transparency) or JPEG (without). Returns (bytes, media type, extension), or
    None when the image is left untouched: not a reducible format, animated, undecodable, or the
    re-encoded version would not be smaller."""
    if media_type not in REDUCIBLE_TYPES:
        return None
    from PIL import Image as PILImage, ImageOps

    try:
        image = PILImage.open(io.BytesIO(content))
        image.load()
    except Exception:  # noqa: BLE001 - corrupted or exotic file: keep what the site serves
        return None
    if getattr(image, "is_animated", False):
        return None

    image = ImageOps.exif_transpose(image)
    width, height = image.size
    scale = settings.max_size / max(width, height)
    resized = scale < 1
    if resized:
        image = image.resize((max(1, round(width * scale)), max(1, round(height * scale))), PILImage.LANCZOS)

    has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    if media_type == "image/jpeg":
        if not resized:
            return None  # re-encoding a JPEG that already fits only loses quality
        target = "JPEG"
    elif media_type == "image/png":
        target = "PNG"
    else:  # webp, bmp: pick a format every reader understands
        target = "PNG" if has_alpha else "JPEG"

    out = io.BytesIO()
    if target == "JPEG":
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        image.save(out, "JPEG", quality=settings.jpeg_quality, optimize=True)
        new_type, extension = "image/jpeg", "jpg"
    else:
        if resized and image.mode == "P":
            image = image.convert("RGBA" if has_alpha else "RGB")
        image.save(out, "PNG", optimize=True)
        new_type, extension = "image/png", "png"
    data = out.getvalue()
    if not resized and media_type == new_type and len(data) >= len(content):
        return None  # same format, same pixels, not smaller: keep the original bytes
    return data, new_type, extension


def get_blake2b_hash(content: bytes) -> str:
    hasher = blake2b()
    hasher.update(content)
    return hasher.hexdigest()

@dataclass
class Chapters:
    num: int                # position in the book; update_<num>.xhtml
    original_href: str      # absolute URL of the page, slash-terminated
    txt: str                # title shown in the navigation
    new_href: str
    original_href_slug: str  # "Update%2001/"


@dataclass
class Image:
    num: int
    src: str
    tag: BeautifulSoup      # the <img> (src) or <a> (href) this came from; rewritten in place once downloaded
    url: str | None         # absolute URL, None when it could not be repaired
    root_url: str           # the page it was found on, for the failure report


@dataclass
class IndexedEpubImage:
    """A downloaded image as stored in the book, keyed by its original URL (old_name)."""
    hash: str
    old_name: str
    new_name: str
    data: EpubImage


@dataclass
class Intro:
    title: str
    language: str
    author: str
    intro: BeautifulSoup
    images: List[Image]
    chapters: List[Chapters]
    published_on: str                       # "Added to the archive on ..." as written on the page
    began: str | None = None                # "Began on ..."
    ended: str | None = None                # "Ended on ..."
    parts: int | None = None                # "This LP has N parts."
    tags: List[str] = field(default_factory=list)
    thread_title: str | None = None         # the original forum thread
    thread_url: str | None = None


LP_DATE_FORMAT = "%b %d, %Y"  # how lparchive writes dates: "Oct 26, 2009"
PUBLISHER = "The Let's Play Archive"
STATISTICS = {
    "began": re.compile(r"^Began on (.+)$"),
    "ended": re.compile(r"^Ended on (.+)$"),
    "parts": re.compile(r"^This LP has (\d+) parts?\.?$"),
}


def parse_lp_date(text: str | None) -> datetime.datetime | None:
    try:
        return datetime.datetime.strptime(text.strip(), LP_DATE_FORMAT) if text else None
    except ValueError:
        return None


def compose_description(intro: Intro, url: str) -> str:
    """A synopsis for the reader's library, built from what the landing page states about the LP."""
    parts = [f"Let's Play of {intro.title} by {intro.author}."]
    if intro.parts and intro.began and intro.ended:
        when = f"between {intro.began} and {intro.ended}" if intro.began != intro.ended else f"on {intro.began}"
        parts.append(f"{intro.parts} updates posted {when}.")
    elif intro.parts:
        parts.append(f"{intro.parts} updates.")
    elif intro.began and intro.ended:
        parts.append(f"Posted between {intro.began} and {intro.ended}.")
    parts.append(f"Archived by {PUBLISHER} at {url} on {intro.published_on}.")
    if intro.thread_url:
        parts.append(f"Original thread: {intro.thread_url}")
    return " ".join(parts)


@dataclass
class Update:
    content: BeautifulSoup
    images: List[Image]


FIND_FILES = re.compile(r"([.])[^/.]+$")
DOT_NOT_IN_A_NUMBER = re.compile(r"(?<!\d)\.|\.(?!\d)")
# Links to image files, whatever the case of the extension and ignoring any query string or fragment
IMAGE_FILE_LINK = re.compile(r"\.(jpe?g|png|gif|webp|bmp|svg)(?=[?#]|$)", re.IGNORECASE)
# lparchive's own wording for a thumbnail's link: "Click here for the full 728x866 image."
FULL_IMAGE_LINK_TEXT = re.compile(r"\bfull\b.*\bimage\b", re.IGNORECASE | re.DOTALL)

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
    if not content:
        return None  # some hosts answer 200 with an empty body for images that are gone
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
INTRO_FILE_NAME = "introduction.xhtml"

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
        """Point every link either inside the book (chapters, landing page) or at an absolute URL.

        Links are resolved against the page they appear on, exactly like a browser would, so
        "../Update%2002/", "/Other-LP/" and "manual.pdf" all end up unambiguous. Links to images
        that get embedded are rewritten in place once downloaded (see point_at_embedded)."""
        if not current_url.endswith("/"):
            current_url += "/"

        in_book = {c.original_href: c.new_href for c in chapters}
        if chapters:
            # original_href is root + "/" + slug, both slash-terminated: a link back to the landing page
            root = chapters[0].original_href[:-len(chapters[0].original_href_slug)]
            in_book[root] = INTRO_FILE_NAME

        for link in content.find_all("a", href=True):
            href = link["href"].strip()
            if not href or href.startswith("#"):
                continue  # in-page anchor
            full = Extractor.get_full_url(current_url, href)
            if full is None:
                continue  # mailto:, javascript:, unrepairable scheme typo... leave as is
            target, fragment = urldefrag(full)
            key = target if target.endswith("/") else target + "/"
            if key in in_book:
                link["href"] = in_book[key] + (f"#{fragment}" if fragment else "")
            else:
                link["href"] = full

    @staticmethod
    def intro(url: str, p: BeautifulSoup) -> Intro:
        content = p.find("div", id="content")
        archival = p.find("li", id="archival")
        author_meta = p.find("meta", attrs={"name": "author"})
        missing = [name for name, found in (("the content block", content), ("the archival date", archival),
                                            ("the author", author_meta), ("the title", p.title)) if found is None]
        if missing:
            raise NotALetsPlayError(
                f"{url} is not the page of a Let's Play: {', '.join(missing)} could not be found on it.\n"
                f"A Let's Play address looks like {LPARCHIVE_ROOT}/Name-Of-The-Lets-Play")

        title = p.title.text
        author = author_meta.get("content", None) or "Unknown"
        language = "en"
        chapters = Extractor.all_chapters(url, p)
        Extractor.fix_links(content, chapters, url)

        Extractor.inline_full_size_images(content)
        images = Extractor.all_images(content, url)

        published_on = archival.find("strong").text

        statistics = {}
        stats_list = p.find("ul", id="statistics")
        for item in stats_list.find_all("li") if stats_list else []:
            text = " ".join(item.get_text(" ").split())
            for key, pattern in STATISTICS.items():
                if m := pattern.match(text):
                    statistics[key] = m.group(1)
        tag_list = p.find("li", id="taglist")
        tags = [a.get_text(strip=True) for a in tag_list.find_all("a")] if tag_list else []
        thread = p.find("p", id="thread")
        thread_link = thread.find("a", href=True) if thread else None

        return Intro(
            title=title, language=language, author=author, intro=content, images=images, chapters=chapters,
            published_on=published_on,
            began=statistics.get("began"), ended=statistics.get("ended"),
            parts=int(statistics["parts"]) if "parts" in statistics else None,
            tags=[t for t in tags if t],
            thread_title=thread_link.get_text(" ", strip=True) if thread_link else None,
            thread_url=thread_link["href"].strip() if thread_link else None,
        )

    @staticmethod
    def all_chapters(root_url: str, p: BeautifulSoup) -> List[Chapters]:
        """The pages of the Let's Play, in reading order.

        A chapter is any link whose target is a directory right under the LP's own URL: "Update%2001/",
        "Introduction/", "Cast/", "Epilogue/"... whatever the author named it. Everything else is
        structurally not a chapter: files, anchors, other LPs, other sites, the LP root itself.
        Chapters are taken in document order, each one once: on the archive the landing page's
        lists and prose interleave freely (checked over every landing page), so document order is
        the reading order, and preferring <ul class="toc"> entries would scramble it."""
        content = p.find("div", id="content")
        root = root_url[:-1] if root_url.endswith("/") else root_url
        base = root + "/"

        chapters: list[Chapters] = []
        seen: set[str] = set()
        for link in content.find_all("a", href=True):
            slug = Extractor.chapter_slug(base, link["href"])
            if slug is None or slug in seen:
                continue
            seen.add(slug)
            text = " ".join(link.get_text(" ").split())
            chapters.append(Chapters(
                num=len(chapters),
                original_href=base + slug,
                txt=text or unquote(slug[:-1]),
                new_href=f"update_{len(chapters)}.xhtml",
                original_href_slug=slug,
            ))
        return chapters

    @staticmethod
    def chapter_slug(base: str, href: str) -> str | None:
        """'Update%2001/' when `href`, seen on a page at `base` (slash-terminated), points at a
        directory directly under it; None otherwise."""
        href = href.strip()
        if not href or href.startswith("#"):
            return None
        full = Extractor.get_full_url(base, href)
        if full is None:
            return None
        target, _ = urldefrag(full)
        if "?" in target or not target.startswith(base):
            return None
        rest = target[len(base):]
        is_directory = rest.endswith("/")
        rest = rest.rstrip("/")
        if not rest or "/" in rest:
            return None
        # Without a trailing slash, a dot means a file ("map.png", "notes.html", or a broken image link
        # such as "197-9rO6g."), except between digits: "Update%2012.5" is a page.
        if not is_directory and DOT_NOT_IN_A_NUMBER.search(rest):
            return None
        return rest + "/"

    @staticmethod
    def get_full_url(root_url: str, src: str) -> str | None:
        """Absolute URL of `src` as found on the page at `root_url` (a directory-like page URL).

        Returns None when `src` can't be an http(s) URL (mailto:, javascript:, broken scheme...)."""
        src = src.strip().replace("\\", "/")
        if FIXABLE_SCHEME.match(src) or src.startswith("//") or HAS_SCHEME.match(src):
            return normalize_url(src)
        base = str(root_url)
        if not base.endswith("/"):
            base += "/"
        return urljoin(base, src)


    @staticmethod
    def inline_full_size_images(content: BeautifulSoup) -> int:
        """Show the full-size picture where the post shows a thumbnail linking to it.

        Forum posts shrink big pictures and link to the original, in two shapes:
          <a href="full.png"><img src="thumb.png"/></a>
          <img src="thumb.png"/><a href="full.png">Click here for the full 728x866 image.</a>
        A book has no "click to enlarge": the thumbnail becomes the full picture (the stylesheet fits
        it to the screen) and the link goes. Only the full picture is then downloaded. Links to images
        with no thumbnail to pair with are left alone. Returns the number of replacements."""
        replaced = 0
        for link in content.find_all("a", href=True):
            href = link["href"].strip()
            if not IMAGE_FILE_LINK.search(href):
                continue
            wrapped = link.find_all("img")
            if len(wrapped) == 1 and not "".join(link.find_all(string=True)).strip():
                thumbnail = wrapped[0]            # <a href="full"><img src="thumb"/></a>
                thumbnail["src"] = href
                link.replace_with(thumbnail)
                replaced += 1
                continue
            if wrapped or not FULL_IMAGE_LINK_TEXT.search(link.get_text(" ")):
                continue
            previous = link.previous_sibling     # <img src="thumb"/> [<br/>] <a href="full">Click here...</a>
            while previous is not None and (getattr(previous, "name", None) == "br"
                                            or (getattr(previous, "name", None) is None and not str(previous).strip())):
                previous = previous.previous_sibling
            if getattr(previous, "name", None) == "img":
                previous["src"] = href
                link.decompose()
                replaced += 1
        return replaced

    @staticmethod
    def all_images(content: BeautifulSoup, root_url: str) -> List[Image]:
        # Get direct image tags
        images = content.find_all("img")
        images = (x for x in images if x.get("src", None) is not None)
        r = []

        # Add direct images
        for i, x in enumerate(images):
            r.append(Image(
                num=i,
                src=x['src'],
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
                tag=link,  # Use the link tag itself
                url=Extractor.get_full_url(root_url, link['href']),
                root_url=root_url
            ))

        return r

    @staticmethod
    def get_update(chapters: List[Chapters], p: BeautifulSoup, chapter: Chapters) -> Update:
        content = p.find("div", id="content")
        Extractor.inline_full_size_images(content)
        images = Extractor.all_images(content, chapter.original_href)
        Extractor.fix_links(content, chapters, chapter.original_href)
        return Update(content=content, images=images)


@dataclass
class Page:
    num: int
    chapter: EpubHtml
    images: List[IndexedEpubImage]

@dataclass
class Fetched:
    """A successfully downloaded resource. Processing it happens outside the retry loop."""
    url: str
    body: bytes
    content_type: str | None
    encoding: str

    def text(self) -> str:
        return self.body.decode(self.encoding, errors="replace")


CURL_HEADERS = {
    "user-agent": "curl/8.1.1",
    "accept": "*/*"
}

class FetchError(RuntimeError):
    """A resource could not be retrieved. `url` and, when known, the HTTP `status` are kept for reporting."""

    def __init__(self, message: str, url: str = "", status: int | None = None):
        super().__init__(message)
        self.url = url
        self.status = status


class NonRetryableError(FetchError):
    """A failure that will not go away by trying again (malformed URL, 404...)."""


class RetriesExhaustedError(FetchError):
    """The resource was still unavailable after all retries (network trouble, 5xx...)."""


@dataclass
class SkippedResource:
    page: str
    url: str
    reason: str


# Exit codes of the command line tool. argparse uses 2 for usage errors.
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_NOT_FOUND = 3
EXIT_NETWORK = 4
EXIT_OUTPUT = 5
EXIT_CACHE = 6
EXIT_INTERRUPTED = 130


class ExtractionError(RuntimeError):
    """The book could not be built; the message is a full report meant to be shown to the user."""
    exit_code = EXIT_FAILURE


class StrictModeError(ExtractionError):
    """Resources were skipped while --strict was requested."""


class MissingUpdatesError(ExtractionError):
    """One or more updates (chapters) could not be retrieved."""


class OutputError(ExtractionError):
    """The output file can't be written."""
    exit_code = EXIT_OUTPUT


class CacheError(ExtractionError):
    """The --cache database can't be used."""
    exit_code = EXIT_CACHE


def resolve_cache_path(path: str) -> str:
    """Where the --cache SQLite file lives: `path`, with .sqlite added when it has no extension."""
    path = os.path.abspath(os.path.expanduser(path))
    return path if os.path.splitext(path)[1] else path + ".sqlite"


def check_cache_path(path: str) -> str:
    """Validate the --cache location before any download. Returns the resolved file path.

    Creates the database if it does not exist yet, and fails early if the file is a directory, is
    not a SQLite database, or is locked by another run."""
    if os.path.isdir(os.path.expanduser(path)):
        raise CacheError(f"Cannot use {os.path.abspath(os.path.expanduser(path))} as the cache: it is a directory.")
    file = resolve_cache_path(path)
    directory = os.path.dirname(file)
    if not os.path.isdir(directory):
        raise CacheError(f"Cannot use {file} as the cache: the directory {directory} does not exist.")
    # A real write, not just opening: on some mounted filesystems (virtiofs, as used by Docker Desktop)
    # the very first write to a freshly created database fails with "readonly database" and the next
    # one succeeds, so one retry is allowed.
    for attempt in (1, 2):
        try:
            connection = sqlite3.connect(file, timeout=1)
            try:
                connection.execute("BEGIN IMMEDIATE")   # fails at once if another process holds the database
                connection.execute("CREATE TABLE IF NOT EXISTS lparchive2epub_probe (x)")
                connection.execute("DROP TABLE lparchive2epub_probe")
                connection.commit()
            finally:
                connection.close()  # must not linger: an open handle can leave the file locked for the real cache
            return file
        except sqlite3.OperationalError as e:
            reason = str(e)
            if "readonly" in reason and attempt == 1:
                continue
            if "locked" in reason:
                reason = "it is locked by another run (use a different --cache file, or wait for that run to finish)"
            raise CacheError(f"Cannot use {file} as the cache: {reason}.") from e
        except sqlite3.DatabaseError as e:
            raise CacheError(f"Cannot use {file} as the cache: it is not a SQLite database ({e}).") from e
    return file


class NotFoundError(ExtractionError):
    """The Let's Play landing page does not exist on lparchive.org."""
    exit_code = EXIT_NOT_FOUND


class NetworkError(ExtractionError):
    """lparchive.org could not be reached or kept failing."""
    exit_code = EXIT_NETWORK


class NotALetsPlayError(ExtractionError):
    """The page exists but is not the landing page of a Let's Play (author page, tag listing...)."""
    exit_code = EXIT_NOT_FOUND


LPARCHIVE_HOSTS = {"lparchive.org", "www.lparchive.org"}
LPARCHIVE_ROOT = "https://lparchive.org"


def normalize_lp_url(arg: str) -> str:
    """Turn any address on lparchive.org into the canonical URL of the Let's Play it belongs to.

    "lparchive.org/Some-LP/", "http://www.lparchive.org/Some-LP/Update%2003/#part2" and
    "https://lparchive.org/Some-LP?x=1" all give "https://lparchive.org/Some-LP".
    Raises ValueError with a user-facing message when the address is not on lparchive.org or
    does not name a Let's Play."""
    text = arg.strip()
    if not text:
        raise ValueError("no URL given")
    if "://" not in text:
        text = "https://" + text.lstrip("/")
    parsed = urlparse(text)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(f"{arg} is not an http(s) URL")
    if parsed.hostname is None or parsed.hostname.lower() not in LPARCHIVE_HOSTS:
        raise ValueError(f"{arg} is not an lparchive.org URL")
    segments = [seg for seg in parsed.path.split("/") if seg]
    if not segments:
        raise ValueError(f"{arg} does not name a Let's Play: expected something like {LPARCHIVE_ROOT}/Name-Of-The-Lets-Play")
    return f"{LPARCHIVE_ROOT}/{segments[0]}"


def landing_page_error(url: str, e: Exception) -> ExtractionError:
    """Turn a failure to fetch the landing page into a message a user can act on."""
    status = getattr(e, "status", None)
    if status == 404:
        return NotFoundError(
            f"Not found: {url} answered HTTP 404.\n"
            "Check the URL: a Let's Play address looks like https://lparchive.org/Name-Of-The-Lets-Play")
    if status is not None:
        return NetworkError(f"lparchive.org answered HTTP {status} for {url}. Try again later.")
    cause = getattr(e, "__cause__", None) or e
    detail = str(cause) or type(cause).__name__
    return NetworkError(f"Could not reach {url}: {detail}\nCheck your network connection and try again.")


# Characters Windows refuses in file names (and that confuse shells everywhere), plus control characters
UNSAFE_IN_FILE_NAMES = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MAX_FILE_NAME_LENGTH = 150


def safe_file_name(title: str, fallback: str) -> str:
    """The Let's Play's title as a file name every filesystem accepts, or `fallback` (the URL slug)
    when nothing usable is left."""
    name = UNSAFE_IN_FILE_NAMES.sub(" ", title)
    name = " ".join(name.split()).strip(". ")
    if len(name) > MAX_FILE_NAME_LENGTH:
        name = name[:MAX_FILE_NAME_LENGTH].rstrip(". ")
    return (name or fallback) + ".epub"


def resolve_output_path(file: str | None, title: str, url: str) -> str:
    """Where the book goes: `file` as given, or "<title>.epub" in `file` when that is a directory,
    or in the current directory when no output was given."""
    if file is None:
        return safe_file_name(title, url.rstrip("/").rsplit("/", 1)[-1])
    if os.path.isdir(file):
        return os.path.join(file, safe_file_name(title, url.rstrip("/").rsplit("/", 1)[-1]))
    return file


def check_output_directory(file: str | None):
    """Fail early, before any download, if the book can't possibly be written where `file` points:
    `file` is the book's path, a directory to put it in, or None for the current directory."""
    if file is None:
        directory = os.getcwd()
    elif os.path.isdir(file):
        directory = file
    else:
        directory = os.path.dirname(os.path.abspath(file))
        if not os.path.isdir(directory):
            raise OutputError(f"Cannot write the book to {file}: the directory {directory} does not exist.")
    if not os.access(directory, os.W_OK):
        raise OutputError(f"Cannot write the book in {directory}: the directory is not writable.")


def check_output_path(file: str):
    """Fail if the book can't be written at `file` (a file path, resolved)."""
    check_output_directory(file)
    if os.path.isdir(file):
        raise OutputError(f"Cannot write the book to {file}: it is a directory.")
    if os.path.exists(file) and not os.access(file, os.W_OK):
        raise OutputError(f"Cannot write the book to {file}: the file exists and is not writable.")


def write_book(file: str, book: EpubBook, mtime: datetime.datetime):
    """Write the book through a temporary file, so a failure never leaves a truncated epub behind.

    ebooklib only uses `mtime` for the dcterms:modified metadata and stamps every zip entry with the
    current time, which would make two builds of the same LP differ. The archive is rewritten with
    `mtime` on every entry so the output is byte-identical from one run to the next."""
    partial = file + ".part"
    try:
        epub.write_epub(partial, book, options={"mtime": mtime, "raise_exceptions": True})
        _rewrite_with_fixed_timestamps(partial, file, mtime)
    except OSError as e:
        raise OutputError(f"Cannot write the book to {file}: {e.strerror or e}") from e
    finally:
        try:
            os.remove(partial)
        except OSError:
            pass


def _rewrite_with_fixed_timestamps(src: str, dst: str, mtime: datetime.datetime):
    date_time = max(mtime, datetime.datetime(1980, 1, 1)).timetuple()[:6]  # zip can't store dates before 1980
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
        for info in zin.infolist():
            fixed = zipfile.ZipInfo(info.filename, date_time=date_time)
            fixed.compress_type = info.compress_type
            fixed.external_attr = info.external_attr
            zout.writestr(fixed, zin.read(info.filename))


ISSUES_URL = "https://github.com/Arwalk/lparchive2epub/issues/new"

# Client errors that may succeed later: request timeout, too many requests
RETRYABLE_CLIENT_STATUSES = {408, 429}
# Exponential backoff between retries: base * 2^attempt seconds (2s, 4s, 8s, 16s). Tests set it to 0.
RETRY_BACKOFF_BASE = 1.0


async def fetch_with_retries(session: aiohttp.ClientSession, url: str, max_retries: int | None = None,
                             fetch: FetchSettings | None = None) -> Fetched:
    """Download `url` (status 200 and the whole body), retrying on network trouble and 5xx/408/429.

    Only the download is retried. Whatever the caller does with the bytes afterwards (parsing,
    image sniffing...) runs outside this loop, so a bug there fails once and fast instead of
    re-downloading the resource five times with 30 s of backoff."""
    if max_retries is None:
        max_retries = fetch.retries if fetch is not None else DEFAULT_RETRIES
    retry_count = 0
    last_exception = None

    while retry_count < max_retries:
        try:
            async with (fetch.limit() if fetch is not None else contextlib.nullcontext()), \
                    session.get(url, headers=CURL_HEADERS) as r:
                if 400 <= r.status < 500 and r.status not in RETRYABLE_CLIENT_STATUSES:
                    raise NonRetryableError(f"Failed to get resource {url}, status code: {r.status}", url, r.status)
                if r.status != 200:
                    raise FetchError(f"Failed to get resource {url}, status code: {r.status}", url, r.status)
                body = await r.read()
                headers = getattr(r, "headers", None) or {}
                get_encoding = getattr(r, "get_encoding", None)
                encoding = get_encoding() if callable(get_encoding) else "utf-8"
                return Fetched(url, body, headers.get("Content-Type"), encoding or "utf-8")
        except NonRetryableError:
            raise
        except aiohttp.InvalidURL as e:
            raise NonRetryableError(f"Invalid URL {url}: {e}", url) from e
        except sqlite3.Error as e:
            # The --cache database, not the network: retrying would only hide it behind a network error
            raise CacheError(f"The cache database failed while fetching {url}: {e}") from e
        except Exception as e:
            last_exception = e
            retry_count += 1
            if retry_count < max_retries:
                await asyncio.sleep(RETRY_BACKOFF_BASE * (2 ** retry_count))
    raise RetriesExhaustedError(f"Failed to get resource {url} after {max_retries} retries: {last_exception}",
                                url, getattr(last_exception, "status", None)) from last_exception



class ImageRegistry:
    """Per-run memory of images, shared by every page being built.

    by_url: one future per resolved URL, so a URL referenced from many pages is downloaded once.
    The future is kept after a failure too: later references get the stored error immediately
    instead of re-running the download and its retries (a dead host would otherwise cost
    5 attempts and 30 s of backoff per reference).
    by_content: hash of the downloaded bytes -> future of the finished image, so a second URL serving
    the same bytes reuses the stored image (and skips the optional resize pass) instead of being
    processed and held twice. A future, because identical downloads usually land at the same time."""

    def __init__(self):
        self.by_url: dict[str, asyncio.Future] = {}
        self.by_content: dict[str, asyncio.Future] = {}


async def _get_image(session: aiohttp.ClientSession, img: Image, registry: ImageRegistry | None = None,
                     processing: ImageProcessing | None = None, fetch: FetchSettings | None = None) -> IndexedEpubImage:
    # Get the image URL from either src (for img tags) or href (for a tags)
    img_url = img.url
    if img_url is None:
        raise NonRetryableError(f"Malformed URL that could not be repaired: {img.src}")

    if registry is not None:
        if img_url in registry.by_url:
            return await registry.by_url[img_url]
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        registry.by_url[img_url] = future
    else:
        future = None

    def build(fetched: Fetched, reduced: tuple[bytes, str, str] | None) -> IndexedEpubImage:
        content = fetched.body
        media_type, extension = _detect_or_fail(fetched, img_url)
        if reduced is not None:
            content, media_type, extension = reduced
        if processing is not None:
            processing.record(len(fetched.body), len(content))
        img_hash = get_blake2b_hash(content)
        new_name = f"images/{img_hash}.{extension}"
        return IndexedEpubImage(
            img_hash,
            img_url,  # Use the original URL as old_name
            new_name,
            EpubImage(
                uid=f"i{img_hash}",
                file_name=new_name,
                media_type=media_type,
                content=content)
        )

    try:
        fetched = await fetch_with_retries(session, img_url, fetch=fetch)
        raw_hash = get_blake2b_hash(fetched.body)
        if registry is not None and raw_hash in registry.by_content:
            # Same bytes already seen under another URL: share the stored image (it may still be
            # being processed), keeping this URL as old_name so the page's links to it get rewritten.
            known = await registry.by_content[raw_hash]
            if processing is not None:
                processing.record(len(fetched.body), len(known.data.content))
            res = IndexedEpubImage(known.hash, img_url, known.new_name, known.data)
        else:
            content_future = asyncio.get_running_loop().create_future() if registry is not None else None
            if content_future is not None:
                registry.by_content[raw_hash] = content_future
            try:
                reduced = None
                if processing is not None:
                    media_type, _ = _detect_or_fail(fetched, img_url)
                    # CPU-bound (decode, resize, encode): off the event loop so downloads keep flowing
                    reduced = await asyncio.to_thread(reduce_image, fetched.body, media_type, processing)
                res = build(fetched, reduced)
            except Exception as e:
                if content_future is not None:
                    content_future.set_exception(e)
                    content_future.exception()
                raise
            if content_future is not None:
                content_future.set_result(res)
        if future:
            future.set_result(res)
        return res
    except Exception as e:
        if future:
            future.set_exception(e)
            # Mark the exception as retrieved, so asyncio doesn't complain if nobody else awaits it.
            # The future stays in the registry: the failure is remembered for the rest of the run.
            future.exception()
        raise

def _detect_or_fail(fetched: Fetched, img_url: str) -> tuple[str, str]:
    detected = detect_image_type(fetched.body, img_url, fetched.content_type)
    if detected is None:
        declared = (fetched.content_type or "unknown type").split(";")[0].strip()
        raise NonRetryableError(f"Not an image: the server answered with {declared} ({len(fetched.body)} bytes)",
                                img_url)
    return detected


def _describe(e: Exception) -> str:
    """Fetch errors are self-explanatory; anything else is unexpected, so say what kind of error it was."""
    if isinstance(e, FetchError):
        return str(e)
    return f"{type(e).__name__}: {e}" if str(e) else type(e).__name__


def _skipped(img: Image, e: Exception) -> SkippedResource:
    return SkippedResource(page=img.root_url, url=img.src, reason=_describe(e))


async def build_intro(session: aiohttp.ClientSession, url_root: str, intro: Intro, registry: ImageRegistry | None = None,
                      failures: list[SkippedResource] = None, processing: ImageProcessing | None = None,
                      fetch: FetchSettings | None = None) -> Page:
    # Named after the Let's Play: many LPs have their own "Introduction" update right after it
    intro_chapter = epub.EpubHtml(title=intro.title, file_name=INTRO_FILE_NAME, lang=intro.language)
    intro_chapter.add_item(get_style_item())
    tasks = []
    for image in intro.images:
        task = asyncio.ensure_future(_get_image(session, image, registry, processing, fetch))
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    images = []
    for img, res in zip(intro.images, results):
        if isinstance(res, Exception):
            if failures is not None:
                failures.append(_skipped(img, res))
        else:
            images.append(res)

    for image, result in zip(intro.images, results):
        if not isinstance(result, Exception):
            point_at_embedded(image, result)

    intro_chapter.content = str(intro.intro)

    return Page(0, intro_chapter, in_document_order(intro.images, images))


def point_at_embedded(image: Image, stored: IndexedEpubImage):
    """Make the tag the image came from show the stored copy: src for <img>, href for <a>."""
    image.tag["href" if image.tag.name == "a" else "src"] = stored.new_name


async def build_update(session: aiohttp.ClientSession, chapter: Chapters, data: Update, intro: Intro, registry: ImageRegistry | None = None,
                       failures: list[SkippedResource] = None, processing: ImageProcessing | None = None,
                       fetch: FetchSettings | None = None) -> Page:
    update_chapter = epub.EpubHtml(title=str(chapter.txt), file_name=chapter.new_href,
                                   lang=intro.language)  # TODO: fix language
    update_chapter.add_item(get_style_item())

    img_builder = functools.partial(_get_image, session, registry=registry, processing=processing, fetch=fetch)

    # Queue-based worker pool to cap concurrency
    q: asyncio.Queue = asyncio.Queue()
    images: list[IndexedEpubImage] = []

    async def worker():
        while True:
            try:
                img = await q.get()
                try:
                    res = await img_builder(img)
                    point_at_embedded(img, res)
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

    return Page(chapter.num, update_chapter, in_document_order(data.images, images))


def in_document_order(wanted: List[Image], fetched: List[IndexedEpubImage]) -> List[IndexedEpubImage]:
    """Order downloaded images as they appear on the page, not as the downloads happened to finish.

    The book's manifest follows this order, so it must not depend on network timing; otherwise two
    runs on the same LP give two different files."""
    by_url = {img.old_name: img for img in fetched}
    ordered, seen = [], set()
    for image in wanted:
        img = by_url.get(image.url)
        if img is not None and img.old_name not in seen:
            seen.add(img.old_name)
            ordered.append(img)
    return ordered


def add_page(known_images: set, book: EpubBook, toc: List, spine: List, page: Page):
    book.add_item(page.chapter)
    for img in page.images:
        if img.hash not in known_images:
            book.add_item(img.data)
            known_images.add(img.hash)
    toc.append(epub.Link(page.chapter.file_name, page.chapter.title, page.chapter.id))
    spine.append(page.chapter)


async def build_single_page(session: aiohttp.ClientSession, intro: Intro, chapter: Chapters, all_chapters: List[Chapters], pbar,
                            registry: ImageRegistry | None = None, failures: list[SkippedResource] = None,
                            processing: ImageProcessing | None = None, fetch: FetchSettings | None = None) -> Page:
    fetched = await fetch_with_retries(session, chapter.original_href, fetch=fetch)
    chapter_bs = get_cleaned_html(fetched.text())
    update = Extractor.get_update(all_chapters, chapter_bs, chapter)
    page = await build_update(session, chapter, update, intro, registry, failures, processing, fetch)
    pbar.update(1)
    return page

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


async def lparchive2epub(url: str, file: str | None = None, root_session: aiohttp.ClientSession | None = None,
                         writer=log, strict: bool = False, allow_missing_updates: bool = False,
                         image_processing: ImageProcessing | None = None, cover: bytes | None | bool = True,
                         fetch: FetchSettings | None = None) -> str:
    """Build the book for `url` at `file` (a path, a directory, or None for "<title>.epub" in the current
    directory). Returns the path of the written book."""
    try:
        url = normalize_lp_url(url)
    except ValueError as e:
        raise NotFoundError(str(e)) from e
    if root_session is None:
        root_session = aiohttp.ClientSession(timeout=CLIENT_TIMEOUT)
    async with root_session as session:
        return await do(url, file, session, writer, strict, allow_missing_updates, image_processing, cover, fetch)


tags_to_clean = [
    "st1:place",
    "st1:city",
    "st1:country-region",
    "st1:placename",
    "st1:placetype",
    "st1:state",
    "o:p"
]


# Active content has no place in a book (and makes epubcheck demand the "scripted" property).
TAGS_TO_DROP = ["script", "noscript", "style", "form", "input", "button", "select", "textarea"]
# Embedded players: replaced by a plain link to what they were showing, when they point somewhere.
EMBED_TAGS = ["iframe", "embed", "object", "video", "audio"]
# HTML 4 presentational attributes that are invalid in XHTML 5 and that the stylesheet supersedes anyway.
ATTRIBUTES_TO_DROP = {"border", "align", "valign", "bgcolor", "background", "cellpadding", "cellspacing",
                      "hspace", "vspace", "nowrap", "target", "rel"}
SPOILER_CLASS = "bbc-spoiler"
# Block-level elements that EPUB does not allow inside a link (or any inline element)
BLOCK_TAGS = ["p", "div", "blockquote", "ul", "ol", "table", "pre", "h1", "h2", "h3", "h4", "h5", "h6"]
INLINE_WRAPPERS = ["a", "b", "i", "u", "s", "em", "strong", "span", "small", "sub", "sup", "code"]


def get_cleaned_html(page: str) -> BeautifulSoup:
    """Parse a page and make its markup fit for a book: no scripts, handlers or players, no legacy
    attributes, and spoilers that stay readable."""
    soup = BeautifulSoup(page, "html.parser")
    for tag in tags_to_clean:
        while found := soup.find(tag):
            found.unwrap()
    sanitize(soup)
    return soup


def sanitize(soup: BeautifulSoup):
    for element in soup.find_all(TAGS_TO_DROP):
        element.decompose()

    for element in soup.find_all(EMBED_TAGS):
        source = element.get("src") or element.get("data")
        if source and HAS_SCHEME.match(source.strip()):
            link = soup.new_tag("a", href=source.strip())
            link.string = source.strip()
            paragraph = soup.new_tag("p")
            paragraph.append(f"[{element.name}: ")
            paragraph.append(link)
            paragraph.append("]")
            element.replace_with(paragraph)
        else:
            element.decompose()

    # <font color="red"> -> <span style="color: red">, <center> -> <div style="text-align: center">
    for font in soup.find_all("font"):
        font.name = "span"
        color = font.attrs.pop("color", None)
        font.attrs.pop("size", None)
        font.attrs.pop("face", None)
        if color:
            font["style"] = f"color: {color};"
    for center in soup.find_all("center"):
        center.name = "div"
        center["style"] = "text-align: center;"

    unnest_blocks_from_inline(soup)

    for element in soup.find_all(True):
        for attribute in list(element.attrs):
            if attribute.startswith("on") or attribute in ATTRIBUTES_TO_DROP:
                del element.attrs[attribute]
        # <a name="x"> is the HTML 4 anchor; XHTML 5 wants an id
        if element.name == "a" and "name" in element.attrs:
            element.attrs.setdefault("id", element.attrs["name"])
            del element.attrs["name"]
        # Forum spoilers come with black-on-black inline styles (and hover handlers, removed above):
        # unreadable on paper. The stylesheet marks .bbc-spoiler instead.
        classes = element.get("class") or []
        if SPOILER_CLASS in classes or _hides_its_text(element.get("style")):
            element.attrs.pop("style", None)
            if SPOILER_CLASS not in classes:
                element["class"] = classes + [SPOILER_CLASS]


def unnest_blocks_from_inline(soup: BeautifulSoup):
    """Forum posts contain things like <a href="full.png"><p><img src="thumb.png"/></p></a>: a paragraph
    inside a link. EPUB only allows inline content in a link, so epubcheck rejects the page.
    A link (or other inline wrapper) around exactly one block is turned inside out,
    <p><a href="full.png"><img/></a></p>, keeping both the paragraph and the link; around anything
    more complicated, the blocks are unwrapped so their content stays, inline, inside the link."""
    for wrapper in soup.find_all(INLINE_WRAPPERS):
        blocks = [child for child in wrapper.children if getattr(child, "name", None) in BLOCK_TAGS]
        if not blocks:
            continue
        others = [child for child in wrapper.children
                  if child not in blocks and (getattr(child, "name", None) is not None or str(child).strip())]
        if len(blocks) == 1 and not others and not blocks[0].find(BLOCK_TAGS):
            block = blocks[0]
            wrapper.replace_with(block)      # the block takes the wrapper's place...
            block.insert(0, wrapper.extract() if wrapper.parent else wrapper)
            for child in list(block.children)[1:]:
                wrapper.append(child.extract())   # ...and the wrapper moves inside it, around its content
        else:
            for block in wrapper.find_all(BLOCK_TAGS):
                block.unwrap()


def _hides_its_text(style: str | None) -> bool:
    """True for inline styles that paint the text in its own background colour (the forum spoiler trick)."""
    if not style:
        return False
    declarations = {}
    for declaration in style.split(";"):
        name, _, value = declaration.partition(":")
        declarations[name.strip().lower()] = " ".join(value.lower().split())
    color, background = declarations.get("color"), declarations.get("background-color") or declarations.get("background")
    return bool(color) and color == background


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


async def do(url: str, file: str | None, session: aiohttp.ClientSession, writer, strict: bool = False,
             allow_missing_updates: bool = False, image_processing: ImageProcessing | None = None,
             cover: bytes | None | bool = True, fetch: FetchSettings | None = None) -> str:
    """`file`: the book's path, a directory to put "<title>.epub" in, or None for the current directory.
    `cover`: True for a generated text cover, bytes for a custom image, None/False for no cover.
    `writer` gets the final report and summary; progress messages go through it too unless `fetch.quiet`.
    Returns the path of the written book."""
    fetch = fetch or FetchSettings()
    say = (lambda *_: None) if fetch.quiet else writer
    check_output_directory(file)
    say(f"extracting lp from {url}")
    say("getting landing page")
    try:
        page_text = (await fetch_with_retries(session, url, fetch=fetch)).text()
    except (FetchError, aiohttp.ClientError, OSError) as e:
        raise landing_page_error(url, e) from e

    landing = get_cleaned_html(page_text)

    book = epub.EpubBook()
    intro = Extractor.intro(url, landing)
    file = resolve_output_path(file, intro.title, url)
    check_output_path(file)

    toc = []
    spine = []
    description = compose_description(intro, url)
    if cover:
        cover_bytes = cover if isinstance(cover, bytes) else make_cover(intro.title, intro.author)
        cover_type = detect_image_type(cover_bytes)   # by content only: no file name to fall back on
        if cover_type is None:
            raise OutputError("The cover is not an image file.")
        cover_name = COVER_FILE_NAME.rsplit(".", 1)[0] + "." + cover_type[1]
        # Adds the image (with the cover-image property and the EPUB 2 <meta name="cover">) and a
        # cover.xhtml page with id "cover"
        book.set_cover(cover_name, cover_bytes)
        book.get_item_with_id("cover").is_linear = True   # part of the reading order, not a detached page
        spine.append("cover")
    title_page = epub.EpubHtml(title="Title page", file_name=TITLE_PAGE_FILE_NAME, lang=intro.language)
    title_page.add_item(get_style_item())
    title_page.content = make_title_page(intro, url, description)
    book.add_item(title_page)
    toc.append(epub.Link(title_page.file_name, title_page.title, title_page.id))
    spine.append(title_page)
    spine.append("nav")

    say("building intro")
    image_registry = ImageRegistry()
    failures: list[SkippedResource] = []
    missing_updates: list[tuple[int, Chapters, Exception]] = []
    epub_intro = await build_intro(session, url, intro, image_registry, failures, image_processing, fetch)

    known_images: set[str] = set()

    add_page(known_images, book, toc, spine, epub_intro)

    # pages takes a vastly inequal times to get, so it's faster to gather and sort
    # gotta go fast, but also keep the page order.

    say("building chapters / updates")

    pages_indexed: list[tuple[int, Page]] = []

    with tqdm(total=len(intro.chapters), desc="Gathering and building pages", disable=fetch.quiet) as pbar:
        q: asyncio.Queue = asyncio.Queue()

        async def worker():
            while True:
                try:
                    i, chapter = await q.get()
                except asyncio.CancelledError:
                    break
                try:
                    page = await build_single_page(session, intro, chapter, intro.chapters, pbar, image_registry,
                                                   failures, image_processing, fetch)
                except asyncio.CancelledError:
                    raise  # task_done() runs in the finally clause below
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
        fatal = [e for _, _, e in missing_updates if isinstance(e, ExtractionError)]
        if fatal:
            raise fatal[0]  # e.g. a broken --cache database: not a per-update problem, say so directly
        missing = [SkippedResource(page=c.original_href, url=c.original_href, reason=_describe(e))
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

    for p in tqdm(pages, desc="Adding pages to book", disable=fetch.quiet):
        add_page(known_images, book, toc, spine, p)

    say("preparing book structure")
    book.toc = toc

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    book.spine = spine

    book.add_item(get_style_item())

    book.add_author(intro.author)
    book.set_title(intro.title)
    book.set_language(intro.language)
    book.add_metadata("DC", "source", url)
    book.add_metadata("DC", "publisher", PUBLISHER)
    book.add_metadata("DC", "description", description)
    # Publication date: when the LP was finished, else when it started, else when it was archived
    published = parse_lp_date(intro.ended) or parse_lp_date(intro.began) or parse_lp_date(intro.published_on)
    if published:
        book.add_metadata("DC", "date", published.strftime("%Y-%m-%d"))
    for subject in ["Let's Play", *intro.tags]:
        book.add_metadata("DC", "subject", subject)
    if intro.thread_url:
        book.add_metadata("DC", "relation", intro.thread_url)
    # Stable across runs: Python's hash() must not be used here, it is randomised per process.
    book.set_identifier(f"lparchive2epub-{get_blake2b_hash(intro.title.encode("utf-8"))}-{get_blake2b_hash(intro.author.encode("utf-8"))}-{get_blake2b_hash(url.encode("utf-8"))}")

    mtime = datetime.datetime.strptime(intro.published_on, "%b %d, %Y")

    if image_processing is not None:
        writer(image_processing.summary())
    say(f"Writing book file {file}")
    write_book(file, book, mtime)

    if failures:
        writer(format_failures_report(
            url, failures,
            "Missing images were left as external links in the book; "
            "missing updates (--allow-missing-updates) were replaced by a placeholder page linking to the original."))
    return file
