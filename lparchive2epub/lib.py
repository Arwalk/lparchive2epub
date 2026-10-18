import asyncio
import contextlib
import datetime
import functools
import html
import io
import mimetypes
import os
import re
import sqlite3
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from hashlib import blake2b
from typing import List
from urllib.parse import urlparse, urlsplit, urlunsplit, urljoin, urldefrag, unquote, quote

import aiohttp
from bs4 import BeautifulSoup, Comment
from bs4.element import NavigableString, PreformattedString, Tag
from ebooklib import epub
from ebooklib.epub import EpubHtml, EpubImage, EpubBook
from tqdm.asyncio import tqdm

from lparchive2epub.cover import COVER_FILE_NAME, TITLE_PAGE_FILE_NAME, make_cover, make_title_page, tool_version
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
    quiet: bool = False          # no progress messages through the writer, and no progress bars unless `bars` says so
    bars: bool | None = None     # progress bars on stderr: None follows `quiet`; True shows them for a quiet build
                                 # too, for a caller that builds many books under its own bar and wants to see
                                 # the one in hand advance (the bars nest under its own and clear when done)
    _semaphore: asyncio.Semaphore | None = field(default=None, repr=False, compare=False)

    def limit(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.concurrency)   # created inside the running loop
        return self._semaphore

    def progress_bar(self, iterable=None, total: int | None = None, desc: str | None = None) -> tqdm:
        """A bar for one step of the build. Nested under a caller's own bar, it clears once the step is done
        (tqdm's leave=None), so that caller keeps one line for its run and one for the step in hand."""
        shown = self.bars if self.bars is not None else not self.quiet
        return tqdm(iterable, total=total, desc=desc, disable=not shown, leave=None)

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
REDUCIBLE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"}
# Formats no EPUB reader displays: converted whether or not --max-image-size was asked for
UNREADABLE_TYPES = {"image/tiff"}


def convert_for_readers(content: bytes, media_type: str) -> tuple[bytes, str, str] | None:
    """A TIFF (Myth-II-Soulblighter's maps) as PNG, at full size: readers do not show TIFF at all."""
    return reduce_image(content, media_type, ImageProcessing(max_size=sys.maxsize))


def reduce_image(content: bytes, media_type: str, settings: ImageProcessing) -> tuple[bytes, str, str] | None:
    """Shrink an image to at most `settings.max_size` pixels on its longest edge and re-encode it.

    JPEG stays JPEG (at `jpeg_quality`), PNG stays PNG. WebP and BMP, which many readers can't show,
    become PNG (with transparency) or JPEG (without); TIFF, which none shows, becomes PNG (lossless:
    they are maps and scans). Returns (bytes, media type, extension), or
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
    elif media_type in ("image/png", "image/tiff"):
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
    html: str | None = None  # the page once downloaded (prefetched, or read while following next links)
    order: float = -1.0      # reading order; a page found through next links sits between two listed ones
    next_slug: str | None = None  # where the page's own "next" link points, once the page was read
    fetch_error: Exception | None = None  # why the page could not be downloaded, when it could not

    def __post_init__(self):
        if self.order < 0:
            self.order = float(self.num)


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
    size: int           # of the stored bytes; kept here so a spooled image need not be read back


class SpooledImage(EpubImage):
    """An image whose bytes wait in a file until the book is written, so that building a large LP
    does not hold every picture in memory.

    Read once: ebooklib's writer calls get_content() exactly once per item (add_page adds each image
    once), and the file is deleted as soon as it has been read, so the spool empties as the book
    fills. A second call would fail with a missing file."""

    def __init__(self, uid: str, file_name: str, media_type: str, path: str, size: int):
        super().__init__(uid=uid, file_name=file_name, media_type=media_type)
        self.path = path
        self.size = size

    def get_content(self, default=None):
        with open(self.path, "rb") as f:
            content = f.read()
        os.remove(self.path)
        return content


class FreedOnWriteImage(EpubImage):
    """The in-memory alternative (--images-in-memory): the bytes stay in memory until the book is
    written, but are dropped as soon as ebooklib has read them, so the zip rewrite that follows starts
    with the images already gone. Read once, like SpooledImage: a second read is a bug and says so."""

    def get_content(self, default=None):
        if self.content is None:
            raise RuntimeError(f"{self.file_name} was already written to the book")
        content, self.content = self.content, None
        return content


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
# Markers around the post in a raw (un-templated) update page, see Extractor.content_block
RAW_CONTENT_BEGIN = "BEGIN_CONTENT"
RAW_CONTENT_END = "END_CONTENT"


class NotAnUpdatePageError(RuntimeError):
    """A chapter's page has no post in it: not an update page."""
DOT_NOT_IN_A_NUMBER = re.compile(r"(?<!\d)\.|\.(?!\d)")
# Links to image files, whatever the case of the extension and ignoring any query string or fragment
IMAGE_FILE_LINK = re.compile(r"\.(jpe?g|png|gif|webp|bmp|svg)(?=\?|$)", re.IGNORECASE)
# Wiki file-description pages ("/wiki/File:X.jpg", "/index.php/File:X.jpg", "/File:X.jpg") are HTML, not pictures
WIKI_FILE_PAGE = re.compile(r"/(?:File|Image):", re.IGNORECASE)


def is_image_link(href: str) -> bool:
    """Whether a link points at a picture file, judging by its name: the extension ends the path, a
    query string may follow. The fragment does not count ("Redingote#/media/File:X.jpg" is an
    article), and neither do wiki file-description pages, which are HTML."""
    target = urldefrag(href.strip())[0]
    return bool(IMAGE_FILE_LINK.search(target)) and not WIKI_FILE_PAGE.search(target)
# lparchive's own wording for a thumbnail's link: "Click here for the full 728x866 image."
FULL_IMAGE_LINK_TEXT = re.compile(r"\bfull\b.*\bimage\b", re.IGNORECASE | re.DOTALL)

# (media subtype, file extension) by magic number. Checked in order.
IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "png", "png"),
    (b"GIF87a", "gif", "gif"),
    (b"GIF89a", "gif", "gif"),
    (b"\xff\xd8\xff", "jpeg", "jpg"),
    (b"BM", "bmp", "bmp"),
    (b"II*\x00", "tiff", "tiff"),   # little-endian TIFF...
    (b"MM\x00*", "tiff", "tiff"),   # ...and big-endian (Myth-II-Soulblighter's maps)
)
IMAGE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
    "image/svg+xml": "svg",
    "image/tiff": "tiff",
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

# Typos in the scheme part of a URL found in some LPs: "hhttp://", "htttp://", "ttp://", "http:/", "http//"...
FIXABLE_SCHEME = re.compile(r"^h*t+p+(s?)\s*(?::/*|//+)", re.IGNORECASE)
HAS_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
# Forum smilies are referenced as "Smilies/emot-x.gif" or "../Smilies/emot-x.gif". Some LPs keep their own
# copy in <LP>/Smilies/ (Arcanum, Dwarf-Fortress-Headshoots, Grandia...), with bytes of their own and a few
# names of their own; the site-wide folder https://lparchive.org/Smilies/ has every name the archive-wide
# run found missing (128/128 on 2026-10-17). Groups: the LP slug, the smilie file name.
SMILIE_PATH = re.compile(r"^/(?P<lp>[^/]+)/(?:.*/)?Smilies/(?P<name>[^/]+)$", re.IGNORECASE)


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


def is_lparchive_url(url: str) -> bool:
    return urlparse(url).hostname in ("lparchive.org", "www.lparchive.org")


# Schemes a reader can follow. The rest is dead weight in a book: javascript (scripts are dropped),
# data (epubcheck RSC-029), file, and unregistered ones such as steam (HTM-025).
LINK_SCHEMES = frozenset({"http", "https", "ftp", "mailto", "irc", "news", "nntp", "tel", "telnet", "xmpp", "urn"})
NEEDS_HOST = frozenset({"http", "https", "ftp"})
# RFC 3986: unreserved characters, sub-delims, ":" and "@" stay as they are in a path; "?" too in a query
# or a fragment. "%" stays so that an existing %20 is not doubled (a bare "%" is encoded beforehand).
PATH_SAFE = "/:@!$&'()*+,;=%"
QUERY_SAFE = PATH_SAFE + "?"
BARE_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
# What no host name can hold: whitespace, delimiters, an empty label ("www..."); IDN and IPv6 are fine
BAD_HOST = re.compile(r"[\s/?#@\[\]\\^|<>%\"{}`]|^\.|\.\.")


def to_uri(href: str) -> str | None:
    """`href` written as a valid URI reference (RFC 3986), or None when no encoding can make it one.

    Pages are hand-written: links carry raw spaces ("avis/1 - Mine Level 1.avi"), brackets, quotes
    and non-ASCII that browsers quietly repair but XHTML does not allow (epubcheck RSC-020 in 98 books
    of the archive-wide run). The path, query and fragment are percent-encoded, existing escapes kept.
    None for what encoding cannot save: a host with a space or an empty label, a port that is not a
    number, a scheme no reader can follow (LINK_SCHEMES)."""
    href = BARE_PERCENT.sub("%25", href.strip())
    try:
        parts = urlsplit(href)
        host, _port = parts.hostname, parts.port   # ValueError: a port that is no number ("http://http:ustwo.com")
    except ValueError:
        return None
    if parts.scheme and parts.scheme not in LINK_SCHEMES:
        return None
    if host:
        if BAD_HOST.search(host):
            return None
    elif parts.scheme in NEEDS_HOST:
        return None
    return urlunsplit(parts._replace(path=quote(parts.path, safe=PATH_SAFE, errors="replace"),
                                     query=quote(parts.query, safe=QUERY_SAFE, errors="replace"),
                                     fragment=quote(parts.fragment, safe=QUERY_SAFE, errors="replace")))


def lparchive_fallback_urls(url: str) -> list[str]:
    """Other spellings of an lparchive.org URL worth trying, in order, after it answered 404.

    - The archiver saved some files under the literal name "...Pole&amp;Paddle.jpg"; the page's
      "&amp;" was decoded into "&" by the HTML parser, and the file exists only under the entity.
    - A smilie referenced relative to the update page ("Smilies/emot-x.gif" -> <LP>/Update 3/Smilies/)
      is in the LP's own Smilies/ folder when it has one, else in the site-wide one (437 of the
      failures in the archive-wide run).
    - A landing page links its pictures as "62-B04.png", but they live in the LP's Images/ folder
      (Ratchet-Clank-Into-the-Nexus: 50 pictures, 404 in a browser too).
    External URLs are never respelled: their '&' separate real query parameters."""
    if not is_lparchive_url(url):
        return []
    parsed = urlsplit(url)   # not urlparse: it would take "Pole&amp;Paddle.jpg" apart at the ';'
    paths = [parsed.path]
    if "&" in parsed.path and "&amp;" not in parsed.path:
        paths += [p.replace("&", "&amp;") for p in paths]
    smilie = SMILIE_PATH.match(parsed.path)
    if smilie:
        paths += [p for p in (f"/{smilie['lp']}/Smilies/{smilie['name']}", f"/Smilies/{smilie['name']}") if p not in paths]
    segments = parsed.path.split("/")
    if len(segments) == 3 and all(segments[1:]) and segments[1].lower() != "smilies":
        # "/<LP>/<file>": a picture next to the landing page
        paths += [p.replace(f"/{segments[1]}/", f"/{segments[1]}/Images/", 1) for p in paths]
    return [urlunsplit(parsed._replace(path=p)) for p in paths[1:]]


class Extractor:

    @staticmethod
    def fix_links(content, chapters, current_url: str):
        """Point every link either inside the book (chapters, landing page) or at an absolute URL,
        written as a valid URI.

        Links are resolved against the page they appear on, exactly like a browser would, so
        "../Update%2002/", "/Other-LP/" and "manual.pdf" all end up unambiguous, then percent-encoded
        (see to_uri): "avis/1 - Mine Level 1.avi" is a valid link in a browser, not in XHTML. A link
        that no encoding can make valid, or that no reader could follow (steam:, javascript:), is
        unwrapped: its text stays, a dead link is worse than none. Links to images that get embedded
        are rewritten in place once downloaded (see point_at_embedded)."""
        if not current_url.endswith("/"):
            current_url += "/"

        def key_of(url: str) -> str:
            # "Update 1/" and "Update%201/" are the same page (canonical_slug): compare encoded alike
            return canonical_slug(url if url.endswith("/") else url + "/")

        in_book = {key_of(c.original_href): c.new_href for c in chapters}
        if chapters:
            # original_href is root + "/" + slug, both slash-terminated: a link back to the landing page
            root = chapters[0].original_href[:-len(chapters[0].original_href_slug)]
            in_book[key_of(root)] = INTRO_FILE_NAME

        for link in content.find_all("a", href=True):
            href = link["href"].strip()
            if not href:
                continue
            if href.startswith("#"):
                link["href"] = to_uri(href) or href   # in-page anchor: encoded, never None
                continue
            full = Extractor.get_full_url(current_url, href)
            uri = to_uri(href if full is None else full)   # mailto: and the like are encoded, not resolved
            if uri is None:
                link.unwrap()
                continue
            target, fragment = urldefrag(uri)
            new_href = in_book.get(key_of(target))
            link["href"] = uri if new_href is None else new_href + (f"#{fragment}" if fragment else "")

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
            thread_url=to_uri(thread_link["href"]) if thread_link else None,
        )

    @staticmethod
    def all_chapters(root_url: str, p: BeautifulSoup) -> List[Chapters]:
        """The pages of the Let's Play, in reading order.

        A chapter is any link whose target is a directory right under the LP's own URL: "Update%2001/",
        "Introduction/", "Cast/", "Epilogue/"... whatever the author named it. Everything else is
        structurally not a chapter: files, anchors, other LPs, other sites, the LP root itself.
        Chapters are taken in document order, each one once: on the archive the landing page's
        lists and prose interleave freely (checked over every landing page), so document order is
        the reading order. One exception: a page mentioned in the prose above the table of contents
        ("read Matthew right after Genesis", "Character Recap, spoilers after chapter 82") and listed
        again in it takes its table-of-contents position. The table of contents is every
        <ul class="toc"> plus everything after a "Table of Contents" heading."""
        content = p.find("div", id="content")
        root = root_url[:-1] if root_url.endswith("/") else root_url
        base = root + "/"

        in_toc = {id(a) for toc in content.find_all("ul", class_="toc") for a in toc.find_all("a", href=True)}
        heading = next((h for h in content.find_all(["h1", "h2", "h3"])
                        if TOC_HEADING.search(h.get_text(" ", strip=True))), None)
        if heading is not None:
            in_toc.update(id(a) for a in heading.find_all_next("a", href=True))

        found: dict[str, tuple[int, str]] = {}      # slug -> (position, text) of the first mention
        placed: dict[str, tuple[int, str]] = {}     # slug -> (position, text) of the first mention in the toc
        for position, link in enumerate(content.find_all("a", href=True)):
            slug = Extractor.chapter_slug(base, link["href"])
            if slug is None:
                continue
            text = " ".join(link.get_text(" ").split())
            found.setdefault(slug, (position, text))
            if id(link) in in_toc:
                placed.setdefault(slug, (position, text))

        def order_key(slug: str) -> int:
            return placed.get(slug, found[slug])[0]

        chapters: list[Chapters] = []
        for slug in sorted(found, key=order_key):
            text = placed.get(slug, ("", ""))[1] or found[slug][1] or unquote(slug[:-1])
            chapters.append(Chapters(
                num=len(chapters),
                original_href=base + slug,
                txt=text,
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
    def get_image_url(root_url: str, src: str) -> str | None:
        """get_full_url for a picture. A reference to an lparchive.org file (relative, or absolute on
        that host) names an archived file, and the archiver kept names such as
        "37-attachment.php?postid=402560042." and "16-60954.jpg?1315256898.": '?' and '#' are
        file-name characters there, never a query or a fragment, so they are percent-encoded.
        Absolute URLs elsewhere keep their query string."""
        src = src.strip().replace("\\", "/")
        absolute = FIXABLE_SCHEME.match(src) or src.startswith("//") or HAS_SCHEME.match(src)
        if not absolute:
            src = src.replace("?", "%3F").replace("#", "%23")
        url = Extractor.get_full_url(root_url, src)
        if url is not None and absolute and is_lparchive_url(url):
            url = url.replace("?", "%3F").replace("#", "%23")
        return url

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
            if not is_image_link(href):
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
        images = (x for x in images if (x.get("src") or "").strip())   # <img src=""> would resolve to the page itself
        r = []

        # Add direct images
        for i, x in enumerate(images):
            r.append(Image(
                num=i,
                src=x['src'],
                tag=x,
                url=Extractor.get_image_url(root_url, x["src"]),
                root_url=root_url
            ))

        # Find image links - typically "Click here for full image" links
        image_links = content.find_all("a", href=lambda x: x and is_image_link(x))

        # Add linked images to be saved, but don't modify the HTML structure
        for i, link in enumerate(image_links, start=len(r)):
            r.append(Image(
                num=i,
                src=link['href'],
                tag=link,  # Use the link tag itself
                url=Extractor.get_image_url(root_url, link['href']),
                root_url=root_url
            ))

        return r

    @staticmethod
    def content_block(p: BeautifulSoup):
        """The post of an update page: <div id="content"> on the archive's templated pages.

        A few pages are served raw, as the author's source file instead of the templated page
        (Vanguard Bandits' contest entries, linked from the landing page's prose): no <div id="content">,
        the post sits between <!-- BEGIN_CONTENT --> and <!-- END_CONTENT --> comments. The post is moved
        into a fresh content div so the rest of the build does not need to know. A page with neither is
        not an update page (an error page or an index served with status 200)."""
        content = p.find("div", id="content")
        if content is not None:
            return content
        begin = p.find(string=lambda s: isinstance(s, Comment) and RAW_CONTENT_BEGIN in s)
        if begin is None:
            raise NotAnUpdatePageError("the page has no content block: not an update page")
        content = p.new_tag("div", id="content")
        begin.replace_with(content)
        node = content.next_sibling
        while node is not None:
            following = node.next_sibling
            if isinstance(node, Comment) and RAW_CONTENT_END in node:
                node.extract()
                break
            content.append(node.extract())
            node = following
        return content

    @staticmethod
    def get_update(chapters: List[Chapters], p: BeautifulSoup, chapter: Chapters) -> Update:
        content = Extractor.content_block(p)
        Extractor.inline_full_size_images(content)
        images = Extractor.all_images(content, chapter.original_href)
        Extractor.fix_links(content, chapters, chapter.original_href)
        return Update(content=content, images=images)


@dataclass
class Page:
    num: int
    chapter: EpubHtml
    images: List[IndexedEpubImage]
    # images the page links to (<a href>) rather than shows: each gets a small page of its own, since an
    # EPUB hyperlink may only lead to a content document, not straight to an image file
    linked: List[IndexedEpubImage] = field(default_factory=list)

@dataclass
class Fetched:
    """A successfully downloaded resource. Processing it happens outside the retry loop."""
    url: str
    body: bytes
    content_type: str | None
    encoding: str

    def text(self) -> str:
        return self.body.decode(self.encoding, errors="replace")


def request_headers() -> dict[str, str]:
    """Headers sent with every request. A descriptive User-Agent with a contact URL, as bot policies ask
    for: checked 2026-10-17, i.imgur.com answers 200 to it (429 to aiohttp's default UA, the reason the
    tool used to pose as curl), www.uesp.net answers 200 (403 to curl/8.1.1), and Wikimedia's policy
    (https://w.wiki/4wJS) 403s generic clients."""
    return {
        "user-agent": f"lparchive2epub/{tool_version()} (+{REPOSITORY_URL})",
        "accept": "*/*",
    }


REPOSITORY_URL = "https://github.com/Arwalk/lparchive2epub"

class FetchError(RuntimeError):
    """A resource could not be retrieved. `url` and, when known, the HTTP `status` are kept for reporting."""

    def __init__(self, message: str, url: str = "", status: int | None = None):
        super().__init__(message)
        self.url = url
        self.status = status


class NonRetryableError(FetchError):
    """A failure that will not go away by trying again (malformed URL, 404...)."""


class NotAnImageError(NonRetryableError):
    """The server answered 200 with something that is not a picture (an empty body, an HTML page)."""


class RetriesExhaustedError(FetchError):
    """The resource was still unavailable after all retries (network trouble, 5xx...)."""


@dataclass
class SkippedResource:
    page: str
    url: str
    reason: str
    cause: str = "other"   # one of FAILURE_CLASSES, see classify_failure


# Why a resource could not be retrieved, from the tool's point of view: everything but OTHER is beyond its
# reach, so the report only asks for a bug report when an OTHER failure is present. In report order.
DEAD_HOST = "dead-host"        # the external host does not resolve, refuses connections or never answers
GONE = "gone"                  # the external host answers 403/404/410 for the picture
ARCHIVE_COPY = "archive-copy"  # lparchive.org's own copy is empty or an HTML page saved under an image name
WEB_PAGE = "web-page"          # the external host answers an HTML page (hotlink protection, parking page)
TEMPORARY = "temporary"        # server errors, disconnections: not gone, just not now
OTHER = "other"                # a 404 on lparchive.org, a malformed URL, a crash: maybe the tool's doing
FAILURE_CLASSES = (DEAD_HOST, GONE, ARCHIVE_COPY, WEB_PAGE, TEMPORARY, OTHER)


def classify_failure(e: Exception, url: str | None) -> str:
    """Which of FAILURE_CLASSES the failure `e` of fetching `url` (the resolved URL, None when it could
    not be built) falls into."""
    on_archive = url is not None and is_lparchive_url(url)
    if isinstance(e, NotAnImageError):
        return ARCHIVE_COPY if on_archive else WEB_PAGE
    if isinstance(e, NonRetryableError):
        if e.status in (403, 404, 410) and not on_archive:
            return GONE
        return OTHER
    if isinstance(e, RetriesExhaustedError):
        if on_archive or e.status is not None:
            return TEMPORARY
        return DEAD_HOST
    return OTHER


# Exit codes of the command line tool. argparse uses 2 for usage errors.
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_NOT_FOUND = 3
EXIT_NETWORK = 4
EXIT_OUTPUT = 5
EXIT_CACHE = 6
EXIT_CHECK = 7
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


class CheckError(ExtractionError):
    """--check: epubcheck could not run or finish. The book was written all the same."""
    exit_code = EXIT_CHECK


class InvalidBookError(ExtractionError):
    """--check --strict: epubcheck found errors in the book, which was written all the same."""
    exit_code = EXIT_CHECK


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
                    session.get(url, headers=request_headers()) as r:
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
        except aiohttp.TooManyRedirects as e:
            # Renamed LPs (Homeworld-Cataclysm -> cataclysmberry) 301-loop forever between the old and the
            # new slug for pages that do not exist: trying again would loop again
            raise NonRetryableError(f"Failed to get resource {url}: too many redirects", url) from e
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

    spool_dir: when given, every stored image is written there as <hash>.<ext> right after download
    and only read back, one at a time, while the book is written (see SpooledImage). Without it the
    bytes stay in memory until the end, which for a large LP means several times the book's size.

    by_url: one future per resolved URL, so a URL referenced from many pages is downloaded once.
    The future is kept after a failure too: later references get the stored error immediately
    instead of re-running the download and its retries (a dead host would otherwise cost
    5 attempts and 30 s of backoff per reference).
    by_content: hash of the downloaded bytes -> future of the finished image, so a second URL serving
    the same bytes reuses the stored image (and skips the optional resize pass) instead of being
    processed and held twice. A future, because identical downloads usually land at the same time."""

    def __init__(self, spool_dir: str | None = None):
        self.by_url: dict[str, asyncio.Future] = {}
        self.by_content: dict[str, asyncio.Future] = {}
        self.spool_dir = spool_dir


def spool_write(spool_dir: str, name: str, content: bytes) -> str:
    """Write `content` as `name` in the spool, atomically: two downloads can reduce to the same bytes
    at the same time and both land on this name, so each writes its own temporary file first."""
    path = os.path.join(spool_dir, name)
    fd, partial = tempfile.mkstemp(dir=spool_dir, prefix=name + ".")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        os.replace(partial, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(partial)
        raise
    return path


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

    async def build(fetched: Fetched, reduced: tuple[bytes, str, str] | None) -> IndexedEpubImage:
        content = fetched.body
        media_type, extension = _detect_or_fail(fetched, img_url)
        if reduced is not None:
            content, media_type, extension = reduced
        if processing is not None:
            processing.record(len(fetched.body), len(content))
        img_hash = get_blake2b_hash(content)
        new_name = f"images/{img_hash}.{extension}"
        spool_dir = registry.spool_dir if registry is not None else None
        if spool_dir is None:
            data = FreedOnWriteImage(uid=f"i{img_hash}", file_name=new_name, media_type=media_type, content=content)
        else:
            try:
                # in a thread like the resize: a slow disk must not stall the downloads
                path = await asyncio.to_thread(spool_write, spool_dir, f"{img_hash}.{extension}", content)
            except OSError as e:
                raise OutputError(f"Cannot keep the images for the book in {spool_dir}: {e.strerror or e}") from e
            data = SpooledImage(f"i{img_hash}", new_name, media_type, path, len(content))
        return IndexedEpubImage(img_hash, img_url, new_name, data, len(content))  # old_name: the original URL

    try:
        fetched = await _fetch_image(session, img_url, fetch)
        raw_hash = get_blake2b_hash(fetched.body)
        if registry is not None and raw_hash in registry.by_content:
            # Same bytes already seen under another URL: share the stored image (it may still be
            # being processed), keeping this URL as old_name so the page's links to it get rewritten.
            known = await registry.by_content[raw_hash]
            if processing is not None:
                processing.record(len(fetched.body), known.size)
            res = IndexedEpubImage(known.hash, img_url, known.new_name, known.data, known.size)
        else:
            content_future = asyncio.get_running_loop().create_future() if registry is not None else None
            if content_future is not None:
                registry.by_content[raw_hash] = content_future
            try:
                reduced = None
                media_type, _ = _detect_or_fail(fetched, img_url)
                if processing is not None:
                    # CPU-bound (decode, resize, encode): off the event loop so downloads keep flowing
                    reduced = await asyncio.to_thread(reduce_image, fetched.body, media_type, processing)
                elif media_type in UNREADABLE_TYPES:
                    reduced = await asyncio.to_thread(convert_for_readers, fetched.body, media_type)
                res = await build(fetched, reduced)
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

async def _fetch_image(session: aiohttp.ClientSession, img_url: str, fetch: FetchSettings | None) -> Fetched:
    """Download the image, trying the other spellings lparchive may have saved it under after a 404.
    The error raised is the one for the URL the page gave, the fallbacks being an implementation detail."""
    try:
        return await fetch_with_retries(session, img_url, fetch=fetch)
    except NonRetryableError as first:
        if first.status != 404:
            raise
        for alternative in lparchive_fallback_urls(img_url):
            try:
                return await fetch_with_retries(session, alternative, fetch=fetch)
            except NonRetryableError:
                continue
        raise first


def _detect_or_fail(fetched: Fetched, img_url: str) -> tuple[str, str]:
    detected = detect_image_type(fetched.body, img_url, fetched.content_type)
    if detected is None:
        declared = (fetched.content_type or "unknown type").split(";")[0].strip()
        raise NotAnImageError(f"Not an image: the server answered with {declared} ({len(fetched.body)} bytes)",
                              img_url)
    return detected


def _describe(e: Exception) -> str:
    """Fetch errors are self-explanatory; anything else is unexpected, so say what kind of error it was."""
    if isinstance(e, FetchError):
        return str(e)
    return f"{type(e).__name__}: {e}" if str(e) else type(e).__name__


def _skipped(img: Image, e: Exception) -> SkippedResource:
    return SkippedResource(page=img.root_url, url=img.src, reason=_describe(e), cause=classify_failure(e, img.url))


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

    fatal = [res for res in results if isinstance(res, ExtractionError)]
    if fatal:
        raise fatal[0]   # not a per-image problem (spool disk full, broken cache...): stop the build
    images = []
    for img, res in zip(intro.images, results):
        if isinstance(res, Exception):
            if failures is not None:
                failures.append(_skipped(img, res))
            mark_unavailable(img)
        else:
            images.append(res)

    for image, result in zip(intro.images, results):
        if not isinstance(result, Exception):
            point_at_embedded(image, result)

    intro_chapter.content = str(intro.intro)

    return Page(0, intro_chapter, in_document_order(intro.images, images), linked_images(intro.images, images))


def point_at_embedded(image: Image, stored: IndexedEpubImage):
    """Make the tag the image came from show the stored copy: src for <img>; for <a>, href to the
    image's own page (see image_page_name)."""
    if image.tag.name == "a":
        image.tag["href"] = image_page_name(stored)
    else:
        image.tag["src"] = stored.new_name


def image_page_name(stored: IndexedEpubImage) -> str:
    return f"image_{stored.hash}.xhtml"


def make_image_page(stored: IndexedEpubImage, lang: str) -> EpubHtml:
    """The page a link to an image leads to: just the picture, fitted to the screen by the stylesheet.
    Outside the reading order (linear="no"): reached from the link, not by turning pages."""
    name = unquote(stored.old_name.rstrip("/").rsplit("/", 1)[-1]) or stored.old_name
    page = epub.EpubHtml(uid=f"image_{stored.hash}", title=name, file_name=image_page_name(stored), lang=lang)
    page.add_item(get_style_item())
    page.content = f'<p class="linked-image"><img src="{stored.new_name}" alt="{html.escape(name, quote=True)}"/></p>'
    page.is_linear = False
    return page


def linked_images(wanted: List[Image], fetched: List[IndexedEpubImage]) -> List[IndexedEpubImage]:
    """The downloaded images that `wanted` links to (<a>) rather than shows, in page order."""
    return in_document_order([image for image in wanted if image.tag.name == "a"], fetched)


def mark_unavailable(image: Image):
    """An <img> that could not be downloaded must not keep its page-relative src: inside the book that
    is a path to nothing (readers show a broken icon, epubcheck a missing resource). Replace it by a
    visible note linking to the original, so the reader knows what was there and can still try it
    online. Links (<a>) need nothing: fix_links already made them absolute."""
    tag = image.tag
    if tag.name != "img":
        return
    soup = tag
    while soup.parent is not None:
        soup = soup.parent
    name = image.src if image.url is None else (unquote(image.src.rstrip("/").rsplit("/", 1)[-1]) or image.src)
    alt = " ".join((tag.get("alt") or "").split())
    note = soup.new_tag("span", attrs={"class": "missing-image"})
    note.append(f"[image not available: {alt + ' - ' if alt else ''}")
    original = to_uri(image.url) if image.url else None   # the URL may hold spaces ("setz/Advent Rising/ethan6.jpg")
    if original:
        link = soup.new_tag("a", href=original)
        link.string = name
        note.append(link)
    else:
        note.append(name)
    note.append("]")
    tag.replace_with(note)


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
    fatal: list[Exception] = []

    async def worker():
        while True:
            try:
                img = await q.get()
                try:
                    res = await img_builder(img)
                    point_at_embedded(img, res)
                    images.append(res)
                except ExtractionError as e:
                    # Not a per-image problem (spool disk full, broken cache...): the build must stop,
                    # but keep draining the queue so q.join() below returns
                    fatal.append(e)
                except Exception as e:
                    # Missing images are not worth failing the whole book: keep the original link
                    if failures is not None:
                        failures.append(_skipped(img, e))
                    mark_unavailable(img)
                finally:
                    q.task_done()
            except asyncio.CancelledError:
                break

    workers = [asyncio.create_task(worker()) for _ in range(CONCURRENCY_LIMIT_IMAGES)]
    try:
        for image in data.images:
            await q.put(image)
        await q.join()
    finally:
        # also on cancellation (Ctrl-C), so no worker is left writing to a spool being removed
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
    if fatal:
        raise fatal[0]

    update_chapter.content = str(data.content)

    return Page(chapter.num, update_chapter, in_document_order(data.images, images), linked_images(data.images, images))


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


def add_page(known_images: set, book: EpubBook, toc: List, spine: List, page: Page, lang: str = "en",
             known_image_pages: set | None = None):
    """Add the page, its images and, once per image, the page each linked image gets (see Page.linked).
    `known_images` and `known_image_pages` hold the hashes already added, shared by every call."""
    book.add_item(page.chapter)
    for img in page.images:
        if img.hash not in known_images:
            book.add_item(img.data)
            known_images.add(img.hash)
    toc.append(epub.Link(page.chapter.file_name, page.chapter.title, page.chapter.id))
    spine.append(page.chapter)
    for img in page.linked:
        if known_image_pages is not None and img.hash not in known_image_pages:
            image_page = make_image_page(img, lang)
            book.add_item(image_page)
            spine.append(image_page)   # linear="no": reachable from the link, skipped when turning pages
            known_image_pages.add(img.hash)


async def build_single_page(session: aiohttp.ClientSession, intro: Intro, chapter: Chapters, all_chapters: List[Chapters], pbar,
                            registry: ImageRegistry | None = None, failures: list[SkippedResource] = None,
                            processing: ImageProcessing | None = None, fetch: FetchSettings | None = None) -> Page:
    if chapter.fetch_error is not None:
        raise chapter.fetch_error
    html = chapter.html if chapter.html is not None else (await fetch_with_retries(session, chapter.original_href, fetch=fetch)).text()
    chapter_bs = get_cleaned_html(html)
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


# Where the walk starts when the landing page lists no update at all
FIRST_UPDATE_GUESSES = ("Update%2001/", "Update%201/")
MAX_UNLISTED_WALK = 5000
# "<LP title> Part #647 - Robin C" -> "Robin C"
PART_TITLE = re.compile(r"\bPart #\d+\s*-\s*(.+)$")
NUMBERED_UPDATE = re.compile(r"^Update%20(\d+)/$")
# The heading above a landing page's list of updates, when the author put one
TOC_HEADING = re.compile(r"table of contents|^contents$|^index$|^updates$", re.IGNORECASE)


def canonical_slug(slug: str) -> str:
    """The same page spelled the way the landing page spells it: "Update%20647/" whether the link said
    "Update 647/" or "Update%20647/"."""
    return quote(unquote(slug), safe="/()!*'-_.~")


def slug_key(slug: str) -> str:
    """Identity of a page for "have we seen it": like canonical_slug, and "Update%2009/" and
    "Update%209/" count as the same page (the landing page pads the number, a next link may not).
    The site itself is strict about the padding in URLs, so this is only for comparisons."""
    slug = canonical_slug(slug)
    m = NUMBERED_UPDATE.match(slug)
    return f"Update%20{int(m.group(1))}/" if m else slug


async def prefetch_chapters(session: aiohttp.ClientSession, chapters: list[Chapters], fetch: FetchSettings | None,
                            pbar=None):
    """Download the listed pages (HTML only, a few tens of KB each) so that next links can be read
    before the book is built. A page that fails is left without HTML: building it fails later, with
    the usual report."""
    async def one(chapter: Chapters):
        try:
            chapter.html = (await fetch_with_retries(session, chapter.original_href, fetch=fetch)).text()
            chapter.next_slug = _next_slug(_lp_base(chapter), chapter.original_href, chapter.html)
        except FetchError as e:
            chapter.fetch_error = e   # reported when the book is built; not retried again here
        if pbar is not None:
            pbar.update(1)
    await asyncio.gather(*(one(c) for c in chapters if c.html is None))


def _lp_base(chapter: Chapters) -> str:
    return chapter.original_href[:-len(chapter.original_href_slug)]


async def discover_unlisted_chapters(session: aiohttp.ClientSession, url: str, chapters: list[Chapters],
                                     fetch: FetchSettings | None = None,
                                     failures: list[SkippedResource] | None = None) -> list[Chapters]:
    """Pages the landing page does not list.

    Some landing pages stop listing updates at some point (Fire Emblem Awakening lists 646 of its
    954 pages), list none at all (The Blackwell Legacy), or skip one (Resident Evil 1's page 59).
    Three ways to find them, in order: follow each listed page's "next" link while it leads to an
    unknown page; when nothing is listed, start from "Update 1"; and try the number after the
    highest "Update N" until the site answers 404. Found pages are placed right after the page that
    led to them, and keep their HTML so they are not downloaded twice."""
    base = (url[:-1] if url.endswith("/") else url) + "/"
    known = {slug_key(c.original_href_slug) for c in chapters}
    found: list[Chapters] = []

    async def page_html(href: str) -> str | None:
        try:
            html = (await fetch_with_retries(session, href, fetch=fetch)).text()
        except NonRetryableError:
            return None   # 404 and the like: the chain stops here
        except FetchError as e:
            if failures is not None:
                failures.append(SkippedResource(page=url, url=href, reason=f"while looking for unlisted updates: {e}",
                                                cause=classify_failure(e, href)))
            return None
        # A 200 that is not an update page (a redirect to the index, an error page) ends the chain too
        return html if 'id="content"' in html else None

    def add(slug: str, html: str, after: Chapters | None, step: int) -> Chapters:
        num = len(chapters) + len(found)
        order = after.order + step * 1e-4 if after is not None else float(num)
        chapter = _chapter_from_page(base, slug, html, num, order)
        known.add(slug_key(slug))
        found.append(chapter)
        return chapter

    async def walk(start: Chapters):
        current, step = start, 1
        while len(found) < MAX_UNLISTED_WALK:
            if current.fetch_error is not None:
                return
            if current.html is None:
                current.html = await page_html(current.original_href)
                if current.html is None:
                    return
                current.next_slug = _next_slug(base, current.original_href, current.html)
            nxt = current.next_slug
            if nxt is None or slug_key(nxt) in known:
                return
            html = await page_html(base + nxt)
            if html is None:
                return
            current, step = add(nxt, html, start, step), step + 1

    if not chapters:
        for guess in FIRST_UPDATE_GUESSES:
            html = await page_html(base + guess)
            if html is not None:
                await walk(add(guess, html, None, 0))
                break

    for chapter in sorted(chapters, key=lambda c: c.order):
        await walk(chapter)

    # Pages nothing links to: "Update N+1" after the highest number seen
    numbered = [(int(m.group(1)), len(m.group(1)), c) for c in [*chapters, *found]
                if (m := NUMBERED_UPDATE.match(canonical_slug(c.original_href_slug)))]
    if numbered:
        n, width, last = max(numbered, key=lambda x: x[0])
        step = 1
        while len(found) < MAX_UNLISTED_WALK:
            slug = f"Update%20{n + step:0{width}d}/"
            if slug_key(slug) in known:
                break
            html = await page_html(base + slug)
            if html is None:
                break
            probed = add(slug, html, last, step)
            await walk(probed)
            step += 1
    return found


def _next_slug(base: str, page_url: str, html: str) -> str | None:
    """The slug under the LP root `base` that the page's 'next' navigation link points at, in
    canonical spelling, if any. The link is relative to the page ("../Update 647/")."""
    soup = BeautifulSoup(html, "html.parser")
    link = soup.find("a", class_="next", href=True)
    if link is None:
        return None
    full = Extractor.get_full_url(page_url, link["href"])
    slug = Extractor.chapter_slug(base, full) if full else None
    return canonical_slug(slug) if slug else None


def _chapter_from_page(base: str, slug: str, html: str, num: int, order: float) -> Chapters:
    soup = BeautifulSoup(html, "html.parser")
    title = " ".join(soup.title.get_text(" ").split()) if soup.title else ""
    m = PART_TITLE.search(title)
    return Chapters(num=num, original_href=base + slug, txt=(m.group(1) if m else None) or unquote(slug[:-1]),
                    new_href=f"update_{num}.xhtml", original_href_slug=slug, html=html, order=order,
                    next_slug=_next_slug(base, base + slug, html))


async def lparchive2epub(url: str, file: str | None = None, root_session: aiohttp.ClientSession | None = None,
                         writer=log, strict: bool = False, allow_missing_updates: bool = False,
                         image_processing: ImageProcessing | None = None, cover: bytes | None | bool = True,
                         fetch: FetchSettings | None = None, spool_images: bool = True, check: bool = False) -> str:
    """Build the book for `url` at `file` (a path, a directory, or None for "<title>.epub" in the current
    directory). Returns the path of the written book. See `do` for the options."""
    try:
        url = normalize_lp_url(url)
    except ValueError as e:
        raise NotFoundError(str(e)) from e
    if root_session is None:
        root_session = aiohttp.ClientSession(timeout=CLIENT_TIMEOUT)
    async with root_session as session:
        return await do(url, file, session, writer, strict, allow_missing_updates, image_processing, cover, fetch,
                        spool_images, check)


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
# Where a Flash-era <object> names its movie: <param name="movie" value="http://www.youtube.com/v/...">
PLAYER_SOURCE_PARAMS = ("movie", "src", "url")


def player_source(element) -> str | None:
    """What a player was showing: its own src/data, else the movie <param> of a Flash <object>, else the
    src of a player or <source> nested inside it (2008-era YouTube embeds are an <object> wrapping an
    <embed>, the address only in those two places)."""
    source = element.get("src") or element.get("data")
    if source:
        return source
    for param in element.find_all("param"):
        if (param.get("name") or "").lower() in PLAYER_SOURCE_PARAMS and param.get("value"):
            return param["value"]
    for nested in element.find_all(EMBED_TAGS + ["source"]):
        source = nested.get("src") or nested.get("data")
        if source:
            return source
    return None
# HTML 4 presentational attributes that are invalid in XHTML 5 and that the stylesheet supersedes anyway.
ATTRIBUTES_TO_DROP = {"border", "align", "valign", "bgcolor", "background", "cellpadding", "cellspacing",
                      "hspace", "vspace", "nowrap", "target", "rel"}
# Column layout is presentational too: <table><col width="99%"><tr>..., the archive's own markup on
# 386 landing pages, is invalid XHTML 5 twice over (<col> belongs inside <colgroup>, width on neither:
# epubcheck RSC-005 in 388 books of the archive-wide run). The stylesheet lays the tables out.
TABLE_LAYOUT_TAGS = ["colgroup", "col"]
SPOILER_CLASS = "bbc-spoiler"
# HTML 4 inline elements that XHTML 5 dropped (epubcheck RSC-005 "element not allowed here"), and what
# shows the same thing today: <tt> is seen in 8 landing pages of the archive, the others are there for
# completeness. (<u> and <s> are still HTML.)
LEGACY_INLINE_TAGS = {
    "tt": ("code", None),
    "big": ("span", "font-size: larger;"),
    "strike": ("s", None),
    "acronym": ("abbr", None),
    "nobr": ("span", "white-space: nowrap;"),
    "blink": ("span", None),
    "marquee": ("span", None),
}
# What XHTML 5 allows directly inside a list: items, and the two tags TAGS_TO_DROP removes anyway.
LIST_TAGS = ["ul", "ol"]
LIST_CHILD_TAGS = ("li", "script", "template")
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
        if element.decomposed:
            continue   # nested in a player handled just before: one link per player, not one per level
        source = player_source(element)
        if source and HAS_SCHEME.match(source.strip()):
            link = soup.new_tag("a", href=source.strip())
            link.string = source.strip()
            paragraph = soup.new_tag("p")
            paragraph.append(f"[{element.name}: ")
            paragraph.append(link)
            paragraph.append("]")
            element.replace_with(paragraph)
        element.decompose()   # the replaced player too, so its nested players are seen as handled
    for param in soup.find_all("param"):
        param.decompose()
    for layout in soup.find_all(TABLE_LAYOUT_TAGS):
        layout.decompose()   # a <col> inside a <colgroup> goes with it; decomposing it again is harmless

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
    for legacy in soup.find_all(list(LEGACY_INLINE_TAGS)):
        legacy.name, style = LEGACY_INLINE_TAGS[legacy.name]
        if style:
            legacy["style"] = style

    nest_orphan_items(soup)
    nest_stray_list_content(soup)
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


def nest_orphan_items(soup: BeautifulSoup):
    """Forum authors write <li> with no list around it (the bullets show all the same), inside bold text, links
    and strike-throughs, and one after another without closing any. XHTML 5 wants every <li> directly in a
    <ul>/<ol> (epubcheck RSC-005 "element li not allowed here" in 70 books of the archive-wide run), and the
    unclosed ones do worse: html.parser nests each item in the one before, and the end tags bs4 then writes
    mislead ebooklib's lxml re-parse into closing the enclosing list early, dropping the items that follow
    into the page. This does to the tree what every browser does while parsing: an item that opens inside
    another closes it, so the inner one and whatever follows it move out; an inline wrapper around items goes
    inside each of them (<b><li>x</li></b> -> <li><b>x</b></li>), whatever else it held keeping a copy of its
    own in place, for nest_stray_list_content to sort out; and a run of items with no list at all gets a <ul>."""
    for item in soup.find_all("li"):
        while (parent := item.parent).name not in LIST_TAGS:
            if parent.name in INLINE_WRAPPERS:
                _turn_inside_out(soup, parent)
            elif parent.name == "li":
                parent.insert_after(item, *item.next_siblings)
            else:
                run, between, node = [item], [], item.next_sibling
                while node is not None:
                    if isinstance(node, Tag) and node.name == "li":
                        run += between + [node]   # the whitespace and comments between two items go in the list...
                        between = []
                    elif _is_blank(node):
                        between.append(node)      # ...those after the last one stay out
                    else:
                        break
                    node = node.next_sibling
                lst = soup.new_tag("ul")
                item.insert_before(lst)
                lst.extend(run)
                break


def _turn_inside_out(soup: BeautifulSoup, wrapper: Tag):
    """<b>intro<li>x</li><li>y</li></b> -> <b>intro</b><li><b>x</b></li><li><b>y</b></li>: the wrapper is unwrapped
    and copies of it go around every run of inline content it held, into its items and their nested lists at any
    depth (<b><ul><li>x<ul><li>y</li></ul></li></ul></b> -> <ul><li><b>x</b><ul><li><b>y</b></li></ul></li></ul>).
    A block of another kind is left as it is, without the wrapper. An id (or the HTML 4 name that becomes one)
    goes on the first copy."""
    attrs = dict(wrapper.attrs)

    def copy() -> Tag:
        nonlocal attrs
        tag = soup.new_tag(wrapper.name, attrs={name: list(value) if isinstance(value, list) else value
                                                for name, value in attrs.items()})
        attrs = {name: value for name, value in attrs.items() if name not in ("id", "name")}
        return tag

    def push_into(container: Tag):
        run = None
        for child in list(container.children):
            if isinstance(child, Tag) and (child.name == "li" or child.name in BLOCK_TAGS):
                if child.name == "li":
                    push_into(child)
                elif child.name in LIST_TAGS:
                    for item in child.find_all("li", recursive=False):
                        push_into(item)
                run = None
            elif run is None and _is_blank(child):
                continue   # whitespace and comments between items stay loose
            else:
                if run is None:
                    run = copy()
                    child.insert_before(run)
                run.append(child)

    push_into(wrapper)
    wrapper.unwrap()


def _is_blank(node) -> bool:
    """Whitespace-only text, or a comment (or CDATA, doctype...): nothing a reader sees."""
    return isinstance(node, NavigableString) and (isinstance(node, PreformattedString) or not node.strip())


def nest_stray_list_content(soup: BeautifulSoup):
    """Forum authors close </li> early or never open one, so a <ul> ends up holding <br>s, text, <b>s, <img>s,
    headings or a whole nested <ul> between its items or before the first one. XHTML 5 allows nothing but
    <li> there (epubcheck RSC-005 in 123 books of the archive-wide run) and both parsers leave it where it
    is. What follows an item becomes the item's continuation (a nested list inside the item before it is
    how nested lists are written: nothing moves on the page); what comes before the first item gets an
    unmarked item of its own, indented and without a bullet, which is how browsers show it. Runs after
    nest_orphan_items, so every item already sits directly in its list."""
    for lst in soup.find_all(LIST_TAGS):
        item, moving = None, False
        for child in list(lst.children):
            if isinstance(child, Tag):
                if child.name == "li":
                    item, moving = child, False
                    continue
                if child.name in LIST_CHILD_TAGS:
                    moving = False
                    continue
            elif isinstance(child, PreformattedString) or not str(child).strip():
                if moving:
                    item.append(child.extract())   # the space or comment between two moved words goes with them...
                continue                           # ...the whitespace and comments between items stay
            if item is None:
                item = soup.new_tag("li", style="list-style-type: none;")
                child.insert_before(item)
            item.append(child.extract())
            moving = True


def unnest_blocks_from_inline(soup: BeautifulSoup):
    """Forum posts contain things like <a href="full.png"><p><img src="thumb.png"/></p></a>: a paragraph
    inside a link. EPUB only allows inline content in a link, so epubcheck rejects the page.
    A link (or other inline wrapper) around exactly one block is turned inside out,
    <p><a href="full.png"><img/></a></p>, keeping both the paragraph and the link; around anything
    more complicated, the blocks are unwrapped so their content stays, inline, inside the link. Not a list,
    though, at any depth: unwrapping one orphans its items, and turning the wrapper inside out around it puts
    them under the wrapper (<ul><b><li>x</li></b></ul>: RSC-005 "element li not allowed here" in 4 landing
    pages of the archive); the wrapper goes inside each item instead, the way nest_orphan_items treats a
    wrapper that holds bare items."""
    for wrapper in soup.find_all(INLINE_WRAPPERS):
        blocks = [child for child in wrapper.children if getattr(child, "name", None) in BLOCK_TAGS]
        if not blocks:
            continue
        others = [child for child in wrapper.children
                  if child not in blocks and (getattr(child, "name", None) is not None or str(child).strip())]
        if len(blocks) == 1 and not others and not blocks[0].find(BLOCK_TAGS) and blocks[0].name not in LIST_TAGS:
            block = blocks[0]
            wrapper.replace_with(block)      # the block takes the wrapper's place...
            block.insert(0, wrapper.extract() if wrapper.parent else wrapper)
            for child in list(block.children)[1:]:
                wrapper.append(child.extract())   # ...and the wrapper moves inside it, around its content
        else:
            lists = wrapper.find_all(LIST_TAGS)
            for block in wrapper.find_all(BLOCK_TAGS):
                if block.name not in LIST_TAGS:
                    block.unwrap()
            if lists:
                _turn_inside_out(soup, wrapper)


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


def _hosts_summary(urls: list[str], top: int = 3) -> str:
    """"i.minus.com 177, tinypic.com 25 and 4 more hosts": where the failures are, most frequent first."""
    counts: dict[str, int] = {}
    for u in urls:
        host = urlsplit(u).hostname or u
        counts[host] = counts.get(host, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    text = ", ".join(f"{host} {n}" for host, n in ranked[:top])
    if len(ranked) > top:
        text += f" and {len(ranked) - top} more host{'s' if len(ranked) - top > 1 else ''}"
    return text


def _class_heading(cause: str, failures: list[SkippedResource], what: str) -> str:
    n = len(failures)
    hosts = _hosts_summary([f.url for f in failures])
    if cause == DEAD_HOST:
        return f"{n} image(s) on hosts that no longer exist or do not answer ({hosts}):"
    if cause == GONE:
        return f"{n} image(s) their host no longer serves (HTTP 403, 404 or 410; {hosts}):"
    if cause == ARCHIVE_COPY:
        return f"{n} image(s) whose copy on lparchive.org is empty, or is a web page saved under the image's name:"
    if cause == WEB_PAGE:
        return f"{n} image(s) whose host answers an empty file or a web page instead of the picture (hotlink protection, parking page; {hosts}):"
    if cause == TEMPORARY:
        return f"{n} {what} whose host had trouble (server error, disconnection); try again later:"
    return f"{n} {what} that failed for a reason this tool may be able to do something about:"


def format_failures_report(url: str, failures: list[SkippedResource], outcome: str, what: str = "resource(s)") -> str:
    """The list of what could not be retrieved, grouped by cause (FAILURE_CLASSES) with a plain heading
    for each. Dead hosts, pictures gone from their host and broken copies on the archive are beyond the
    tool, so the request for a bug report only appears when some failure may be its doing (OTHER)."""
    unique = list({(f.page, f.url, f.reason, f.cause): f for f in failures}.values())
    separator = "-" * 72
    lines = [
        separator,
        f"lparchive2epub: {len(unique)} {what} could not be retrieved while extracting {url}",
    ]
    for cause in FAILURE_CLASSES:
        group = [f for f in unique if f.cause == cause]
        if not group:
            continue
        lines.append(_class_heading(cause, group, what))
        for f in group:
            if f.page != f.url:
                lines.append(f"  - page:   {f.page}")
                lines.append(f"    url:    {f.url}")
            else:
                lines.append(f"  - url:    {f.url}")
            lines.append(f"    reason: {f.reason}")
    lines.append(separator)
    lines.append(outcome)
    if any(f.cause == OTHER for f in unique):
        lines.append(f"Please open an issue at {ISSUES_URL} and paste the output between the lines above,")
        lines.append("so these cases can be handled in a future release.")
    return "\n".join(lines)


async def do(url: str, file: str | None, session: aiohttp.ClientSession, writer, strict: bool = False,
             allow_missing_updates: bool = False, image_processing: ImageProcessing | None = None,
             cover: bytes | None | bool = True, fetch: FetchSettings | None = None, spool_images: bool = True,
             check: bool = False) -> str:
    """`file`: the book's path, a directory to put "<title>.epub" in, or None for the current directory.
    `cover`: True for a generated text cover, bytes for a custom image, None/False for no cover.
    `writer` gets the final report and summary; progress messages go through it too unless `fetch.quiet`.
    `spool_images`: keep the downloaded images in a temporary directory until the book is written
    (memory then stays flat whatever the size of the LP); False keeps them all in memory.
    `check`: validate the written book with epubcheck (see lparchive2epub.check) and report its findings;
    with `strict`, errors raise InvalidBookError (the book is kept).
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

    try:
        landing = get_cleaned_html(page_text)
        intro = Extractor.intro(url, landing)
    except ExtractionError:
        raise
    except Exception as e:   # noqa: BLE001 - a parser or sanitiser bug must come out as a report, not a traceback
        raise ExtractionError(f"Could not read the landing page {url}: {type(e).__name__}: {e}\n"
                              f"This is a bug. Please open an issue at {ISSUES_URL} with the URL you used.") from e

    book = epub.EpubBook()
    file = resolve_output_path(file, intro.title, url)
    check_output_path(file)
    # Images wait on disk until the book is written (see SpooledImage); the directory goes away with
    # the build, on success, failure and Ctrl-C alike (ignore_cleanup_errors: a write still in flight
    # in a thread may land a file after the removal started)
    spool = (tempfile.TemporaryDirectory(prefix="lparchive2epub-", ignore_cleanup_errors=True) if spool_images
             else contextlib.nullcontext(None))
    with spool as spool_dir:
        failures: list[SkippedResource] = []

        with fetch.progress_bar(total=len(intro.chapters), desc="Getting the updates' pages") as pbar:
            await prefetch_chapters(session, intro.chapters, fetch, pbar)
        say("looking for updates the landing page does not list")
        unlisted = await discover_unlisted_chapters(session, url, intro.chapters, fetch, failures)
        if unlisted:
            say(f"found {len(unlisted)} more update(s) by following the pages' next links")
            intro.chapters.extend(unlisted)

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
        image_registry = ImageRegistry(spool_dir)
        missing_updates: list[tuple[float, Chapters, Exception]] = []
        epub_intro = await build_intro(session, url, intro, image_registry, failures, image_processing, fetch)

        known_images: set[str] = set()
        known_image_pages: set[str] = set()

        add_page(known_images, book, toc, spine, epub_intro, intro.language, known_image_pages)

        # pages takes a vastly inequal times to get, so it's faster to gather and sort
        # gotta go fast, but also keep the page order.

        say("building chapters / updates")

        pages_indexed: list[tuple[float, Page]] = []

        with fetch.progress_bar(total=len(intro.chapters), desc="Gathering and building pages") as pbar:
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
            try:
                for chapter in intro.chapters:
                    await q.put((chapter.order, chapter))
                await q.join()
            finally:
                # also on cancellation (Ctrl-C), so the spool is not removed under a running worker
                for w in workers:
                    w.cancel()
                await asyncio.gather(*workers, return_exceptions=True)

        if missing_updates:
            missing_updates.sort(key=lambda x: x[0])
            fatal = [e for _, _, e in missing_updates if isinstance(e, ExtractionError)]
            if fatal:
                raise fatal[0]  # e.g. a broken --cache database: not a per-update problem, say so directly
            missing = [SkippedResource(page=c.original_href, url=c.original_href, reason=_describe(e),
                                       cause=classify_failure(e, c.original_href))
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

        for p in fetch.progress_bar(pages, desc="Adding pages to book"):
            add_page(known_images, book, toc, spine, p, intro.language, known_image_pages)

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
                "Missing images were replaced by a note linking to the original; "
                "missing updates (--allow-missing-updates) were replaced by a placeholder page linking to the original."))
        if check:
            from lparchive2epub.check import run_epubcheck, format_check_report   # optional dependency
            say("checking the book with epubcheck")
            result = await asyncio.to_thread(run_epubcheck, file)   # a JVM run: off the event loop
            if strict and result.errors:
                raise InvalidBookError(format_check_report(
                    file, result, f"The book was written at {file} all the same, but --strict was requested."))
            if result.findings:
                writer(format_check_report(
                    file, result,
                    f"The book was written at {file} all the same; "
                    + ("a strict reader may refuse it or show it wrong." if result.errors
                       else "warnings are advice, readers accept the book.")))
            else:
                say(f"epubcheck {result.version}: no problems found")
        return file
