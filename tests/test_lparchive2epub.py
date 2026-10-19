import asyncio
import datetime
import gzip
import hashlib
import io
import json
import os
import random
import re
import sys
import zipfile
from urllib.parse import unquote

import aiohttp
from tqdm.asyncio import tqdm
from lparchive2epub.lib import Extractor, Chapters, BeautifulSoup, normalize_url, build_update, Update, Intro, format_failures_report, ISSUES_URL, do, StrictModeError, MissingUpdatesError, ExtractionError, OutputError, check_output_path, detect_image_type, NotFoundError, NetworkError, RetriesExhaustedError, NotALetsPlayError, normalize_lp_url, fetch_with_retries, Fetched, get_cleaned_html, compose_description, parse_lp_date, reduce_image, ImageProcessing, ImageRegistry, FetchSettings, check_cache_path, discover_unlisted_chapters, canonical_slug, safe_file_name, resolve_output_path, resolve_cache_path, CacheError, EXIT_CACHE, EXIT_NOT_FOUND, EXIT_NETWORK, EXIT_OUTPUT, EXIT_INTERRUPTED
import lparchive2epub.lib as lib
from lparchive2epub import main as cli
from importlib.resources import files
import tests.resources as resources
import pytest
import tempfile
from aiohttp_client_cache import CachedSession, SQLiteBackend


def load_html(path: str):
    p = files(resources).joinpath(path)
    # noinspection PyTypeChecker
    with open(p, mode="rb") as f:
        return f.read()


re1 = load_html("Resident Evil 1.html")
headshoots = load_html("Dwarf Fortress - Headshoots.html")
xcom = load_html("X-COM_ Terror from the Deep.html")


def test_extractor_intro():
    b = BeautifulSoup(re1, "html.parser")
    intro = Extractor.intro("https://lparchive.org/Resident-Evil-1", b)
    assert intro.title == "Resident Evil 1"
    assert intro.author == "The Dark Id"
    assert intro.language == "en"

    b = BeautifulSoup(headshoots, "html.parser")
    intro = Extractor.intro("https://lparchive.org/Dwarf-Fortress-Headshoots", b)
    assert intro.title == "Dwarf Fortress - Headshoots"
    assert intro.author == "Various"
    assert intro.language == "en"

    b = BeautifulSoup(xcom, "html.parser")
    intro = Extractor.intro("https://lparchive.org/X-COM-Terror-from-the-Deep", b)
    assert intro.title == "X-COM: Terror from the Deep"
    assert intro.author == "GuavaMoment"
    assert intro.language == "en"


def test_extractor_chapters():
    b = BeautifulSoup(re1, "html.parser")
    chapters = Extractor.all_chapters("https://lparchive.org/Resident-Evil-1", b)
    assert len(chapters) == 58
    assert chapters[0] == Chapters(num=0, 
                                   new_href="update_0.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%201/',
                                   txt='Foreword:',
                                   original_href_slug="Update%201/")
    assert chapters[1] == Chapters(num=1, 
                                   new_href="update_1.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%202/',
                                   txt="Episode I: C'mon C'mon",
                                   original_href_slug="Update%202/")
    assert chapters[2] == Chapters(num=2, 
                                   new_href="update_2.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%203/',
                                   txt='Episode II: Break on Through to the Other Side',
                                   original_href_slug="Update%203/")
    assert chapters[3] == Chapters(num=3, 
                                   new_href="update_3.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%204/',
                                   txt='Episode III: Monster Mash',
                                   original_href_slug="Update%204/")
    assert chapters[4] == Chapters(num=4, 
                                   new_href="update_4.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%205/',
                                   txt='Episode IV: Walk This Way',
                                   original_href_slug="Update%205/")
    assert chapters[5] == Chapters(num=5, 
                                   new_href="update_5.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%206/',
                                   txt='Episode V: With a Little Help from My Friends',
                                   original_href_slug="Update%206/")
    assert chapters[6] == Chapters(num=6, 
                                   new_href="update_6.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%207/',
                                   txt="Episode VI: You've Got A Friend In Me",
                                   original_href_slug="Update%207/")
    assert chapters[7] == Chapters(num=7, 
                                   new_href="update_7.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%208/',
                                   txt='Episode VII: The Devil Went Down to Georgia',
                                   original_href_slug="Update%208/")
    assert chapters[8] == Chapters(num=8, 
                                   new_href="update_8.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%209/',
                                   txt='Episode VIII: Hurt',
                                   original_href_slug="Update%209/")
    assert chapters[9] == Chapters(num=9, 
                                   new_href="update_9.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%2010/',
                                   txt='Episode IX: The Best Things in Life are Free',
                                   original_href_slug="Update%2010/")
    assert chapters[10] == Chapters(num=10, 
                                    new_href="update_10.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2011/',
                                    txt='Episode X: Another One Bites the Dust',
                                    original_href_slug="Update%2011/")
    assert chapters[11] == Chapters(num=11, 
                                    new_href="update_11.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2012/',
                                    txt='Episode XI: Moonlight Sonata',
                                    original_href_slug="Update%2012/")
    assert chapters[12] == Chapters(num=12, 
                                    new_href="update_12.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2013/',
                                    txt="Episode XII: I've Gotta Get a Message to You",
                                    original_href_slug="Update%2013/")
    assert chapters[13] == Chapters(num=13, 
                                    new_href="update_13.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2014/',
                                    txt='Episode XIII: Communication Breakdown',
                                    original_href_slug="Update%2014/")
    assert chapters[14] == Chapters(num=14, 
                                    new_href="update_14.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2015/',
                                    txt='Episode XIV: Thriller',
                                    original_href_slug="Update%2015/")
    assert chapters[15] == Chapters(num=15, 
                                    new_href="update_15.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2016/',
                                    txt='Tangent: Adagio',
                                    original_href_slug="Update%2016/")
    assert chapters[16] == Chapters(num=16, 
                                    new_href="update_16.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2017/',
                                    txt='Tangent: Baroque',
                                    original_href_slug="Update%2017/")
    assert chapters[17] == Chapters(num=17, 
                                    new_href="update_17.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2018/',
                                    txt='Tangent: Cadenza',
                                    original_href_slug="Update%2018/")
    assert chapters[18] == Chapters(num=18, 
                                    new_href="update_18.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2019/',
                                    txt='Tangent: Dissonance',
                                    original_href_slug="Update%2019/")
    assert chapters[19] == Chapters(num=19, 
                                    new_href="update_19.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2020/',
                                    txt='Tangent: Dissonance B',
                                    original_href_slug="Update%2020/")
    assert chapters[20] == Chapters(num=20, 
                                    new_href="update_20.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2021/',
                                    txt='Tangent: Dissonance C',
                                    original_href_slug="Update%2021/")
    assert chapters[21] == Chapters(num=21, 
                                    new_href="update_21.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2022/',
                                    txt='Tangent: Dissonance D',
                                    original_href_slug="Update%2022/")
    assert chapters[22] == Chapters(num=22, 
                                    new_href="update_22.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2023/',
                                    txt='Tangent: Dissonance E',
                                    original_href_slug="Update%2023/")
    assert chapters[23] == Chapters(num=23, 
                                    new_href="update_23.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2024/',
                                    txt='Tangent: Etude',
                                    original_href_slug="Update%2024/")
    assert chapters[24] == Chapters(num=24, 
                                    new_href="update_24.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2025/',
                                    txt='Tangent: Etude B',
                                    original_href_slug="Update%2025/")
    assert chapters[25] == Chapters(num=25, 
                                    new_href="update_25.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2026/',
                                    txt='Tangent: Etude C',
                                    original_href_slug="Update%2026/")
    assert chapters[26] == Chapters(num=26, 
                                    new_href="update_26.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2027/',
                                    txt='Episode XV: Mexican Radio',
                                    original_href_slug="Update%2027/")
    assert chapters[27] == Chapters(num=27, 
                                    new_href="update_27.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2028/',
                                    txt='Episode XVI: Wishing You Were Here',
                                    original_href_slug="Update%2028/")
    assert chapters[28] == Chapters(num=28, 
                                    new_href="update_28.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2029/',
                                    txt='Chapter 29',
                                    original_href_slug="Update%2029/")
    assert chapters[29] == Chapters(num=29, 
                                    new_href="update_29.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2030/',
                                    txt='Episode XVII: Funky Town',
                                    original_href_slug="Update%2030/")
    assert chapters[30] == Chapters(num=30, 
                                    new_href="update_30.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2031/',
                                    txt='Episode XVIII: Beneath the Sea',
                                    original_href_slug="Update%2031/")
    assert chapters[31] == Chapters(num=31, 
                                    new_href="update_31.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2032/',
                                    txt='Episode XIX: Somewhere Over the Rainbow',
                                    original_href_slug="Update%2032/")
    assert chapters[32] == Chapters(num=32, 
                                    new_href="update_32.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2033/',
                                    txt='Episode XX: Another Brick in the Wall',
                                    original_href_slug="Update%2033/")
    assert chapters[33] == Chapters(num=33, 
                                    new_href="update_33.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2034/',
                                    txt='Episode XXI: Black Dog',
                                    original_href_slug="Update%2034/")
    assert chapters[34] == Chapters(num=34, 
                                    new_href="update_34.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2035/',
                                    txt='Episode XXII: Gotta Get Away',
                                    original_href_slug="Update%2035/")
    assert chapters[35] == Chapters(num=35, 
                                    new_href="update_35.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2036/',
                                    txt='Episode XXIII: Dazed and Confused',
                                    original_href_slug="Update%2036/")
    assert chapters[36] == Chapters(num=36, 
                                    new_href="update_36.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2037/',
                                    txt="Episode XXIV: It Won't Be Long",
                                    original_href_slug="Update%2037/")
    assert chapters[37] == Chapters(num=37, 
                                    new_href="update_37.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2038/',
                                    txt='Episode XV: Comfortably Numb',
                                    original_href_slug="Update%2038/")
    assert chapters[38] == Chapters(num=38, 
                                    new_href="update_38.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2039/',
                                    txt="Episode XXVI: Blowin' in the Wind",
                                    original_href_slug="Update%2039/")
    assert chapters[39] == Chapters(num=39, 
                                    new_href="update_39.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2040/',
                                    txt="Episode XXVII: Don't Stop 'Til You Get Enough",
                                    original_href_slug="Update%2040/")
    assert chapters[40] == Chapters(num=40, 
                                    new_href="update_40.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2041/',
                                    txt='Episode XXVIII: Already Gone',
                                    original_href_slug="Update%2041/")
    assert chapters[41] == Chapters(num=41, 
                                    new_href="update_41.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2042/',
                                    txt='Episode XXIX: Losing my Religion',
                                    original_href_slug="Update%2042/")
    assert chapters[42] == Chapters(num=42, 
                                    new_href="update_42.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2043/',
                                    txt='Episode XXX: Everybody Hurts',
                                    original_href_slug="Update%2043/")
    assert chapters[43] == Chapters(num=43, 
                                    new_href="update_43.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2044/',
                                    txt="Bonus Episode: Wesker's Report II (Part I)",
                                    original_href_slug="Update%2044/")
    assert chapters[44] == Chapters(num=44, 
                                    new_href="update_44.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2045/',
                                    txt='Bonus Episode: Wesker\'s Report II - "Alexia 1"',
                                    original_href_slug="Update%2045/")
    assert chapters[45] == Chapters(num=45, 
                                    new_href="update_45.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2046/',
                                    txt='Bonus Episode: Wesker\'s Report II - "Alexia 2"',
                                    original_href_slug="Update%2046/")
    assert chapters[46] == Chapters(num=46, 
                                    new_href="update_46.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2047/',
                                    txt='Bonus Episode: Wesker\'s Report II - "Nemesis"',
                                    original_href_slug="Update%2047/")
    assert chapters[47] == Chapters(num=47, 
                                    new_href="update_47.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2048/',
                                    txt='Bonus Episode: Wesker\'s Report II - "G-Virus"',
                                    original_href_slug="Update%2048/")
    assert chapters[48] == Chapters(num=48, 
                                    new_href="update_48.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2049/',
                                    txt='Episode XXXI: Weird Science',
                                    original_href_slug="Update%2049/")
    assert chapters[49] == Chapters(num=49, 
                                    new_href="update_49.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2050/',
                                    txt='Episode XXXII: Video Killed the Radio Star',
                                    original_href_slug="Update%2050/")
    assert chapters[50] == Chapters(num=50, 
                                    new_href="update_50.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2051/',
                                    txt='Episode XXXIII: Walking on Sunshine',
                                    original_href_slug="Update%2051/")
    assert chapters[51] == Chapters(num=51, 
                                    new_href="update_51.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2052/',
                                    txt="XXXIV: Singin' in the Rain",
                                    original_href_slug="Update%2052/")
    assert chapters[52] == Chapters(num=52, 
                                    new_href="update_52.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2053/',
                                    txt="Episode XXXV: Knockin' on Heaven's Door",
                                    original_href_slug="Update%2053/")
    assert chapters[53] == Chapters(num=53, 
                                    new_href="update_53.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2054/',
                                    txt='Episode XXXVI: Helter Skelter',
                                    original_href_slug="Update%2054/")
    assert chapters[54] == Chapters(num=54, 
                                    new_href="update_54.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2055/',
                                    txt='Episode XXXVII: Stairway to Heaven',
                                    original_href_slug="Update%2055/")
    assert chapters[55] == Chapters(num=55, 
                                    new_href="update_55.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2056/',
                                    txt='Episode XXXVIII: We Will Rock You',
                                    original_href_slug="Update%2056/")
    assert chapters[56] == Chapters(num=56, 
                                    new_href="update_56.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2057/',
                                    txt="Episode XXXIX: Don't Fear the Reaper",
                                    original_href_slug="Update%2057/")
    assert chapters[57] == Chapters(num=57, 
                                    new_href="update_57.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2058/',
                                    txt='Episode XL: Paint it, Black',
                                    original_href_slug="Update%2058/")

    b = BeautifulSoup(headshoots, "html.parser")
    chapters = Extractor.all_chapters("whatever", b)
    assert len(chapters) == 90

    b = BeautifulSoup(xcom, "html.parser")
    chapters = Extractor.all_chapters("whatever", b)
    assert len(chapters) == 18


def test_all_images():
    b = BeautifulSoup(re1, "html.parser")
    content = b.find("div", id="content")
    images = Extractor.all_images(content, "https://lparchive.org/Resident-Evil-1/")
    assert len(images) == 0

    b = BeautifulSoup(headshoots, "html.parser")
    content = b.find("div", id="content")
    images = Extractor.all_images(content, "https://lparchive.org/Dwarf-Fortress-Headshoots/")
    assert len(images) == 16

    b = BeautifulSoup(xcom, "html.parser")
    content = b.find("div", id="content")
    images = Extractor.all_images(content, "https://lparchive.org/X-COM-Terror-from-the-Deep/")
    assert len(images) == 1

LIVE_CHECKSUMS = os.path.join(os.path.dirname(__file__), "resources", "live_checksums.json")


def _live_checksums() -> dict:
    with open(LIVE_CHECKSUMS, encoding="utf-8") as f:
        return json.load(f)["lets_plays"]


def _live_checksums_libxml2() -> str:
    with open(LIVE_CHECKSUMS, encoding="utf-8") as f:
        return json.load(f)["libxml2"]


def test_live_checksum_ignores_the_tool_version_but_nothing_else():
    from util.live_checksums import book_checksum

    def book(version: str, text: str = "hello") -> str:
        path = tempfile.mktemp(suffix=".epub")
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("mimetype", "application/epub+zip")
            z.writestr("EPUB/title_page.xhtml", f'<p class="colophon">Converted by lparchive2epub {version}.</p>')
            z.writestr("EPUB/update_0.xhtml", text)
        return path

    assert book_checksum(book("1.4.2")) == book_checksum(book("2.0.0")) == book_checksum(book("dev"))
    assert book_checksum(book("2.0.0")) != book_checksum(book("2.0.0", "other text"))

    def book_with_sources(version: str, lp: str = "https://lparchive.org/X") -> str:
        path = book("2.0.0")
        with zipfile.ZipFile(path, "a") as z:
            z.writestr("EPUB/sources.json", json.dumps({"lets_play": lp, "tool": {"name": "lparchive2epub", "version": version}}))
        return path

    assert book_checksum(book_with_sources("1.4.2")) == book_checksum(book_with_sources("dev"))
    assert book_checksum(book_with_sources("2.0.0")) != book_checksum(book_with_sources("2.0.0", "https://lparchive.org/Y"))
    assert book_checksum(book_with_sources("2.0.0")) != book_checksum(book("2.0.0"))


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.parametrize("slug", sorted(_live_checksums()))
async def test_live_build_matches_recorded_checksum(slug):
    """Builds the Let's Play from lparchive.org and compares the book byte for byte with the last
    recorded build. A mismatch means the output changed: the tool (then regenerate with
    util/live_checksums.py) or the site (a dead image host, an edited page)."""
    from util.live_checksums import build_checksum, libxml2_version
    expected = _live_checksums()[slug]
    actual = await asyncio.wait_for(build_checksum(slug, None), timeout=600)
    # ebooklib re-serialises every page with lxml's bundled libxml2 (2.14 in the Linux wheels, 2.11 in the Windows
    # ones): page_content() irons out the known difference, so the books must match either way, but a new one
    # should be told apart from a change of the tool or the site at first sight
    recorded, running = _live_checksums_libxml2(), libxml2_version()
    parser = (f" The checksums were recorded with libxml2 {recorded} and this lxml bundles {running}: a difference "
              f"in how the pages are re-serialised is the first suspect." if running != recorded else "")
    assert actual == expected, (f"{slug}: the book built today differs from the recorded one. If the tool changed on "
                                f"purpose, run `uv run python util/live_checksums.py` and commit the new checksums."
                                + parser)


@pytest.mark.parametrize(("url", "expected"), [
    ("hhttp://lpix.org/2495492/purski.png", "http://lpix.org/2495492/purski.png"),
    ("ttp://lpix.org/582487/mons051.png", "http://lpix.org/582487/mons051.png"),   # a missing h (Legend-of-Mana)
    ("ttps://example.com/a.png", "https://example.com/a.png"),
    ("htttps://example.com/a.png", "https://example.com/a.png"),
    ("HTTP://example.com/a.png", "http://example.com/a.png"),
    ("http:/example.com/a.png", "http://example.com/a.png"),
    ("http//example.com/a.png", "http://example.com/a.png"),
    ("http:///example.com/a.png", "http://example.com/a.png"),
    ("//example.com/a.png", "https://example.com/a.png"),
    ("  http://example.com/a.png ", "http://example.com/a.png"),
    ("https://example.com/a.png", "https://example.com/a.png"),
    ("ftp://example.com/a.png", None),
    ("javascript:void(0)", None),
    ("hhttp://", None),
])
def test_normalize_url(url, expected):
    assert normalize_url(url) == expected


def test_get_full_url():
    root = "https://lparchive.org/Shin-Megami-Tensei-Devil-Summoner/Update%2011/"
    assert Extractor.get_full_url(root, "hhttp://lpix.org/2495492/purski.png") == "http://lpix.org/2495492/purski.png"
    assert Extractor.get_full_url(root, "1.png") == f"{root}1.png"
    assert Extractor.get_full_url(root, "../1.png") == "https://lparchive.org/Shin-Megami-Tensei-Devil-Summoner/1.png"
    assert Extractor.get_full_url(root, "mailto:someone@example.com") is None
    assert Extractor.get_full_url(root, "javascript:void(0)") is None
    # site-absolute paths are relative to the host, not to the page
    assert Extractor.get_full_url(root, "/site_images/x.png") == "https://lparchive.org/site_images/x.png"
    # forum smilies resolve like anything else; where they really live is a download-time concern
    # (see test_lparchive_fallback_urls)
    assert Extractor.get_full_url(root, "../Smilies/emot-smith.gif") == "https://lparchive.org/Shin-Megami-Tensei-Devil-Summoner/Smilies/emot-smith.gif"
    assert Extractor.get_full_url(root, "Smilies/emot-smith.gif") == f"{root}Smilies/emot-smith.gif"
    assert Extractor.get_full_url(root, "/Smilies/emot-smith.gif") == "https://lparchive.org/Smilies/emot-smith.gif"
    assert Extractor.get_full_url(root, "//lpix.org/a.png") == "https://lpix.org/a.png"
    assert Extractor.get_full_url(root, " img\\sub\\a.png ") == f"{root}img/sub/a.png"
    assert Extractor.get_full_url(root, "https://lpix.org/a.png") == "https://lpix.org/a.png"
    # the landing page URL has no trailing slash
    assert Extractor.get_full_url("https://lparchive.org/Some-LP", "Update%2001/") == "https://lparchive.org/Some-LP/Update%2001/"


@pytest.mark.parametrize(("href", "expected"), [
    # spaces, brackets, quotes and the like: what browsers quietly repair and XHTML forbids (RSC-020)
    ("https://lparchive.org/Blackthorne/avis/1 - Mine Level 1 - It's Show Time!.avi",
     "https://lparchive.org/Blackthorne/avis/1%20-%20Mine%20Level%201%20-%20It's%20Show%20Time!.avi"),
    ("mailto:missing-img@lparchive.org?subject=Advent Rising - (01.jpg)",
     "mailto:missing-img@lparchive.org?subject=Advent%20Rising%20-%20(01.jpg)"),
    ("http://www.youtube.com/watch?v=TxJ7ivNRTxo[/url", "http://www.youtube.com/watch?v=TxJ7ivNRTxo%5B/url"),
    ('http://example.com/a"b<c>d|e^f{g}h`i\\j', "http://example.com/a%22b%3Cc%3Ed%7Ce%5Ef%7Bg%7Dh%60i%5Cj"),
    ("http://azuredreamsshrine.netfirms.com/English/items2.html#General Store",
     "http://azuredreamsshrine.netfirms.com/English/items2.html#General%20Store"),
    ("https://example.com/a#b#c", "https://example.com/a#b%23c"),
    ("https://example.com/café", "https://example.com/caf%C3%A9"),
    # existing escapes are kept (not doubled), a bare % is encoded
    ("https://example.com/Rock%20The%20Planet%20%234/100%.html", "https://example.com/Rock%20The%20Planet%20%234/100%25.html"),
    ("https://lpix.org/3158584/May%92n - Obelisk.mp3", "https://lpix.org/3158584/May%92n%20-%20Obelisk.mp3"),
    # RFC 3986 lets these be: untouched
    ("https://example.com/a(b)*c,d;e=f+g$h&i@j~k!?x=1&y=2", "https://example.com/a(b)*c,d;e=f+g$h&i@j~k!?x=1&y=2"),
    ("http://user:pw@my_host.example.com:8080/x", "http://user:pw@my_host.example.com:8080/x"),
    ("http://[::1]/x", "http://[::1]/x"),
    ("http://müller.de/x", "http://müller.de/x"),
    ("irc://irc.synirc.net/lp", "irc://irc.synirc.net/lp"),
    ("ftp://example.com/x", "ftp://example.com/x"),
    # relative references and in-page anchors are encoded alike
    ("Update 01/", "Update%2001/"),
    ("#General Store", "#General%20Store"),
    ("  //lpix.org/a b.png  ", "//lpix.org/a%20b.png"),
    # no encoding can save these: a host with a space or an empty label, a port that is no number
    ("http:// http://video.google.com/videoplay?docid=1", None),
    ("http://www...", None),
    ("http://http:ustwo.com", None),
    ("http://exa mple.com/", None),
    ("http:///x", None),
    ("http://[abc/x", None),
    # no reader can follow these: unregistered (HTM-025), data (RSC-029), scripts (dropped from the book)
    ("steam://run/341190/", None),
    ("data:text/plain,hello", None),
    ("javascript:void(0)", None),
])
def test_to_uri(href, expected):
    assert lib.to_uri(href) == expected


@pytest.mark.asyncio
async def test_build_update_skips_unreachable_images():
    root = "https://lparchive.org/Some-LP/Update%201/"
    html = ('<div id="content"><a href="ftp://example.com/broken.png">full image</a>'
            '<img src="hhttp://"/></div>')
    content = BeautifulSoup(html, "html.parser").find("div", id="content")
    images = Extractor.all_images(content, root)
    chapter = Chapters(num=1, original_href=root, txt="Update 1", new_href="update_1.xhtml",
                       original_href_slug="Update%201/")
    intro = Intro(title="t", language="en", author="a", intro=None, images=[], chapters=[chapter], published_on="")
    failures = []

    async with aiohttp.ClientSession() as session:
        page = await asyncio.wait_for(
            build_update(session, chapter, Update(content=content, images=images), intro, ImageRegistry(), failures),
            timeout=5)

    assert page.images == []
    assert sorted(f.url for f in failures) == ["ftp://example.com/broken.png", "hhttp://"]
    assert all(f.page == root for f in failures)
    assert 'href="ftp://example.com/broken.png"' in page.chapter.content

    report = format_failures_report("https://lparchive.org/Some-LP", failures + failures, "outcome")
    assert report.count("url:    ftp://example.com/broken.png") == 1
    assert ISSUES_URL in report


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake png payload"
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"fake jpeg payload"
GIF_BYTES = b"GIF89a" + b"fake gif payload"
WEBP_BYTES = b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"fake webp payload"


class _FakeResponse:
    def __init__(self, status: int, body: bytes, content_type: str | None = None):
        self.status = status
        self._body = body
        self.content = self
        self.headers = {"Content-Type": content_type} if content_type else {}

    async def text(self):
        return self._body.decode("utf-8", errors="replace")

    async def read(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    """Serves the X-COM landing page fixture; chapters are tiny pages, one of them answering 404."""

    def __init__(self, failing_slug: str, responses: dict | None = None):
        self.failing_slug = failing_slug
        self.requested = []
        self.responses = responses or {}  # url -> _FakeResponse, checked first

    def get(self, url, **kwargs):
        self.requested.append(url)
        if url in self.responses:
            return self.responses[url]
        if url.rstrip("/") == "https://lparchive.org/X-COM-Terror-from-the-Deep":
            return _FakeResponse(200, xcom)
        if self.failing_slug in url:
            return _FakeResponse(404, b"not here")
        if "Update" in url:
            number = re.search(r"Update%20(\d+)/", url)
            # like the site: only X-COM's 18 updates exist by default, anything else is 404 unless given
            if not url.startswith("https://lparchive.org/X-COM-Terror-from-the-Deep/") or (number and int(number.group(1)) > 18):
                return _FakeResponse(404, b"no such update")
            return _FakeResponse(200, f'<div id="content"><h3>{unquote(url)}</h3>some text</div>'.encode())
        return _FakeResponse(200, PNG_BYTES)

    async def close(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()


def _chapter_files(epub_path: str) -> list[str]:
    with zipfile.ZipFile(epub_path) as z:
        return sorted(n for n in z.namelist() if re.fullmatch(r"EPUB/update_\d+\.xhtml", n))


@pytest.mark.asyncio
async def test_unretrievable_chapter_fails_loudly_by_default():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    failing = "Update%2005/"
    session = _FakeSession(failing)
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        with pytest.raises(MissingUpdatesError) as exc_info:
            await asyncio.wait_for(do(url, out, session, lambda *_: None), timeout=30)
        assert not os.path.exists(out)

    report = str(exc_info.value)
    assert isinstance(exc_info.value, ExtractionError)
    assert "1 update(s) could not be retrieved" in report
    assert f"url:    {url}/{failing}" in report
    assert "status code: 404" in report
    assert "No book was written" in report
    assert "--allow-missing-updates" in report
    assert "1 update(s) that failed for a reason this tool may be able to do something about:" in report
    assert ISSUES_URL in report   # a listed update is on the archive: a 404 there is unexpected, unlike a picture's


@pytest.mark.asyncio
async def test_unretrievable_chapter_gets_placeholder_when_allowed():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    failing = "Update%2005/"
    session = _FakeSession(failing)
    messages = []
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, messages.append, allow_missing_updates=True), timeout=30)

        # all 18 chapters are present, including a placeholder for the failed one
        assert len(_chapter_files(out)) == 18
        with zipfile.ZipFile(out) as z:
            placeholder = z.read("EPUB/update_4.xhtml").decode()
            good = z.read("EPUB/update_3.xhtml").decode()
    assert f"{url}/{failing}" in placeholder
    assert "could not be retrieved" in placeholder
    assert "could not be retrieved" not in good

    report = "\n".join(messages)
    assert "1 resource(s) could not be retrieved" in report
    assert f"url:    {url}/{failing}" in report
    assert "status code: 404" in report
    assert "placeholder" in report


@pytest.mark.asyncio
async def test_unretrievable_chapter_fails_in_strict_mode_even_when_allowed():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    session = _FakeSession("Update%2005/")
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        with pytest.raises(StrictModeError) as exc_info:
            await asyncio.wait_for(do(url, out, session, lambda *_: None, strict=True, allow_missing_updates=True),
                                   timeout=30)
        assert not os.path.exists(out)
    assert f"{url}/Update%2005/" in str(exc_info.value)


def test_fix_links_rewrites_chapter_links_without_trailing_slash():
    root = "https://lparchive.org/Some-LP"
    chapters = [
        Chapters(num=0, original_href=f"{root}/Update%2001/", txt="Update 1", new_href="update_0.xhtml",
                 original_href_slug="Update%2001/"),
        Chapters(num=1, original_href=f"{root}/Update%2002/", txt="Update 2", new_href="update_1.xhtml",
                 original_href_slug="Update%2002/"),
    ]
    html = ('<div id="content">'
            '<a href="../Update%2001/">plain</a>'
            '<a href="../Update%2001/#part2">anchor</a>'
            '<a href="../Update%2002">no trailing slash</a>'
            '<a href="../Update%2002/map.png">asset in a chapter</a>'
            '<a href="manual.pdf">local asset</a>'
            '<a href="../">back to the landing page</a>'
            '<a href="#top">in-page anchor</a>'
            '<a href="/Other-LP/">another LP, site-absolute</a>'
            '<a href="/site_images/x.png">site-absolute asset</a>'
            '<a href="//lpix.org/a.png">scheme-relative</a>'
            '<a href="http://example.com/Update%2001/">unrelated host, left alone</a>'
            '<a href="mailto:someone@example.com">mail</a>'
            '<a href="hhttp://lpix.org/b.png">repairable typo</a>'
            '</div>')
    content = BeautifulSoup(html, "html.parser").find("div", id="content")

    Extractor.fix_links(content, chapters, f"{root}/Update%2003/")

    hrefs = [a["href"] for a in content.find_all("a")]
    assert hrefs == [
        "update_0.xhtml",
        "update_0.xhtml#part2",
        "update_1.xhtml",
        f"{root}/Update%2002/map.png",
        f"{root}/Update%2003/manual.pdf",
        "introduction.xhtml",
        "#top",
        "https://lparchive.org/Other-LP/",
        "https://lparchive.org/site_images/x.png",
        "https://lpix.org/a.png",
        "http://example.com/Update%2001/",
        "mailto:someone@example.com",
        "http://lpix.org/b.png",
    ]
    assert not any(".xhtml/" in h for h in hrefs)


def test_fix_links_on_the_landing_page_resolves_against_the_lp_root():
    root = "https://lparchive.org/Some-LP"
    chapters = [Chapters(num=0, original_href=f"{root}/Update%2001/", txt="Update 1", new_href="update_0.xhtml",
                         original_href_slug="Update%2001/")]
    html = ('<div id="content"><a href="Update%2001/">toc</a><a href="/X-COM-Interceptor/">other lp</a>'
            '<a href="Images/map.png">asset</a><a href="Update%20(1)/">regex chars are harmless</a></div>')
    content = BeautifulSoup(html, "html.parser").find("div", id="content")
    Extractor.fix_links(content, chapters, root)
    assert [a["href"] for a in content.find_all("a")] == [
        "update_0.xhtml", "https://lparchive.org/X-COM-Interceptor/", f"{root}/Images/map.png",
        f"{root}/Update%20(1)/"]


def test_fix_links_writes_valid_uris_and_unwraps_links_nothing_can_follow():
    """Hand-written hrefs carry spaces, brackets and quotes (epubcheck RSC-020 in 98 books of the
    archive-wide run): resolved, then encoded. A link that no encoding can save, or that no reader could
    follow, is unwrapped: the text stays, the dead link goes."""
    root = "https://lparchive.org/Blackthorne"
    chapters = [Chapters(num=0, original_href=f"{root}/Update%2001/", txt="Update 1", new_href="update_0.xhtml",
                         original_href_slug="Update%2001/"),
                Chapters(num=1, original_href=f"{root}/Update%2002/", txt="Update 2", new_href="update_1.xhtml",
                         original_href_slug="Update%2002/")]
    html = ('<div id="content">'
            '<a href="avis/1 - Mine Level 1 - It\'s Show Time!.avi">archived video</a>'
            '<a href="mailto:missing-img@lparchive.org?subject=Advent Rising - (01.jpg)">missing picture</a>'
            '<a href="http://www.miketyndall.com/setz/Advent Rising/comics/Rock The Planet %234.zip">external</a>'
            '<a href="http://www.youtube.com/watch?v=TxJ7ivNRTxo[/url">forum markup glued on</a>'
            '<a href="http://azuredreamsshrine.netfirms.com/English/items2.html#General Store">fragment</a>'
            '<a href="#General Store">in-page anchor</a>'
            '<a href="Update 02/#part 2">chapter link with raw spaces</a>'
            '<a href="http:// http://video.google.com/videoplay?docid=1">garbage</a>'
            '<a href="http://http:ustwo.com">more <b>garbage</b></a>'
            '<a href="steam://run/341190/">on Steam</a>'
            '<a href="javascript:void(0)">spoiler toggle</a>'
            '</div>')
    content = BeautifulSoup(html, "html.parser").find("div", id="content")

    Extractor.fix_links(content, chapters, root)

    assert [a["href"] for a in content.find_all("a")] == [
        f"{root}/avis/1%20-%20Mine%20Level%201%20-%20It's%20Show%20Time!.avi",
        "mailto:missing-img@lparchive.org?subject=Advent%20Rising%20-%20(01.jpg)",
        "http://www.miketyndall.com/setz/Advent%20Rising/comics/Rock%20The%20Planet%20%234.zip",
        "http://www.youtube.com/watch?v=TxJ7ivNRTxo%5B/url",
        "http://azuredreamsshrine.netfirms.com/English/items2.html#General%20Store",
        "#General%20Store",
        "update_1.xhtml#part%202",
    ]
    assert str(content).endswith('</a>garbagemore <b>garbage</b>on Steamspoiler toggle</div>')


@pytest.mark.asyncio
async def test_intro_toc_links_point_at_existing_chapter_files():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    session = _FakeSession(failing_slug="never-matches")
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, lambda *_: None), timeout=30)
        with zipfile.ZipFile(out) as z:
            files = set(z.namelist())
            intro = z.read("EPUB/introduction.xhtml").decode()
    toc_links = re.findall(r'href="(update_[^"]+)"', intro)
    assert len(toc_links) == 18
    assert all(f"EPUB/{h}" in files for h in toc_links), toc_links
    # links to other LPs leave the book as absolute URLs instead of dangling container paths
    assert 'href="https://lparchive.org/X-COM-Interceptor/"' in intro
    assert 'href="/X-COM-Interceptor/"' not in intro


@pytest.mark.asyncio
async def test_missing_output_directory_fails_before_any_download():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    session = _FakeSession(failing_slug="never-matches")
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/does-not-exist/book.epub"
        with pytest.raises(OutputError) as exc_info:
            await do(url, out, session, lambda *_: None)
        assert not os.path.exists(out)
    assert session.requested == []
    assert isinstance(exc_info.value, ExtractionError)
    assert out in str(exc_info.value)
    assert "does not exist" in str(exc_info.value)


def test_check_output_path_rejects_directory_and_unwritable_locations():
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(OutputError, match="is a directory"):
            check_output_path(d)
        check_output_path(f"{d}/fine.epub")  # does not raise
        existing = f"{d}/existing.epub"
        open(existing, "wb").close()
        check_output_path(existing)  # overwriting an existing writable file is fine
        if os.name != "nt" and os.geteuid() != 0:
            os.chmod(d, 0o500)
            try:
                with pytest.raises(OutputError, match="not writable"):
                    check_output_path(f"{d}/nope.epub")
            finally:
                os.chmod(d, 0o700)


@pytest.mark.asyncio
async def test_write_failure_is_reported_and_leaves_no_partial_file(monkeypatch):
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    session = _FakeSession(failing_slug="never-matches")
    import lparchive2epub.lib as lib

    def exploding_write(name, book, options=None):
        with open(name, "wb") as f:
            f.write(b"half a zip")
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(lib.epub, "write_epub", exploding_write)
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        with pytest.raises(OutputError, match="No space left on device"):
            await do(url, out, session, lambda *_: None)
        assert os.listdir(d) == []


@pytest.mark.parametrize(("content", "url", "content_type", "expected"), [
    (PNG_BYTES, "http://x/a.JPG", None, ("image/png", "png")),           # bytes win over a wrong extension
    (JPEG_BYTES, "http://x/a.jpeg", None, ("image/jpeg", "jpg")),
    (JPEG_BYTES, "http://x/a.PNG?size=large", None, ("image/jpeg", "jpg")),
    (GIF_BYTES, "http://x/a.GIF", None, ("image/gif", "gif")),
    (WEBP_BYTES, "http://x/a", None, ("image/webp", "webp")),
    (b"BMfake", "http://x/a.bmp", None, ("image/bmp", "bmp")),
    (b"MM\x00*fake", "http://x/1-map14.tiff.", "application/octet-stream", ("image/tiff", "tiff")),
    (b"II*\x00fake", "http://x/a", None, ("image/tiff", "tiff")),
    (b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', "http://x/a", None, ("image/svg+xml", "svg")),
    (b"\x00\x01unknown", "http://x/a.webp", None, None),                     # the URL does not make it an image...
    (b"\x00\x01unknown", "http://x/a", "image/gif; charset=binary", None),    # ...nor does the header
    (b"<!DOCTYPE html><html><body>Not found</body></html>", "http://x/a.png", "text/html", None),
    # what lparchive.org serves under a picture's name, with the picture's Content-Type (9vb.13): the author's
    # site's page behind a byte-order mark (Fatestay-night), an XHTML 404 page (Ogre-Battle-64), an ad frame
    # (Final-Fantasy-IV-The-After-Years), a host's page behind a byte-order mark (SpaceChem-2012-Tournament)
    (b"\xef\xbb\xbf<!DOCTYPE html PUBLIC \"-//W3C//DTD XHTML 1.0 Transitional//EN\">\r\n<html>", "http://x/47-cas03b.png", "image/png", None),
    (b'<?xml version="1.0" encoding="iso-8859-1"?>\n<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"', "http://x/snap0005.jpg", "image/jpeg", None),
    (b"<!--\n\n624 total\n468 ad\n-->\n\n<html>", "http://x/55-AY055.jpg", "image/jpeg", None),
    (b"\xef\xbb\xbf<!DOCTYPE html>", "http://img.example/cumulative-quantity.png", "text/html", None),
    (b"<?php echo 'no'; ?>", "http://x/a.gif", "image/gif", None),
    (b"\xef\xbb\xbf<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>", "http://x/a.png", "image/png", ("image/svg+xml", "svg")),
    (b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg"></svg>', "http://x/a", None, ("image/svg+xml", "svg")),
    (b"\x00\x01unknown", "http://x/a.php", "text/plain", None),
    (b"", "http://x/a.gif", "image/gif", None),                           # empty body, whatever the header says
])
def test_detect_image_type(content, url, content_type, expected):
    assert detect_image_type(content, url, content_type) == expected


def test_all_images_finds_linked_images_regardless_of_extension_case_or_query():
    html = ('<div id="content">'
            '<a href="full.JPG">1</a> <a href="full.jpeg">2</a> <a href="full.webp?dl=1">3</a> '
            '<a href="full.png#top">4</a> <a href="notes.txt">no</a> <a href="Update%2002/">no</a>'
            '</div>')
    content = BeautifulSoup(html, "html.parser").find("div", id="content")
    images = Extractor.all_images(content, "https://lparchive.org/Some-LP/Update%2001/")
    assert [i.src for i in images] == ["full.JPG", "full.jpeg", "full.webp?dl=1", "full.png#top"]


def test_wiki_file_pages_and_empty_src_are_not_image_references():
    html = ('<div id="content">'
            '<a href="https://en.wikipedia.org/wiki/File:San_Francisco_in_ruin_edit2.jpg">1</a> '
            '<a href="https://en.wikipedia.org/wiki/Redingote#/media/File:Dandies_of_1831.jpg">2</a> '
            '<a href="http://hard-light.net/wiki/index.php/File:Moloch480x340.jpg">3</a> '
            '<a href="http://terraria.gamepedia.com/File:Shotgun.png">4</a> '
            '<a href="https://bulbapedia.bulbagarden.net/wiki/file:VSHoney.png">5</a> '
            '<a href="https://en.wikipedia.org/wiki/Image:Old_namespace.gif">6</a> '
            '<a href="article.html#figure.png">7</a> '
            '<img src=""/> <img src="  "/> <img/> '
            '<a href="https://upload.wikimedia.org/wikipedia/commons/0/03/Maev.jpg">real</a> '
            '<a href="https://en.wikipedia.org/wiki/File:Thumb.jpg"><img src="thumb.png"/></a>'
            '</div>')
    content = BeautifulSoup(html, "html.parser").find("div", id="content")
    assert Extractor.inline_full_size_images(content) == 0        # a File: page is not the full-size picture
    images = Extractor.all_images(content, "https://lparchive.org/Some-LP/Update%2001/")
    assert [i.src for i in images] == ["thumb.png", "https://upload.wikimedia.org/wikipedia/commons/0/03/Maev.jpg"]
    assert all(i.url for i in images)
    assert len(content.find_all("a")) == 9                        # the links stay plain links


@pytest.mark.asyncio
async def test_wiki_file_links_are_kept_and_not_fetched_and_empty_src_is_not_reported():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    page = f"{url}/Update%2001/"
    wiki = "https://en.wikipedia.org/wiki/File:San_Francisco_in_ruin_edit2.jpg"
    session = _FakeSession("never-matches", responses={wiki: _FakeResponse(403, b"forbidden"),
                                                       f"{page}shot.png": _FakeResponse(200, PNG_BYTES)})
    session.responses[page] = _FakeResponse(
        200, f'<div id="content"><a href="{wiki}">the picture</a> <img src=""/> <img src="shot.png"/></div>'.encode())
    messages = []
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, messages.append), timeout=30)
        with zipfile.ZipFile(out) as z:
            chapter = z.read("EPUB/update_0.xhtml").decode()

    assert wiki not in session.requested
    assert session.requested.count(page) == 1                     # not downloaded a second time as an image
    assert f'<a href="{wiki}">the picture</a>' in chapter
    assert "missing-image" not in chapter
    report = "\n".join(messages)
    assert "could not be retrieved" not in report and "url:    \n" not in report


@pytest.mark.asyncio
async def test_image_media_type_comes_from_content_and_non_images_are_skipped():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    jpeg_as_png_url = f"{url}/Update%2001/shot.PNG"
    dead_host_url = "http://img.example/dead.jpg"
    page_as_png_url = f"{url}/Update%2001/47-cas03b.png"
    page_as_png = b"\xef\xbb\xbf<!DOCTYPE html PUBLIC>\r\n<html><body>Videos</body></html>"
    session = _FakeSession("never-matches", responses={
        jpeg_as_png_url: _FakeResponse(200, JPEG_BYTES, "image/png"),   # lying extension and header
        dead_host_url: _FakeResponse(200, b"<!DOCTYPE html><html><body>gone</body></html>", "text/html"),
        # an HTML page saved under the picture's name, served with the picture's type (Fatestay-night update 46)
        page_as_png_url: _FakeResponse(200, page_as_png, "image/png"),
    })
    # one chapter embeds the three images
    session.responses[f"{url}/Update%2001/"] = _FakeResponse(
        200, f'<div id="content"><img src="shot.PNG"/><img src="{dead_host_url}"/><img src="47-cas03b.png"/></div>'.encode())
    messages = []
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, messages.append), timeout=30)
        with zipfile.ZipFile(out) as z:
            opf = z.read("EPUB/content.opf").decode()
            chapter = z.read("EPUB/update_0.xhtml").decode()
            image_files = [n for n in z.namelist() if n.startswith("EPUB/images/")]

    jpeg_items = re.findall(r'<item href="(images/[^"]+)" id="[^"]+" media-type="image/jpeg"/>', opf)
    assert len(jpeg_items) == 1 and jpeg_items[0].endswith(".jpg")
    assert f'src="{jpeg_items[0]}"' in chapter
    assert all(n.endswith((".png", ".jpg")) for n in image_files)
    assert "image/PNG" not in opf and "image/peg" not in opf
    # the HTML page served instead of an image is not embedded: a note links to it, and it is reported
    assert dead_host_url in chapter
    assert f'<span class="missing-image">[image not available: <a href="{dead_host_url}">dead.jpg</a>]</span>' in chapter
    assert not any("html" in n for n in image_files)
    assert not any(hashlib.blake2b(page_as_png).hexdigest() in n for n in image_files)   # the page served as image/png is not in the book either
    assert f'<span class="missing-image">[image not available: <a href="{page_as_png_url}">47-cas03b.png</a>]</span>' in chapter
    report = "\n".join(messages)
    assert dead_host_url in report and "Not an image" in report and "text/html" in report
    assert "the server answered image/png, but the body is a web page (" in report
    assert "1 image(s) whose copy on lparchive.org is empty, or is a web page saved under the image's name:" in report
    assert "Please open an issue" not in report   # nothing the tool can do about either


@pytest.mark.asyncio
async def test_a_picture_stored_gzip_compressed_is_unwrapped():
    """Saints-Row-2's fan art: lparchive keeps a gzip stream of the PNG under the .png name and serves it
    as image/png with no Content-Encoding, so aiohttp hands the gzip bytes over. The picture is inside:
    the book gets the PNG, named after the PNG's bytes. A gzip of something else, or a broken gzip, is
    not an image, as before."""
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    picture = _make_image("PNG", (8, 6))
    session = _FakeSession("never-matches", responses={
        f"{url}/Update%2001/12-fanart.png": _FakeResponse(200, gzip.compress(picture), "image/png"),
        f"{url}/Update%2001/page.png": _FakeResponse(200, gzip.compress(b"<!DOCTYPE html><html></html>"), "image/png"),
        f"{url}/Update%2001/broken.png": _FakeResponse(200, gzip.compress(picture)[:40], "image/png"),
    })
    session.responses[f"{url}/Update%2001/"] = _FakeResponse(
        200, b'<div id="content"><img src="12-fanart.png"/><img src="page.png"/><img src="broken.png"/></div>')
    messages = []
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, messages.append), timeout=30)
        with zipfile.ZipFile(out) as z:
            chapter = z.read("EPUB/update_0.xhtml").decode()
            name = f"EPUB/images/{hashlib.blake2b(picture).hexdigest()}.png"
            assert name in z.namelist(), z.namelist()
            assert z.read(name) == picture
            opf = z.read("EPUB/content.opf").decode()
    assert f'<item href="{name.removeprefix("EPUB/")}" id="i{hashlib.blake2b(picture).hexdigest()}" media-type="image/png"/>' in opf
    assert f'<span class="missing-image">[image not available: <a href="{url}/Update%2001/page.png">page.png</a>]</span>' in chapter
    assert f'<span class="missing-image">[image not available: <a href="{url}/Update%2001/broken.png">broken.png</a>]</span>' in chapter
    report = "\n".join(messages)
    assert "page.png" in report and "but the body is a web page" in report
    assert "broken.png" in report and "the server answered with image/png (40 bytes)" in report


def test_get_image_url_keeps_question_mark_and_hash_in_archived_file_names():
    root = "https://lparchive.org/Advance-Wars/Update%2001/"
    assert Extractor.get_image_url(root, "37-attachment.php?postid=402560042.") == f"{root}37-attachment.php%3Fpostid=402560042."
    assert Extractor.get_image_url(root, "16-60954.jpg?1315256898") == f"{root}16-60954.jpg%3F1315256898"
    assert Extractor.get_image_url(root, "../Images/pic.png#frag") == "https://lparchive.org/Advance-Wars/Images/pic.png%23frag"
    assert Extractor.get_image_url(root, "21-Ashley?.png") == f"{root}21-Ashley%3F.png"
    # the same for absolute references to lparchive.org (the landing page writes them that way)
    assert Extractor.get_image_url("https://lparchive.org/Dead-Rising-2", "https://lparchive.org/Dead-Rising-2/Images/13-Kkg3RCP.jpg?1.") == "https://lparchive.org/Dead-Rising-2/Images/13-Kkg3RCP.jpg%3F1."
    assert Extractor.get_image_url(root, "hhttp://lparchive.org/Some-LP/Images/a.png?1") == "http://lparchive.org/Some-LP/Images/a.png%3F1"
    # absolute URLs elsewhere keep a real query string and fragment
    assert Extractor.get_image_url(root, "https://lpix.org/a.png?x=1#f") == "https://lpix.org/a.png?x=1#f"
    assert Extractor.get_image_url(root, "//lpix.org/a.php?id=2") == "https://lpix.org/a.php?id=2"
    assert Extractor.get_image_url(root, "https://lparchive.org.evil.example/a.png?1") == "https://lparchive.org.evil.example/a.png?1"
    # and everything get_full_url does still applies
    assert Extractor.get_image_url(root, "../Smilies/emot-smith.gif") == "https://lparchive.org/Advance-Wars/Smilies/emot-smith.gif"
    assert Extractor.get_image_url(root, "javascript:void(0)") is None
    assert Extractor.get_image_url(root, "hhttp://lpix.org/a.png") == "http://lpix.org/a.png"


def test_lparchive_fallback_urls():
    assert lib.lparchive_fallback_urls("https://lparchive.org/Echo-Night/Images/40-Pole&Paddle.jpg") == [
        "https://lparchive.org/Echo-Night/Images/40-Pole&amp;Paddle.jpg"]
    assert lib.lparchive_fallback_urls("https://lparchive.org/Echo-Night/Images/40-Pole&amp;Paddle.jpg") == []
    assert lib.lparchive_fallback_urls("https://lparchive.org/Echo-Night/Images/40-Pole.jpg") == []
    assert lib.lparchive_fallback_urls("https://img.example/show.php?a=1&b=2") == []   # a real query string
    # a forum cache-busting query the archiver dropped (Quest-64 update 9): the name cut after its extension
    assert lib.lparchive_fallback_urls("https://lparchive.org/Quest-64/Update%209/1-questtales.png%3Ft=1203476272") == [
        "https://lparchive.org/Quest-64/Update%209/1-questtales.png"]
    assert lib.lparchive_fallback_urls("https://lparchive.org/Advance-Wars/Update%201/21-Ashley%3F.png") == []   # no extension before the '?'
    assert lib.lparchive_fallback_urls("https://lparchive.org/Some-LP/1-a.jpg%3F12") == [
        "https://lparchive.org/Some-LP/1-a.jpg", "https://lparchive.org/Some-LP/Images/1-a.jpg%3F12", "https://lparchive.org/Some-LP/Images/1-a.jpg"]
    # a picture referenced next to the landing page normally lives in the LP's Images/ folder
    root = "https://lparchive.org/Ratchet-Clank-Into-the-Nexus"
    assert lib.lparchive_fallback_urls(f"{root}/62-B04.png") == [f"{root}/Images/62-B04.png"]
    assert lib.lparchive_fallback_urls(f"{root}/Images/62-B04.png") == []
    assert lib.lparchive_fallback_urls(f"{root}/Update%2001/62-B04.png") == []
    assert lib.lparchive_fallback_urls(f"{root}/") == []
    assert lib.lparchive_fallback_urls(f"{root}/1-a&b.png") == [
        f"{root}/1-a&amp;b.png", f"{root}/Images/1-a&b.png", f"{root}/Images/1-a&amp;b.png"]
    # smilies: the LP's own Smilies/ folder first (its copies differ, and some names exist only there),
    # then the site-wide one
    assert lib.lparchive_fallback_urls("https://lparchive.org/Grandia/Update%20195/Smilies/emot-allears.gif") == [
        "https://lparchive.org/Grandia/Smilies/emot-allears.gif", "https://lparchive.org/Smilies/emot-allears.gif"]
    assert lib.lparchive_fallback_urls("https://lparchive.org/Dark-Souls/Smilies/emot-colbert.gif") == [
        "https://lparchive.org/Smilies/emot-colbert.gif"]
    assert lib.lparchive_fallback_urls("https://lparchive.org/Smilies/emot-argh.gif") == []
    assert lib.lparchive_fallback_urls("https://fi.somethingawful.com/images/smilies/emot-argh.gif") == []


@pytest.mark.asyncio
async def test_landing_page_picture_missing_the_images_folder_is_fetched_from_it():
    root = "https://lparchive.org/Ratchet-Clank-Into-the-Nexus"
    wrong, right = f"{root}/62-B04.png", f"{root}/Images/62-B04.png"
    session = _FakeSession("never-matches", responses={
        wrong: _FakeResponse(404, b"not here"), right: _FakeResponse(200, PNG_BYTES, "image/png")})
    tag = BeautifulSoup('<a href="62-B04.png" target="_blank">B04</a>', "html.parser").a
    image = lib.Image(num=0, src="62-B04.png", tag=tag, url=Extractor.get_image_url(root, "62-B04.png"), root_url=root)
    assert image.url == wrong

    stored = await asyncio.wait_for(lib._get_image(session, image, ImageRegistry()), timeout=5)

    assert session.requested == [wrong, right]
    assert stored.old_name == wrong          # the page's reference is what gets rewritten
    assert stored.new_name.endswith(".png")

    # a picture that is nowhere stays reported under the URL the page gave
    nowhere = lib.Image(num=1, src="99-X.png", tag=tag, url=f"{root}/99-X.png", root_url=root)
    session.responses[f"{root}/99-X.png"] = _FakeResponse(404, b"no")
    session.responses[f"{root}/Images/99-X.png"] = _FakeResponse(404, b"no")
    with pytest.raises(lib.NonRetryableError, match=re.escape(f"{root}/99-X.png, status code: 404")):
        await asyncio.wait_for(lib._get_image(session, nowhere, ImageRegistry()), timeout=5)


@pytest.mark.asyncio
async def test_picture_archived_without_its_query_string_is_fetched_from_the_cut_name():
    root = "https://lparchive.org/Quest-64/Update%209/"
    with_query, cut = f"{root}1-questtales.png%3Ft=1203476272", f"{root}1-questtales.png"
    session = _FakeSession("never-matches", responses={
        with_query: _FakeResponse(404, b"not here"), cut: _FakeResponse(200, PNG_BYTES, "image/png")})
    src = "1-questtales.png?t=1203476272"
    tag = BeautifulSoup(f'<img src="{src}"/>', "html.parser").img
    image = lib.Image(num=0, src=src, tag=tag, url=Extractor.get_image_url(root, src), root_url=root)
    assert image.url == with_query

    stored = await asyncio.wait_for(lib._get_image(session, image, ImageRegistry()), timeout=5)

    assert session.requested == [with_query, cut]
    assert stored.old_name == with_query


@pytest.mark.asyncio
async def test_archived_names_with_url_syntax_are_fetched_and_the_entity_spelling_is_tried_after_a_404():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    page = f"{url}/Update%2001/"
    attachment_as_query = f"{page}37-attachment.php?postid=402560042."       # what urljoin would produce
    attachment = f"{page}37-attachment.php%3Fpostid=402560042."
    pole_decoded = f"{url}/Images/40-Pole&Paddle.jpg"                         # what the HTML parser yields
    pole_entity = f"{url}/Images/40-Pole&amp;Paddle.jpg"                      # the archived file name
    stored_decoded = f"{page}41-Fish&Chips.jpg"                               # a '&' name that does exist as such
    external = "http://img.example/show.php?a=1&b=2"                          # external 404: not respelled
    session = _FakeSession("never-matches", responses={
        attachment_as_query: _FakeResponse(404, b"not here"),
        attachment: _FakeResponse(200, PNG_BYTES, "application/octet-stream"),
        pole_decoded: _FakeResponse(404, b"not here"),
        pole_entity: _FakeResponse(200, JPEG_BYTES, "image/jpeg"),
        stored_decoded: _FakeResponse(200, GIF_BYTES, "image/gif"),
        external: _FakeResponse(404, b"gone"),
    })
    session.responses[page] = _FakeResponse(200, (
        '<div id="content"><img src="37-attachment.php?postid=402560042."/>'
        '<img src="../Images/40-Pole&amp;Paddle.jpg"/>'
        '<img src="41-Fish&amp;Chips.jpg"/>'
        f'<img src="{external.replace("&", "&amp;")}"/></div>').encode())
    messages = []
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, messages.append), timeout=30)
        with zipfile.ZipFile(out) as z:
            chapter = z.read("EPUB/update_0.xhtml").decode()
            stored = [n for n in z.namelist() if n.startswith("EPUB/images/")]

    assert attachment in session.requested and attachment_as_query not in session.requested
    assert session.requested.count(pole_decoded) == 1 and session.requested.count(pole_entity) == 1
    assert session.requested.index(pole_decoded) < session.requested.index(pole_entity)
    assert session.requested.count(stored_decoded) == 1 and stored_decoded.replace("&", "&amp;") not in session.requested
    assert session.requested.count(external) == 1 and external.replace("&", "&amp;") not in session.requested
    assert sorted(n.rsplit(".", 1)[1] for n in stored if "cover" not in n) == ["gif", "jpg", "png"]
    assert chapter.count("missing-image") == 1 and f'href="{external.replace("&", "&amp;")}"' in chapter
    report = "\n".join(messages)
    assert external in report and "status code: 404" in report
    assert "Pole" not in report and "attachment" not in report and "Fish" not in report


@pytest.mark.asyncio
async def test_smilies_come_from_the_lp_s_own_folder_or_else_the_site_wide_one():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    page = f"{url}/Update%2001/"
    site_wide = "https://lparchive.org/Smilies/emot-allears.gif"
    own_copy = f"{url}/Smilies/emot-2bong.png"                    # exists only in this LP's folder (Headshoots)
    session = _FakeSession("never-matches", responses={
        f"{page}Smilies/emot-allears.gif": _FakeResponse(404, b"not here"),     # like the site: resolved
        f"{url}/Smilies/emot-allears.gif": _FakeResponse(404, b"not here"),     # against the page, they 404
        site_wide: _FakeResponse(200, GIF_BYTES, "image/gif"),
        f"{page}Smilies/emot-2bong.png": _FakeResponse(404, b"not here"),
        own_copy: _FakeResponse(200, PNG_BYTES, "image/png"),
        "https://lparchive.org/Smilies/emot-2bong.png": _FakeResponse(404, b"not here"),
    })
    session.responses[page] = _FakeResponse(200, (
        b'<div id="content"><img src="Smilies/emot-allears.gif"/> and <img src="../Smilies/emot-allears.gif"/>'
        b' <img src="Smilies/emot-2bong.png"/></div>'))
    messages = []
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, messages.append), timeout=30)
        with zipfile.ZipFile(out) as z:
            chapter = z.read("EPUB/update_0.xhtml").decode()
            gifs = [n for n in z.namelist() if n.startswith("EPUB/images/") and n.endswith(".gif")]

    # the page's own spelling is tried first, so an LP's own copy wins when it has one
    assert session.requested.index(f"{page}Smilies/emot-allears.gif") < session.requested.index(site_wide)
    assert own_copy in session.requested and "https://lparchive.org/Smilies/emot-2bong.png" not in session.requested
    assert len(gifs) == 1                                        # the two references to allears share one file
    assert chapter.count(f'src="{gifs[0].removeprefix("EPUB/")}"') == 2
    assert "missing-image" not in chapter
    assert "Smilies" not in "\n".join(messages)


def test_classify_failure():
    archive, elsewhere = "https://lparchive.org/Some-LP/Update%2001/a.png", "http://img.example/a.png"
    not_an_image = lib.NotAnImageError("Not an image: the server answered with image/png (0 bytes)")
    assert lib.classify_failure(not_an_image, archive) == lib.ARCHIVE_COPY
    assert lib.classify_failure(not_an_image, elsewhere) == lib.WEB_PAGE
    for status in (400, 403, 404, 410, 418, 451):   # any 4xx off the archive: the host will not serve it
        gone = lib.NonRetryableError(f"Failed to get resource {elsewhere}, status code: {status}", elsewhere, status)
        assert lib.classify_failure(gone, elsewhere) == lib.GONE
    for status in (404, 410):   # on the archive, after every fallback spelling: the file was never archived
        missing = lib.NonRetryableError(f"Failed to get resource {archive}, status code: {status}", archive, status)
        assert lib.classify_failure(missing, archive) == lib.ARCHIVE_MISSING
        assert lib.classify_failure(missing, archive, page=True) == lib.OTHER   # a listed update that 404s is unexpected
    forbidden = lib.NonRetryableError(f"Failed to get resource {archive}, status code: 403", archive, 403)
    assert lib.classify_failure(forbidden, archive) == lib.OTHER   # the archive does not answer 403: unexpected
    broken = "https://lparchive.org/Legend-of-Wulin-Heroes/Update%2018/9-Hunt_snakebladder.jpg</missing><missing>10-hunt_beargall.jpg"
    assert lib.classify_failure(lib.NonRetryableError(f"Failed to get resource {broken}, status code: 404", broken, 404), broken) == lib.OTHER
    assert lib.classify_failure(lib.NonRetryableError("Malformed URL that could not be repaired: hhttp://"), None) == lib.OTHER
    assert lib.classify_failure(lib.NonRetryableError(f"Failed to get resource {elsewhere}: too many redirects", elsewhere), elsewhere) == lib.OTHER
    unreachable = RetriesExhaustedError(f"Failed to get resource {elsewhere} after 5 retries: Cannot connect to host", elsewhere)
    assert lib.classify_failure(unreachable, elsewhere) == lib.DEAD_HOST
    assert lib.classify_failure(unreachable, archive) == lib.TEMPORARY
    server_error = RetriesExhaustedError(f"Failed to get resource {elsewhere} after 5 retries: status code: 503", elsewhere, 503)
    assert lib.classify_failure(server_error, elsewhere) == lib.TEMPORARY
    assert lib.classify_failure(AttributeError("'NoneType' object has no attribute 'find_all'"), archive) == lib.OTHER


def test_failures_report_groups_by_cause_and_asks_for_an_issue_only_when_it_can_help():
    page = "https://lparchive.org/Some-LP/Update%2001/"
    beyond_reach = [
        lib.SkippedResource(page, "http://i.minus.com/a.png", "Failed ... getaddrinfo failed", lib.DEAD_HOST),
        lib.SkippedResource(page, "http://i.minus.com/b.png", "Failed ... getaddrinfo failed", lib.DEAD_HOST),
        lib.SkippedResource(page, "http://xs.to/c.png", "Failed ... getaddrinfo failed", lib.DEAD_HOST),
        lib.SkippedResource(page, "http://tinypic.com/d.png", "Failed ... getaddrinfo failed", lib.DEAD_HOST),
        lib.SkippedResource(page, "http://waffleimages.com/e.png", "Failed ... getaddrinfo failed", lib.DEAD_HOST),
        lib.SkippedResource(page, "http://abload.de/f.png", "Failed ..., status code: 410", lib.GONE),
        lib.SkippedResource(page, "12-shot.png", "Not an image: the server answered with image/png (0 bytes)", lib.ARCHIVE_COPY),
        lib.SkippedResource(page, "13-never.png", "Failed ..., status code: 404", lib.ARCHIVE_MISSING),
        lib.SkippedResource(page, "http://photobucket.com/g.png", "Not an image: ... text/html (7584 bytes)", lib.WEB_PAGE),
        lib.SkippedResource(page, "http://slow.example/h.png", "Failed ... after 5 retries: status code: 503", lib.TEMPORARY),
        lib.SkippedResource(page, "http://abload.de/f.png", "Failed ..., status code: 410", lib.GONE),   # a duplicate
    ]
    report = format_failures_report("https://lparchive.org/Some-LP", beyond_reach, "outcome line")
    assert "10 resource(s) could not be retrieved" in report
    assert ISSUES_URL not in report and "open an issue" not in report
    assert "5 image(s) on hosts that no longer exist or do not answer (i.minus.com 2, tinypic.com 1, waffleimages.com 1 and 1 more host):" in report
    assert "1 image(s) their host no longer serves (HTTP 403, 404, 410 or another 4xx; abload.de 1):" in report
    assert "1 image(s) whose copy on lparchive.org is empty, or is a web page saved under the image's name:" in report
    assert "1 image(s) that are not on lparchive.org (HTTP 404 under every spelling this tool knows):" in report
    assert "1 image(s) whose host answers an empty file or a web page instead of the picture (hotlink protection, parking page; photobucket.com 1):" in report
    assert "1 resource(s) whose host had trouble (server error, disconnection); try again later:" in report
    assert report.count("url:    http://abload.de/f.png") == 1
    assert report.index("hosts that no longer exist") < report.index("no longer serves") < report.index("copy on lparchive.org") \
        < report.index("not on lparchive.org") < report.index("web page instead") < report.index("had trouble") < report.index("outcome line")

    needs_a_look = beyond_reach + [lib.SkippedResource(page, "hhttp://", "Malformed URL that could not be repaired: hhttp://")]
    report = format_failures_report("https://lparchive.org/Some-LP", needs_a_look, "outcome line")
    assert "1 resource(s) that failed for a reason this tool may be able to do something about:" in report
    assert report.index("outcome line") < report.index(f"Please open an issue at {ISSUES_URL}")
    # missing updates keep their wording
    report = format_failures_report("https://lparchive.org/Some-LP", [lib.SkippedResource(page, page, "status code: 404")],
                                    "outcome", what="update(s)")
    assert "1 update(s) could not be retrieved" in report and "1 update(s) that failed" in report and ISSUES_URL in report


@pytest.mark.asyncio
async def test_report_asks_for_an_issue_only_for_failures_the_tool_may_handle():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    page = f"{url}/Update%2001/"
    gone, broken, archive_404 = "http://img.example/gone.png", f"{page}3-empty.png", f"{page}4-missing.png"
    session = _FakeSession("never-matches", responses={
        gone: _FakeResponse(404, b"gone"),
        broken: _FakeResponse(200, b"", "image/png"),
        archive_404: _FakeResponse(404, b"not here"),
        f"{page}5-a.jpg</missing><missing>6-b.jpg": _FakeResponse(404, b"not here"),
    })
    for name, body in (("beyond-reach", f'<img src="{gone}"/><img src="3-empty.png"/><img src="4-missing.png"/>'),
                       ("needs-a-look", f'<img src="{gone}"/><img src="5-a.jpg</missing><missing>6-b.jpg"/>')):
        session.responses[page] = _FakeResponse(200, f'<div id="content">{body}</div>'.encode())
        messages = []
        with tempfile.TemporaryDirectory() as d:
            await asyncio.wait_for(do(url, f"{d}/book.epub", session, messages.append), timeout=30)
        report = messages[-1]
        assert gone in report
        if name == "beyond-reach":
            assert "3 resource(s) could not be retrieved" in report
            assert "their host no longer serves" in report and "copy on lparchive.org is empty" in report
            assert "not on lparchive.org (HTTP 404" in report and "4-missing.png" in report
            assert ISSUES_URL not in report
        else:
            assert "2 resource(s) could not be retrieved" in report
            assert "may be able to do something about" in report and "5-a.jpg</missing><missing>6-b.jpg" in report
            assert ISSUES_URL in report


@pytest.mark.asyncio
async def test_landing_page_404_is_a_not_found_error():
    url = "https://lparchive.org/This-LP-Does-Not-Exist"
    session = _FakeSession("never-matches", responses={url: _FakeResponse(404, b"nope")})
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(NotFoundError) as exc_info:
            await do(url, f"{d}/book.epub", session, lambda *_: None)
    msg = str(exc_info.value)
    assert exc_info.value.exit_code == EXIT_NOT_FOUND
    assert url in msg and "404" in msg and "Check the URL" in msg
    assert "Traceback" not in msg


class _UnreachableSession(_FakeSession):
    def get(self, url, **kwargs):
        self.requested.append(url)
        raise aiohttp.ClientConnectionError("Cannot connect to host lparchive.org:443 [Name or service not known]")


@pytest.mark.asyncio
async def test_unreachable_landing_page_is_a_network_error(monkeypatch):
    monkeypatch.setattr(lib, "RETRY_BACKOFF_BASE", 0)
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    session = _UnreachableSession("never-matches")
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(NetworkError) as exc_info:
            await asyncio.wait_for(do(url, f"{d}/book.epub", session, lambda *_: None), timeout=10)
    assert exc_info.value.exit_code == EXIT_NETWORK
    assert "Could not reach" in str(exc_info.value) and url in str(exc_info.value)
    assert "Name or service not known" in str(exc_info.value)
    assert len(session.requested) == 5  # all retries were used
    assert isinstance(exc_info.value.__cause__, RetriesExhaustedError)


@pytest.mark.asyncio
async def test_server_error_on_landing_page_is_a_network_error(monkeypatch):
    monkeypatch.setattr(lib, "RETRY_BACKOFF_BASE", 0)
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    session = _FakeSession("never-matches", responses={url: _FakeResponse(503, b"down")})
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(NetworkError, match="HTTP 503"):
            await asyncio.wait_for(do(url, f"{d}/book.epub", session, lambda *_: None), timeout=10)


def _run_cli_with(monkeypatch, capsys, exc):
    async def fake(*args, **kwargs):
        raise exc
    monkeypatch.setattr(cli, "lparchive2epub", fake)
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["https://lparchive.org/Some-LP", "out.epub"])
    return exit_info.value.code, capsys.readouterr().err


@pytest.mark.parametrize(("exc", "code", "text"), [
    (NotFoundError("Not found: nope"), EXIT_NOT_FOUND, "Not found: nope"),
    (NetworkError("Could not reach"), EXIT_NETWORK, "Could not reach"),
    (OutputError("Cannot write"), EXIT_OUTPUT, "Cannot write"),
    (StrictModeError("strict report"), 1, "strict report"),
    (MissingUpdatesError("missing report"), 1, "missing report"),
    (lib.CheckError("The book was written at x, but epubcheck could not run: boom"), lib.EXIT_CHECK, "epubcheck could not run"),
    (lib.InvalidBookError("check report"), lib.EXIT_CHECK, "check report"),
    (KeyboardInterrupt(), EXIT_INTERRUPTED, "Interrupted. No book was written."),
])
def test_cli_exit_codes_and_messages(monkeypatch, capsys, exc, code, text):
    exit_code, err = _run_cli_with(monkeypatch, capsys, exc)
    assert exit_code == code
    assert text in err
    assert "Traceback" not in err


def test_cli_unexpected_error_asks_for_a_bug_report(monkeypatch, capsys):
    exit_code, err = _run_cli_with(monkeypatch, capsys, AttributeError("'NoneType' object has no attribute 'find'"))
    assert exit_code == 1
    assert "unexpected error: AttributeError" in err
    assert ISSUES_URL in err
    assert "Traceback" in err  # kept on purpose: it is what the bug report needs


class _JitteryResponse(_FakeResponse):
    """Answers after a random delay, so downloads finish in a different order every run."""

    def __init__(self, status, body, rng, content_type=None):
        super().__init__(status, body, content_type)
        self._rng = rng

    async def read(self):
        await asyncio.sleep(self._rng.random() * 0.02)
        return self._body

    async def text(self):
        await asyncio.sleep(self._rng.random() * 0.02)
        return self._body.decode("utf-8", errors="replace")


class _JitterySession(_FakeSession):
    """Chapters with several distinct images each, some shared between chapters; random latency."""

    def __init__(self, seed: int):
        super().__init__("never-matches")
        self.rng = random.Random(seed)

    def get(self, url, **kwargs):
        self.requested.append(url)
        if url.rstrip("/") == "https://lparchive.org/X-COM-Terror-from-the-Deep":
            return _JitteryResponse(200, xcom, self.rng)
        m = re.search(r"Update%20(\d+)/$", url)
        if m and int(m.group(1)) > 18:
            return _JitteryResponse(404, b"no such update", self.rng)
        if m:
            n = int(m.group(1))
            imgs = "".join(f'<img src="{n}-{i}.png"/>' for i in range(6)) + '<img src="../shared.png"/>'
            return _JitteryResponse(200, f'<div id="content"><h3>Update {n}</h3>{imgs}</div>'.encode(), self.rng)
        # distinct content per image URL, so every image gets its own hash
        return _JitteryResponse(200, PNG_BYTES + url.encode(), self.rng)


async def _build_with_seed(seed: int) -> bytes:
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, _JitterySession(seed), lambda *_: None), timeout=60)
        with open(out, "rb") as f:
            return f.read()


@pytest.mark.asyncio
async def test_output_is_byte_identical_whatever_the_download_order():
    first, second, third = [await _build_with_seed(seed) for seed in (1, 2, 3)]
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest() == hashlib.sha256(third).hexdigest()
    with zipfile.ZipFile(io.BytesIO(first)) as z:
        opf = z.read("EPUB/content.opf").decode()
        images = [i for i in re.findall(r'href="images/[^"]+"', opf) if "cover" not in i]
        # zip entries are stamped with the LP's archival date, not the build time
        assert {info.date_time for info in z.infolist()} == {(2010, 5, 14, 0, 0, 0)}
        assert z.infolist()[0].filename == "mimetype" and z.infolist()[0].compress_type == zipfile.ZIP_STORED
        assert z.testzip() is None
    assert len(images) == 18 * 6 + 1 + 1  # 6 per chapter, one shared, one in the intro
    assert "lparchive2epub-" in opf and opf.count("<dc:identifier") == 1


@pytest.mark.parametrize(("given", "expected"), [
    ("https://lparchive.org/X-COM-Terror-from-the-Deep", "https://lparchive.org/X-COM-Terror-from-the-Deep"),
    ("https://lparchive.org/X-COM-Terror-from-the-Deep/", "https://lparchive.org/X-COM-Terror-from-the-Deep"),
    ("https://lparchive.org/X-COM-Terror-from-the-Deep/Update%2001/", "https://lparchive.org/X-COM-Terror-from-the-Deep"),
    ("https://lparchive.org/Some-LP/Update%2003/#part2", "https://lparchive.org/Some-LP"),
    ("https://lparchive.org/Some-LP?x=1", "https://lparchive.org/Some-LP"),
    ("http://www.lparchive.org/Some-LP/", "https://lparchive.org/Some-LP"),
    ("HTTPS://LPARCHIVE.ORG/Some-LP", "https://lparchive.org/Some-LP"),
    ("lparchive.org/Some-LP", "https://lparchive.org/Some-LP"),
    ("  https://lparchive.org/Some-LP  ", "https://lparchive.org/Some-LP"),
])
def test_normalize_lp_url(given, expected):
    assert normalize_lp_url(given) == expected


@pytest.mark.parametrize("given", [
    "https://lparchive.org/",
    "https://lparchive.org",
    "lparchive.org",
    "https://evil.example/?lparchive.org",
    "https://evil.example/lparchive.org/Some-LP",
    "https://notlparchive.org/Some-LP",
    "https://lparchive.org.evil.example/Some-LP",
    "ftp://lparchive.org/Some-LP",
    "",
])
def test_normalize_lp_url_rejects_non_lp_addresses(given):
    with pytest.raises(ValueError):
        normalize_lp_url(given)


def test_cli_rejects_bad_url_with_usage_error(capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["https://evil.example/?lparchive.org", "out.epub"])
    assert exit_info.value.code == 2
    assert "is not an lparchive.org URL" in capsys.readouterr().err


def test_cli_normalises_the_url_before_extracting(monkeypatch):
    seen = {}

    async def fake(url, *args, **kwargs):
        seen["url"] = url

    monkeypatch.setattr(cli, "lparchive2epub", fake)
    cli.main(["lparchive.org/Some-LP/Update%2007/", "out.epub"])
    assert seen["url"] == "https://lparchive.org/Some-LP"


NOT_AN_LP_PAGE = b"""<html><head><title>GuavaMoment's Let's Plays</title></head>
<body><div class="header">The Let's Play Archive</div><ul><li><a href="/X-COM-Terror-from-the-Deep/">X-COM</a></li></ul></body></html>"""


def test_intro_rejects_a_page_that_is_not_a_lets_play():
    with pytest.raises(NotALetsPlayError) as exc_info:
        Extractor.intro("https://lparchive.org/author", BeautifulSoup(NOT_AN_LP_PAGE, "html.parser"))
    msg = str(exc_info.value)
    assert "is not the page of a Let's Play" in msg
    assert "the content block" in msg and "the archival date" in msg and "the author" in msg
    assert exc_info.value.exit_code == EXIT_NOT_FOUND


@pytest.mark.asyncio
async def test_non_lp_page_fails_cleanly_through_do():
    url = "https://lparchive.org/author"
    session = _FakeSession("never-matches", responses={url: _FakeResponse(200, NOT_AN_LP_PAGE)})
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(NotALetsPlayError):
            await do(url, f"{d}/book.epub", session, lambda *_: None)
        assert os.listdir(d) == []


@pytest.mark.asyncio
async def test_requests_carry_a_descriptive_user_agent():
    """Bot policies (Wikimedia's, uesp.net's) refuse generic clients; imgur refuses aiohttp's default.
    Live check of 2026-10-17 in lib.request_headers' docstring."""
    class _RecordingSession(_FakeSession):
        def get(self, url, **kwargs):
            self.headers = kwargs.get("headers")
            return super().get(url, **kwargs)

    session = _RecordingSession("never-matches")
    await fetch_with_retries(session, "https://lparchive.org/X-COM-Terror-from-the-Deep/Update%2001/a.png")
    agent = session.headers["user-agent"]
    assert re.fullmatch(r"lparchive2epub/\S+ \(\+https://github\.com/Arwalk/lparchive2epub\)", agent), agent
    assert "aiohttp" not in agent and "curl" not in agent
    assert session.headers["accept"] == "*/*"


@pytest.mark.asyncio
async def test_fetch_with_retries_returns_body_and_decodes_text():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    session = _FakeSession("never-matches", responses={url: _FakeResponse(200, "caf\u00e9".encode("utf-8"), "text/html; charset=utf-8")})
    fetched = await fetch_with_retries(session, url)
    assert isinstance(fetched, Fetched)
    assert fetched.body == "caf\u00e9".encode("utf-8") and fetched.text() == "caf\u00e9"
    assert fetched.content_type == "text/html; charset=utf-8"
    assert session.requested == [url]


def _redirect_loop(url: str) -> aiohttp.TooManyRedirects:
    """What aiohttp raises on a renamed LP: a ClientResponseError with status 0 and an empty message."""
    from multidict import CIMultiDict, CIMultiDictProxy
    from yarl import URL
    info = aiohttp.RequestInfo(URL(url), "GET", CIMultiDictProxy(CIMultiDict()), URL(url))
    return aiohttp.TooManyRedirects(info, ())


class _RenamedLpSession(_FakeSession):
    """X-COM, except that the given pages 301-loop (like a renamed LP's missing updates) instead of answering 404."""

    def __init__(self, looping: set[str]):
        super().__init__("never-matches")
        self.looping = looping

    def get(self, url, **kwargs):
        if url in self.looping:
            self.requested.append(url)
            raise _redirect_loop(url)
        return super().get(url, **kwargs)


@pytest.mark.asyncio
async def test_redirect_loops_fail_at_once_and_end_the_search_for_unlisted_updates_silently(monkeypatch):
    monkeypatch.setattr(lib, "RETRY_BACKOFF_BASE", 0)
    url = "https://lparchive.org/Homeworld-Cataclysm/Update%2001/"
    session = _RenamedLpSession({url})
    with pytest.raises(lib.NonRetryableError, match="too many redirects") as e:
        await fetch_with_retries(session, url, max_retries=5)
    assert session.requested == [url]              # no retries, no backoff
    assert isinstance(e.value.__cause__, aiohttp.TooManyRedirects)

    # through the build: the probe for the page after the last listed one loops; the book is complete
    # and nothing is reported, exactly as if the site had answered 404
    probe = "https://lparchive.org/X-COM-Terror-from-the-Deep/Update%2019/"
    session = _RenamedLpSession({probe})
    messages = []
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do("https://lparchive.org/X-COM-Terror-from-the-Deep", out, session, messages.append), timeout=30)
        chapters = _chapter_files(out)
    assert session.requested.count(probe) == 1
    assert len(chapters) == 18
    assert "unlisted" not in "\n".join(messages) and "could not be retrieved" not in "\n".join(messages)


@pytest.mark.asyncio
async def test_transient_server_errors_are_retried_but_processing_errors_are_not(monkeypatch):
    monkeypatch.setattr(lib, "RETRY_BACKOFF_BASE", 0)
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    flaky_chapter = f"{url}/Update%2003/"
    broken_chapter = f"{url}/Update%2007/"
    session = _FakeSession("never-matches", responses={flaky_chapter: _FakeResponse(503, b"down")})

    real_get_update = lib.Extractor.get_update

    def get_update(chapters, p, chapter):
        if chapter.original_href == broken_chapter:
            raise KeyError("simulated parsing bug")
        return real_get_update(chapters, p, chapter)

    monkeypatch.setattr(lib.Extractor, "get_update", staticmethod(get_update))
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(MissingUpdatesError) as exc_info:
            await asyncio.wait_for(do(url, f"{d}/book.epub", session, lambda *_: None), timeout=10)

    assert session.requested.count(flaky_chapter) == 5      # network-ish failure: all retries used
    assert session.requested.count(broken_chapter) == 1     # processing failure: downloaded once, no retry
    report = str(exc_info.value)
    assert "2 update(s) could not be retrieved" in report
    assert "after 5 retries" in report and "status code: 503" in report
    assert "KeyError: 'simulated parsing bug'" in report


def test_stylesheet_is_self_contained_and_sized_for_lparchive_markup():
    from lparchive2epub.style import get_style_item, style, STYLE_FILE_NAME
    item = get_style_item()
    assert item.file_name == STYLE_FILE_NAME and item.media_type == "text/css"
    content = item.get_content()
    assert (content.decode() if isinstance(content, bytes) else content) == style
    # nothing epubcheck objects to: no external resources, no forbidden properties
    assert "@font-face" not in style and "url(" not in style and "direction" not in style
    assert "!important" not in style
    # the reader's font and colours stay in charge
    assert "body {" in style and "font-family" not in style.split("}")[0]
    assert "background" not in style
    # update titles are h3 on lparchive: they must not render smaller than the text
    m = re.search(r"h3 \{ font-size: ([\d.]+)em; \}", style)
    assert m and float(m.group(1)) > 1.0
    # images fit the screen, aspect ratio kept
    assert re.search(r"img \{[^}]*max-width: 100%;[^}]*height: auto;", style)
    # the markup actually present in lparchive pages is covered
    for selector in (".bbc-block", ".bbc-block h4", "blockquote", ".bbc-spoiler", "ul.toc li", "pre, code"):
        assert selector in style, selector
    assert len(style.splitlines()) < 120


@pytest.mark.asyncio
async def test_book_has_exactly_one_stylesheet_linked_from_every_page():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    session = _FakeSession("never-matches")
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, lambda *_: None), timeout=30)
        with zipfile.ZipFile(out) as z:
            css = [n for n in z.namelist() if n.endswith(".css")]
            assert css == ["EPUB/style/lparchive.css"]
            for n in z.namelist():
                if n.endswith(".xhtml") and n not in ("EPUB/nav.xhtml", "EPUB/cover.xhtml"):
                    assert 'href="style/lparchive.css"' in z.read(n).decode(), n


def test_sanitize_strips_active_content_and_legacy_markup():
    html = """<div id="content">
      <script>alert(1)</script><noscript>no</noscript><style>b{color:red}</style>
      <form action="/x"><input type="text"/><button>go</button><select><option>a</option></select><textarea>t</textarea></form>
      <iframe src="https://www.youtube.com/embed/abc123" width="560" height="315"></iframe>
      <embed src="relative.swf"/>
      <object data="https://example.com/thing.swf"></object>
      <img alt="" border="0" class="img" src="1.png" title=":smug:" width="640" height="480"/>
      <a href="https://example.com/" rel="nofollow" target="_blank" onclick="track()">link</a>
      <a name="part2">anchor</a><a name="part3" id="keep">anchor with id</a>
      <font color="red" size="3" face="Arial">red text</font>
      <center>centered</center>
      <tt>mono</tt> <big>large</big> <strike>struck</strike> <acronym title="Let's Play">LP</acronym> <nobr>no break</nobr> <blink>hi</blink>
      <table border="1" cellpadding="2" cellspacing="0" align="center"><tr><td valign="top" bgcolor="#fff" nowrap="nowrap">cell</td></tr></table>
      <table><col width="99%"><tr><td>column layout</td></tr></table>
      <span style="color: #336699;">speaker colour kept</span>
      <span class="bbc-spoiler" onmouseout="x()" onmouseover="y()" style="color: rgb(0, 0, 0); background-color: rgb(0, 0, 0);">hidden</span>
      <span style="color:#000000; background:#000000">also hidden, no class</span>
      <o:p>office</o:p><st1:place>Tokyo</st1:place>
      <pan style="color: red;">missing an s</pan> <misisng>typo</misisng> <h0>no such heading</h0> <didn't>text in brackets</didn't> <a< href="u">broken link</a<>
      <xmp>verbatim</xmp>
      <img src="x.png" border"0" alt=""/> <img src="y.png" width="50%" height="100"/>
      <ul type="disc"><li>a</li></ul> <ol type="A" start="3"><li>b</li></ol>
      <a href="u" _blank="">target</a> <a href="v" src="s" alt="t" data-x="1" frameborder="0">not an image</a>
      <table width="80%"><tr><td width="70" colspan="2" rowspan="1">cell</td></tr></table>
      <span hecatoncheires="" it="">broken quoting</span>
    </div>"""
    soup = get_cleaned_html(html)
    out = str(soup)
    # HTML 4 inline elements XHTML 5 dropped (epubcheck RSC-005 on The-Blackwell-Legacy's <tt>)
    assert "<code>mono</code>" in out and '<span style="font-size: larger;">large</span>' in out
    assert "<s>struck</s>" in out and '<abbr title="Let\'s Play">LP</abbr>' in out
    assert '<span style="white-space: nowrap;">no break</span>' in out and "<span>hi</span>" in out
    assert not re.search(r"<(tt|big|strike|acronym|nobr|blink)\b", out)

    for gone in ("<script", "<noscript", "<style", "<form", "<input", "<button", "<select", "<textarea",
                 "<iframe", "<embed", "<object", "<font", "<center", "<o:p", "<col", "onclick", "onmouseout", "onmouseover",
                 'border="', 'rel="', 'target="', 'align="', 'valign="', 'bgcolor="', 'nowrap="', 'cellpadding="',
                 'cellspacing="', 'name="', 'size="', 'face="'):
        assert gone not in out, gone

    # players become plain links to what they embedded; a relative/unknown source is just dropped
    assert '<p>[iframe: <a href="https://www.youtube.com/embed/abc123">https://www.youtube.com/embed/abc123</a>]</p>' in out
    assert '<p>[object: <a href="https://example.com/thing.swf">https://example.com/thing.swf</a>]</p>' in out
    assert "relative.swf" not in out
    # useful attributes survive
    assert '<img alt="" class="img" height="480" src="1.png" title=":smug:" width="640"/>' in out
    assert '<a href="https://example.com/">link</a>' in out
    assert '<a id="part2">anchor</a>' in out and '<a id="keep">anchor with id</a>' in out
    assert '<span style="color: red;">red text</span>' in out
    assert '<div style="text-align: center;">centered</div>' in out
    assert '<span style="color: #336699;">speaker colour kept</span>' in out
    assert "<table><tr><td>column layout</td></tr></table>" in out   # the rows stay, the <col> goes
    # spoilers are readable and marked for the stylesheet
    assert '<span class="bbc-spoiler">hidden</span>' in out
    assert '<span class="bbc-spoiler">also hidden, no class</span>' in out
    assert "officeTokyo" in out

    # elements XHTML 5 does not know are unwrapped, their text kept, like a browser shows them: typos (Daikatana's
    # <pan>, <misisng>, <h0>, The-Suffering's <a<), text in angle brackets (Star-Control-2's <didn't>), Office
    # namespaces; <xmp> is the old verbatim-text element, shown preformatted (Policenauts). RSC-005 in 5 books.
    assert "missing an s typo no such heading text in brackets broken link" in out
    assert not re.search(r"<(pan|misisng|h0|didn|a<|xmp|o:p|st1:place)\b", out)
    assert "<pre>verbatim</pre>" in out
    # attributes XHTML 5 does not allow are dropped, whatever the element, and so are the attribute names broken
    # quoting leaves the parser with (Ever-17's <img border"0">, <a target= _blank>, "hecatoncheires"); what it
    # allows on the element stays, an integer-only attribute only with an integer. RSC-005 in 14 books.
    assert '<img alt="" src="x.png"/>' in out and '<img height="100" src="y.png"/>' in out
    assert "<ul><li>a</li></ul>" in out and '<ol start="3" type="A"><li>b</li></ol>' in out
    assert '<a href="u">target</a>' in out and '<a href="v">not an image</a>' in out
    assert '<table><tr><td colspan="2" rowspan="1">cell</td></tr></table>' in out
    assert "<span>broken quoting</span>" in out
    for gone in ('border"0"', "_blank", "data-x", "frameborder", 'width="50%"', 'width="80%"', 'width="70"',
                 'type="disc"', "hecatoncheires", 'it=""', 'src="s"', 'alt="t"'):
        assert gone not in out, gone


def test_sanitize_drops_comments():
    """XML forbids "--" inside a comment, and authors write <!-- ------ --> separators and comment markup out:
    epubcheck RSC-016, a FATAL that stops the parse of the page, in 12 books of the archive-wide run. Neither
    parser drops a comment, so sanitize() does: a reader never sees one."""
    from ebooklib.utils import parse_html_string
    from lxml import etree
    html = ('<div id="content"><p>x <!-- a -- b --> y</p><!-- ---------- --><ul><li>a<!-- c --></li>'
            '<!-- <li>commented out</li> --></ul><table><!-- -- --><tr><td>cell<!--x--></td></tr></table></div>')
    out = str(get_cleaned_html(html))
    assert "<!--" not in out and "--" not in out
    assert "<p>x  y</p>" in out and "<li>a</li>" in out and "<td>cell</td>" in out and "commented out" not in out
    written = etree.tostring(parse_html_string(out), method="xml").decode()   # what ebooklib writes to the XHTML
    assert "<!--" not in written and "<p>x  y</p>" in written


FLASH_YOUTUBE = """<div class="bbcode_video"><object width="425" height="344">
  <param name="movie" value="http://www.youtube-nocookie.com/v/xsMN4L8BH8k&amp;hl=en&amp;fs=1">
  <param name="allowFullScreen" value="true"></param><param name="allowscriptaccess" value="always"></param>
  <embed src="http://www.youtube-nocookie.com/v/xsMN4L8BH8k&amp;hl=en&amp;fs=1" type="application/x-shockwave-flash"
         allowscriptaccess="always" allowfullscreen="true" width="425" height="344"></embed>
</object></div>"""
FLASH_LINK = '<p>[object: <a href="http://www.youtube-nocookie.com/v/xsMN4L8BH8k&amp;hl=en&amp;fs=1">http://www.youtube-nocookie.com/v/xsMN4L8BH8k&amp;hl=en&amp;fs=1</a>]</p>'


@pytest.mark.parametrize(("markup", "expected", "absent"), [
    # 2008-era YouTube embed: <object> wrapping <embed>, the address in the movie param and the embed.
    # One link for the whole thing; the nested, already removed <embed> used to crash the sanitiser.
    (FLASH_YOUTUBE, [FLASH_LINK], ["<object", "<embed", "<param", "allowscriptaccess"]),
    # the movie param alone is enough
    ('<object><param name="Movie" value="http://www.youtube.com/v/abc"/></object>',
     ['<p>[object: <a href="http://www.youtube.com/v/abc">http://www.youtube.com/v/abc</a>]</p>'], ["<object", "<param"]),
    # no address with a scheme anywhere: dropped, quietly
    ('<p>before</p><object><embed src="relative.swf"/></object><p>after</p>', ["<p>before</p>", "<p>after</p>"],
     ["<object", "<embed", "relative.swf"]),
    # HTML 5 nesting: <video> with <source> children, one link
    ('<video controls="controls"><source src="https://example.com/clip.mp4" type="video/mp4"/><source src="https://example.com/clip.webm"/></video>',
     ['<p>[video: <a href="https://example.com/clip.mp4">https://example.com/clip.mp4</a>]</p>'], ["<video", "<source", "clip.webm"]),
], ids=["flash-youtube", "movie-param-only", "no-scheme", "video-source"])
def test_sanitize_turns_nested_players_into_one_link(markup, expected, absent):
    out = str(get_cleaned_html(f'<div id="content">{markup}</div>'))
    for fragment in expected:
        assert fragment in out, fragment
    for fragment in absent:
        assert fragment not in out, fragment
    assert out.count("[object:") + out.count("[video:") + out.count("[embed:") <= 1


@pytest.mark.asyncio
async def test_flash_embed_on_the_landing_page_does_not_stop_the_build():
    """Beyond Divinity: the same markup on the landing page used to end in a bare traceback."""
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    opening = xcom.index(b">", xcom.index(b'id="content"')) + 1   # right inside the content div
    landing = xcom[:opening] + FLASH_YOUTUBE.encode() + xcom[opening:]
    session = _FakeSession("never-matches", responses={url: _FakeResponse(200, landing)})
    files = await _build_book(session)
    intro = files["EPUB/introduction.xhtml"].decode()
    assert FLASH_LINK in intro and "<object" not in intro and "<embed" not in intro


@pytest.mark.asyncio
async def test_missing_picture_inside_a_link_leaves_no_link_in_a_link_in_the_book():
    """La-Pucelle-Tactics update 32: <a href="video"><img src="12-LPT-00049.jpg"></a>, the archive's copy of the
    picture empty. The note that replaces it must not link the original: that is a link in a link (RSC-005)."""
    from ebooklib.utils import parse_html_string
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    opening = xcom.index(b">", xcom.index(b'id="content"')) + 1
    markup = b'<a href="http://v/watch"><img src="http://x/a.gif"/></a>'
    landing = xcom[:opening] + markup + xcom[opening:]
    session = _FakeSession("never-matches", responses={url: _FakeResponse(200, landing),
                                                       "http://x/a.gif": _FakeResponse(200, b"", "image/gif")})
    files = await _build_book(session)
    intro = files["EPUB/introduction.xhtml"].decode()
    assert '<a href="http://v/watch"><span class="missing-image">[image not available: a.gif]</span></a>' in intro
    assert _nested_links(parse_html_string(files["EPUB/introduction.xhtml"])) == []


@pytest.mark.asyncio
async def test_landing_page_parser_bug_is_reported_not_a_bare_traceback(monkeypatch):
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"

    def broken_sanitize(soup):
        raise AttributeError("'NoneType' object has no attribute 'get'")

    monkeypatch.setattr(lib, "sanitize", broken_sanitize)
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(ExtractionError, match=r"Could not read the landing page .*AttributeError.*\n.*bug.*issue") as e:
            await do(url, f"{d}/book.epub", _FakeSession("never-matches"), lambda *_: None)
        assert e.value.exit_code == lib.EXIT_FAILURE and os.listdir(d) == []

@pytest.mark.asyncio
async def test_built_pages_contain_no_handlers_or_legacy_attributes():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    spoiler_chapter = f"{url}/Update%2001/"
    session = _FakeSession("never-matches")
    session.responses[spoiler_chapter] = _FakeResponse(200, (
        '<div id="content"><img alt="" border="0" class="img" src="1.png"/>'
        '<span class="bbc-spoiler" onmouseover="a()" style="color:#000;background-color:#000">secret</span>'
        '<iframe src="https://www.youtube.com/embed/abc"></iframe><a href="https://x.example/" target="_blank">x</a></div>'
    ).encode())
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, lambda *_: None), timeout=30)
        with zipfile.ZipFile(out) as z:
            pages = {n: z.read(n).decode() for n in z.namelist() if n.endswith(".xhtml")}
    for name, page in pages.items():
        assert not re.search(r'\son[a-z]+="', page), name
        assert 'border="' not in page and 'target="' not in page and 'rel="nofollow"' not in page, name
    chapter = pages["EPUB/update_0.xhtml"]
    assert '<span class="bbc-spoiler">secret</span>' in chapter
    assert '<a href="https://www.youtube.com/embed/abc">' in chapter and "<iframe" not in chapter


def test_extractor_reads_the_landing_page_facts():
    intro = Extractor.intro("https://lparchive.org/X-COM-Terror-from-the-Deep", BeautifulSoup(xcom, "html.parser"))
    assert (intro.began, intro.ended, intro.parts) == ("Oct 26, 2009", "Apr 09, 2010", 18)
    assert intro.published_on == "May 14, 2010"
    assert intro.tags == ["hybrid", "voice"]
    assert intro.thread_url == "http://forums.somethingawful.com/showthread.php?threadid=3220122"
    assert intro.thread_title.startswith("The X-COM: Terror From The Deep")
    # the build reads the facts from the sanitised page: its head and the archive's own markup must survive sanitize()
    cleaned = Extractor.intro("https://lparchive.org/X-COM-Terror-from-the-Deep", get_cleaned_html(xcom))
    for fact in ("title", "author", "began", "ended", "parts", "published_on", "tags", "thread_url", "thread_title"):
        assert getattr(cleaned, fact) == getattr(intro, fact), fact
    assert [c.original_href for c in cleaned.chapters] == [c.original_href for c in intro.chapters]

    intro = Extractor.intro("https://lparchive.org/Resident-Evil-1", BeautifulSoup(re1, "html.parser"))
    assert (intro.began, intro.ended, intro.parts) == ("Sep 10, 2007", "Nov 16, 2007", 59)
    assert intro.tags == ["screenshot", "humorous", "challenges", "narrative"]

    intro = Extractor.intro("https://lparchive.org/Dwarf-Fortress-Headshoots", BeautifulSoup(headshoots, "html.parser"))
    assert (intro.began, intro.ended, intro.parts) == ("Apr 25, 2009", "Apr 25, 2009", 90)
    assert intro.author == "Various"


def test_extractor_tolerates_missing_optional_facts():
    html = b"""<html><head><title>Old LP</title><meta name="author" content="Someone"/></head><body>
    <ul id="statistics"><li id="archival">Added to the archive on <strong>Jan 02, 2008</strong></li></ul>
    <div id="content">hello</div></body></html>"""
    intro = Extractor.intro("https://lparchive.org/Old-LP", BeautifulSoup(html, "html.parser"))
    assert (intro.began, intro.ended, intro.parts, intro.tags, intro.thread_url) == (None, None, None, [], None)
    assert compose_description(intro, "https://lparchive.org/Old-LP") == (
        "Let's Play of Old LP by Someone. Archived by The Let's Play Archive at https://lparchive.org/Old-LP on Jan 02, 2008.")


def test_missing_image_note_links_the_original_at_a_valid_uri():
    """The note's link is the picture's URL, which can hold spaces too ("setz/Advent Rising/ethan6.jpg");
    a URL that cannot be made valid gives a note without a link, and so does a picture inside a link (the
    author's, to a video, in La-Pucelle-Tactics and Long-Live-the-Queen): a link may not hold a link (epubcheck
    RSC-005, 2 books of the archive-wide run), and ebooklib's lxml re-parse leaves one nested through the <span>."""
    from ebooklib.utils import parse_html_string
    soup = BeautifulSoup('<div id="content"><img alt="Ethan" src="ethan6.jpg"/><img src="x.jpg"/>'
                         '<a href="http://v/"><img src="y.jpg"/></a></div>', "html.parser")
    spaced, garbage, linked = soup.find_all("img")
    lib.mark_unavailable(lib.Image(0, "ethan6.jpg", spaced, "http://www.miketyndall.com/setz/Advent Rising/ethan6.jpg", "http://x/"))
    lib.mark_unavailable(lib.Image(1, "x.jpg", garbage, "http://http:ustwo.com/x.jpg", "http://x/"))
    lib.mark_unavailable(lib.Image(2, "y.jpg", linked, "http://x/y.jpg", "http://x/"))
    assert str(soup) == ('<div id="content"><span class="missing-image">[image not available: Ethan - '
                         '<a href="http://www.miketyndall.com/setz/Advent%20Rising/ethan6.jpg">ethan6.jpg</a>]</span>'
                         '<span class="missing-image">[image not available: x.jpg]</span>'
                         '<a href="http://v/"><span class="missing-image">[image not available: y.jpg]</span></a></div>')
    assert _nested_links(parse_html_string(str(soup))) == []


def test_thread_link_is_written_as_a_valid_uri_or_dropped():
    from lparchive2epub.cover import make_title_page

    def intro_with(thread_href: str):
        html = f"""<html><head><title>Old LP</title><meta name="author" content="Someone"/></head><body>
        <ul id="statistics"><li id="archival">Added to the archive on <strong>Jan 02, 2008</strong></li></ul>
        <p id="thread">Original Thread: <a id="threadlink" href="{thread_href}">The thread</a></p>
        <div id="content">hello</div></body></html>"""
        return Extractor.intro("https://lparchive.org/Old-LP", BeautifulSoup(html, "html.parser"))

    intro = intro_with("http://forums.example.com/show thread.php?threadid=1 ")
    assert intro.thread_url == "http://forums.example.com/show%20thread.php?threadid=1"
    page = make_title_page(intro, "https://lparchive.org/Old-LP", "")
    assert '<a href="http://forums.example.com/show%20thread.php?threadid=1">The thread</a>' in page

    intro = intro_with("http://http:forums.example.com/")
    assert (intro.thread_url, intro.thread_title) == (None, "The thread")
    page = make_title_page(intro, "https://lparchive.org/Old-LP", "")
    assert "<p>Original thread: The thread</p>" in page and "http:forums" not in page

    # page-relative on the 27 LPs of the Devolution megathread: in the book it would name a file that
    # does not exist (epubcheck RSC-007), so it is resolved against the LP's URL
    intro = intro_with("/Devolution/")
    assert intro.thread_url == "https://lparchive.org/Devolution/"
    page = make_title_page(intro, "https://lparchive.org/Old-LP", "")
    assert '<a href="https://lparchive.org/Devolution/">The thread</a>' in page
    assert intro_with("mailto:someone@example.com").thread_url == "mailto:someone@example.com"


def test_compose_description_and_dates():
    intro = Extractor.intro("https://lparchive.org/X-COM-Terror-from-the-Deep", BeautifulSoup(xcom, "html.parser"))
    assert compose_description(intro, "https://lparchive.org/X-COM-Terror-from-the-Deep") == (
        "Let's Play of X-COM: Terror from the Deep by GuavaMoment. "
        "18 updates posted between Oct 26, 2009 and Apr 09, 2010. "
        "Archived by The Let's Play Archive at https://lparchive.org/X-COM-Terror-from-the-Deep on May 14, 2010. "
        "Original thread: http://forums.somethingawful.com/showthread.php?threadid=3220122")
    headshoots_intro = Extractor.intro("https://lparchive.org/Dwarf-Fortress-Headshoots", BeautifulSoup(headshoots, "html.parser"))
    assert "90 updates posted on Apr 25, 2009." in compose_description(headshoots_intro, "u")
    assert parse_lp_date("Apr 09, 2010") == datetime.datetime(2010, 4, 9)
    assert parse_lp_date("not a date") is None and parse_lp_date(None) is None


@pytest.mark.asyncio
async def test_book_carries_dublin_core_metadata_from_the_landing_page():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    session = _FakeSession("never-matches")
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, lambda *_: None), timeout=30)
        with zipfile.ZipFile(out) as z:
            opf = z.read("EPUB/content.opf").decode()
    assert "<dc:title>X-COM: Terror from the Deep</dc:title>" in opf
    assert ">GuavaMoment</dc:creator>" in opf
    assert "<dc:publisher>The Let's Play Archive</dc:publisher>" in opf
    assert "<dc:date>2010-04-09</dc:date>" in opf
    assert "<dc:description>Let's Play of X-COM: Terror from the Deep by GuavaMoment. 18 updates posted between" in opf
    assert re.findall(r"<dc:subject>([^<]+)</dc:subject>", opf) == ["Let's Play", "hybrid", "voice"]
    assert "<dc:relation>http://forums.somethingawful.com/showthread.php?threadid=3220122</dc:relation>" in opf
    assert f"<dc:source>{url}</dc:source>" in opf
    assert 'property="dcterms:modified">2010-05-14T00:00:00Z' in opf


def _make_image(fmt: str, size=(3000, 1000), mode="RGB", **save_kwargs) -> bytes:
    from PIL import Image as PILImage, ImageDraw
    image = PILImage.new(mode, size, (200, 30, 30) if mode == "RGB" else (200, 30, 30, 128) if mode == "RGBA" else 128)
    draw = ImageDraw.Draw(image)
    for x in range(0, size[0], 97):  # some structure, so JPEG has something to encode
        draw.line([(x, 0), (size[0] - x, size[1])], fill=(10, 10, 200) if mode == "RGB" else (10, 10, 200, 255) if mode == "RGBA" else 20, width=5)
    out = io.BytesIO()
    image.save(out, fmt, **save_kwargs)
    return out.getvalue()


def _dimensions(data: bytes):
    from PIL import Image as PILImage
    return PILImage.open(io.BytesIO(data)).size


def test_reduce_image_shrinks_and_reencodes_as_promised():
    settings = ImageProcessing(max_size=1600, jpeg_quality=80)

    big_jpeg = _make_image("JPEG", (3000, 1000), quality=95)
    data, media_type, ext = reduce_image(big_jpeg, "image/jpeg", settings)
    assert (media_type, ext) == ("image/jpeg", "jpg")
    assert _dimensions(data) == (1600, 533) and len(data) < len(big_jpeg)

    small_jpeg = _make_image("JPEG", (800, 600))
    assert reduce_image(small_jpeg, "image/jpeg", settings) is None  # fits: never re-encoded (generation loss)

    # a noisy picture, like a photo: flat synthetic images compress better before resizing than after
    from PIL import Image as PILImage
    noise = PILImage.frombytes("RGBA", (2000, 2500), random.Random(0).randbytes(2000 * 2500 * 4))
    buffer = io.BytesIO()
    noise.save(buffer, "PNG")
    big_png = buffer.getvalue()
    data, media_type, ext = reduce_image(big_png, "image/png", settings)
    assert (media_type, ext) == ("image/png", "png")
    assert _dimensions(data) == (1280, 1600) and len(data) < len(big_png)

    small_png = _make_image("PNG", (300, 200), optimize=True)
    assert reduce_image(small_png, "image/png", settings) is None   # already optimised and fits: untouched

    webp = _make_image("WEBP", (400, 300))
    data, media_type, ext = reduce_image(webp, "image/webp", settings)
    assert (media_type, ext) == ("image/jpeg", "jpg") and _dimensions(data) == (400, 300)

    webp_alpha = _make_image("WEBP", (400, 300), mode="RGBA")
    data, media_type, ext = reduce_image(webp_alpha, "image/webp", settings)
    assert (media_type, ext) == ("image/png", "png")

    bmp = _make_image("BMP", (400, 300))
    data, media_type, ext = reduce_image(bmp, "image/bmp", settings)
    assert (media_type, ext) == ("image/png", "png") and len(data) < len(bmp)   # lossless, like TIFF: screenshots

    assert reduce_image(GIF_BYTES, "image/gif", settings) is None          # GIFs are never touched
    assert reduce_image(b"\x89PNG\r\n\x1a\ncorrupted", "image/png", settings) is None  # undecodable: kept


def test_reduce_image_turns_tiff_and_bmp_into_png():
    tiff = _make_image("TIFF", (40, 30), mode="RGBA")
    assert tiff.startswith((b"II*\x00", b"MM\x00*"))
    data, media_type, extension = reduce_image(tiff, "image/tiff", ImageProcessing(max_size=1600))
    assert (media_type, extension) == ("image/png", "png") and data.startswith(b"\x89PNG")
    data, media_type, extension = lib.convert_for_readers(_make_image("TIFF", (3000, 1000)), "image/tiff")
    from PIL import Image as PILImage
    assert media_type == "image/png" and PILImage.open(io.BytesIO(data)).size == (3000, 1000)   # full size: not a resize

    # BMP (RSC-032 in 11 books of the archive run): PNG too, lossless, even without alpha (a screenshot)
    bmp = _make_image("BMP", (40, 30))
    assert bmp.startswith(b"BM") and lib.detect_image_type(bmp) == ("image/bmp", "bmp")
    assert "image/bmp" in lib.UNREADABLE_TYPES
    data, media_type, extension = lib.convert_for_readers(bmp, "image/bmp")
    assert (media_type, extension) == ("image/png", "png") and data.startswith(b"\x89PNG")
    converted = PILImage.open(io.BytesIO(data))
    assert converted.size == (40, 30)
    assert converted.convert("RGB").tobytes() == PILImage.open(io.BytesIO(bmp)).convert("RGB").tobytes()   # same pixels


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt, mode, name, old_suffixes, old_type", [
    ("TIFF", "RGBA", "1-map14.tiff.", (".tiff", ".tif"), "image/tiff"),   # X-COM-Terror-from-the-Deep's maps
    ("BMP", "RGB", "Tie%201.bmp", (".bmp",), "image/bmp"),                # Tie-Fighter's screenshot, no alpha
])
async def test_tiff_and_bmp_end_up_in_the_book_as_png_even_without_image_processing(fmt, mode, name, old_suffixes, old_type):
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    page = f"{url}/Update%2001/"
    session = _FakeSession("never-matches", responses={
        f"{page}{name}": _FakeResponse(200, _make_image(fmt, (60, 40), mode=mode), "application/octet-stream")})
    session.responses[page] = _FakeResponse(200, f'<div id="content"><img src="{name}"/></div>'.encode())
    for processing in (None, ImageProcessing(max_size=1600)):
        messages = []
        with tempfile.TemporaryDirectory() as d:
            await asyncio.wait_for(do(url, f"{d}/book.epub", session, messages.append, image_processing=processing), timeout=30)
            with zipfile.ZipFile(f"{d}/book.epub") as z:
                names = z.namelist()
                opf = z.read("EPUB/content.opf").decode()
                chapter = z.read("EPUB/update_0.xhtml").decode()
                assert "missing-image" not in chapter
                shown = re.search(r'src="(images/[0-9a-f]+\.png)"', chapter).group(1)   # the map, now a PNG
                from PIL import Image as PILImage
                converted = PILImage.open(io.BytesIO(z.read(f"EPUB/{shown}")))
                assert converted.format == "PNG" and converted.size == (60, 40)
        assert not any(n.endswith(old_suffixes) for n in names) and old_type not in opf
        assert not any("could not be retrieved" in m for m in messages)


def test_reduce_image_leaves_animated_gifs_alone_even_when_asked_about_png():
    from PIL import Image as PILImage
    frames = [PILImage.new("P", (2000, 2000), i) for i in range(3)]
    out = io.BytesIO()
    frames[0].save(out, "GIF", save_all=True, append_images=frames[1:])
    assert reduce_image(out.getvalue(), "image/gif", ImageProcessing(1600)) is None


def test_reduce_image_applies_exif_orientation():
    from PIL import Image as PILImage
    image = PILImage.new("RGB", (3000, 1000), (0, 0, 0))
    exif = PILImage.Exif()
    exif[0x0112] = 6  # rotate 90 degrees clockwise
    out = io.BytesIO()
    image.save(out, "JPEG", exif=exif)
    data, _, _ = reduce_image(out.getvalue(), "image/jpeg", ImageProcessing(1600))
    assert _dimensions(data) == (533, 1600)


@pytest.mark.asyncio
async def test_max_image_size_option_reduces_images_in_the_book_and_reports_it():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    big_jpeg = _make_image("JPEG", (3200, 2400), quality=95)
    webp = _make_image("WEBP", (500, 400))
    session = _FakeSession("never-matches", responses={
        f"{url}/Update%2001/": _FakeResponse(200, b'<div id="content"><img src="huge.jpg"/><img src="pic.webp"/><img src="tiny.png"/></div>'),
        f"{url}/Update%2001/huge.jpg": _FakeResponse(200, big_jpeg),
        f"{url}/Update%2001/pic.webp": _FakeResponse(200, webp),
        f"{url}/Update%2001/tiny.png": _FakeResponse(200, PNG_BYTES),  # not decodable: kept as is
    })
    messages = []
    processing = ImageProcessing(max_size=1600, jpeg_quality=80)
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, messages.append, image_processing=processing), timeout=60)
        with zipfile.ZipFile(out) as z:
            opf = z.read("EPUB/content.opf").decode()
            chapter = z.read("EPUB/update_0.xhtml").decode()
            images = {n: z.read(n) for n in z.namelist() if n.startswith("EPUB/images/") and "cover" not in n}
    jpegs = [n for n, data in images.items() if n.endswith(".jpg")]
    assert len(jpegs) == 2 and all(max(_dimensions(images[n])) <= 1600 for n in jpegs)
    assert not any(n.endswith(".webp") for n in images) and "image/webp" not in opf
    assert sum(len(d) for d in images.values()) < len(big_jpeg)
    assert all(f'src="{n.removeprefix("EPUB/")}"' in chapter for n in jpegs)
    assert processing.seen >= 3 and processing.changed == 2 and processing.bytes_out < processing.bytes_in
    assert any(m.startswith("Images: 2 of ") and "MB -> " in m for m in messages)


@pytest.mark.asyncio
async def test_without_the_option_images_are_kept_byte_for_byte():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    big_jpeg = _make_image("JPEG", (3200, 2400), quality=95)
    session = _FakeSession("never-matches", responses={
        f"{url}/Update%2001/": _FakeResponse(200, b'<div id="content"><img src="huge.jpg"/></div>'),
        f"{url}/Update%2001/huge.jpg": _FakeResponse(200, big_jpeg),
    })
    messages = []
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, messages.append), timeout=60)
        with zipfile.ZipFile(out) as z:
            stored = [z.read(n) for n in z.namelist() if n.endswith(".jpg") and "cover" not in n]
    assert stored == [big_jpeg]
    assert not any(m.startswith("Images:") for m in messages)


def test_cli_image_flags(monkeypatch):
    seen = {}

    async def fake(url, *args, **kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(cli, "lparchive2epub", fake)
    cli.main(["https://lparchive.org/Some-LP", "out.epub"])
    assert seen["image_processing"] is None
    cli.main(["--max-image-size", "1600", "--jpeg-quality", "70", "https://lparchive.org/Some-LP", "out.epub"])
    assert (seen["image_processing"].max_size, seen["image_processing"].jpeg_quality) == (1600, 70)
    for bad in (["--max-image-size", "0"], ["--max-image-size", "big"], ["--jpeg-quality", "101"]):
        with pytest.raises(SystemExit) as exit_info:
            cli.main([*bad, "https://lparchive.org/Some-LP", "out.epub"])
        assert exit_info.value.code == 2


def _chapters_sharing_image(url: str, image_url: str, chapters=(1, 2, 3)):
    return {f"{url}/Update%200{n}/": _FakeResponse(200, f'<div id="content"><p>text {n}</p><img src="{image_url}"/></div>'.encode())
            for n in chapters}


class _FlakyImageSession(_FakeSession):
    """One image URL always answers 503; everything else as usual."""

    def __init__(self, dead_url: str):
        super().__init__("never-matches")
        self.dead_url = dead_url

    def get(self, url, **kwargs):
        if url == self.dead_url:
            self.requested.append(url)
            return _FakeResponse(503, b"down")
        return super().get(url, **kwargs)


@pytest.mark.asyncio
async def test_registry_remembers_a_failed_image_for_the_whole_run(monkeypatch):
    monkeypatch.setattr(lib, "RETRY_BACKOFF_BASE", 0)
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    dead = "http://img.example/dead.png"
    session = _FlakyImageSession(dead)
    session.responses.update(_chapters_sharing_image(url, dead))
    messages = []
    with tempfile.TemporaryDirectory() as d:
        await asyncio.wait_for(do(url, f"{d}/book.epub", session, messages.append), timeout=30)
    # one download attempt (with its 5 retries) for the whole run, not one per referencing chapter
    assert session.requested.count(dead) == 5
    report = "\n".join(messages)
    assert "status code: 503" in report
    # ...but every page that needed it is still listed
    for n in (1, 2, 3):
        assert f"page:   {url}/Update%200{n}/" in report


@pytest.mark.asyncio
async def test_registry_remembers_a_404_image_too():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    missing = f"{url}/Update%2001/missing.png"
    session = _FakeSession("never-matches", responses={missing: _FakeResponse(404, b"gone")})
    session.responses.update(_chapters_sharing_image(url, missing))
    with tempfile.TemporaryDirectory() as d:
        await asyncio.wait_for(do(url, f"{d}/book.epub", session, lambda *_: None), timeout=30)
    assert session.requested.count(missing) == 1


@pytest.mark.asyncio
async def test_identical_bytes_under_different_urls_are_processed_and_stored_once(monkeypatch):
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    picture = _make_image("JPEG", (3200, 2400), quality=95)
    urls = [f"{url}/Update%200{n}/same-{n}.jpg" for n in (1, 2, 3)]
    session = _FakeSession("never-matches", responses={u: _FakeResponse(200, picture) for u in urls})
    for n, u in zip((1, 2, 3), urls):
        session.responses[f"{url}/Update%200{n}/"] = _FakeResponse(
            200, f'<div id="content"><img src="same-{n}.jpg"/><a href="same-{n}.jpg">full</a></div>'.encode())

    calls = []
    real_reduce = lib.reduce_image

    def counting_reduce(content, media_type, settings):
        calls.append(media_type)
        return real_reduce(content, media_type, settings)

    monkeypatch.setattr(lib, "reduce_image", counting_reduce)
    processing = ImageProcessing(max_size=1600)
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, lambda *_: None, image_processing=processing), timeout=60)
        with zipfile.ZipFile(out) as z:
            images = [n for n in z.namelist() if n.startswith("EPUB/images/") and n.endswith(".jpg") and "cover" not in n]
            pages = [z.read(f"EPUB/update_{i}.xhtml").decode() for i in range(3)]

    assert [session.requested.count(u) for u in urls] == [1, 1, 1]   # each URL still downloaded once
    assert calls.count("image/jpeg") == 1                            # resized once, not three times
    assert len(images) == 1                                          # stored once
    stored = images[0].removeprefix("EPUB/")
    image_page = "image_" + stored.removeprefix("images/").removesuffix(".jpg") + ".xhtml"
    for page in pages:                                               # every page's links rewritten to it
        assert f'src="{stored}"' in page and f'href="{image_page}"' in page
    assert processing.changed == 3   # each download is accounted for in the report (plus the intro's image)


def test_cache_path_resolution_and_checks():
    with tempfile.TemporaryDirectory() as d:
        # resolve_cache_path returns os.path.abspath: on Windows the separator becomes a backslash
        assert resolve_cache_path(f"{d}/lp") == os.path.join(d, "lp.sqlite")
        assert resolve_cache_path(f"{d}/lp.db") == os.path.join(d, "lp.db")
        created = check_cache_path(f"{d}/lp")
        assert created == os.path.join(d, "lp.sqlite") and os.path.exists(created)
        with pytest.raises(CacheError, match="is a directory"):
            check_cache_path(d)
        with pytest.raises(CacheError, match="does not exist"):
            check_cache_path(f"{d}/nope/lp")
        with open(f"{d}/text.sqlite", "w") as f:
            f.write("this is not a database, it is a text file with enough bytes to have a header")
        with pytest.raises(CacheError, match="not a SQLite database"):
            check_cache_path(f"{d}/text.sqlite")
        import sqlite3
        holder = sqlite3.connect(created)
        holder.execute("BEGIN IMMEDIATE")
        try:
            with pytest.raises(CacheError, match="locked by another run") as exc_info:
                check_cache_path(created)
            assert exc_info.value.exit_code == EXIT_CACHE
        finally:
            holder.rollback()
            holder.close()


def test_cli_cache_flag(monkeypatch, capsys):
    seen = {}

    async def fake(url, file, session=None, *args, **kwargs):
        seen["session"] = session
        if session is not None:
            await session.close()

    monkeypatch.setattr(cli, "lparchive2epub", fake)
    cli.main(["https://lparchive.org/Some-LP", "out.epub"])
    assert type(seen["session"]) is aiohttp.ClientSession   # a plain session: no cache unless asked
    assert seen["session"].timeout.sock_read == 60          # a stalled host doesn't park a worker for minutes
    with tempfile.TemporaryDirectory() as d:
        cli.main(["--cache", f"{d}/lp", "https://lparchive.org/Some-LP", "out.epub"])
        assert isinstance(seen["session"], CachedSession) and isinstance(seen["session"].cache, SQLiteBackend)
        assert os.path.exists(f"{d}/lp.sqlite")
        assert f"using cache {os.path.join(d, 'lp.sqlite')}" in capsys.readouterr().err
        with pytest.raises(SystemExit) as exit_info:
            cli.main(["--cache", d, "https://lparchive.org/Some-LP", "out.epub"])
        assert exit_info.value.code == EXIT_CACHE
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--no-cache", "https://lparchive.org/Some-LP", "out.epub"])
    assert exit_info.value.code == 2


def _mini_lp_app(hits: list):
    """A tiny Let's Play served by aiohttp: the X-COM landing page, 18 small updates, one image each."""
    from aiohttp import web

    async def handler(request: web.Request):
        path = request.path
        hits.append(path)
        if path.rstrip("/") == "/X-COM-Terror-from-the-Deep":
            return web.Response(body=xcom, content_type="text/html")
        if path.endswith((".jpg", ".png")):
            return web.Response(body=PNG_BYTES + path.encode(), content_type="image/png")
        number = re.search(r"/Update (\d+)/$", path)
        if number and int(number.group(1)) <= 18:   # like the site: 18 updates, then 404
            return web.Response(body=f'<div id="content"><p>{path}</p><img src="shot.png"/></div>'.encode(),
                                content_type="text/html")
        return web.Response(status=404)

    app = web.Application()
    app.router.add_get("/{tail:.*}", handler)
    return app


@pytest.mark.asyncio
async def test_sqlite_cache_makes_a_second_build_free_of_requests():
    from aiohttp.test_utils import TestServer
    hits = []
    server = TestServer(_mini_lp_app(hits))
    await server.start_server()
    try:
        url = str(server.make_url("/X-COM-Terror-from-the-Deep"))
        with tempfile.TemporaryDirectory() as d:
            cache_file = check_cache_path(f"{d}/cache")

            async def build(session, out):
                async with session:
                    await asyncio.wait_for(do(url, out, session, lambda *_: None), timeout=60)
                with open(out, "rb") as f:
                    return f.read()

            def cached():
                return CachedSession(cache=SQLiteBackend(cache_file, expire_after=-1, fast_save=True, autoclose=True))

            def served():   # the probe for a 19th update answers 404, which is never cached: not counted
                return [h for h in hits if "Update 19" not in h]

            first = await build(cached(), f"{d}/one.epub")
            first_hits = len(served())
            assert first_hits >= 1 + 18 + 18   # landing page, 18 updates, 18 images

            second = await build(cached(), f"{d}/two.epub")
            assert len(served()) == first_hits    # everything came from the cache
            assert second == first                # and the book is the same

            await build(aiohttp.ClientSession(), f"{d}/three.epub")
            assert len(served()) == 2 * first_hits    # without the cache, everything is fetched again
    finally:
        await server.close()


FRONT_PAGE_SNIPPET = """<html><body><script>var x = 1;</script><script>
  tocdata=[{'t':'Space Quest 1','a':'Son of Bug Jug','u':'/Space-Quest-Series/','ty':'1','tg':['screenshot']},
           {'t':'Space Quest 2','a':'Son of Bug Jug','u':'/Space-Quest-Series/','ty':'1','tg':['screenshot']},
           {'t':'007: Nightfire','a':'ThornBrain','u':'/007-Nightfire/','ty':'2','tg':['video']}];
  other = 2;</script></body></html>"""


def test_snapshot_index_groups_series_pages_and_sorts():
    from util.snapshot_landing_pages import read_index
    index = read_index(FRONT_PAGE_SNIPPET)
    assert [e["slug"] for e in index] == ["007-Nightfire", "Space-Quest-Series"]
    series = index[1]
    assert series["url"] == "https://lparchive.org/Space-Quest-Series"
    assert [listing["title"] for listing in series["listed_as"]] == ["Space Quest 1", "Space Quest 2"]
    assert series["type"] == "1" and series["tags"] == ["screenshot"]


def test_snapshot_zip_is_deterministic_and_lists_failures():
    from util.snapshot_landing_pages import read_index, write_zip
    index = read_index(FRONT_PAGE_SNIPPET)
    pages = {"007-Nightfire": b"<html>nightfire</html>"}
    failures = {"Space-Quest-Series": "Failed to get resource ..., status code: 404"}
    with tempfile.TemporaryDirectory() as d:
        a, b = f"{d}/a.zip", f"{d}/b.zip"
        write_zip(__import__("pathlib").Path(a), index, pages, failures)
        write_zip(__import__("pathlib").Path(b), index, pages, failures)
        with open(a, "rb") as fa, open(b, "rb") as fb:
            assert fa.read() == fb.read()
        with zipfile.ZipFile(a) as z:
            assert z.namelist() == ["index.json", "landing_pages/007-Nightfire.html"]
            manifest = json.loads(z.read("index.json"))
            by_slug = {e["slug"]: e for e in manifest["lets_plays"]}
            assert by_slug["007-Nightfire"]["file"] == "landing_pages/007-Nightfire.html"
            assert by_slug["Space-Quest-Series"]["file"] is None
            assert "404" in by_slug["Space-Quest-Series"]["error"]
            assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in z.infolist())


def test_landing_page_snapshot_is_complete_and_parses():
    """The archive snapshot used by the archive-wide tests: every indexed page is present and is an LP page."""
    path = os.path.join(os.path.dirname(__file__), "resources", "landing_pages.zip")
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("index.json"))
        entries = manifest["lets_plays"]
        assert len(entries) > 2500
        assert all(e["file"] for e in entries), [e["slug"] for e in entries if not e["file"]]
        assert set(z.namelist()) == {"index.json", *(e["file"] for e in entries)}
        sample = z.read(entries[0]["file"])
    assert b'id="content"' in sample and b'id="archival"' in sample


SNAPSHOT = os.path.join(os.path.dirname(__file__), "resources", "landing_pages.zip")


def snapshot_page(slug: str) -> BeautifulSoup:
    with zipfile.ZipFile(SNAPSHOT) as z:
        return BeautifulSoup(z.read(f"landing_pages/{slug}.html"), "html.parser")


def test_chapter_slug_rules():
    base = "https://lparchive.org/Some-LP/"
    slug = Extractor.chapter_slug
    assert slug(base, "Update%2001/") == "Update%2001/"
    assert slug(base, "Update%2001") == "Update%2001/"              # no trailing slash
    assert slug(base, "Update%2012.5/") == "Update%2012.5/"         # a dot inside a number is not an extension
    assert slug(base, "Update%2012.5") == "Update%2012.5/"
    assert slug(base, "Update%2045/#FAQ") == "Update%2045/"         # fragment dropped
    assert slug(base, "Dive%201") == "Dive%201/"                     # any name, not just "Update"
    assert slug(base, "https://lparchive.org/Some-LP/Epilogue/") == "Epilogue/"
    assert slug(base, "/Some-LP/Cast/") == "Cast/"
    for not_a_chapter in ("", "#top", "../", "/", "https://lparchive.org/Some-LP/", "/Other-LP/",
                          "https://lparchive.org/Other-LP/Update%201/", "http://example.com/Update%201/",
                          "Images/map.png", "map.png", "notes.html", "197-9rO6g.", "12-Saintskoden.",
                          "Update%201/map.png", "Update%201/sub/", "Update%201?x=1", "mailto:a@b.c",
                          "javascript:void(0)"):
        assert slug(base, not_a_chapter) is None, not_a_chapter


def test_all_chapters_is_structural_deduplicated_and_in_document_order():
    html = """<div id="content">
      <p>Skip to <a href="Update%203/">the good part</a> or read the <a href="Cast/">cast</a> first.</p>
      <ul class="toc">
        <li><a href="Prologue/">Prologue</a></li>
        <li><a href="Update%201/">Update 1</a></li>
        <li><a href="Update%202/"></a></li>
        <li><a href="Update%203/">Update 3</a> (<a href="Update%203/#part2">part 2</a>)</li>
        <li><a href="Update%203.5/">Interlude</a></li>
        <li><a href="Update%203/Images/map.png">map</a></li>
      </ul>
      <p>Also: <a href="../">index</a>, <a href="/Other-LP/">another LP</a>, <a href="https://example.com/">site</a>,
         <a href="#top">top</a>, <a href="Epilogue">Epilogue</a>, <a href="Update%201/">Update 1 again</a></p>
    </div>"""
    chapters = Extractor.all_chapters("https://lparchive.org/Some-LP", BeautifulSoup(html, "html.parser"))
    # "Update 3" is mentioned in the prose and listed in the toc: the toc decides its place and its title;
    # "Cast" is only mentioned in the prose and keeps its place
    assert [c.original_href_slug for c in chapters] == [
        "Cast/", "Prologue/", "Update%201/", "Update%202/", "Update%203/", "Update%203.5/", "Epilogue/"]
    assert [c.txt for c in chapters] == ["cast", "Prologue", "Update 1", "Update 2", "Update 3", "Interlude", "Epilogue"]
    assert [c.num for c in chapters] == list(range(7))
    assert [c.new_href for c in chapters][:2] == ["update_0.xhtml", "update_1.xhtml"]
    assert chapters[0].original_href == "https://lparchive.org/Some-LP/Cast/"


@pytest.mark.parametrize(("slug", "count", "first", "expected_somewhere"), [
    ("Dwarf-Fortress-Boatmurdered", 66, "Introduction/", ["Update%201-41/", "Update%202-1/"]),
    ("Arcanum", None, "Intro/", ["Epilogue/"]),
    ("Martian-Dreams", None, None, ["Cast/"]),
    ("Transistor-(by-Non-EuclideanCat)", None, None, ["Dive%201/", "Functions/"]),
    ("Empire-Total-War", None, "Update%2001/", ["QA%2035/"]),
    ("Advance-Wars", None, None, ["Update%2073.5/"]),
])
def test_chapters_found_without_a_hard_coded_list(slug, count, first, expected_somewhere):
    chapters = Extractor.all_chapters(f"https://lparchive.org/{slug}", snapshot_page(slug))
    slugs = [c.original_href_slug for c in chapters]
    assert len(slugs) == len(set(slugs))
    if count is not None:
        assert len(slugs) == count
    if first is not None:
        assert slugs[0] == first
    for expected in expected_somewhere:
        assert expected in slugs, expected


GOLDEN = os.path.join(os.path.dirname(__file__), "resources", "chapters.json")


def _golden():
    with open(GOLDEN, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def archive():
    """Every landing page of the archive with what the extractor must find on it."""
    golden = _golden()
    with zipfile.ZipFile(SNAPSHOT) as z:
        manifest = json.loads(z.read("index.json"))
        assert manifest["snapshot_date"] == golden["snapshot_date"], \
            "chapters.json was generated from another snapshot: rerun util/generate_chapter_golden.py"
        pages = {e["slug"]: z.read(e["file"]) for e in manifest["lets_plays"]}
    assert set(pages) == set(golden["lets_plays"])
    return pages, golden["lets_plays"]


@pytest.mark.archive
@pytest.mark.parametrize("slug", sorted(_golden()["lets_plays"]))
def test_every_landing_page_extracts_as_recorded(archive, slug):
    pages, expected = archive
    intro = Extractor.intro(f"https://lparchive.org/{slug}", BeautifulSoup(pages[slug], "html.parser"))
    want = expected[slug]
    facts = {"title": intro.title, "author": intro.author, "parts": intro.parts, "began": intro.began,
             "ended": intro.ended, "published_on": intro.published_on, "tags": intro.tags,
             "thread_url": intro.thread_url}
    assert facts == {k: want[k] for k in facts}
    assert [[c.original_href_slug, c.txt] for c in intro.chapters] == want["chapters"], \
        f"chapters of {slug} changed; if intended, rerun util/generate_chapter_golden.py and review the diff"
    assert [c.num for c in intro.chapters] == list(range(len(intro.chapters)))


def test_table_column_layout_is_dropped_so_the_page_validates():
    """<table><col width="99%"><tr>... is the archive's own markup on 386 landing pages; XHTML 5 allows
    <col> only inside <colgroup> and width on neither (epubcheck RSC-005 in 388 books of the archive-wide
    run). ebooklib re-parses every page with lxml before writing it and keeps <col> where it stands, so the
    check is made on that shape: what is written, not what bs4 saw."""
    from ebooklib.utils import parse_html_string
    html = ('<div id="content">'
            '<table><col width="99%"/><col width="1%"/><tr><td>a</td><td>b</td></tr></table>'
            '<table><colgroup><col span="2"/></colgroup><tr><td>c</td></tr></table>'
            '</div>')
    out = str(get_cleaned_html(html))
    assert "<table><tr><td>a</td><td>b</td></tr></table>" in out
    assert "<table><tr><td>c</td></tr></table>" in out
    assert "<col" not in out   # neither <col> nor <colgroup>

    with zipfile.ZipFile(SNAPSHOT) as z:   # 007-Everything-or-Nothing: three <table><col width="99%">
        page = z.read("landing_pages/007-Everything-or-Nothing.html").decode("utf-8")
    written = parse_html_string(str(get_cleaned_html(page)))
    assert written.findall(".//col") == [] and written.findall(".//colgroup") == []
    assert len(written.findall(".//table")) == 3


def _stray_list_content(tree) -> list[str]:
    """What sits directly inside a <ul>/<ol> of an lxml tree other than items: tag names, and "text"."""
    found = []
    for lst in tree.iter("ul", "ol"):
        if (lst.text or "").strip():
            found.append("text")
        for child in lst:
            if isinstance(child.tag, str) and child.tag not in ("li", "script", "template"):   # comments have no tag name
                found.append(child.tag)
            if (child.tail or "").strip():
                found.append("text")
    return found


def test_stray_content_in_lists_moves_into_items_so_the_page_validates():
    """Forum authors close </li> early or never open one, so a <ul> holds <br>s, text, <b>s, <img>s, headings or a
    whole nested <ul> between its items or before the first one; XHTML 5 allows nothing but <li> there (epubcheck
    RSC-005 "expected the element end-tag or element li" in 123 books of the archive-wide run) and neither bs4 nor
    ebooklib's lxml re-parse moves it. What follows an item joins it; what precedes the first item gets an unmarked
    item of its own, which is how browsers show stray text in a list: indented, without a bullet."""
    from ebooklib.utils import parse_html_string

    def clean(html: str) -> str:
        return str(get_cleaned_html(f'<div id="content">{html}</div>'))

    def untouched(html: str) -> str:
        return str(BeautifulSoup(f'<div id="content">{html}</div>', "html.parser"))

    # between and after items: the item's continuation (a nested list inside the item before it is how nested lists
    # are written, so the page looks the same)
    assert clean('<ul><li>a</li><br/>text<b>bold</b><ul><li>nested</li></ul></ul>') == \
        '<div id="content"><ul><li>a<br/>text<b>bold</b><ul><li>nested</li></ul></li></ul></div>'
    assert clean('<ol><li>a</li><h2>Heading</h2><div>d</div><img src="x.png"/><li>b</li>tail</ol>') == \
        '<div id="content"><ol><li>a<h2>Heading</h2><div>d</div><img src="x.png"/></li><li>btail</li></ol></div>'
    # before the first item: an item without a bullet
    assert clean('<ol><b>Intro</b><br/>text<li>a</li></ol>') == \
        '<div id="content"><ol><li style="list-style-type: none;"><b>Intro</b><br/>text</li><li>a</li></ol></div>'
    # a list used as an indent, with no item at all (Dragon-Warrior-I)
    assert clean('<ul> <b>A</b> interacts.<br/> <b>B</b> cancels. </ul>') == \
        '<div id="content"><ul> <li style="list-style-type: none;"><b>A</b> interacts.<br/> <b>B</b> cancels. </li></ul></div>'
    # a list holding nothing but another list (Dead-Rising's table of contents): no phantom bullet
    assert clean('<ul class="bbc-list"> <ul class="toc"><li>x</li></ul> </ul>') == \
        '<div id="content"><ul class="bbc-list"> <li style="list-style-type: none;"><ul class="toc"><li>x</li></ul> </li></ul></div>'
    # the space between two moved words moves with them (a comment there is gone before: sanitize() drops them all);
    # between items, whitespace and <template> stay
    assert clean('<ul><li>a</li>\n<b>x</b> <!-- c --> <i>y</i>\n<li>b</li></ul>') == \
        '<div id="content"><ul><li>a<b>x</b>  <i>y</i>\n</li>\n<li>b</li></ul></div>'
    for fine in ('<ul>\n  <li>a</li>\n\n  <li>b</li>\n</ul>', '<ol><li>a</li><template>t</template></ol>'):
        assert clean(fine) == untouched(fine)

    # the shape ebooklib writes, after its lxml re-parse
    written = parse_html_string(clean('<ul><li>a</li><br/>text<b>bold</b><ul><li>nested</li></ul></ul>'
                                      '<ol><b>Intro</b><br/><li>a</li><h2>H</h2><img src="x.png"/></ol>'
                                      '<ul> <ul class="toc"><li>x</li></ul> </ul>'))
    assert _stray_list_content(written) == []
    assert len(written.findall(".//ul")) == 4 and len(written.findall(".//ol")) == 1   # two of them nested

    # real landing pages: Might-and-Magic (<br> and <ul> in <ul>, introduction.xhtml:276 of the archive-wide run) and
    # Quake, which shows nearly every shape at once: 23 nested lists, headings, pictures, line breaks and bare text
    with zipfile.ZipFile(SNAPSHOT) as z:
        for slug in ("Might-and-Magic", "Quake"):
            page = z.read(f"landing_pages/{slug}.html").decode("utf-8")
            as_served = parse_html_string(page)
            assert _stray_list_content(as_served), slug   # the page needs the fix
            written = parse_html_string(str(get_cleaned_html(page)))
            assert _stray_list_content(written) == [], slug
            lists = lambda tree: len(list(tree.iter("ul", "ol")))   # noqa: E731
            assert lists(written) == lists(as_served), slug   # every list is still there, none unwrapped


def _orphan_items(tree) -> list[str]:
    """The <li>s of an lxml tree that do not sit directly in a list, as "li in <parent>"."""
    return [f"li in {li.getparent().tag}" for li in tree.iter("li") if li.getparent().tag not in ("ul", "ol")]


def _blocks_in_phrasing(tree) -> list[str]:
    """The blocks (and items, rows, cells) of an lxml tree with an inline wrapper or a <pre> for an ancestor, as "h2 under b"."""
    from lparchive2epub.lib import BLOCK_TAGS, PHRASING_HOLDERS
    found = []
    for block in tree.iter(*BLOCK_TAGS, "li", "tr", "td", "th"):
        wrappers = [ancestor.tag for ancestor in block.iterancestors() if ancestor.tag in PHRASING_HOLDERS]
        if wrappers:
            found.append(f"{block.tag} under {wrappers[0]}")
    return found


def _nested_links(tree) -> list[str]:
    """The links of an lxml tree with a link for an ancestor, as "a under a"."""
    return [f"a under {next(p.tag for p in a.iterancestors() if p.tag == 'a')}" for a in tree.iter("a")
            if any(p.tag == "a" for p in a.iterancestors())]


def _unknown_markup(tree) -> list[str]:
    """The elements of an lxml tree XHTML 5 does not know, and the attributes it does not allow where they are,
    as "pan" and "frameborder on a"."""
    from lparchive2epub.lib import ELEMENT_ATTRIBUTES, GLOBAL_ATTRIBUTES, XHTML_TAGS
    found = []
    for element in tree.iter():
        if not isinstance(element.tag, str):
            continue   # a comment or a processing instruction
        if element.tag not in XHTML_TAGS:
            found.append(element.tag)
        for attribute in element.attrib:
            if attribute not in GLOBAL_ATTRIBUTES | ELEMENT_ATTRIBUTES.get(element.tag, set()):
                found.append(f"{attribute} on {element.tag}")
    return found


def test_orphan_items_get_a_list_so_the_page_validates():
    """Forum authors write <li> with no list around it, inside bold text, links and strike-throughs, and one after
    another without closing any; XHTML 5 wants every item directly in a <ul>/<ol> (epubcheck RSC-005 "element li not
    allowed here" in 70 books of the archive-wide run). sanitize() does what browsers do while parsing: an item that
    opens inside another closes it, a wrapper around items goes inside each of them, bare items get a <ul>."""
    from ebooklib.utils import parse_html_string

    def clean(html: str) -> str:
        return str(get_cleaned_html(f'<div id="content">{html}</div>'))

    # bare items get a list: the archive's own table of contents when the author wrote no <ul> (Second-Sight), items
    # in a table cell (Dwarf-Fortress-Syrupleaf)
    assert clean('<li>x</li> <li>y</li>') == '<div id="content"><ul><li>x</li> <li>y</li></ul></div>'
    assert clean('<!-- BEGIN_TOC --> <li>a</li> <li>b</li> <!-- END_TOC --> text <li>c</li>') == \
        '<div id="content"> <ul><li>a</li> <li>b</li></ul>  text <ul><li>c</li></ul></div>'   # the marker comments go too
    assert clean('<table><tr><td><li>x</li></td></tr></table>') == \
        '<div id="content"><table><tr><td><ul><li>x</li></ul></td></tr></table></div>'
    # a wrapper around items goes inside each of them; what else it held keeps a copy of it, which
    # nest_stray_list_content then makes an unmarked item (Ace-Combat-04) or the continuation of the item before
    assert clean('<ul><b><li>x</li></b><li>y</li></ul>') == '<div id="content"><ul><li><b>x</b></li><li>y</li></ul></div>'
    assert clean('<ul><strong>intro<br/><li>a</li></strong></ul>') == \
        '<div id="content"><ul><li style="list-style-type: none;"><strong>intro<br/></strong></li><li><strong>a</strong></li></ul></div>'
    assert clean('<ul class="toc"><a href="U1"><li>Chapter 1</li></a> <a href="U2"><li>Chapter 2</li></a></ul>') == \
        '<div id="content"><ul class="toc"><li><a href="U1">Chapter 1</a></li> <li><a href="U2">Chapter 2</a></li></ul></div>'
    assert clean('<font color="red"><li>x</li></font>') == \
        '<div id="content"><ul><li><span style="color: red;">x</span></li></ul></div>'
    assert clean('<b id="k">t<li>x</li><li>y</li></b>') == \
        '<div id="content"><b id="k">t</b><ul><li><b>x</b></li><li><b>y</b></li></ul></div>'   # one element per id
    # a whole list inside a wrapper, alone or not (Doom-WADs, Pathologic), at any depth: the same, by
    # unnest_blocks_from_inline, which used to unwrap the list, or turn the wrapper inside out around its items
    assert clean('<b>intro<ul><li>a</li></ul>outro</b>') == \
        '<div id="content"><b>intro</b><ul><li><b>a</b></li></ul><b>outro</b></div>'
    assert clean('<a href="u"><ol class="x"><li>a</li><li>b</li></ol></a>') == \
        '<div id="content"><ol class="x"><li><a href="u">a</a></li><li><a href="u">b</a></li></ol></div>'
    assert clean('<b><ul><li>a<ul><li>n</li></ul></li></ul></b>') == \
        '<div id="content"><ul><li><b>a</b><ul><li><b>n</b></li></ul></li></ul></div>'
    assert clean('<a href="u"><div><ul><li><p>x</p></li></ul></div></a>') == \
        '<div id="content"><ul><li><a href="u">x</a></li></ul></div>'   # the other blocks unwrapped, as ever
    # unclosed items: html.parser nests each in the one before, and the item that opens inside another closes it,
    # as in every browser, taking what follows it along (Killzone-3's strike-through in the middle of a list)
    assert clean('<ul><li>a<li>b</li>c</li></ul>') == '<div id="content"><ul><li>a</li><li>bc</li></ul></div>'
    assert clean('<ul><li>a<br/><s><li>b<br/><li>c</s><br/><li>d</ul>') == \
        '<div id="content"><ul><li>a<br/></li><li><s>b<br/></s></li><li><s>c</s><br/></li><li>d</li></ul></div>'

    # the shape ebooklib writes, after its lxml re-parse: it un-nests <li>a<li>b by itself, but the end tags bs4 writes
    # for the nesting make it close the enclosing list early when a nested list is involved (Angband, update 38),
    # dropping the items that follow into the page: the un-nesting has to happen before the page is serialised
    nested = '<div id="content"><ul><li>a<li>b<ul><li>n1<li>n2</ul>text<li>c</ul>after</div>'
    assert _orphan_items(parse_html_string(str(BeautifulSoup(nested, "html.parser")))) == ["li in div"]
    written = parse_html_string(str(get_cleaned_html(nested)))
    assert _orphan_items(written) == [] and _stray_list_content(written) == []
    outer, inner = written.findall(".//ul")
    assert ["".join(li.itertext()) for li in outer.findall("li")] == ["a", "bn1n2text", "c"] and outer.tail == "after"
    assert ["".join(li.itertext()) for li in inner.findall("li")] == ["n1", "n2"]

    # real landing pages, one per shape: bare items (Second-Sight), items in links (Final-Fantasy-VI), a list in a
    # bold wrapper (Doom-WADs), strike-throughs in the middle of a list of unclosed items (Killzone-3). Every word
    # of the content stays, in order: the fix moves markup, not text.
    with zipfile.ZipFile(SNAPSHOT) as z:
        for slug in ("Second-Sight", "Final-Fantasy-VI", "Doom-WADs", "Killzone-3"):
            page = z.read(f"landing_pages/{slug}.html").decode("utf-8")
            as_served = parse_html_string(page)
            written = parse_html_string(str(get_cleaned_html(page)))
            assert _orphan_items(as_served) or as_served.findall(".//b/ul"), slug   # the page needs the fix
            assert _orphan_items(written) == [] and _stray_list_content(written) == [], slug
            content = lambda tree: "".join(tree.find(".//div[@id='content']").itertext()).split()   # noqa: E731
            assert content(written) == content(as_served), slug


def _table_faults(tree) -> list[str]:
    """What breaks the table content model in an lxml tree: a part outside its home ("tr in div"), a table in a
    table, and what a table, a section or a row holds besides its parts (tag names, and "text")."""
    homes = {"tr": ("table", "thead", "tbody", "tfoot"), "td": ("tr",), "th": ("tr",),
             "thead": ("table",), "tbody": ("table",), "tfoot": ("table",)}
    allowed = {"table": ("caption", "colgroup", "thead", "tbody", "tfoot", "tr", "script", "template"),
               "thead": ("tr", "script", "template"), "tbody": ("tr", "script", "template"),
               "tfoot": ("tr", "script", "template"), "tr": ("td", "th", "script", "template")}
    found = []
    for part in tree.iter(*homes):
        if part.getparent().tag not in homes[part.tag]:
            found.append(f"{part.tag} in {part.getparent().tag}")
    for table in tree.iter("table"):
        if table.getparent().tag in ("table", "thead", "tbody", "tfoot", "tr"):
            found.append(f"table in {table.getparent().tag}")
    for holder in tree.iter(*allowed):
        if (holder.text or "").strip():
            found.append(f"text in {holder.tag}")
        for child in holder:
            if isinstance(child.tag, str) and child.tag not in allowed[holder.tag]:   # comments have no tag name
                found.append(f"{child.tag} in {holder.tag}")
            if (child.tail or "").strip():
                found.append(f"text in {holder.tag}")
    return found


def test_tables_are_repaired_so_the_page_validates():
    """Forum authors leave <tr>s and <td>s unclosed, write rows with no <table> around them inside <b>/<i>, cells
    straight into a table, pictures, text and paragraphs between the rows, and open <table> twice; XHTML 5 wants a
    table made of rows made of cells and nothing else (epubcheck RSC-005 in 17 books of the archive-wide run), and
    ebooklib's lxml re-parse leaves all of it as it stands but the plainest nesting. sanitize() does what browsers
    do while parsing: a part that opens inside another part closes it, a wrapper around rows goes inside the cells,
    bare cells get a row and bare rows a table, and whatever else a table holds goes just before it."""
    from ebooklib.utils import parse_html_string

    def clean(html: str) -> str:
        return str(get_cleaned_html(f'<div id="content">{html}</div>'))[len('<div id="content">'):-len('</div>')]

    # unclosed rows and cells, which html.parser nests ever deeper (Sonic-Advance, Yakuza: 9 of the 17 books), here
    # through an unclosed link too (I-Wanna-Be-The-Guy): lxml un-nests the plain case by itself, not through the link,
    # which stays with its own cell rather than going around the links of the cells that follow
    assert clean('<table><tr><td>a<td>b <tr><td>c<td>d</table>after') == \
        '<table><tr><td>a</td><td>b </td></tr><tr><td>c</td><td>d</td></tr></table>after'
    assert clean('<table><tr><td><a href="X">one<tr><td><a href="Y">two</a></table>') == \
        '<table><tr><td><a href="X">one</a></td></tr><tr><td><a href="Y">two</a></td></tr></table>'
    # rows with no table at all, in bold italics (Metal-Gear-Solid-3, The-Void): the wrappers go inside the cells and
    # the rows get a table; a wrapper around a whole table or a section, the same (Secret-of-Evermore, where
    # unnest_blocks_from_inline used to unwrap the table, or to put the wrapper around the rows)
    assert clean('<i><b><tr><td>x</td><td>y</td></tr> <tr><td>z</td></tr></b></i>after') == \
        '<table><tr><td><i><b>x</b></i></td><td><i><b>y</b></i></td></tr> <tr><td><i><b>z</b></i></td></tr></table>after'
    assert clean('<b><table><tr><td>x</td></tr></table></b>') == '<table><tr><td><b>x</b></td></tr></table>'
    assert clean('<a href="u"><table><tr><td>x</td><td><a href="v">y</a></td></tr></table></a>') == \
        '<table><tr><td><a href="u">x</a></td><td><a href="v">y</a></td></tr></table>'
    assert clean('<table><b><tbody><tr><td>x</td></tr></tbody></b></table>') == \
        '<table><tbody><tr><td><b>x</b></td></tr></tbody></table>'
    assert clean('<div><tbody><tr><td>x</td></tr></tbody></div>') == '<div><table><tbody><tr><td>x</td></tr></tbody></table></div>'
    # inner wrappers first: Secret-of-Evermore's <i><b>...<h1/><table>...</b></i>, where the <i> holds the table on
    # its own once the <b> is inside the cells (the heading is unwrapped, as every block in mixed content is)
    assert clean('<i><b>intro<br/><h1>h</h1><table><tr><td>a<td>b</table></b></i>after') == \
        '<i><b>intro<br/>h</b></i><table><tr><td><i><b>a</b></i></td><td><i><b>b</b></i></td></tr></table>after'
    assert clean('<a href="u"><b><p>x</p></b></a>') == '<p><a href="u"><b>x</b></a></p>'
    # cells with no row (Fahrenheit, Jedi-Academy, Dark-Forces-2), and with no table at all
    assert clean('<table><tr><td>a</td></tr><td>b</td> <td>c</td></table>') == \
        '<table><tr><td>a</td></tr><tr><td>b</td> <td>c</td></tr></table>'
    assert clean('<div><td>x</td></div>') == '<div><table><tr><td>x</td></tr></table></div>'
    # whatever else a table or a row holds goes just before the table, in order, where a browser shows it too
    # (Oracle-Series, Sonic-Adventure-2-Battle, Bioshock: pictures, headings, paragraphs, line breaks and text
    # between the rows); a wrapper around rows and strays goes inside the cells and around the strays
    assert clean('<table><img src="i.png"/><i>who</i> <tr><td>a</td></tr>text<br/><p>para</p><ul><li>l</li></ul></table>') == \
        '<img src="i.png"/><i>who</i> text<br/><p>para</p><ul><li>l</li></ul><table><tr><td>a</td></tr></table>'
    assert clean('<table><tr>intro<td>a</td><p>x</p></tr></table>') == 'intro<p>x</p><table><tr><td>a</td></tr></table>'
    assert clean('<table><tr><td>a</td></tr><b><tr><td>x</td></tr>stray</b></table>') == \
        '<b>stray</b><table><tr><td>a</td></tr><tr><td><b>x</b></td></tr></table>'
    assert clean('<b><ul>stray<li>x</li></ul></b>') == \
        '<ul><li style="list-style-type: none;"><b>stray</b></li><li><b>x</b></li></ul>'   # lists: the same, now
    # a table that opens inside a table closes it, as in a browser: Oracle-Series opens <table> twice and the rest of
    # the page sits in the outer one, which is left empty and goes; rows after an inner table get a table of their own
    assert clean('<table><table><tr><td>a</td></tr></table><br/>rest<table><tr><td>b</td></tr></table>') == \
        '<table><tr><td>a</td></tr></table><br/>rest<table><tr><td>b</td></tr></table>'
    assert clean('<table><tr><td>a</td></tr><table><tr><td>i</td></tr></table><tr><td>b</td></tr></table>') == \
        '<table><tr><td>a</td></tr></table><table><tr><td>i</td></tr></table><table><tr><td>b</td></tr></table>'
    # lists and tables in each other: an item in a table goes before it and gets its list, a row in a list gets its
    # table and goes into the item before it
    assert clean('<table><li>x</li><tr><td>a</td></tr></table>') == '<ul><li>x</li></ul><table><tr><td>a</td></tr></table>'
    assert clean('<ul><li>a</li><tr><td>x</td></tr></ul>') == '<ul><li>a<table><tr><td>x</td></tr></table></li></ul>'
    # well-formed tables are left alone (compared with bs4's own round trip, which drops the indentation), one nested
    # in a cell included
    for fine in ('<table>\n <caption>c</caption>\n <thead><tr><th>h</th></tr></thead>\n <tbody>\n  <tr><td>a</td></tr>\n'
                 ' </tbody>\n</table>', '<table><tr><td><table><tr><td>i</td></tr></table></td></tr></table>'):
        assert clean(fine) == str(BeautifulSoup(f'<div id="content">{fine}</div>', "html.parser"))[len('<div id="content">'):-6]

    # the shape ebooklib writes, after its lxml re-parse, which leaves every one of these as it stands
    for html in ('<table><tr><td><a href="X">one<tr><td><a href="Y">two</a></table>', '<b><tr><td>x</td></tr></b>',
                 '<table><b><tr><td>x</td></tr></b>stray<td>a</td></table>', '<i><b><table><tr><td>a</td></tr></table></b></i>'):
        assert _table_faults(parse_html_string(str(BeautifulSoup(html, "html.parser")))) or "<i>" in html, html
        written = parse_html_string(str(get_cleaned_html(f'<div id="content">{html}</div>')))
        assert _table_faults(written) == [] and written.findall(".//a//a") == [], html
        assert [t.getparent().tag for t in written.iter("table")] == ["div"], html

    # real landing pages, one or two per shape. Every word of the content stays, in order but for what is fostered
    # out from between the rows of Bioshock and Sonic-Adventure-2-Battle (before the table, where a browser shows it)
    inline = ("a", "b", "i", "u", "s", "em", "strong", "span", "small", "sub", "sup", "code")
    with zipfile.ZipFile(SNAPSHOT) as z:
        for slug in ("Legend-of-Zelda-Oracle-Series", "I-Wanna-Be-The-Guy", "Fahrenheit", "Sonic-Advance", "Bioshock",
                     "Sonic-Adventure-2-Battle", "Secret-of-Evermore", "Metal-Gear-Solid-3-Snake-Eater", "The-Void"):
            page = z.read(f"landing_pages/{slug}.html").decode("utf-8")
            soup = BeautifulSoup(page, "html.parser")
            as_written_before = parse_html_string(str(soup))
            assert [f for f in _table_faults(as_written_before) if f != "col in table"] \
                or soup.find("tr").find_parent(inline) is not None, slug   # the page needs the fix
            written = parse_html_string(str(get_cleaned_html(page)))
            assert _table_faults(written) == [] and written.findall(".//a//a") == [], slug
            assert [t.getparent().tag for t in written.iter("table") if t.getparent().tag in inline] == [], slug
            source = soup.find("div", id="content").get_text(" ").split()
            words = " ".join(written.find(".//div[@id='content']").itertext()).split()
            assert words == source or (slug in ("Bioshock", "Sonic-Adventure-2-Battle") and sorted(words) == sorted(source)), slug


def test_rules_and_blocks_hidden_in_void_elements_are_unnested_so_the_page_validates():
    """What unnest_blocks_from_inline missed (RSC-005 in 14 books of the archive-wide run). A <hr> inside bold text,
    a link or a <pre> (the forum's old [code] block, <pre>code:<hr>..., in 11 of them; a <pre> takes phrasing content
    only, like the wrappers, and so does a heading): not a block it knew, and one with no content to keep, so the
    holder is split around it. A heading inside a heading. And a bs4 quirk: after a void tag written without a slash (<img src="a">), html.parser takes the end of the next
    self-closed one of the same name (<img src="b" />) for a redundant </img> and ignores it, so that <img> stays
    open and holds what follows; the page reads the same, but the passes miss the blocks hidden in it
    (Ratchet-Clank-Future-A-Crack-In-Time: headings and lists in an <img> in an unclosed <b>), a link sees its
    thumbnail holding other pictures, and an <input> or <embed> would take a whole post with it when dropped."""
    from ebooklib.utils import parse_html_string
    from lparchive2epub.lib import VOID_TAGS

    def clean(html: str) -> str:
        return str(get_cleaned_html(f'<div id="content">{html}</div>'))[len('<div id="content">'):-len('</div>')]

    # a rule in a wrapper: the wrapper is split around it, each part a copy (the id on the first), the rule stays
    assert clean('<b>one<hr/>two</b>') == '<b>one</b><hr/><b>two</b>'
    assert clean('<b><hr/></b>') == '<hr/>'
    assert clean('<a href="u" id="k">one<hr/>two</a>') == '<a href="u" id="k">one</a><hr/><a href="u">two</a>'
    assert clean('<span><p>x</p><hr/></span>') == '<span>x</span><hr/>'   # the other blocks unwrapped, as ever
    assert clean('<b><ul><li>a<hr/>b</li></ul></b>') == '<ul><li><b>a</b><hr/><b>b</b></li></ul>'
    assert clean('<cite><p>x</p></cite>') == '<p><cite>x</cite></p>'      # every phrasing-only wrapper is looked at
    # a <pre> the same, its copies keeping the text as written; blocks in one are unwrapped, never moved into
    assert clean('<blockquote><pre>code:<hr/>\n\n  LICENCE\n</pre></blockquote>') == \
        '<blockquote><pre>code:</pre><hr/><pre>\n\n  LICENCE\n</pre></blockquote>'   # Bureaucracy
    assert clean('<pre class="c"><b>a<hr/>b</b></pre>') == '<pre class="c"><b>a</b></pre><hr/><pre class="c"><b>b</b></pre>'
    assert clean('<pre><h3>t</h3>\nx</pre>') == '<pre>t\nx</pre>'           # Duke-Nukem-3D
    assert clean('<b><pre>x</pre></b>') == '<pre><b>x</b></pre>'
    assert clean('<pre>a<ul><li>x</li></ul>b</pre>') == '<pre>a</pre><ul><li><pre>x</pre></li></ul><pre>b</pre>'
    # a heading the same; one that opens inside another closes it first, as in a browser: the archive's own heading
    # for an update whose author put markup in its title (Paladins-Quest, update 21)
    assert clean('<h3><strong>Part 22:</strong> Awesome</h1>(fudge)<h1>Bonus: Epilogue.</h3>\n<img src="a.gif"/>') == \
        '<h3><strong>Part 22:</strong> Awesome(fudge)</h3><h1>Bonus: Epilogue.</h1>\n<img src="a.gif"/>'
    assert clean('<h3>a<h1>b</h1>c</h3>') == '<h3>a</h3><h1>b</h1>c'
    assert clean('<h2><p>x</p></h2>') == '<h2>x</h2>' and clean('<h2>a<hr/>b</h2>') == '<h2>a</h2><hr/><h2>b</h2>'
    assert clean('<b><h2>t</h2></b>') == '<h2><b>t</b></h2>'   # a wrapper still goes into its one block
    # void elements html.parser left open: their children go right after them, before anything else is done
    quirk = '<img src="a.png"><img src="b.png"/><b>x<h2>t</h2>y</b>'
    assert BeautifulSoup(quirk, "html.parser").find_all("img")[1].find("h2") is not None   # the quirk, as of bs4 4.14
    assert clean(quirk) == '<img src="a.png"/><img src="b.png"/><b>xty</b>'
    assert clean('<br><br/><p>a</p>') == '<br/><br/><p>a</p>'
    assert clean('<input><input/>text') == 'text'   # the inputs go, not the text they held
    assert clean('<a href="full.png"><img src="t.png"><img src="u.png"/></a>') == \
        '<a href="full.png"><img src="t.png"/><img src="u.png"/></a>'

    # the shape ebooklib writes, after its lxml re-parse, which leaves a rule in a wrapper where it is
    for html in ('<b>one<hr/>two</b>', '<a href="u">one<hr/>two</a>', '<pre>code:<hr/>x</pre>', '<pre><h3>t</h3></pre>',
                 '<h3>a<h1>b</h1></h3>', quirk):
        assert _blocks_in_phrasing(parse_html_string(str(BeautifulSoup(html, "html.parser")))), html
        written = parse_html_string(str(get_cleaned_html(f'<div id="content">{html}</div>')))
        assert _blocks_in_phrasing(written) == [], html

    # the real landing pages, every word of them kept in order: Ratchet's headings and lists out of the bold text,
    # unwrapped like every block in mixed content; Duke-Nukem-3D's heading inside a <pre>
    content = lambda tree: "".join(tree.find(".//div[@id='content']").itertext()).split()   # noqa: E731
    with zipfile.ZipFile(SNAPSHOT) as z:
        for slug, open_voids in (("Ratchet-Clank-Future-A-Crack-In-Time", ["meta", "meta", "img", "img"]), ("Duke-Nukem-3D", ["meta", "meta"])):
            page = z.read(f"landing_pages/{slug}.html").decode("utf-8")
            as_served = BeautifulSoup(page, "html.parser")
            assert [v.name for v in as_served.find_all(VOID_TAGS) if v.contents] == open_voids, slug   # the head too
            assert _blocks_in_phrasing(parse_html_string(str(as_served))), slug   # the page needs the fix
            cleaned = get_cleaned_html(page)
            assert [v.name for v in cleaned.find_all(VOID_TAGS) if v.contents] == [], slug
            written = parse_html_string(str(cleaned))
            assert _blocks_in_phrasing(written) == [], slug
            assert content(written) == content(parse_html_string(page)), slug


def _images_without_source(tree) -> list[str]:
    """The <img>s of an lxml tree with no src, or a blank one, as "img without src"."""
    return ["img without src" for img in tree.iter("img") if not (img.get("src") or "").strip()]


def test_images_without_a_source_are_dropped_so_the_page_validates():
    """Forum smilies that lost their address (<img src="" alt="">, four on the landing page of Super-Ghouls-n-Ghosts,
    one in update 15 of Anachronox) and a </ul> typed inside an <img> tag, which html.parser, like a browser, ends
    before the src (Might-and-Magic). XHTML 5 wants a src at least one character long (epubcheck RSC-005 in 3 books of
    the archive-wide run); all_images skipped them already, but the tag stayed in the page. HTML says what such an
    element represents, its alt text when it has one and nothing otherwise, and that is what sanitize() leaves."""
    from ebooklib.utils import parse_html_string

    def clean(html: str) -> str:
        return str(get_cleaned_html(f'<div id="content">{html}</div>'))[len('<div id="content">'):-len('</div>')]

    assert clean('<p>a<img src=""/>b<img/>c<img src=" " alt=" "/>d</p>') == '<p>abcd</p>'
    assert clean('<p><img alt=":doom:"/></p>') == '<p>:doom:</p>'
    assert clean('<a href="U/"><img alt=":doom:"/></a>') == '<a href="U/">:doom:</a>'
    assert clean('<i>fun of <img alt="" border="0" src=""/>.</i>') == '<i>fun of .</i>'
    assert clean('<img alt="y" src="x.png"/>') == '<img alt="y" src="x.png"/>'   # a picture with an address stays
    # inside a list, the alt text left behind is stray content: moved into an item like any other
    assert clean('<ul><li>a</li><img alt="x"/></ul>') == '<ul><li>ax</li></ul>'

    # the real landing pages, after the lxml re-parse ebooklib writes them through
    with zipfile.ZipFile(SNAPSHOT) as z:
        for slug in ("Super-Ghouls-n-Ghosts-(by-Captain_duck)", "Might-and-Magic"):
            page = z.read(f"landing_pages/{slug}.html").decode("utf-8")
            assert _images_without_source(parse_html_string(page)), slug   # the page needs the fix
            written = parse_html_string(str(get_cleaned_html(page)))
            assert _images_without_source(written) == [], slug
    assert ":doom:" in clean(page)   # Might-and-Magic's smiley, as its alt text


def test_a_link_opened_inside_a_link_closes_it_so_the_page_validates():
    """A link may not hold a link (epubcheck RSC-005 "The a element must not appear inside a elements" in 4 books of
    the archive-wide run). Forum authors put [url=video] around the archive's [timg] thumbnail link (22 landing pages),
    forget a [/url], or open a link in bold text inside a link. A browser closes the outer link where the inner one
    opens, and reopens the inline wrappers between the two around what moves out; ebooklib's lxml re-parse does the
    same for a link directly in a link only. sanitize() does it for every nesting, in bs4, with the same result as
    lxml for the direct one (Laura-Bow's live checksum holds)."""
    from ebooklib.utils import parse_html_string
    from lxml import etree

    def clean(html: str) -> str:
        return str(get_cleaned_html(f'<div id="content">{html}</div>'))[len('<div id="content">'):-len('</div>')]

    assert clean('<a href="x"><b><a href="y">2</a></b></a>') == '<a href="x"><b></b></a><b><a href="y">2</a></b>'
    assert clean('<a href="x">1<b>3<a href="y">2</a>5</b>4</a>6') == '<a href="x">1<b>3</b></a><b><a href="y">2</a>5</b>46'
    assert clean('<a href="x">1<a href="y">2</a>3</a>') == '<a href="x">1</a><a href="y">2</a>3'
    # the id stays on the first part, the wrapper's copy keeps its class
    assert clean('<a href="x" id="k"><span class="c d"><a href="y">2</a></span></a>') == \
        '<a href="x" id="k"><span class="c d"></span></a><span class="c d"><a href="y">2</a></span>'
    # three deep (Tunnel-Rats: [url] around [url] around the thumbnail link), each closing the one before
    assert clean('<a href="1"><a href="2"><a href="3"><img src="t"/></a></a></a>') == \
        '<a href="1"></a><a href="2"></a><a href="3"><img src="t"/></a>'
    assert clean('<a href="x"><b><a href="y">2</a><i><a href="z">3</a></i></b></a>') == \
        '<a href="x"><b></b></a><b><a href="y">2</a><i><a href="z">3</a></i></b>'   # the third is in no link any more
    # a block between the two is unwrapped first (unnest_blocks_from_inline), so only wrappers are split
    assert clean('<a href="x"><p>1<b><a href="y">2</a></b></p></a>') == '<p><a href="x">1<b></b></a><b><a href="y">2</a></b></p>'

    # the shape ebooklib writes, after its lxml re-parse: the direct nesting it un-nests the same way, the others not
    direct = '<a href="x">1<a href="y">2</a>3</a>'
    body = lambda html: etree.tostring(parse_html_string(html).find(".//body"), method="html", encoding="unicode")   # noqa: E731
    assert _nested_links(parse_html_string(direct)) == [] and body(direct) == f"<body>{clean(direct)}</body>"
    for html in ('<a href="x"><b><a href="y">2</a></b></a>', '<a href="x">1<b>3<a href="y">2</a>5</b>4</a>6',
                 '<a href="x"><span><a href="y">2</a>3</span>4</a>'):
        assert _nested_links(parse_html_string(str(BeautifulSoup(html, "html.parser")))) == ["a under a"], html
        assert _nested_links(parse_html_string(str(get_cleaned_html(f'<div id="content">{html}</div>')))) == [], html

    # real landing pages, every word of them kept in order: nested through table cells (Captain-Novolin,
    # I-Wanna-Be-The-Guy) and list items (Ultima-VII-The-Black-Gate), which the table and list repairs un-nest
    # already (the outer link copied into each cell or item); directly (Laura-Bow, Blue-Stinger), which lxml
    # un-nested already, every link still there
    content = lambda tree: "".join(tree.find(".//div[@id='content']").itertext()).split()   # noqa: E731
    with zipfile.ZipFile(SNAPSHOT) as z:
        for slug in ("Captain-Novolin", "I-Wanna-Be-The-Guy", "Ultima-VII-The-Black-Gate", "Laura-Bow-The-Colonels-Bequest", "Blue-Stinger"):
            page = z.read(f"landing_pages/{slug}.html").decode("utf-8")
            as_served = BeautifulSoup(page, "html.parser")
            assert any(a.find_parent("a") for a in as_served.find_all("a")), slug   # the page has the nesting
            written = parse_html_string(str(get_cleaned_html(page)))
            assert _nested_links(written) == [], slug
            assert content(written) == content(parse_html_string(page)), slug
            if slug in ("Laura-Bow-The-Colonels-Bequest", "Blue-Stinger"):
                assert len(list(written.iter("a"))) == len(as_served.find_all("a")), slug


def test_every_landing_page_has_lists_and_tables_that_validate():
    """The invariants behind RSC-005 "expected the element end-tag or element li", "element li not allowed here",
    the table content model and "element hr/h2/ul not allowed here" in phrasing content: once sanitised and
    re-parsed the way ebooklib writes it, no list of any landing page in the archive holds anything but items,
    every item sits directly in a list, every table is made of rows made of cells and nothing else, every row
    and cell sits in its table, no block has an inline wrapper for an ancestor, no link holds a link (22 landing
    pages nest one directly, 3 through a cell or an item), no void element holds anything
    (39 landing pages have one that html.parser left open), and no element or attribute is one XHTML 5 does not
    know (The-Suffering's <a<, Warcraft-II's <h0>, Ever-17's border"0", Oblivion's -target, Zero-Time-Dilemma's
    <ul type>, a width on 4 tables and cells), and no <img> is without a src (Super-Ghouls-n-Ghosts's four
    smilies with an empty one, Might-and-Magic's </ul> typed inside the tag)."""
    from ebooklib.utils import parse_html_string
    from lparchive2epub.lib import VOID_TAGS
    offenders = {}
    with zipfile.ZipFile(SNAPSHOT) as z:
        for name in z.namelist():
            if not name.startswith("landing_pages/"):
                continue
            cleaned = get_cleaned_html(z.read(name).decode("utf-8", "replace"))
            written = parse_html_string(str(cleaned))
            found = _stray_list_content(written) + _orphan_items(written) + _table_faults(written) \
                + _blocks_in_phrasing(written) + _unknown_markup(written) + _nested_links(written) \
                + _images_without_source(written) \
                + [f"content in {v.name}" for v in cleaned.find_all(VOID_TAGS) if v.contents]
            if found:
                offenders[name[len("landing_pages/"):-len(".html")]] = sorted(set(found))
    assert offenders == {}


def test_blocks_inside_links_are_restructured_so_the_page_validates():
    html = ('<div id="content">'
            '<a href="full1.png"><p><img src="thumb1.png"/></p></a>'                    # the Boatmurdered case
            '<b><p>bold paragraph</p></b>'
            '<a href="x/"><p>one</p><p>two</p></a>'                                    # several blocks: unwrap
            '<a href="y/">text <div>and a block</div></a>'                             # mixed: unwrap
            '<a href="z/"><div><p>nested</p></div></a>'                                 # block in block: unwrap
            '<p>a normal <a href="w/">link</a> stays</p>'
            '</div>')
    out = str(get_cleaned_html(html))
    assert '<p><a href="full1.png"><img src="thumb1.png"/></a></p>' in out
    assert '<p><b>bold paragraph</b></p>' in out
    assert '<a href="x/">onetwo</a>' in out
    assert '<a href="y/">text and a block</a>' in out
    assert '<a href="z/">nested</a>' in out
    assert '<p>a normal <a href="w/">link</a> stays</p>' in out
    soup = BeautifulSoup(out, "html.parser")
    for wrapper in soup.find_all(["a", "b", "i", "span"]):
        assert not wrapper.find(["p", "div", "blockquote", "ul", "table", "pre", "hr"]), str(wrapper)


def test_generated_cover_is_a_jpeg_of_the_expected_size_and_deterministic():
    from lparchive2epub.cover import make_cover, COVER_SIZE
    one = make_cover("Dwarf Fortress - Boatmurdered", "Various")
    two = make_cover("Dwarf Fortress - Boatmurdered", "Various")
    assert one == two
    assert detect_image_type(one) == ("image/jpeg", "jpg") and _dimensions(one) == COVER_SIZE
    # very long titles are wrapped and shrunk rather than cut off: the function must not fail
    long_title = "An Extremely Long Title " * 12 + "Supercalifragilisticexpialidociouslylongsinglewordthatdoesnotfit"
    assert _dimensions(make_cover(long_title, "Someone With A Rather Long Name Too")) == COVER_SIZE


def test_title_page_lists_the_landing_page_facts():
    from lparchive2epub.cover import make_title_page
    intro = Extractor.intro("https://lparchive.org/X-COM-Terror-from-the-Deep", BeautifulSoup(xcom, "html.parser"))
    page = make_title_page(intro, "https://lparchive.org/X-COM-Terror-from-the-Deep", "A description <with> markup")
    assert "<h1>X-COM: Terror from the Deep</h1>" in page
    assert "by GuavaMoment" in page
    assert "Updates: 18 updates" in page and "Posted: Oct 26, 2009 to Apr 09, 2010" in page
    assert "Tags: hybrid, voice" in page and "Added to the archive: May 14, 2010" in page
    assert '<a href="http://forums.somethingawful.com/showthread.php?threadid=3220122">' in page
    assert "A description &lt;with&gt; markup" in page and "Converted by lparchive2epub" in page

    # Axelay, as archived: <a id="threadlink" href="/Devolution/"> (RSC-007 in 27 books of the archive-wide run)
    intro = Extractor.intro("https://lparchive.org/Axelay", snapshot_page("Axelay"))
    page = make_title_page(intro, "https://lparchive.org/Axelay", "")
    assert '<a href="https://lparchive.org/Devolution/">This LP was part of the Devolution 2007 megathread!</a>' in page
    assert 'href="/Devolution/"' not in page


async def _build_book(session, **kwargs):
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, lambda *_: None, **kwargs), timeout=60)
        with zipfile.ZipFile(out) as z:
            return {n: z.read(n) for n in z.namelist()}


@pytest.mark.asyncio
async def test_book_opens_on_cover_then_title_page_then_navigation():
    files = await _build_book(_FakeSession("never-matches"))
    opf = files["EPUB/content.opf"].decode()
    assert re.search(r'<item href="images/cover.jpg" id="cover-img" media-type="image/jpeg" properties="cover-image"/>', opf)
    assert len(re.findall(r'<meta name="cover" content="cover-img"\s*/?>', opf)) == 1   # EPUB 2 readers, once
    spine = re.findall(r'<itemref idref="([^"]+)"', opf)
    assert spine[:3] == ["cover", "chapter_0", "nav"]
    assert 'linear="no"' not in opf   # the cover is read first, not a detached page (epubcheck OPF-096)
    assert '<title>Title page</title>' in files["EPUB/title_page.xhtml"].decode()
    nav = files["EPUB/nav.xhtml"].decode()
    assert '<a href="title_page.xhtml">Title page</a>' in nav
    assert '<a href="introduction.xhtml">X-COM: Terror from the Deep</a>' in nav   # landing page named after the LP
    assert nav.count(">Introduction<") == 0
    assert _dimensions(files["EPUB/images/cover.jpg"]) == (1600, 2400)


@pytest.mark.asyncio
async def test_custom_and_no_cover():
    custom = _make_image("PNG", (600, 900))
    files = await _build_book(_FakeSession("never-matches"), cover=custom)
    assert files["EPUB/images/cover.png"] == custom
    assert 'href="images/cover.png" id="cover-img" media-type="image/png" properties="cover-image"' in files["EPUB/content.opf"].decode()

    files = await _build_book(_FakeSession("never-matches"), cover=False)
    opf = files["EPUB/content.opf"].decode()
    assert "cover-image" not in opf and not any("cover" in n for n in files)
    assert re.findall(r'<itemref idref="([^"]+)"', opf)[:2] == ["chapter_0", "nav"]
    assert "EPUB/title_page.xhtml" in files

    with pytest.raises(OutputError, match="not an image"):
        await _build_book(_FakeSession("never-matches"), cover=b"this is not an image")


def test_cli_cover_flags(monkeypatch):
    seen = {}

    async def fake(url, *args, **kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(cli, "lparchive2epub", fake)
    cli.main(["https://lparchive.org/Some-LP", "out.epub"])
    assert seen["cover"] is True
    cli.main(["--no-cover", "https://lparchive.org/Some-LP", "out.epub"])
    assert seen["cover"] is False
    with tempfile.TemporaryDirectory() as d:
        with open(f"{d}/c.png", "wb") as f:
            f.write(PNG_BYTES)
        cli.main(["--cover", f"{d}/c.png", "https://lparchive.org/Some-LP", "out.epub"])
        assert seen["cover"] == PNG_BYTES
        with pytest.raises(SystemExit) as exit_info:
            cli.main(["--cover", f"{d}/missing.png", "https://lparchive.org/Some-LP", "out.epub"])
        assert exit_info.value.code == 1
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--cover", "x.png", "--no-cover", "https://lparchive.org/Some-LP", "out.epub"])
    assert exit_info.value.code == 2


def test_thumbnails_are_replaced_by_their_full_size_picture():
    html = ('<div id="content">'
            '<a href="map_full.png" rel="nofollow"><img alt="" class="img" src="map_thumb.png"/></a><br/>'            # wrapped
            '<img alt="" class="img" src="3-shoes.png"/><a href="4-shoes.png"><br/>Click here for the full 728x866 image.</a><br/>'  # text link after
            '<img src="a.png"/><br/><br/><a href="b.png">Click here for the full 1024x768 image.</a>'                  # over line breaks
            '<a href="other.png">Here is the in-game result.</a>'                                                     # prose link: kept
            '<a href="Update%203/">see update 3</a>'
            '<a href="two.png"><img src="t1.png"/><img src="t2.png"/></a>'                                            # two thumbnails: kept
            '<a href="cap.png"><img src="c.png"/> captioned</a>'                                                      # link with text: kept
            '</div>')
    content = BeautifulSoup(html, "html.parser").find("div", id="content")
    assert Extractor.inline_full_size_images(content) == 3
    out = str(content)
    assert '<img alt="" class="img" src="map_full.png"/><br/>' in out and "map_thumb" not in out
    assert '<img alt="" class="img" src="4-shoes.png"/><br/>' in out and "3-shoes" not in out and "Click here" not in out
    assert '<img src="b.png"/><br/><br/>' in out and 'src="a.png"' not in out
    assert '<a href="other.png">Here is the in-game result.</a>' in out
    assert '<a href="two.png"><img src="t1.png"/><img src="t2.png"/></a>' in out
    assert '<a href="cap.png"><img src="c.png"/> captioned</a>' in out
    images = Extractor.all_images(content, "https://lparchive.org/Some-LP/Update%201/")
    assert [i.src for i in images] == ["map_full.png", "4-shoes.png", "b.png", "t1.png", "t2.png", "c.png",
                                       "other.png", "two.png", "cap.png"]


@pytest.mark.asyncio
async def test_only_the_full_size_picture_is_downloaded_and_embedded():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    full = _make_image("JPEG", (2000, 1500), quality=90)
    thumb = _make_image("JPEG", (200, 150))
    chapter = f"{url}/Update%2001/"
    session = _FakeSession("never-matches", responses={
        chapter: _FakeResponse(200, b'<div id="content"><a href="full.jpg"><p><img src="thumb.jpg"/></p></a>'
                                    b'<p>and <a href="prose.jpg">a prose link</a></p></div>'),
        f"{chapter}full.jpg": _FakeResponse(200, full),
        f"{chapter}thumb.jpg": _FakeResponse(200, thumb),
        f"{chapter}prose.jpg": _FakeResponse(200, PNG_BYTES + b"prose"),
    })
    files = await _build_book(session)
    page = files["EPUB/update_0.xhtml"].decode()
    assert session.requested.count(f"{chapter}full.jpg") == 1
    assert session.requested.count(f"{chapter}thumb.jpg") == 0
    stored = [n for n in files if n.startswith("EPUB/images/") and "cover" not in n]
    assert len(stored) == 2 + 1   # full picture, prose-linked picture, the intro's image
    assert any(files[n] == full for n in stored) and not any(files[n] == thumb for n in stored)
    assert re.search(r'<p>\s*<img src="images/[0-9a-f]+\.jpg"/>\s*</p>', page)   # inline, no link around it
    assert len(re.findall(r'<a href="image_[0-9a-f]+\.xhtml"', page)) == 1   # only the prose link remains a link


class _SlowSession(_FakeSession):
    """Every body read takes a moment, and the session records how many reads overlap."""

    def __init__(self):
        super().__init__("never-matches")
        self.in_flight = 0
        self.max_in_flight = 0

    def get(self, url, **kwargs):
        response = super().get(url, **kwargs)
        session = self

        class Slow(_FakeResponse):
            async def read(inner):
                session.in_flight += 1
                session.max_in_flight = max(session.max_in_flight, session.in_flight)
                try:
                    await asyncio.sleep(0.003)
                    return inner._body
                finally:
                    session.in_flight -= 1

            async def text(inner):
                return (await inner.read()).decode("utf-8", errors="replace")

        return Slow(response.status, response._body, response.headers.get("Content-Type"))


@pytest.mark.asyncio
async def test_concurrency_limit_caps_downloads_in_flight():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    for limit in (1, 3):
        session = _SlowSession()
        with tempfile.TemporaryDirectory() as d:
            await asyncio.wait_for(do(url, f"{d}/book.epub", session, lambda *_: None,
                                      fetch=FetchSettings(concurrency=limit)), timeout=60)
        assert session.max_in_flight == limit
    session = _SlowSession()
    with tempfile.TemporaryDirectory() as d:
        await asyncio.wait_for(do(url, f"{d}/book.epub", session, lambda *_: None), timeout=60)
    assert 3 < session.max_in_flight <= 32   # the default limit applies


@pytest.mark.asyncio
async def test_retries_setting_is_honoured(monkeypatch):
    monkeypatch.setattr(lib, "RETRY_BACKOFF_BASE", 0)
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    flaky = f"{url}/Update%2003/"
    for retries in (1, 2, 7):
        session = _FakeSession("never-matches", responses={flaky: _FakeResponse(503, b"down")})
        with tempfile.TemporaryDirectory() as d:
            with pytest.raises(MissingUpdatesError, match=f"after {retries} retries"):
                await asyncio.wait_for(do(url, f"{d}/book.epub", session, lambda *_: None,
                                          fetch=FetchSettings(retries=retries)), timeout=30)
        assert session.requested.count(flaky) == retries


@pytest.mark.asyncio
async def test_quiet_keeps_only_the_report():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    dead = "http://img.example/dead.png"
    session = _FakeSession("never-matches", responses={dead: _FakeResponse(404, b"gone")})
    session.responses[f"{url}/Update%2001/"] = _FakeResponse(200, f'<div id="content"><img src="{dead}"/></div>'.encode())
    loud, quiet = [], []
    with tempfile.TemporaryDirectory() as d:
        await asyncio.wait_for(do(url, f"{d}/a.epub", session, loud.append), timeout=30)
        await asyncio.wait_for(do(url, f"{d}/b.epub", session, quiet.append, fetch=FetchSettings(quiet=True)), timeout=30)
    assert any(m.startswith("extracting lp from") for m in loud)
    assert len(quiet) == 1 and "could not be retrieved" in quiet[0] and dead in quiet[0]
    assert quiet[0] == loud[-1]


@pytest.mark.asyncio
async def test_quiet_build_can_keep_its_progress_bars(capsys):
    """bars=True: a quiet build (no messages through the writer) still draws its step bars on stderr, for a
    caller that builds many books under its own bar; the bars are transient so they nest under it."""
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    session = _FakeSession("never-matches")
    with tempfile.TemporaryDirectory() as d:
        silent: list[str] = []
        await asyncio.wait_for(do(url, f"{d}/a.epub", session, silent.append, fetch=FetchSettings(quiet=True)), timeout=30)
        assert silent == [] and "Gathering and building pages" not in capsys.readouterr().err
        with tqdm(total=1, desc="run") as run:
            await asyncio.wait_for(do(url, f"{d}/b.epub", session, silent.append,
                                      fetch=FetchSettings(quiet=True, bars=True)), timeout=30)
            bar = FetchSettings(quiet=True, bars=True).progress_bar(total=1, desc="step")
            assert bar.pos != run.pos and bar.leave is None   # nested under the caller's bar, cleared when done
            bar.close()
        assert silent == [] and "Gathering and building pages" in capsys.readouterr().err


def test_cli_download_flags(monkeypatch):
    seen = {}

    async def fake(url, file, session=None, *args, **kwargs):
        seen.update(kwargs)
        await session.close()

    monkeypatch.setattr(cli, "lparchive2epub", fake)
    cli.main(["https://lparchive.org/Some-LP", "out.epub"])
    assert (seen["fetch"].concurrency, seen["fetch"].retries, seen["fetch"].quiet) == (32, 5, False)
    cli.main(["--concurrency", "4", "--retries", "1", "--quiet", "https://lparchive.org/Some-LP", "out.epub"])
    assert (seen["fetch"].concurrency, seen["fetch"].retries, seen["fetch"].quiet) == (4, 1, True)
    for bad in (["--concurrency", "0"], ["--retries", "0"], ["--retries", "many"]):
        with pytest.raises(SystemExit) as exit_info:
            cli.main([*bad, "https://lparchive.org/Some-LP", "out.epub"])
        assert exit_info.value.code == 2


EPUBCHECK_JSON = {   # the shape of epubcheck 5.3's --json output, trimmed
    "messages": [
        {"ID": "RSC-007", "severity": "ERROR", "message": 'Referenced resource "EPUB/images/missing.png" could not be found in the EPUB.',
         "locations": [{"path": "EPUB/update_0.xhtml", "line": 71, "column": 70}], "suggestion": None},
        {"ID": "OPF-003", "severity": "WARNING", "message": 'Item "EPUB/stray.txt" exists in the EPUB, but is not declared in the OPF manifest.',
         "locations": [{"path": "EPUB/stray.txt", "line": -1, "column": -1}], "suggestion": None},
        {"ID": "PKG-012", "severity": "FATAL", "message": "File name contains characters disallowed.", "locations": []},
        {"ID": "ACC-013", "severity": "USAGE", "message": "Content Documents should include a title.", "locations": []},
        # epubcheck groups identical messages and lists every place: 3 stray <br> in a list...
        {"ID": "RSC-005", "severity": "ERROR", "message": 'Error while parsing file: element "br" not allowed here',
         "locations": [{"path": "EPUB/update_0.xhtml", "line": 10, "column": 4}, {"path": "EPUB/update_0.xhtml", "line": 20, "column": 4},
                       {"path": "EPUB/update_2.xhtml", "line": 30, "column": 4}], "suggestion": None},
        # ...and 12 pictures of the wrong type, more places than a finding keeps
        {"ID": "OPF-029", "severity": "ERROR", "message": 'The file does not appear to match the media type.',
         "locations": [{"path": f"EPUB/images/{n}.png", "line": -1, "column": -1} for n in range(12)], "suggestion": None},
    ],
    "checker": {"checkerVersion": "5.3.0", "nFatal": 1, "nError": 16, "nWarning": 1, "nUsage": 1},
}


def test_epubcheck_findings_are_parsed_and_reported():
    from lparchive2epub import check
    result = check.parse_epubcheck(EPUBCHECK_JSON)
    assert result.version == "5.3.0"
    assert [(f.severity, f.id, f.where()) for f in result.findings] == [
        ("ERROR", "RSC-007", "EPUB/update_0.xhtml:71"), ("WARNING", "OPF-003", "EPUB/stray.txt"), ("FATAL", "PKG-012", ""),
        ("ERROR", "RSC-005", "EPUB/update_0.xhtml:10 (+2 more)"), ("ERROR", "OPF-029", "EPUB/images/0.png (+11 more)")]
    assert len(result.errors) == 4 and len(result.warnings) == 1       # USAGE advice is not a finding
    # one finding per distinct message, counting every place it occurs at and keeping the first MAX_LOCATIONS
    assert [f.count for f in result.findings] == [1, 1, 1, 3, 12]
    assert result.findings[0].locations == (("EPUB/update_0.xhtml", 71),)
    assert result.findings[2].locations == ()
    assert result.findings[3].locations == (("EPUB/update_0.xhtml", 10), ("EPUB/update_0.xhtml", 20), ("EPUB/update_2.xhtml", 30))
    assert len(result.findings[4].locations) == check.MAX_LOCATIONS == 10 and result.findings[4].locations[-1] == ("EPUB/images/9.png", -1)
    assert (result.error_count, result.warning_count) == (17, 1)

    report = check.format_check_report("/books/x.epub", result, "outcome line")
    assert "lparchive2epub: epubcheck 5.3.0 found 17 error(s) of 4 kind(s) and 1 warning(s) in /books/x.epub" in report
    assert '  - ERROR RSC-007 EPUB/update_0.xhtml:71: Referenced resource "EPUB/images/missing.png" could not be found in the EPUB.' in report
    assert "  - WARNING OPF-003 EPUB/stray.txt: Item" in report
    assert "  - FATAL PKG-012: File name contains characters disallowed." in report
    assert '  - ERROR RSC-005 EPUB/update_0.xhtml:10 (+2 more): Error while parsing file: element "br" not allowed here' in report
    assert report.index("outcome line") < report.index(ISSUES_URL)
    assert check.parse_epubcheck({"messages": [], "checker": {"checkerVersion": "5.3.0"}}).findings == []
    # when every message occurs once the header says just how many, as before
    warnings_only = check.CheckResult("5.3.0", result.warnings)
    assert "found 1 warning(s) in" in check.format_check_report("x.epub", warnings_only, "o")
    once_each = check.CheckResult("5.3.0", result.findings[:3])
    assert "found 2 error(s) and 1 warning(s) in" in check.format_check_report("x.epub", once_each, "o")


def test_check_availability_is_explained(monkeypatch):
    from lparchive2epub import check
    import shutil
    monkeypatch.setattr(shutil, "which", lambda name: None)
    reason = check.unavailable_reason()
    assert reason is not None and "Java" in reason
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/java")
    assert check.unavailable_reason() is None
    # the CLI refuses --check before downloading anything
    monkeypatch.setattr(check, "unavailable_reason", lambda: "--check needs a Java runtime: 'java' was not found on the PATH")
    called = []

    async def fake(*args, **kwargs):
        called.append(kwargs)

    monkeypatch.setattr(cli, "lparchive2epub", fake)
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--check", "https://lparchive.org/Some-LP", "out.epub"])
    assert exit_info.value.code == 2 and called == []
    # and passes the flag through when it can
    monkeypatch.setattr(check, "unavailable_reason", lambda: None)

    async def fake_ok(url, file, session=None, *args, **kwargs):
        called.append(kwargs)
        await session.close()

    monkeypatch.setattr(cli, "lparchive2epub", fake_ok)
    cli.main(["https://lparchive.org/Some-LP", "out.epub"])
    cli.main(["--check", "https://lparchive.org/Some-LP", "out.epub"])
    assert [k["check"] for k in called] == [False, True]


def _epubcheck_result(*findings):
    from lparchive2epub import check
    return check.CheckResult("5.3.0", [check.Finding(*f) for f in findings])


@pytest.mark.asyncio
async def test_check_reports_epubcheck_findings_after_the_book_is_written(monkeypatch):
    from lparchive2epub import check
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    checked = []

    def fake_run(path):
        checked.append(path)
        assert os.path.exists(path)                      # the check runs on the written book
        return fake_run.result

    monkeypatch.setattr(check, "run_epubcheck", fake_run)
    error = ("ERROR", "RSC-007", 'Referenced resource "EPUB/x.png" could not be found in the EPUB.', "EPUB/update_0.xhtml", 71)
    warning = ("WARNING", "OPF-003", "Item exists but is not declared.", "EPUB/stray.txt", None)
    with tempfile.TemporaryDirectory() as d:
        # findings: reported, the book kept, exit status 0 (no exception)
        fake_run.result = _epubcheck_result(error, warning)
        messages = []
        out = await asyncio.wait_for(do(url, f"{d}/a.epub", _FakeSession("never-matches"), messages.append, check=True), timeout=30)
        assert checked == [out] and os.path.exists(out)
        assert "epubcheck 5.3.0 found 1 error(s) and 1 warning(s)" in messages[-1] and "RSC-007" in messages[-1]
        assert "a strict reader may refuse it" in messages[-1] and ISSUES_URL in messages[-1]
        # nothing found: no report, a progress line only
        fake_run.result = _epubcheck_result()
        messages = []
        await asyncio.wait_for(do(url, f"{d}/b.epub", _FakeSession("never-matches"), messages.append, check=True), timeout=30)
        assert not any("lparchive2epub: epubcheck" in m for m in messages)   # no report...
        assert any("epubcheck 5.3.0: no problems found" in m for m in messages)   # ...a progress line
        quiet = []
        await asyncio.wait_for(do(url, f"{d}/c.epub", _FakeSession("never-matches"), quiet.append, check=True,
                                  fetch=FetchSettings(quiet=True)), timeout=30)
        assert quiet == []
        # --strict: errors fail the run (the book is kept), warnings do not
        fake_run.result = _epubcheck_result(error)
        with pytest.raises(lib.InvalidBookError, match="--strict was requested") as e:
            await asyncio.wait_for(do(url, f"{d}/d.epub", _FakeSession("never-matches"), lambda *_: None, strict=True, check=True), timeout=30)
        assert e.value.exit_code == lib.EXIT_CHECK and os.path.exists(f"{d}/d.epub")
        fake_run.result = _epubcheck_result(warning)
        messages = []
        await asyncio.wait_for(do(url, f"{d}/e.epub", _FakeSession("never-matches"), messages.append, strict=True, check=True), timeout=30)
        assert "found 1 warning(s)" in messages[-1] and "readers accept the book" in messages[-1]
        # without --check epubcheck never runs
        checked.clear()
        await asyncio.wait_for(do(url, f"{d}/f.epub", _FakeSession("never-matches"), lambda *_: None), timeout=30)
        assert checked == []


def test_run_epubcheck_failures_are_check_errors(monkeypatch):
    import subprocess
    from lparchive2epub import check

    class _Completed:
        def __init__(self, stdout=b"", stderr=b"", returncode=1):
            self.stdout, self.stderr, self.returncode = stdout, stderr, returncode

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Completed(b"", b"Error occurred during initialization of VM\nCould not reserve enough space", 1))
    with pytest.raises(lib.CheckError, match="Could not reserve enough space") as e:
        check.run_epubcheck("/books/x.epub")
    assert e.value.exit_code == lib.EXIT_CHECK and "written at /books/x.epub" in str(e.value)

    def timeout(*a, **k):
        raise subprocess.TimeoutExpired(a[0], check.CHECK_TIMEOUT)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(lib.CheckError, match="did not finish"):
        check.run_epubcheck("/books/x.epub")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Completed(json.dumps(EPUBCHECK_JSON).encode(), b"", 1))
    assert len(check.run_epubcheck("/books/x.epub").findings) == 5


@pytest.mark.asyncio
async def test_a_built_book_passes_the_real_epubcheck():
    """The one check that is not written by hand: epubcheck itself, on a book with pictures, image pages,
    a cover and an intro. Needs the epubcheck package and Java; skipped without them."""
    from lparchive2epub import check
    reason = check.unavailable_reason()
    if reason:
        pytest.skip(reason)
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    full = f"{url}/Update%2001/full.png"
    picture = _make_image("PNG", (40, 30))   # a real picture: epubcheck decodes images (PNG_BYTES would be PKG-021)
    session = _FakeSession("never-matches", responses={full: _FakeResponse(200, picture),
                                                       f"{url}/Update%2001/shot.png": _FakeResponse(200, picture),
                                                       # a gzip of a PNG and a web page, both served as image/png (9vb.13)
                                                       f"{url}/Update%2001/12-fanart.png": _FakeResponse(200, gzip.compress(_make_image("PNG", (30, 20))), "image/png"),
                                                       f"{url}/Update%2001/47-cas03b.png": _FakeResponse(200, b"\xef\xbb\xbf<!DOCTYPE html PUBLIC>\r\n<html></html>", "image/png")})
    session.responses[f"{url}/Update%2001/"] = _FakeResponse(
        200, b'<div id="content"><img src="shot.png"/> <a href="full.png">see the full map</a> '
             b'<img src="12-fanart.png"/> <img src="47-cas03b.png"/> '
             b'<a href="https://en.wikipedia.org/wiki/File:X.jpg">wiki</a> <img src="http://img.example/dead.png"/> '
             # links as written on the archive's pages: spaces (RSC-020), a host no encoding can save, an
             # unregistered scheme (HTM-025), and a dead picture whose URL holds spaces (the note links it)
             b'<a href="avis/1 - Mine Level 1 - It\'s Show Time!.avi">video</a> '
             b'<a href="mailto:missing-img@lparchive.org?subject=X - (01.jpg)">lost picture</a> '
             b'<a href="http://http:ustwo.com">garbage</a> <a href="steam://run/341190/">on Steam</a> '
             b'<img src="http://img.example/Advent Rising/ethan6.jpg"/></div>')
    session.responses["http://img.example/dead.png"] = _FakeResponse(404, b"gone")
    session.responses["http://img.example/Advent Rising/ethan6.jpg"] = _FakeResponse(404, b"gone")
    default_get = session.get

    def real_pictures(url_, **kwargs):   # the landing page's own images too: the fake session's stand-in bytes are not a PNG
        response = default_get(url_, **kwargs)
        return _FakeResponse(200, picture) if response._body == PNG_BYTES else response

    session.get = real_pictures
    messages = []
    with tempfile.TemporaryDirectory() as d:
        out = await asyncio.wait_for(do(url, f"{d}/book.epub", session, messages.append, check=True), timeout=120)
        result = await asyncio.to_thread(check.run_epubcheck, out)
        with zipfile.ZipFile(out) as z:
            chapter = z.read("EPUB/update_0.xhtml").decode()
    assert result.findings == [], check.format_check_report(out, result, "")
    assert any("no problems found" in m for m in messages)
    assert f'href="{url}/Update%2001/avis/1%20-%20Mine%20Level%201%20-%20It\'s%20Show%20Time!.avi"' in chapter
    assert 'href="mailto:missing-img@lparchive.org?subject=X%20-%20(01.jpg)"' in chapter
    assert 'href="http://img.example/Advent%20Rising/ethan6.jpg">ethan6.jpg</a>' in chapter
    assert "ustwo" not in chapter and "steam:" not in chapter and "garbage" in chapter and "on Steam" in chapter


@pytest.mark.asyncio
async def test_all_archives_records_epubcheck_findings(monkeypatch):
    """The archive run checks the written books through a queue (BookChecker), not inside the build:
    findings go to the error file as before, a check that could not run is its own entry."""
    import util.all_archives as all_archives
    from util.all_archives import build_one, BookChecker, ErrorLog
    results = iter([
        _epubcheck_result(("ERROR", "RSC-007", "missing", "EPUB/update_0.xhtml", 71), ("WARNING", "OPF-003", "stray", "EPUB/s.txt", None)),
        _epubcheck_result(),
        _epubcheck_result(("ERROR", "RSC-007", "missing again", "EPUB/update_1.xhtml", 3, 3,
                           (("EPUB/update_1.xhtml", 3), ("EPUB/update_1.xhtml", 8), ("EPUB/update_4.xhtml", 3))),
                          ("ERROR", "RSC-007", "another one missing", "EPUB/update_2.xhtml", 5, 2,
                           (("EPUB/update_2.xhtml", 5), ("EPUB/update_2.xhtml", 9)))),
        lib.CheckError("The book was written at x, but epubcheck did not finish within 1800 s"),
    ])

    def fake_run(path):
        assert os.path.exists(path)   # the check runs on the written book
        result = next(results)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(all_archives, "run_epubcheck", fake_run)
    slug = "X-COM-Terror-from-the-Deep"
    with tempfile.TemporaryDirectory() as d:
        errors = ErrorLog(f"{d}/errors.jsonl")
        bar = tqdm(total=0, file=io.StringIO())   # a real bar (a disabled one ignores update), kept off stderr
        checker = BookChecker(errors, bar)
        checker.start(1)
        for n in range(4):   # the same LP four times, in four output directories
            os.mkdir(f"{d}/{n}")
            session = _FakeSession("never-matches")
            assert await asyncio.wait_for(build_one(slug, f"{d}/{n}", f"{d}/{n}", errors, lambda *_: session), timeout=30)
            checker.submit(slug, f"{d}/{n}/{slug}.epub")
        await asyncio.wait_for(checker.drain(), timeout=30)
        assert bar.total == 4 and bar.n == 4 and checker.workers == []
        assert all(os.path.exists(f"{d}/{n}/{slug}.epub") for n in range(4))   # the books stay, checked or not
        with open(f"{d}/errors.jsonl", encoding="utf-8") as f:
            entries = [json.loads(line) for line in f]
    assert [(e["slug"], e["kind"]) for e in entries] == [(slug, "epubcheck"), (slug, "epubcheck"), (slug, "check-failed")]
    assert "epubcheck 5.3.0 found 1 error(s) and 1 warning(s)" in entries[0]["report"]
    assert "The book was written all the same." in entries[0]["report"] and ISSUES_URL in entries[0]["report"]
    assert "epubcheck 5.3.0 found 5 error(s) of 2 kind(s) in" in entries[1]["report"]
    assert "  - ERROR RSC-007 EPUB/update_1.xhtml:3 (+2 more): missing again" in entries[1]["report"]
    assert entries[0]["messages"] == [
        {"severity": "ERROR", "id": "RSC-007", "message": "missing", "path": "EPUB/update_0.xhtml", "line": 71, "count": 1, "locations": []},
        {"severity": "WARNING", "id": "OPF-003", "message": "stray", "path": "EPUB/s.txt", "line": None, "count": 1, "locations": []}]
    assert entries[1]["messages"][0]["count"] == 3
    assert entries[1]["messages"][0]["locations"] == [["EPUB/update_1.xhtml", 3], ["EPUB/update_1.xhtml", 8], ["EPUB/update_4.xhtml", 3]]
    assert entries[2]["error"] == "CheckError" and "did not finish" in entries[2]["message"] and "messages" not in entries[2]
    # the summary counts occurrences (1 + 3 + 2 RSC-007, two of them one book's two texts), not kinds
    assert errors.check_summary() == ("epubcheck found fault with 2 book(s); most frequent (occurrences): RSC-007 6, OPF-003 1; "
                                      "1 book(s) could not be checked")
    assert ErrorLog(None).check_summary() == "epubcheck found no fault with any book"
    # the build itself never checks (the iterator is exhausted: a call would fail), and an idle checker drains at once
    with tempfile.TemporaryDirectory() as d:
        session = _FakeSession("never-matches")
        assert await asyncio.wait_for(build_one("X-COM-Terror-from-the-Deep", d, d, ErrorLog(None), lambda *_: session), timeout=30)
        await asyncio.wait_for(BookChecker(ErrorLog(None), tqdm(disable=True)).drain(), timeout=5)


@pytest.mark.asyncio
async def test_all_archives_checks_in_the_background(monkeypatch):
    """The checks do not hold the builds back, and workers added later share the queue."""
    import threading
    import util.all_archives as all_archives
    from util.all_archives import build_one, BookChecker, ErrorLog
    release = threading.Event()
    lock = threading.Lock()
    in_flight, peak = [0], [0]

    def slow_run(path):
        with lock:
            in_flight[0] += 1
            peak[0] = max(peak[0], in_flight[0])
        assert release.wait(30)   # the event of the moment: the test swaps it for the second scenario
        with lock:
            in_flight[0] -= 1
        return _epubcheck_result()

    monkeypatch.setattr(all_archives, "run_epubcheck", slow_run)
    bar = tqdm(total=0, file=io.StringIO())
    checker = BookChecker(ErrorLog(None), bar)
    checker.start(1)
    for n in range(3):
        checker.submit(f"LP-{n}", f"/books/LP-{n}.epub")
    await asyncio.sleep(0.1)
    assert in_flight[0] == 1 and bar.total == 3 and bar.n == 0   # one check blocked, the others queued
    with tempfile.TemporaryDirectory() as d:   # ...and a build goes through meanwhile
        session = _FakeSession("never-matches")
        assert await asyncio.wait_for(build_one("X-COM-Terror-from-the-Deep", d, d, ErrorLog(None), lambda *_: session), timeout=30)
    checker.start(2)
    await asyncio.sleep(0.1)
    assert in_flight[0] == 3   # the new workers picked up the queued books
    release.set()
    await asyncio.wait_for(checker.drain(), timeout=30)
    assert peak[0] == 3 and bar.n == 3 and checker.workers == []
    # interrupted (Ctrl-C): stop() does not wait for the queue and counts what was left unchecked
    release.clear()
    checker = BookChecker(ErrorLog(None), tqdm(total=0, file=io.StringIO()))
    checker.start(1)
    for n in range(3):
        checker.submit(f"LP-{n}", f"/books/LP-{n}.epub")
    await asyncio.sleep(0.1)
    assert in_flight[0] == 1
    assert await asyncio.wait_for(checker.stop(), timeout=5) == 3 and checker.workers == []   # one in flight, two queued
    release.set()   # let the thread finish (the JVM would run on regardless)


@pytest.mark.parametrize(("title", "expected"), [
    ("X-COM: Terror from the Deep", "X-COM Terror from the Deep.epub"),
    ("Dwarf Fortress - Boatmurdered", "Dwarf Fortress - Boatmurdered.epub"),
    ('Banjo-Kazooie: Grunty"s Revenge', "Banjo-Kazooie Grunty s Revenge.epub"),
    ("What? / Why! | Who*", "What Why! Who.epub"),
    ("  spaced   out...  ", "spaced out.epub"),
    ("A" * 200, "A" * 150 + ".epub"),
    ('"?:*', "Some-LP.epub"),   # nothing usable: the URL slug
])
def test_safe_file_name(title, expected):
    assert safe_file_name(title, "Some-LP") == expected


def test_resolve_output_path():
    url = "https://lparchive.org/Some-LP"
    assert resolve_output_path(None, "A: B", url) == "A B.epub"
    assert resolve_output_path("my.epub", "A: B", url) == "my.epub"
    with tempfile.TemporaryDirectory() as d:
        assert resolve_output_path(d, "A: B", url) == os.path.join(d, "A B.epub")
        assert resolve_output_path(f"{d}/x.epub", "A: B", url) == f"{d}/x.epub"


@pytest.mark.asyncio
async def test_output_defaults_to_the_title_in_the_current_directory(monkeypatch, tmp_path):
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    messages = []
    # pytest's tmp_path, not TemporaryDirectory: monkeypatch restores the cwd only at teardown, and Windows
    # refuses to delete the current directory (WinError 32) when a with-block would remove it before that
    d = str(tmp_path)
    monkeypatch.chdir(d)
    written = await asyncio.wait_for(do(url, None, _FakeSession("never-matches"), messages.append), timeout=30)
    assert written == "X-COM Terror from the Deep.epub"
    assert os.listdir(d) == ["X-COM Terror from the Deep.epub"]
    assert any(m == "Writing book file X-COM Terror from the Deep.epub" for m in messages)
    os.mkdir(f"{d}/books")
    written = await asyncio.wait_for(do(url, f"{d}/books", _FakeSession("never-matches"), lambda *_: None), timeout=30)
    assert written == os.path.join(f"{d}/books", "X-COM Terror from the Deep.epub") and os.path.exists(written)
    written = await asyncio.wait_for(do(url, f"{d}/named.epub", _FakeSession("never-matches"), lambda *_: None), timeout=30)
    assert written == f"{d}/named.epub" and os.path.exists(written)


def test_page_content_normalises_newlines_like_html5():
    """CR LF and a lone CR become LF, in text and in attributes alike, nothing else moves."""
    soup = BeautifulSoup('<div title="x\r\ny">a\r\nb\rc\n<pre>d\r\n\r\ne</pre></div>', "html.parser")
    assert lib.page_content(soup) == '<div title="x\ny">a\nb\nc\n<pre>d\n\ne</pre></div>'


@pytest.mark.asyncio
async def test_page_newlines_are_normalised_before_ebooklib_sees_them(monkeypatch):
    """lparchive's template has CRLF lines. libxml2 2.14 (lxml's Linux wheels) normalises them while ebooklib
    re-parses the page, 2.11 (lxml's Windows wheels) keeps the CR and writes it as &#13;, which made 6 of the 21
    live books differ on Windows. So the CR must already be gone from the content handed to ebooklib, for the
    intro, the updates and the placeholders: the book is then the same whichever libxml2 lxml bundles."""
    import ebooklib
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"

    class CRLFSession(_FakeSession):
        def get(self, url, **kwargs):
            response = super().get(url, **kwargs)
            if response.status == 200 and response._body is not PNG_BYTES:   # the landing page and the updates
                response._body = response._body.replace(b"\n", b"\r\n").replace(b"<h3>", b"<h3>\r", 1)
            return response

    books = []
    write_book = lib.write_book

    def recording_write_book(file, book, mtime):
        books.append(book)
        write_book(file, book, mtime)

    monkeypatch.setattr(lib, "write_book", recording_write_book)
    with tempfile.TemporaryDirectory() as d:
        written = await asyncio.wait_for(do(url, f"{d}/x.epub", CRLFSession("Update%2003"), lambda *_: None,
                                            allow_missing_updates=True), timeout=30)
        pages = {item.file_name: item.content for item in books[0].get_items_of_type(ebooklib.ITEM_DOCUMENT)
                 if item.file_name.startswith(("introduction", "update_"))}
        assert len(pages) == 19 and "introduction.xhtml" in pages and "update_2.xhtml" in pages   # 18 updates, one a placeholder
        for name, content in pages.items():
            assert "\r" not in content, name
        assert "some text" in pages["update_0.xhtml"] and "\n" in pages["update_0.xhtml"]   # the newlines stayed newlines
        with zipfile.ZipFile(written) as z:
            for name in z.namelist():
                if name.endswith(".xhtml"):
                    data = z.read(name)
                    assert b"\r" not in data and b"&#13;" not in data, name


@pytest.mark.asyncio
async def test_bad_output_directory_still_fails_before_any_download():
    session = _FakeSession("never-matches")
    with tempfile.TemporaryDirectory() as d:
        with pytest.raises(OutputError, match="does not exist"):
            await do("https://lparchive.org/X-COM-Terror-from-the-Deep", f"{d}/nope/x.epub", session, lambda *_: None)
    assert session.requested == []


def test_cli_output_is_optional_and_printed_when_quiet(monkeypatch, capsys):
    seen = {}

    async def fake(url, file, session=None, *args, **kwargs):
        seen["url"], seen["file"] = url, file
        await session.close()
        return "Some LP.epub"

    monkeypatch.setattr(cli, "lparchive2epub", fake)
    cli.main(["https://lparchive.org/Some-LP"])
    assert (seen["url"], seen["file"]) == ("https://lparchive.org/Some-LP", None)
    assert capsys.readouterr().out == ""
    cli.main(["--quiet", "https://lparchive.org/Some-LP", "out.epub"])
    assert seen["file"] == "out.epub"
    assert capsys.readouterr().out == "Some LP.epub\n"


def _update_page(lp: str, n: int, prev: int | None, nxt: int | None, title: str, width: int = 1) -> bytes:
    nav = ""
    if prev is not None:
        nav += f'<a class="prev" href="../Update {prev:0{width}d}/"><strong>&larr;</strong>Previous</a>'
    if nxt is not None:
        nav += f'<a class="next" href="../Update {nxt:0{width}d}/">Next<strong>&rarr;</strong></a>'
    return (f"<html><head><title>{lp} Part #{n} - {title}</title></head><body>"
            f'<div class="updatenav">{nav}</div><div id="content"><h3>Part {n}: {title}</h3><p>text {n}</p></div>'
            f"</body></html>").encode()


def test_canonical_slug():
    assert canonical_slug("Update 647/") == "Update%20647/"
    assert canonical_slug("Update%20647/") == "Update%20647/"
    assert canonical_slug("Update%201-41/") == "Update%201-41/"
    assert canonical_slug("Star-Fox-(by-X)/") == "Star-Fox-(by-X)/"


@pytest.mark.asyncio
async def test_unlisted_updates_are_found_by_following_next_links():
    url = "https://lparchive.org/Fire-Emblem-Awakening"
    # the landing page: a two-entry LP; pages 3, 4 and 5 exist but are not listed; 5 has no next link
    landing = xcom.replace(b"X-COM: Terror from the Deep", b"Fire Emblem: Awakening")
    landing = re.sub(rb'<ul class="toc">.*?</ul>', b'<ul class="toc"><li><a href="Update%201/">Update 1</a></li>'
                     b'<li><a href="Update%202/">Update 2</a></li></ul>', landing, flags=re.S)
    responses = {url: _FakeResponse(200, landing)}
    for n, (prev, nxt) in {1: (None, 2), 2: (1, 3), 3: (2, 4), 4: (3, 5), 5: (4, None)}.items():
        responses[f"{url}/Update%20{n}/"] = _FakeResponse(200, _update_page("Fire Emblem: Awakening", n, prev, nxt, f"Chapter {n}"))
    session = _FakeSession("never-matches", responses=responses)
    messages = []
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, messages.append), timeout=30)
        with zipfile.ZipFile(out) as z:
            nav = z.read("EPUB/nav.xhtml").decode()
            pages = [n for n in z.namelist() if re.fullmatch(r"EPUB/update_\d+\.xhtml", n)]
    assert len(pages) == 5
    assert re.findall(r'<a href="update_\d+\.xhtml">([^<]*)</a>', nav) == ["Update 1", "Update 2", "Chapter 3", "Chapter 4", "Chapter 5"]
    assert any(m == "found 3 more update(s) by following the pages' next links" for m in messages)
    # every page downloaded exactly once, the walk's reads included
    for n in range(1, 6):
        assert session.requested.count(f"{url}/Update%20{n}/") == 1, n


@pytest.mark.asyncio
async def test_landing_page_without_any_update_link_starts_from_update_one():
    url = "https://lparchive.org/The-Blackwell-Legacy"
    landing = re.sub(rb'<ul class="toc">.*?</ul>', b"", xcom, flags=re.S).replace(b"X-COM: Terror from the Deep", b"The Blackwell Legacy")
    responses = {url: _FakeResponse(200, landing), f"{url}/Update%2001/": _FakeResponse(404, b"no padded")}
    for n, (prev, nxt) in {1: (None, 2), 2: (1, 3), 3: (2, None)}.items():
        responses[f"{url}/Update%20{n}/"] = _FakeResponse(200, _update_page("The Blackwell Legacy", n, prev, nxt, f"Rosa {n}"))
    session = _FakeSession("never-matches", responses=responses)
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, lambda *_: None), timeout=30)
        with zipfile.ZipFile(out) as z:
            nav = z.read("EPUB/nav.xhtml").decode()
    assert re.findall(r'<a href="update_\d+\.xhtml">([^<]*)</a>', nav) == ["Rosa 1", "Rosa 2", "Rosa 3"]
    assert session.requested.count(f"{url}/Update%2001/") == 1   # the padded guess was tried first


@pytest.mark.asyncio
async def test_walk_stops_on_cycles_and_dead_pages():
    url = "https://lparchive.org/Some-LP"
    base = url + "/"
    chapters = [Chapters(num=0, original_href=base + "Update%201/", txt="Update 1", new_href="update_0.xhtml", original_href_slug="Update%201/")]
    # next points back at a listed page: nothing found
    session = _FakeSession("never-matches", responses={base + "Update%201/": _FakeResponse(200, _update_page("Some LP", 1, None, 1, "loop"))})
    assert await discover_unlisted_chapters(session, url, chapters) == []
    # next points at a page that answers 404: nothing found, no exception
    session = _FakeSession("never-matches", responses={base + "Update%201/": _FakeResponse(200, _update_page("Some LP", 1, None, 2, "x")),
                                                       base + "Update%202/": _FakeResponse(404, b"gone")})
    assert await discover_unlisted_chapters(session, url, chapters) == []
    # the last listed page itself is dead: nothing found, and the build will report it as missing
    session = _FakeSession("never-matches", responses={base + "Update%201/": _FakeResponse(404, b"gone")})
    assert await discover_unlisted_chapters(session, url, chapters) == []
    # a 200 that is not an update page (e.g. a redirect to the index) stops the walk
    session = _FakeSession("never-matches", responses={base + "Update%201/": _FakeResponse(200, _update_page("Some LP", 1, None, 2, "x")),
                                                       base + "Update%202/": _FakeResponse(200, b"<html><body>The Let's Play Archive index</body></html>")})
    assert await discover_unlisted_chapters(session, url, chapters) == []
    # a page with no Part # in its title falls back to the slug
    session = _FakeSession("never-matches", responses={
        base + "Update%201/": _FakeResponse(200, _update_page("Some LP", 1, None, 2, "x")),
        base + "Update%202/": _FakeResponse(200, b'<html><head><title>odd</title></head><body><div id="content">p</div></body></html>')})
    found = await discover_unlisted_chapters(session, url, chapters)
    assert [(c.original_href_slug, c.txt, c.num, c.new_href) for c in found] == [("Update%202/", "Update 2", 1, "update_1.xhtml")]
    assert found[0].html is not None


@pytest.mark.asyncio
async def test_walk_starts_from_every_listed_page_and_keeps_reading_order():
    """Last Bible: the landing page mentions Update 14 in the prose above the table of contents, then
    lists 1..14; 15 is only reachable from 14's next link and must come right after 14."""
    url = "https://lparchive.org/Last-Bible"
    landing = re.sub(rb'<ul class="toc">.*?</ul>', b'<ul class="toc">'
                     + b"".join(f'<li><a href="Update%20{n:02d}/">Update {n}</a></li>'.encode() for n in range(1, 15)) + b"</ul>",
                     xcom, flags=re.S)
    landing = landing.replace(b"<h1><strong>Table of Contents</strong></h1>",
                              b'<p>Read <a href="Update%2014/">Matthew</a> after Genesis</p><h1><strong>Table of Contents</strong></h1>')
    responses = {url: _FakeResponse(200, landing), f"{url}/Update%2016/": _FakeResponse(404, b"no")}
    for n in range(1, 16):
        responses[f"{url}/Update%20{n:02d}/"] = _FakeResponse(200, _update_page("Last Bible", n, n - 1 if n > 1 else None,
                                                                                 n + 1 if n < 15 else None, f"Book {n}", width=2))
    session = _FakeSession("never-matches", responses=responses)
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, lambda *_: None), timeout=30)
        with zipfile.ZipFile(out) as z:
            nav = z.read("EPUB/nav.xhtml").decode()
    titles = re.findall(r'<a href="update_\d+\.xhtml">([^<]*)</a>', nav)
    assert titles == [f"Update {n}" for n in range(1, 15)] + ["Book 15"]
    assert session.requested.count(f"{url}/Update%2015/") == 1
    assert session.requested.count(f"{url}/Update%2016/") == 1   # the numeric probe stops at the first 404


@pytest.mark.asyncio
async def test_pages_nothing_links_to_are_found_by_numbering():
    """Resident Evil 1: 58 listed pages, page 58 has no next link, page 59 exists anyway, 60 does not."""
    url = "https://lparchive.org/Resident-Evil-1"
    landing = re.sub(rb'<ul class="toc">.*?</ul>', b'<ul class="toc"><li><a href="Update%2057/">Update 57</a></li>'
                     b'<li><a href="Update%2058/">Update 58</a></li></ul>', xcom, flags=re.S)
    responses = {url: _FakeResponse(200, landing),
                 f"{url}/Update%2057/": _FakeResponse(200, _update_page("Resident Evil 1", 57, 56, 58, "Episode XXXIX")),
                 f"{url}/Update%2058/": _FakeResponse(200, _update_page("Resident Evil 1", 58, 57, None, "Episode XL")),
                 f"{url}/Update%2059/": _FakeResponse(200, _update_page("Resident Evil 1", 59, 58, None, "Prologue")),
                 f"{url}/Update%2060/": _FakeResponse(404, b"no")}
    session = _FakeSession("never-matches", responses=responses)
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, lambda *_: None), timeout=30)
        with zipfile.ZipFile(out) as z:
            nav = z.read("EPUB/nav.xhtml").decode()
    assert re.findall(r'<a href="update_\d+\.xhtml">([^<]*)</a>', nav) == ["Update 57", "Update 58", "Prologue"]
    assert session.requested.count(f"{url}/Update%2060/") == 1 and session.requested.count(f"{url}/Update%2061/") == 0


@pytest.mark.asyncio
async def test_unavailable_images_become_notes_not_dangling_paths():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    chapter_url = f"{url}/Update%2001/"
    session = _FakeSession("never-matches", responses={
        chapter_url: _FakeResponse(200, (
            b'<div id="content"><img alt="the fort" src="2-transportx.gif"/>'       # host answers 0 bytes
            b'<img src="hhttp://"/>'                                               # URL beyond repair: no link
            b'<p><a href="gone.png">see this</a></p>'                             # a link: already absolute
            b'<img src="ok.png"/></div>')),
        f"{chapter_url}2-transportx.gif": _FakeResponse(200, b"", "image/gif"),
        f"{chapter_url}gone.png": _FakeResponse(404, b"no"),
        f"{chapter_url}ok.png": _FakeResponse(200, PNG_BYTES),
    })
    files = await _build_book(session)
    page = files["EPUB/update_0.xhtml"].decode()
    assert ('<span class="missing-image">[image not available: the fort - '
            f'<a href="{chapter_url}2-transportx.gif">2-transportx.gif</a>]</span>') in page
    assert '<span class="missing-image">[image not available: hhttp://]</span>' in page
    assert f'<a href="{chapter_url}gone.png">see this</a>' in page
    assert re.search(r'<img src="images/[0-9a-f]+\.png"/>', page)
    # no src left that points inside the container at nothing
    for src in re.findall(r'src="([^"]+)"', page):
        assert src.startswith("images/") and f"EPUB/{src}" in files, src
    # the landing page's own images get the same treatment
    intro_session = _FakeSession("never-matches", responses={f"{url}/Images/1-OP80jpg.jpg": _FakeResponse(404, b"no")})
    files = await _build_book(intro_session)
    intro = files["EPUB/introduction.xhtml"].decode()
    assert '[image not available: <a href="https://lparchive.org/X-COM-Terror-from-the-Deep/Images/1-OP80jpg.jpg">1-OP80jpg.jpg</a>]' in intro


def test_code_passes_ruff():
    """Dead imports and names are caught here rather than in review (lparchive2epub-u7y)."""
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run([sys.executable, "-m", "ruff", "check", "lparchive2epub", "util", "tests"],
                            cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_prose_mentions_above_the_table_of_contents_do_not_reorder_chapters():
    root = "https://lparchive.org/Some-LP"

    def order(body: str) -> list[str]:
        soup = BeautifulSoup(f'<div id="content">{body}</div>', "html.parser")
        return [c.original_href_slug + ":" + c.txt for c in Extractor.all_chapters(root, soup)]

    # mentioned in the prose, listed in a ul.toc: the list decides; the list's text is used
    assert order('<p>Read <a href="Update%203/">three</a> first.</p><ul class="toc"><li><a href="Update%201/">One</a></li>'
                 '<li><a href="Update%202/">Two</a></li><li><a href="Update%203/">Three</a></li></ul>') == \
        ["Update%201/:One", "Update%202/:Two", "Update%203/:Three"]
    # no ul.toc, but a "Table of Contents" heading: everything after it is the list (image links, empty text)
    assert order('<p>Skip to <a href="Update%203/">Matthew</a>.</p><h1>Table of Contents</h1>'
                 '<a href="Update%201/"><img src="1.png"/></a><a href="Update%202/"><img src="2.png"/></a>'
                 '<a href="Update%203/"><img src="3.png"/></a>') == \
        ["Update%201/:Update 1", "Update%202/:Update 2", "Update%203/:Matthew"]
    # a page only mentioned in the prose keeps its place; a mention after the list changes nothing
    assert order('<p><a href="Bonus/">Bonus</a></p><h2>Contents</h2><a href="Update%201/">One</a>'
                 '<a href="Update%202/">Two</a><p>See <a href="Update%201/">one</a> again.</p>') == \
        ["Bonus/:Bonus", "Update%201/:One", "Update%202/:Two"]
    # no list marker at all: document order, first mention wins (the author's own order is respected)
    assert order('<a href="Update%2065/">Skip ahead</a><br/><a href="Update%201/">One</a><a href="Update%2065/">Sixty-five</a>') == \
        ["Update%2065/:Skip ahead", "Update%201/:One"]


# Let's Plays whose landing page deliberately lists numbered updates out of numeric order (sections,
# story/gameplay pairs, "read this first" notes, a pointer to a later update with no list marker).
# Reviewed one by one when the ordering rule was chosen; the book follows the author's order.
NON_NUMERIC_ORDER = {
    "Assassins-Creed-IV-Black-Flag", "Buzz-Aldrins-Race-Into-Space", "Dark-Souls-II", "Dead-Space-3",
    "Dekiru-Otoko-no-Mote-Life", "Descent", "Dragon-Warrior-VII", "Fire-Emblem-Awakening", "Fire-Emblem-Blazing-Sword",
    "Gothic", "Legend-of-Wulin-Heroes", "Lunar-Dragon-Song", "Lure-of-the-Temptress", "Mega-Man-4-(by-Simply-Simon)",
    "Mega-Man-5", "Pacific-General", "Paradox-Hohenzollern", "Puzzle-Agent", "Quest-for-Glory-1-5", "Rainbow-Six",
    "Ryse-Son-of-Rome", "Secret-of-Mana-(by-Ryushikaze)", "Shogo-Mobile-Armor-Division", "Siren-2", "Tropico-3",
    "Umineko-no-Naku-Koro-ni", "Warcraft-II", "Wing-Commander-III-Standoff",
}
UPDATE_NUMBER = re.compile(r"^Update%20([\d-]+)/$")


def test_chapter_order_is_coherent_across_the_archive():
    """Numbered updates come in increasing order everywhere except the reviewed exceptions, so a
    future change to chapter detection that scrambles an LP's order fails here with its name."""
    golden = _golden()["lets_plays"]
    out_of_order = set()
    for slug, record in golden.items():
        numbers = [tuple(int(x) for x in m.group(1).split("-")) for c in record["chapters"] if (m := UPDATE_NUMBER.match(c[0]))]
        if any(b <= a for a, b in zip(numbers, numbers[1:])):
            out_of_order.add(slug)
    assert out_of_order <= NON_NUMERIC_ORDER, sorted(out_of_order - NON_NUMERIC_ORDER)
    # the ones the ordering rule corrected
    chapters = {slug: [c[0] for c in golden[slug]["chapters"]] for slug in ("Last-Bible", "Omensight", "Legend-of-Wulin-Heroes")}
    assert chapters["Last-Bible"] == [f"Update%20{n:02d}/" for n in range(1, 15)]
    assert chapters["Omensight"][:10] == [f"Update%20{n:02d}/" for n in range(1, 11)]
    wulin = chapters["Legend-of-Wulin-Heroes"]
    assert wulin.index("Update%2082/") == wulin.index("Update%2081/") + 1   # listed in the toc: moved there
    assert wulin.index("Update%2041/") < wulin.index("Update%2001/")         # only mentioned in the prose: stays
    # the Let's Plays the live test builds
    live = _live_checksums()
    for slug in live:
        numbers = [tuple(int(x) for x in m.group(1).split("-")) for c in golden[slug]["chapters"] if (m := UPDATE_NUMBER.match(c[0]))]
        assert numbers == sorted(numbers), slug


@pytest.mark.asyncio
async def test_all_archives_error_file_records_failures_and_skipped_resources():
    from util.all_archives import build_one, ErrorLog
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    dead = "http://img.example/dead.png"
    sessions = {
        # builds, but one image is dead -> a "skipped-resources" entry
        "X-COM-Terror-from-the-Deep": _FakeSession("never-matches", responses={
            f"{url}/Update%2001/": _FakeResponse(200, f'<div id="content"><img src="{dead}"/></div>'.encode()),
            dead: _FakeResponse(404, b"gone")}),
        # an update answers 503 -> the build fails -> a "build-failed" entry with the report
        "Broken-LP": _FakeSession("never-matches", responses={
            "https://lparchive.org/Broken-LP": _FakeResponse(200, xcom),
            "https://lparchive.org/Broken-LP/Update%2003/": _FakeResponse(503, b"down")}),
        # not an LP page at all
        "Nope": _FakeSession("never-matches", responses={"https://lparchive.org/Nope": _FakeResponse(200, NOT_AN_LP_PAGE)}),
    }

    def factory(cache_dir, slug):
        return sessions[slug]

    with tempfile.TemporaryDirectory() as d:
        errors = ErrorLog(f"{d}/errors.jsonl")
        import lparchive2epub.lib as lib_module
        lib_module.RETRY_BACKOFF_BASE = 0
        try:
            results = [await asyncio.wait_for(build_one(slug, d, d, errors, factory), timeout=30) for slug in sessions]
        finally:
            lib_module.RETRY_BACKOFF_BASE = 1.0
        assert results == [True, False, False]
        assert os.path.exists(f"{d}/X-COM-Terror-from-the-Deep.epub") and not os.path.exists(f"{d}/Broken-LP.epub")
        with open(f"{d}/errors.jsonl", encoding="utf-8") as f:
            entries = [json.loads(line) for line in f]
    assert [(e["slug"], e["kind"]) for e in entries] == [
        ("X-COM-Terror-from-the-Deep", "skipped-resources"), ("Broken-LP", "build-failed"), ("Nope", "build-failed")]
    assert dead in entries[0]["report"] and "status code: 404" in entries[0]["report"] and "error" not in entries[0]
    assert entries[1]["error"] == "MissingUpdatesError" and "Update%2003/" in entries[1]["report"] and "503" in entries[1]["report"]
    assert entries[2]["error"] == "NotALetsPlayError" and "is not the page of a Let's Play" in entries[2]["message"]
    assert all(e["url"] == f"https://lparchive.org/{e['slug']}" and e["time"].endswith("+00:00") for e in entries)
    # no file requested: nothing is written, nothing fails
    assert ErrorLog(None).record("x", "build-failed", "r") is None


def test_all_archives_select_resumes_and_skips_videos():
    from util.all_archives import select
    index = [{"slug": "Done-LP", "type": "1"}, {"slug": "Video-LP", "type": "2"}, {"slug": "Hybrid-LP", "type": "3"},
             {"slug": "Untyped-LP", "type": None}]
    with tempfile.TemporaryDirectory() as d:
        open(f"{d}/Done-LP.epub", "wb").close()
        assert select(index, d, skip_videos=False, force=False) == (["Video-LP", "Hybrid-LP", "Untyped-LP"], 0, 1)
        assert select(index, d, skip_videos=True, force=False) == (["Hybrid-LP", "Untyped-LP"], 1, 1)
        assert select(index, d, skip_videos=True, force=True) == (["Done-LP", "Hybrid-LP", "Untyped-LP"], 1, 0)
        assert select(index, d, skip_videos=False, force=True) == (["Done-LP", "Video-LP", "Hybrid-LP", "Untyped-LP"], 0, 0)


@pytest.mark.asyncio
async def test_all_archives_passes_build_options_through():
    from util.all_archives import build_one, BuildOptions, ErrorLog
    from lparchive2epub.lib import ImageProcessing, FetchSettings
    from PIL import Image as PILImage
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    big = PILImage.new("RGB", (3000, 1000), "red")
    out = io.BytesIO()
    big.save(out, "JPEG")
    picture = "http://img.example/big.jpg"
    session = _FakeSession("never-matches", responses={
        f"{url}/Update%2001/": _FakeResponse(200, f'<div id="content"><img src="{picture}"/></div>'.encode()),
        picture: _FakeResponse(200, out.getvalue(), "image/jpeg")})
    processing = ImageProcessing(1600, 70)
    options = BuildOptions(image_processing=processing, cover=False, fetch=FetchSettings(concurrency=2, retries=1, quiet=True))
    with tempfile.TemporaryDirectory() as d:
        assert await asyncio.wait_for(build_one("X-COM-Terror-from-the-Deep", d, d, ErrorLog(None), lambda *_: session, options), timeout=30)
        with zipfile.ZipFile(f"{d}/X-COM-Terror-from-the-Deep.epub") as z:
            names = z.namelist()
            shrunk = [n for n in names if n.endswith(".jpg") or n.endswith(".jpeg")]
            assert shrunk and PILImage.open(io.BytesIO(z.read(shrunk[0]))).size == (1600, 533)
    assert processing.changed == 1 and not any("cover" in n for n in names)


def _image_items(book):
    from ebooklib.epub import EpubImage
    return [i for i in book.get_items() if isinstance(i, EpubImage) and i.file_name.startswith("images/") and "cover" not in i.file_name]


@pytest.mark.asyncio
async def test_images_wait_on_disk_until_the_book_is_written(monkeypatch):
    """Memory must not grow with the book: images go to a folder under the temporary directory as they
    are downloaded, are read back one by one while writing, each deleted once in the book, and the
    folder disappears with the build. --images-in-memory keeps them in memory and writes the same book."""
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    real_write = lib.epub.write_epub
    seen = {}

    def spying_write(name, book, options=None):
        spools = [p for p in os.listdir(seen["tmp"]) if p.startswith("lparchive2epub-")]
        items = _image_items(book)
        seen["spools"], seen["items"] = spools, items
        if spools:
            folder = os.path.join(seen["tmp"], spools[0])
            seen["files"] = {open(os.path.join(folder, f), "rb").read() for f in os.listdir(folder)}
            assert all(isinstance(i, lib.SpooledImage) and os.path.dirname(i.path) == folder for i in items)
        else:
            assert all(isinstance(i, lib.FreedOnWriteImage) and i.content == PNG_BYTES for i in items)
        real_write(name, book, options)
        seen["left"] = os.listdir(folder) if spools else None

    monkeypatch.setattr(lib.epub, "write_epub", spying_write)
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as d:
        monkeypatch.setenv("TMPDIR", tmp)
        monkeypatch.setattr(tempfile, "tempdir", None)   # forget the cached location
        seen["tmp"] = tmp
        await asyncio.wait_for(do(url, f"{d}/spooled.epub", _FakeSession("never-matches"), lambda *_: None), timeout=30)
        assert len(seen["spools"]) == 1 and seen["items"] and seen["files"] == {PNG_BYTES}
        assert seen["left"] == []                         # every image deleted as it went into the book
        assert os.listdir(tmp) == []                      # the folder itself is gone with the build
        assert os.listdir(d) == ["spooled.epub"]

        await asyncio.wait_for(do(url, f"{d}/in-memory.epub", _FakeSession("never-matches"), lambda *_: None, spool_images=False), timeout=30)
        assert seen["spools"] == [] and seen["items"]
        assert all(i.content is None for i in seen["items"])   # bytes dropped as each image was written
        with pytest.raises(RuntimeError, match="already written"):
            seen["items"][0].get_content()
        with open(f"{d}/spooled.epub", "rb") as a, open(f"{d}/in-memory.epub", "rb") as b:
            assert a.read() == b.read()


@pytest.mark.asyncio
async def test_spool_disk_error_aborts_the_build_instead_of_skipping_images(monkeypatch):
    """A full disk under the image folder is not a per-image problem: no book, a clear error, and the
    folder is removed. Checked for an image of the intro and for one of an update."""
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    other = b"\x89PNG\r\n\x1a\n" + b"another png"
    real_spool_write = lib.spool_write

    def full_disk_for(victim):
        def spool_write(spool_dir, name, content):
            if content == victim:
                raise OSError(28, "No space left on device")
            return real_spool_write(spool_dir, name, content)
        return spool_write

    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as d:
        monkeypatch.setenv("TMPDIR", tmp)
        monkeypatch.setattr(tempfile, "tempdir", None)
        for victim, responses in [
                (PNG_BYTES, {}),                                    # the intro's image, like every other
                (other, {f"{url}/Update%2001/": _FakeResponse(200, b'<div id="content"><img src="other.png"/></div>'),
                         f"{url}/Update%2001/other.png": _FakeResponse(200, other)})]:
            monkeypatch.setattr(lib, "spool_write", full_disk_for(victim))
            messages = []
            with pytest.raises(OutputError, match="No space left on device"):
                await asyncio.wait_for(do(url, f"{d}/book.epub", _FakeSession("never-matches", responses=responses), messages.append), timeout=30)
            assert os.listdir(d) == [] and os.listdir(tmp) == []
            assert not any("could not be retrieved" in m for m in messages)


@pytest.mark.asyncio
async def test_identical_images_share_one_spooled_file():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    urls = [f"{url}/Update%2001/a.png", f"{url}/Update%2002/b.png"]
    session = _FakeSession("never-matches", responses={u: _FakeResponse(200, PNG_BYTES) for u in urls})
    with tempfile.TemporaryDirectory() as d:
        registry = ImageRegistry(spool_dir=d)
        images = [lib.Image(n, u, BeautifulSoup("<img/>", "html.parser").img, u, url) for n, u in enumerate(urls)]
        first, second = await asyncio.gather(*(lib._get_image(session, img, registry) for img in images))
        assert first.data is second.data and isinstance(first.data, lib.SpooledImage)
        assert first.size == second.size == len(PNG_BYTES) and first.old_name != second.old_name
        assert os.listdir(d) == [os.path.basename(first.data.path)]
        assert first.data.get_content() == PNG_BYTES and os.listdir(d) == []   # read once, then gone


@pytest.mark.asyncio
async def test_links_to_images_lead_to_a_page_showing_the_image():
    """An EPUB hyperlink may only lead to a content document (epubcheck RSC-010 otherwise): a link to a
    picture gets a small page of its own, once per picture, outside the reading order."""
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    picture = b"\x89PNG\r\n\x1a\n" + b"the big one"
    pages = {1: '<p>See <a href="Images/big%20map.png">the full map</a> and <a href="Images/big%20map.png">again</a>.</p>',
             2: '<p><a href="../Update%2001/Images/big%20map.png">Same picture, other page</a></p>'}
    session = _FakeSession("never-matches", responses={
        f"{url}/Update%2001/Images/big%20map.png": _FakeResponse(200, picture),
        **{f"{url}/Update%200{n}/": _FakeResponse(200, f'<div id="content">{body}</div>'.encode()) for n, body in pages.items()}})
    files = await _build_book(session)
    stored = [n for n in files if files[n] == picture]
    assert len(stored) == 1
    image_hash = stored[0].removeprefix("EPUB/images/").removesuffix(".png")
    image_page = f"image_{image_hash}.xhtml"
    for n in (1, 2):
        page = files[f"EPUB/update_{n - 1}.xhtml"].decode()
        assert f'href="{image_page}"' in page and 'href="images/' not in page
    wrapper = files[f"EPUB/{image_page}"].decode()
    assert f'<img src="images/{image_hash}.png" alt="big map.png"/>' in wrapper and "<title>big map.png</title>" in wrapper
    assert 'href="style/lparchive.css"' in wrapper                        # styled like the rest, so the picture fits the screen
    opf = files["EPUB/content.opf"].decode()
    assert opf.count(f'href="{image_page}"') == 1                         # one page for the picture, linked from two updates
    assert f'<itemref idref="image_{image_hash}" linear="no"/>' in opf    # reachable from the link, skipped when turning pages
    assert image_page not in files["EPUB/nav.xhtml"].decode()


def _sources(files: dict) -> dict:
    opf = files["EPUB/content.opf"].decode()
    assert '<item href="sources.json" id="sources" media-type="application/json"/>' in opf
    assert 'idref="sources"' not in opf and "sources.json" not in files["EPUB/nav.xhtml"].decode()
    return json.loads(files["EPUB/sources.json"].decode("utf-8"))


@pytest.mark.asyncio
async def test_book_records_where_every_page_and_image_came_from():
    """sources.json (lparchive2epub-368): the book renames pages and pictures, so it says itself where each
    came from, for whoever holds only the book once the site is gone. Listed in the package, shown by no
    reader, the same from one build to the next."""
    from lparchive2epub.cover import tool_version
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    u1, u2 = f"{url}/Update%2001/", f"{url}/Update%2002/"
    tiff = _make_image("TIFF", (40, 30))
    shot = PNG_BYTES + b"shot"   # not PNG_BYTES: the fake session serves those for the landing page's own picture
    session = _FakeSession("never-matches", responses={
        u1: _FakeResponse(200, b'<div id="content"><img src="shot.png"/><img src="shot.png"/><img src="map.tif"/>'
                               b'<img src="http://dead.example/a.png"/><a href="ftp://x/y.png">odd</a>'
                               b'<a href="Images/big.png">the big one</a></div>'),
        u2: _FakeResponse(200, b'<div id="content"><img src="../Update%2001/shot.png"/><img src="same.png"/>'
                               b'<img src="Smilies/emot-x.gif"/><img src="never.png"/></div>'),
        f"{u1}shot.png": _FakeResponse(200, shot, "image/png; charset=binary"),
        f"{u2}same.png": _FakeResponse(200, shot, "image/x-png"),                 # same bytes, other URL
        f"{u1}map.tif": _FakeResponse(200, tiff, "image/tiff"),                   # converted to PNG
        "http://dead.example/a.png": _FakeResponse(404, b"gone"),
        f"{u1}Images/big.png": _FakeResponse(200, PNG_BYTES + b"big"),           # linked: gets an image page
        f"{u2}Smilies/emot-x.gif": _FakeResponse(404, b"not here"),              # a smilie: found site-wide (fallback)
        f"{url}/Smilies/emot-x.gif": _FakeResponse(404, b"no own copy"),
        "https://lparchive.org/Smilies/emot-x.gif": _FakeResponse(200, GIF_BYTES, None),
        f"{u2}never.png": _FakeResponse(404, b"never archived"),                # skipped: archive-missing
    })
    files = await _build_book(session)
    data = _sources(files)
    assert data["format"] == "lparchive2epub sources 1" and data["lets_play"] == url
    assert data["tool"] == {"name": "lparchive2epub", "version": tool_version()}
    assert data["options"] == {"max_image_size": None, "jpeg_quality": None}
    assert set(data) == {"format", "lets_play", "tool", "options", "hash", "pages", "images", "skipped"}   # no build time

    pages = data["pages"]
    assert pages[0] == {"file": "introduction.xhtml", "url": url}
    updates = [p for p in pages if p["file"].startswith("update_")]
    assert len(updates) == 18 and [p["file"] for p in updates] == [f"update_{n}.xhtml" for n in range(18)]
    assert updates[0] == {"file": "update_0.xhtml", "url": u1, "title": "Update/Video 1", "listed": True, "retrieved": True}
    assert updates[1]["url"] == u2 and updates[1]["title"] == "Update/Video 2"
    image_pages = [p for p in pages if p["file"].startswith("image_")]
    big_hash = lib.get_blake2b_hash(PNG_BYTES + b"big")
    assert image_pages == [{"file": f"image_{big_hash}.xhtml", "shows": f"images/{big_hash}.png"}]
    assert [p["file"] for p in pages] == ["introduction.xhtml", *(p["file"] for p in updates), *(p["file"] for p in image_pages)]

    images = {i["file"]: i for i in data["images"]}
    assert list(images) == sorted(images)
    stored_shot = images[f"images/{lib.get_blake2b_hash(shot)}.png"]
    assert stored_shot["media_type"] == "image/png" and stored_shot["size"] == len(shot) and "original" not in stored_shot
    assert stored_shot["sources"] == [   # sorted by URL; the references of a URL sorted and deduplicated
        {"url": f"{u1}shot.png", "served_type": "image/png",
         "references": [{"page": u1, "src": "shot.png"}, {"page": u2, "src": "../Update%2001/shot.png"}]},
        {"url": f"{u2}same.png", "served_type": "image/x-png", "references": [{"page": u2, "src": "same.png"}]},
    ]
    (converted,) = [i for i in images.values() if i.get("original")]
    assert converted["media_type"] == "image/png" and converted["file"].endswith(".png")
    assert converted["original"] == {"blake2b": lib.get_blake2b_hash(tiff), "size": len(tiff), "media_type": "image/tiff"}
    assert converted["sources"] == [{"url": f"{u1}map.tif", "served_type": "image/tiff", "references": [{"page": u1, "src": "map.tif"}]}]
    smilie = images[f"images/{lib.get_blake2b_hash(GIF_BYTES)}.gif"]
    assert smilie["sources"] == [{"url": f"{u2}Smilies/emot-x.gif", "fetched_from": "https://lparchive.org/Smilies/emot-x.gif",
                                  "served_type": None, "references": [{"page": u2, "src": "Smilies/emot-x.gif"}]}]
    assert f"images/{big_hash}.png" in images
    landing_picture = images[f"images/{lib.get_blake2b_hash(PNG_BYTES)}.png"]
    assert landing_picture["sources"][0]["references"] == [{"page": url, "src": "Images/1-OP80jpg.jpg"}]
    assert len(images) == 5   # the cover is not a downloaded picture

    assert data["skipped"] == [
        {"url": None, "cause": "other", "references": [{"page": u1, "src": "ftp://x/y.png"}]},
        {"url": "http://dead.example/a.png", "cause": "gone", "references": [{"page": u1, "src": "http://dead.example/a.png"}]},
        {"url": f"{u2}never.png", "cause": "archive-missing", "references": [{"page": u2, "src": "never.png"}]},
    ]
    assert (await _build_book(session))["EPUB/sources.json"] == files["EPUB/sources.json"]   # a second build: the same file


@pytest.mark.asyncio
async def test_sources_mark_placeholders_and_updates_found_through_next_links():
    url = "https://lparchive.org/Fire-Emblem-Awakening"
    landing = xcom.replace(b"X-COM: Terror from the Deep", b"Fire Emblem: Awakening")
    landing = re.sub(rb'<ul class="toc">.*?</ul>', b'<ul class="toc"><li><a href="Update%201/">Update 1</a></li>'
                     b'<li><a href="Update%202/">Update 2</a></li><li><a href="Update%204/">Update 4</a></li></ul>', landing, flags=re.S)
    responses = {url: _FakeResponse(200, landing), f"{url}/Update%204/": _FakeResponse(503, b"later")}
    for n, (prev, nxt) in {1: (None, 2), 2: (1, 3), 3: (2, 4)}.items():
        responses[f"{url}/Update%20{n}/"] = _FakeResponse(200, _update_page("Fire Emblem: Awakening", n, prev, nxt, f"Chapter {n}"))
    session = _FakeSession("never-matches", responses=responses)
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, lambda *_: None, allow_missing_updates=True,
                                  fetch=FetchSettings(retries=1)), timeout=60)
        with zipfile.ZipFile(out) as z:
            files = {n: z.read(n) for n in z.namelist()}
    pages = [p for p in _sources(files)["pages"] if p["file"].startswith("update_")]
    assert pages == [
        {"file": "update_0.xhtml", "url": f"{url}/Update%201/", "title": "Update 1", "listed": True, "retrieved": True},
        {"file": "update_1.xhtml", "url": f"{url}/Update%202/", "title": "Update 2", "listed": True, "retrieved": True},
        {"file": "update_3.xhtml", "url": f"{url}/Update%203/", "title": "Chapter 3", "listed": False, "retrieved": True},
        {"file": "update_2.xhtml", "url": f"{url}/Update%204/", "title": "Update 4", "listed": True, "retrieved": False},
    ]


@pytest.mark.asyncio
async def test_sources_record_the_reduction_options_and_original_bytes():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    big_jpeg = _make_image("JPEG", (800, 200), quality=95)
    session = _FakeSession("never-matches", responses={
        f"{url}/Update%2001/": _FakeResponse(200, b'<div id="content"><img src="huge.jpg"/><img src="tiny.png"/></div>'),
        f"{url}/Update%2001/huge.jpg": _FakeResponse(200, big_jpeg, "image/jpeg"),
        f"{url}/Update%2001/tiny.png": _FakeResponse(200, PNG_BYTES),   # not decodable: kept as is
    })
    files = await _build_book(session, image_processing=ImageProcessing(max_size=50, jpeg_quality=70))
    data = _sources(files)
    assert data["options"] == {"max_image_size": 50, "jpeg_quality": 70}
    (reduced,) = [i for i in data["images"] if i["file"].endswith(".jpg")]
    assert reduced["original"] == {"blake2b": lib.get_blake2b_hash(big_jpeg), "size": len(big_jpeg), "media_type": "image/jpeg"}
    assert reduced["size"] == len(files[f"EPUB/{reduced['file']}"]) < len(big_jpeg)
    (kept,) = [i for i in data["images"] if i["file"].endswith(".png")]
    assert "original" not in kept and kept["size"] == len(PNG_BYTES)


# A page the archive serves raw, as the author's source file, instead of through its template: no
# <div id="content">, the post sits between marker comments (Vanguard Bandits' Contest1/ .. Contest13/).
RAW_UPDATE_PAGE = """<html>

<head>
<meta http-equiv="content-type" content="text/html; charset=utf-8" />
<meta http-equiv="content-language" content="en" />
</head>

<body>
<!-- NOTE: Don't change the layout of these, it will be parsed by a script. -->

<!-- Chapter Titles are specified in the TOC in the index -->

<!-- !!DO NOT REMOVE!! BEGIN_CONTENT !!DO NOT REMOVE!! -->
		Challenges? I'll bite.<br />
<!-- an author's separator -- not valid XML -->
<br />
<img src="entry.png" /> See <a href="../Update%2001/">the first update</a>.
<!-- !!DO NOT REMOVE!! END_CONTENT !!DO NOT REMOVE!! -->
</body>
</html>
<!-- date  -->
"""


def test_raw_update_page_is_read_between_its_content_markers():
    root = "https://lparchive.org/Vanguard-Bandits/"
    chapters = [Chapters(0, root + "Update%2001/", "Update 01", "update_0.xhtml", "Update%2001/"),
                Chapters(1, root + "Contest1/", "Simply Simon", "update_1.xhtml", "Contest1/")]
    update = Extractor.get_update(chapters, get_cleaned_html(RAW_UPDATE_PAGE), chapters[1])
    out = str(update.content)
    assert out.startswith('<div id="content">') and out.endswith("</div>")
    assert "Challenges? I'll bite." in out
    assert "<!--" not in out   # the markers and the comments around them stay out of the book
    assert [i.url for i in update.images] == [root + "Contest1/entry.png"]
    assert 'href="update_0.xhtml"' in out   # links are resolved like on any other page


def test_page_without_any_content_block_is_not_an_update_page():
    chapter = Chapters(0, "https://lparchive.org/Some-LP/Index/", "Index", "update_0.xhtml", "Index/")
    with pytest.raises(lib.NotAnUpdatePageError, match="not an update page"):
        Extractor.get_update([chapter], get_cleaned_html("<html><body><p>Not a post.</p></body></html>"), chapter)


@pytest.mark.asyncio
async def test_raw_update_page_ends_up_in_the_book():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    session = _FakeSession("nothing-fails", responses={f"{url}/Update%2005/": _FakeResponse(200, RAW_UPDATE_PAGE.encode())})
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, lambda *_: None), timeout=30)
        assert len(_chapter_files(out)) == 18
        with zipfile.ZipFile(out) as z:
            page = z.read("EPUB/update_4.xhtml").decode()
    assert "Challenges? I'll bite." in page
    assert "DO NOT REMOVE" not in page


def test_readme_shows_the_current_help(monkeypatch):
    """The README pastes the --help text: it must be the parser's, as argparse lays it out on an 80-column terminal."""
    monkeypatch.setenv("COLUMNS", "80")
    readme = (files(resources) / ".." / ".." / "README.md").read_text(encoding="utf-8")
    start = readme.index("```\nusage: lparchive2epub") + len("```\n")
    pasted = readme[start:readme.index("```", start)]
    assert pasted == cli.arg_parser.format_help()
