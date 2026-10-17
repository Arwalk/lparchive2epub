import asyncio
import datetime
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


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.parametrize("slug", sorted(_live_checksums()))
async def test_live_build_matches_recorded_checksum(slug):
    """Builds the Let's Play from lparchive.org and compares the book byte for byte with the last
    recorded build. A mismatch means the output changed: the tool (then regenerate with
    util/live_checksums.py) or the site (a dead image host, an edited page)."""
    from util.live_checksums import build_checksum
    expected = _live_checksums()[slug]
    actual = await asyncio.wait_for(build_checksum(slug, None), timeout=600)
    assert actual == expected, (f"{slug}: the book built today differs from the recorded one. If the tool changed on "
                                f"purpose, run `uv run python util/live_checksums.py` and commit the new checksums.")


@pytest.mark.parametrize(("url", "expected"), [
    ("hhttp://lpix.org/2495492/purski.png", "http://lpix.org/2495492/purski.png"),
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
    # forum smilies: resolved against the page they 404, they all live under /Smilies/ at the site root
    assert Extractor.get_full_url(root, "../Smilies/emot-smith.gif") == "https://lparchive.org/Smilies/emot-smith.gif"
    assert Extractor.get_full_url(root, "Smilies/emot-smith.gif") == "https://lparchive.org/Smilies/emot-smith.gif"
    assert Extractor.get_full_url(root, "https://lparchive.org/Dark-Souls/Smilies/emot-colbert.gif") == "https://lparchive.org/Smilies/emot-colbert.gif"
    assert Extractor.get_full_url(root, "/Smilies/emot-smith.gif") == "https://lparchive.org/Smilies/emot-smith.gif"
    # ...but only on lparchive.org: the forum's own copies are left alone
    assert Extractor.get_full_url(root, "https://fi.somethingawful.com/images/smilies/emot-argh.gif") == "https://fi.somethingawful.com/images/smilies/emot-argh.gif"
    assert Extractor.get_full_url(root, "https://lpix.org/x/Smilies/emot-argh.gif") == "https://lpix.org/x/Smilies/emot-argh.gif"
    assert Extractor.get_full_url(root, "//lpix.org/a.png") == "https://lpix.org/a.png"
    assert Extractor.get_full_url(root, " img\\sub\\a.png ") == f"{root}img/sub/a.png"
    assert Extractor.get_full_url(root, "https://lpix.org/a.png") == "https://lpix.org/a.png"
    # the landing page URL has no trailing slash
    assert Extractor.get_full_url("https://lparchive.org/Some-LP", "Update%2001/") == "https://lparchive.org/Some-LP/Update%2001/"


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
    (b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', "http://x/a", None, ("image/svg+xml", "svg")),
    (b"\x00\x01unknown", "http://x/a.webp", None, ("image/webp", "webp")),             # URL fallback
    (b"\x00\x01unknown", "http://x/a", "image/gif; charset=binary", ("image/gif", "gif")),  # header fallback
    (b"<!DOCTYPE html><html><body>Not found</body></html>", "http://x/a.png", "text/html", None),
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
    session = _FakeSession("never-matches", responses={wiki: _FakeResponse(403, b"forbidden")})
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
    session = _FakeSession("never-matches", responses={
        jpeg_as_png_url: _FakeResponse(200, JPEG_BYTES, "image/png"),   # lying extension and header
        dead_host_url: _FakeResponse(200, b"<!DOCTYPE html><html><body>gone</body></html>", "text/html"),
    })
    # one chapter embeds both images
    session.responses[f"{url}/Update%2001/"] = _FakeResponse(
        200, f'<div id="content"><img src="shot.PNG"/><img src="{dead_host_url}"/></div>'.encode())
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
    report = "\n".join(messages)
    assert dead_host_url in report and "Not an image" in report and "text/html" in report


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
    assert Extractor.get_image_url(root, "../Smilies/emot-smith.gif") == "https://lparchive.org/Smilies/emot-smith.gif"
    assert Extractor.get_image_url(root, "javascript:void(0)") is None
    assert Extractor.get_image_url(root, "hhttp://lpix.org/a.png") == "http://lpix.org/a.png"


def test_lparchive_fallback_urls():
    assert lib.lparchive_fallback_urls("https://lparchive.org/Echo-Night/Images/40-Pole&Paddle.jpg") == [
        "https://lparchive.org/Echo-Night/Images/40-Pole&amp;Paddle.jpg"]
    assert lib.lparchive_fallback_urls("https://lparchive.org/Echo-Night/Images/40-Pole&amp;Paddle.jpg") == []
    assert lib.lparchive_fallback_urls("https://lparchive.org/Echo-Night/Images/40-Pole.jpg") == []
    assert lib.lparchive_fallback_urls("https://img.example/show.php?a=1&b=2") == []   # a real query string
    # a picture referenced next to the landing page normally lives in the LP's Images/ folder
    root = "https://lparchive.org/Ratchet-Clank-Into-the-Nexus"
    assert lib.lparchive_fallback_urls(f"{root}/62-B04.png") == [f"{root}/Images/62-B04.png"]
    assert lib.lparchive_fallback_urls(f"{root}/Images/62-B04.png") == []
    assert lib.lparchive_fallback_urls(f"{root}/Update%2001/62-B04.png") == []
    assert lib.lparchive_fallback_urls(f"{root}/") == []
    assert lib.lparchive_fallback_urls("https://lparchive.org/Smilies/emot-argh.gif") == ["https://lparchive.org/Smilies/Images/emot-argh.gif"]
    assert lib.lparchive_fallback_urls(f"{root}/1-a&b.png") == [
        f"{root}/1-a&amp;b.png", f"{root}/Images/1-a&b.png", f"{root}/Images/1-a&amp;b.png"]


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
async def test_smilies_are_fetched_from_the_site_wide_folder():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    smilie_url = "https://lparchive.org/Smilies/emot-allears.gif"
    wrong_urls = [f"{url}/Update%2001/Smilies/emot-allears.gif", f"{url}/Smilies/emot-allears.gif"]
    session = _FakeSession("never-matches", responses={smilie_url: _FakeResponse(200, GIF_BYTES, "image/gif")})
    for wrong in wrong_urls:
        session.responses[wrong] = _FakeResponse(404, b"not here")   # like the site
    session.responses[f"{url}/Update%2001/"] = _FakeResponse(
        200, b'<div id="content"><img src="Smilies/emot-allears.gif"/> and <img src="../Smilies/emot-allears.gif"/></div>')
    messages = []
    with tempfile.TemporaryDirectory() as d:
        out = f"{d}/book.epub"
        await asyncio.wait_for(do(url, out, session, messages.append), timeout=30)
        with zipfile.ZipFile(out) as z:
            chapter = z.read("EPUB/update_0.xhtml").decode()
            gifs = [n for n in z.namelist() if n.startswith("EPUB/images/") and n.endswith(".gif")]

    assert session.requested.count(smilie_url) == 1          # both references share one download
    assert not any(w in session.requested for w in wrong_urls)
    assert len(gifs) == 1
    assert chapter.count(f'src="{gifs[0].removeprefix("EPUB/")}"') == 2
    assert "missing-image" not in chapter
    assert "Smilies" not in "\n".join(messages)


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
async def test_fetch_with_retries_returns_body_and_decodes_text():
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    session = _FakeSession("never-matches", responses={url: _FakeResponse(200, "caf\u00e9".encode("utf-8"), "text/html; charset=utf-8")})
    fetched = await fetch_with_retries(session, url)
    assert isinstance(fetched, Fetched)
    assert fetched.body == "caf\u00e9".encode("utf-8") and fetched.text() == "caf\u00e9"
    assert fetched.content_type == "text/html; charset=utf-8"
    assert session.requested == [url]


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
      <table border="1" cellpadding="2" cellspacing="0" align="center"><tr><td valign="top" bgcolor="#fff" nowrap="nowrap">cell</td></tr></table>
      <span style="color: #336699;">speaker colour kept</span>
      <span class="bbc-spoiler" onmouseout="x()" onmouseover="y()" style="color: rgb(0, 0, 0); background-color: rgb(0, 0, 0);">hidden</span>
      <span style="color:#000000; background:#000000">also hidden, no class</span>
      <o:p>office</o:p>
    </div>"""
    soup = get_cleaned_html(html)
    out = str(soup)

    for gone in ("<script", "<noscript", "<style", "<form", "<input", "<button", "<select", "<textarea",
                 "<iframe", "<embed", "<object", "<font", "<center", "<o:p", "onclick", "onmouseout", "onmouseover",
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
    # spoilers are readable and marked for the stylesheet
    assert '<span class="bbc-spoiler">hidden</span>' in out
    assert '<span class="bbc-spoiler">also hidden, no class</span>' in out
    assert "office" in out


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
    assert (media_type, ext) == ("image/jpeg", "jpg") and len(data) < len(bmp)

    assert reduce_image(GIF_BYTES, "image/gif", settings) is None          # GIFs are never touched
    assert reduce_image(b"\x89PNG\r\n\x1a\ncorrupted", "image/png", settings) is None  # undecodable: kept


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
        assert resolve_cache_path(f"{d}/lp") == f"{d}/lp.sqlite"
        assert resolve_cache_path(f"{d}/lp.db") == f"{d}/lp.db"
        created = check_cache_path(f"{d}/lp")
        assert created == f"{d}/lp.sqlite" and os.path.exists(created)
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
        assert f"using cache {d}/lp.sqlite" in capsys.readouterr().err
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
        assert not wrapper.find(["p", "div", "blockquote", "ul", "table", "pre"]), str(wrapper)


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
async def test_output_defaults_to_the_title_in_the_current_directory(monkeypatch):
    url = "https://lparchive.org/X-COM-Terror-from-the-Deep"
    messages = []
    with tempfile.TemporaryDirectory() as d:
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
