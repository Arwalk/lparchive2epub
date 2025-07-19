from lparchive2epub.lib import Extractor, Chapters, lparchive2epub, BeautifulSoup
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
