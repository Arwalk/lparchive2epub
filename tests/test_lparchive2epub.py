import asyncio
import hashlib
import io
import os
import random
import re
import zipfile
from urllib.parse import unquote

import aiohttp
from lparchive2epub.lib import Extractor, Chapters, lparchive2epub, BeautifulSoup, normalize_url, build_update, Update, Intro, format_failures_report, ISSUES_URL, do, StrictModeError, MissingUpdatesError, ExtractionError, OutputError, check_output_path, detect_image_type, NotFoundError, NetworkError, RetriesExhaustedError, NotALetsPlayError, normalize_lp_url, fetch_with_retries, Fetched, get_cleaned_html, EXIT_NOT_FOUND, EXIT_NETWORK, EXIT_OUTPUT, EXIT_INTERRUPTED
import lparchive2epub.lib as lib
from lparchive2epub import main as cli
from importlib.resources import files
import tests.resources as resources
import pytest
import tempfile
from blake3 import blake3
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
    intro = Extractor.intro("", b)
    assert intro.title == "Resident Evil 1"
    assert intro.author == "The Dark Id"
    assert intro.language == "en"

    b = BeautifulSoup(headshoots, "html.parser")
    intro = Extractor.intro("",b)
    assert intro.title == "Dwarf Fortress - Headshoots"
    assert intro.author == "Various"
    assert intro.language == "en"

    b = BeautifulSoup(xcom, "html.parser")
    intro = Extractor.intro("", b)
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

@pytest.mark.asyncio
async def test_lparchive2epub(lp, b3sum):
    pytest.skip("Unable to run until ebooklib update")
    if not lp or not b3sum:
        pytest.skip("no tests were collected")
    cache = SQLiteBackend(f"cache/{lp}", autoclose=False, expire_after=None)
    url = f"https://lparchive.org/{lp}"
    with tempfile.NamedTemporaryFile() as temp_file:
        await lparchive2epub(url, temp_file.name, CachedSession(cache=cache))
        file_hasher = blake3(max_threads=blake3.AUTO)
        file_hasher.update_mmap(temp_file.name)
        file_hash = file_hasher.hexdigest()
        assert file_hash == b3sum
    await cache.close()


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
    assert Extractor.get_full_url(root, "../Smilies/emot-smith.gif") == "https://lparchive.org/Shin-Megami-Tensei-Devil-Summoner/Smilies/emot-smith.gif"
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
            build_update(session, chapter, Update(content=content, images=images), intro, {}, failures),
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
            return _FakeResponse(200, f'<div id="content"><h3>{unquote(url)}</h3>some text</div>'.encode())
        return _FakeResponse(200, PNG_BYTES)

    async def close(self):
        pass


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
    # the HTML page served instead of an image is not embedded: link left as is and reported
    assert dead_host_url in chapter
    assert not any("html" in n for n in image_files)
    report = "\n".join(messages)
    assert dead_host_url in report and "Not an image" in report and "text/html" in report


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
        cli.main(["--no-cache", "https://lparchive.org/Some-LP", "out.epub"])
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
        images = re.findall(r'href="images/[^"]+"', opf)
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
    cli.main(["--no-cache", "lparchive.org/Some-LP/Update%2007/", "out.epub"])
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
                if n.endswith(".xhtml") and n != "EPUB/nav.xhtml":
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
