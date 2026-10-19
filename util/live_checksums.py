"""Regenerate tests/resources/live_checksums.json: a checksum of the book the tool builds, today,
for a handful of Let's Plays fetched live from lparchive.org (see book_checksum: the content of the
book, the tool's version left out).

    uv run python util/live_checksums.py [--cache FILE]

`pytest --live` rebuilds the same Let's Plays and compares. A mismatch means the output changed:
either the tool did (intended -> rerun this script and commit the new file) or the site did (an image
host died, a page was edited). The script prints what changed so you can tell which.

ebooklib re-parses and re-serialises every page with lxml's bundled libxml2, so the file also records the
libxml2 version the checksums were made with: lxml's Linux wheels bundle 2.14, its Windows wheels 2.11
(6.1.3 included), and the test names both versions when they differ and the books do too. The one known
difference between them, CR LF kept as &#13; by 2.11, is normalised away by page_content() in lib.py.
"""
import argparse
import asyncio
import datetime
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

import aiohttp
from aiohttp_client_cache import CachedSession, SQLiteBackend
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lparchive2epub.cover import TITLE_PAGE_FILE_NAME  # noqa: E402
from lparchive2epub.lib import CLIENT_TIMEOUT, SOURCES_FILE_NAME, FetchSettings, check_cache_path, lparchive2epub  # noqa: E402

CHECKSUMS = Path(__file__).resolve().parent.parent / "tests" / "resources" / "live_checksums.json"

# Small and varied on purpose: a plain screenshot LP, a two-thread group LP with linked full-size
# pictures, an LP with Intro/Epilogue pages, one whose image host answers empty bodies (skipped
# images in the report), a video LP (no chapters at all), one whose landing page lists no update
# although six exist (found by following next links), a video LP whose landing page lays its
# tables out with <table><col width="99%"> (the archive's own markup on 386 pages, invalid XHTML 5
# that sanitize() drops: epubcheck RSC-005 in 388 books of the first archive-wide run), and a video
# LP linking archived files whose names hold spaces and brackets ("music/area 1 and earth [giga].mp3":
# percent-encoded by to_uri, epubcheck RSC-020 in 98 books of that run), and a video LP whose landing
# page fills its lists with headings, pictures, line breaks, bare text and 23 nested lists between the
# items (moved into the items by sanitize(): epubcheck RSC-005 in 123 books of that run), a video LP whose
# landing page nests unclosed items through a strike-through and wraps items in <b> (un-nested and turned
# inside out by sanitize(): RSC-005 "element li not allowed here" in 70 books of that run), a video LP
# whose landing page puts a whole list inside a <b> (the wrapper goes inside each item: same class), a video
# LP whose landing page opens <table> twice, so that the rest of the page, pictures, lists and three more
# tables, sits inside the outer table (the inner table closes it and whatever else a table holds goes before
# it: RSC-005 in 17 books of that run), and a video LP whose landing page never closes a <tr>, a <td> or the
# <a> in it, so that its rows nest thirteen deep through a link (un-nested, the link kept to its cell: same class),
# and a video LP of the Devolution 2007 megathread, whose landing page links its thread page-relatively
# ("/Devolution/": resolved against the LP's URL by Extractor.intro, epubcheck RSC-007 in 27 books of that run),
# a text LP whose updates quote the game in the forum's old [code] blocks, <pre>code:<hr>... (the <pre> is split
# around the rule by sanitize(): RSC-005 in 11 books of that run), and a video LP whose landing page mixes
# <img ...> and <img ... /> so that html.parser leaves an <img> open around headings and lists inside an unclosed
# <b> (the void element is emptied first: RSC-005 in that book), and a four-part video LP whose landing page gives
# an <img> an attribute named "p" (broken quoting; dropped with every attribute XHTML 5 does not allow: RSC-005
# in 14 books of that run), and a 40-part video LP whose update 32 links a video around a picture the archive
# keeps an empty copy of (the note that replaces the picture names it without a link of its own: a link may not
# hold a link, RSC-005 in 2 books of that run), and a video LP with no update pages whose landing page holds four
# smilies with an empty src (dropped by sanitize(): XHTML 5 wants a src at least one character long, RSC-005 in
# 3 books of that run), and a video LP whose first update links a picture on a host that answers a web page
# behind a byte-order mark (not an image whatever the URL says, now that detect_image_type trusts neither the
# Content-Type nor the URL: epubcheck OPF-029 and PKG-021 in 5 books of that run; Saints-Row-2, whose picture
# lparchive keeps as a gzip stream, is a 203 MB book with a flaky image host, too big for this list).
LETS_PLAYS = [
    "X-COM-Terror-from-the-Deep",
    "Dwarf-Fortress-Boatmurdered",
    "Arcanum",
    "Dwarf-Fortress-Headshoots",
    "007-Nightfire",
    "The-Blackwell-Legacy",
    "007-Everything-or-Nothing",
    "Rez",
    "Quake",
    "Prince-of-Persia-2008-(by-nine-gear-crow)",
    "Doom-WADs",
    "Legend-of-Zelda-Oracle-Series",
    "I-Wanna-Be-The-Guy",
    "Axelay",
    "Laura-Bow-The-Colonels-Bequest",
    "Bureaucracy",
    "Ratchet-Clank-Future-A-Crack-In-Time",
    "Bionic-Commando",
    "La-Pucelle-Tactics",
    "Super-Ghouls-n-Ghosts-(by-Captain_duck)",
    "SpaceChem-2012-Tournament",
]


# The title page says "Converted by lparchive2epub 2.0.0." and sources.json carries the version too: the
# parts of a book that change with a release and not with the tool's behaviour.
COLOPHON_VERSION = re.compile(rb"Converted by lparchive2epub [^<]*\.</p>")
SOURCES_VERSION = re.compile(rb'"version": "[^"]*"')


def libxml2_version() -> str:
    """The libxml2 lxml was built with (the one it bundles in a wheel), as "2.14.6"."""
    return ".".join(str(part) for part in etree.LIBXML_COMPILED_VERSION)


def book_checksum(path: str) -> str:
    """sha256 of the book's content: the name and bytes of every file in the EPUB, in order, with the
    tool's version taken out of the title page. A release must not flip every recorded checksum."""
    digest = hashlib.sha256()
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            data = z.read(info.filename)
            if info.filename == f"EPUB/{TITLE_PAGE_FILE_NAME}":
                data = COLOPHON_VERSION.sub(b"Converted by lparchive2epub.</p>", data)
            elif info.filename == f"EPUB/{SOURCES_FILE_NAME}":
                data = SOURCES_VERSION.sub(b'"version": ""', data)
            digest.update(info.filename.encode("utf-8"))
            digest.update(b"\0")
            digest.update(data)
    return digest.hexdigest()


async def build_checksum(slug: str, cache_file: str | None) -> str:
    if cache_file:
        session = CachedSession(cache=SQLiteBackend(cache_file, expire_after=-1, fast_save=True, autoclose=True),
                                timeout=CLIENT_TIMEOUT)
    else:
        session = aiohttp.ClientSession(timeout=CLIENT_TIMEOUT)
    with tempfile.TemporaryDirectory() as d:
        written = await lparchive2epub(f"https://lparchive.org/{slug}", f"{d}/book.epub", session,
                                       writer=lambda *_: None, fetch=FetchSettings(quiet=True))
        return book_checksum(written)


async def main_async(cache_file: str | None):
    previous = json.loads(CHECKSUMS.read_text())["lets_plays"] if CHECKSUMS.exists() else {}
    current = {}
    for slug in LETS_PLAYS:
        current[slug] = await build_checksum(slug, cache_file)
        state = "unchanged" if previous.get(slug) == current[slug] else "CHANGED" if slug in previous else "new"
        print(f"{slug}: {current[slug][:16]} ({state})", file=sys.stderr)
    CHECKSUMS.write_text(json.dumps({"generated": datetime.date.today().isoformat(), "libxml2": libxml2_version(),
                                     "lets_plays": current}, indent=1) + "\n")
    print(f"written {CHECKSUMS}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Regenerate the live checksums used by `pytest --live`")
    parser.add_argument("--cache", metavar="FILE", help="SQLite cache for the downloads")
    args = parser.parse_args()
    asyncio.run(main_async(check_cache_path(args.cache) if args.cache else None))


if __name__ == "__main__":
    main()
