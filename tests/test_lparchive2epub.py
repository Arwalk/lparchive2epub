import asyncio
import os
import re
import zipfile
from urllib.parse import unquote

import aiohttp
from lparchive2epub.lib import Extractor, Chapters, lparchive2epub, BeautifulSoup, normalize_url, build_update, Update, Intro, format_failures_report, ISSUES_URL, do, StrictModeError, MissingUpdatesError, ExtractionError, OutputError, check_output_path
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


class _FakeResponse:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self._body = body
        self.content = self

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

    def __init__(self, failing_slug: str):
        self.failing_slug = failing_slug
        self.requested = []

    def get(self, url, **kwargs):
        self.requested.append(url)
        if url.rstrip("/") == "https://lparchive.org/X-COM-Terror-from-the-Deep":
            return _FakeResponse(200, xcom)
        if self.failing_slug in url:
            return _FakeResponse(404, b"not here")
        if "Update" in url:
            return _FakeResponse(200, f'<div id="content"><h3>{unquote(url)}</h3>some text</div>'.encode())
        return _FakeResponse(200, b"\x89PNG fake image bytes")

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
            '<a href="Update%2001/">plain</a>'
            '<a href="Update%2001/#part2">anchor</a>'
            '<a href="../Update%2002/">from an update page</a>'
            '<a href="Update%2002/map.png">asset in a chapter</a>'
            '<a href="manual.pdf">local asset</a>'
            '<a href="http://example.com/Update%2001/">unrelated host, left alone</a>'
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
        "http://example.com/update_0.xhtml",
    ]
    assert not any(h.endswith("/") or ".xhtml/" in h for h in hrefs)


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
