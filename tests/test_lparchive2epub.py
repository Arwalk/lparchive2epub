from lparchive2epub.lib import Extractor, Chapters
from importlib.resources import files
import tests.resources as resources
from lparchive2epub.lib import BeautifulSoup


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
    assert chapters[0] == Chapters(new_href="update_0.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%201/', txt='Foreword:')
    assert chapters[1] == Chapters(new_href="update_1.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%202/',
                                   txt="Episode I: C'mon C'mon")
    assert chapters[2] == Chapters(new_href="update_2.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%203/',
                                   txt='Episode II: Break on Through to the Other Side')
    assert chapters[3] == Chapters(new_href="update_3.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%204/',
                                   txt='Episode III: Monster Mash')
    assert chapters[4] == Chapters(new_href="update_4.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%205/',
                                   txt='Episode IV: Walk This Way')
    assert chapters[5] == Chapters(new_href="update_5.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%206/',
                                   txt='Episode V: With a Little Help from My Friends')
    assert chapters[6] == Chapters(new_href="update_6.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%207/',
                                   txt="Episode VI: You've Got A Friend In Me")
    assert chapters[7] == Chapters(new_href="update_7.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%208/',
                                   txt='Episode VII: The Devil Went Down to Georgia')
    assert chapters[8] == Chapters(new_href="update_8.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%209/',
                                   txt='Episode VIII: Hurt')
    assert chapters[9] == Chapters(new_href="update_9.xhtml",
                                   original_href='https://lparchive.org/Resident-Evil-1/Update%2010/',
                                   txt='Episode IX: The Best Things in Life are Free')
    assert chapters[10] == Chapters(new_href="update_10.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2011/',
                                    txt='Episode X: Another One Bites the Dust')
    assert chapters[11] == Chapters(new_href="update_11.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2012/',
                                    txt='Episode XI: Moonlight Sonata')
    assert chapters[12] == Chapters(new_href="update_12.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2013/',
                                    txt="Episode XII: I've Gotta Get a Message to You")
    assert chapters[13] == Chapters(new_href="update_13.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2014/',
                                    txt='Episode XIII: Communication Breakdown')
    assert chapters[14] == Chapters(new_href="update_14.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2015/',
                                    txt='Episode XIV: Thriller')
    assert chapters[15] == Chapters(new_href="update_15.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2016/',
                                    txt='Tangent: Adagio')
    assert chapters[16] == Chapters(new_href="update_16.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2017/',
                                    txt='Tangent: Baroque')
    assert chapters[17] == Chapters(new_href="update_17.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2018/',
                                    txt='Tangent: Cadenza')
    assert chapters[18] == Chapters(new_href="update_18.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2019/',
                                    txt='Tangent: Dissonance')
    assert chapters[19] == Chapters(new_href="update_19.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2020/',
                                    txt='Tangent: Dissonance B')
    assert chapters[20] == Chapters(new_href="update_20.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2021/',
                                    txt='Tangent: Dissonance C')
    assert chapters[21] == Chapters(new_href="update_21.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2022/',
                                    txt='Tangent: Dissonance D')
    assert chapters[22] == Chapters(new_href="update_22.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2023/',
                                    txt='Tangent: Dissonance E')
    assert chapters[23] == Chapters(new_href="update_23.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2024/',
                                    txt='Tangent: Etude')
    assert chapters[24] == Chapters(new_href="update_24.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2025/',
                                    txt='Tangent: Etude B')
    assert chapters[25] == Chapters(new_href="update_25.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2026/',
                                    txt='Tangent: Etude C')
    assert chapters[26] == Chapters(new_href="update_26.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2027/',
                                    txt='Episode XV: Mexican Radio')
    assert chapters[27] == Chapters(new_href="update_27.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2028/',
                                    txt='Episode XVI: Wishing You Were Here')
    assert chapters[28] == Chapters(new_href="update_28.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2029/',
                                    txt='Chapter 29')
    assert chapters[29] == Chapters(new_href="update_29.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2030/',
                                    txt='Episode XVII: Funky Town')
    assert chapters[30] == Chapters(new_href="update_30.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2031/',
                                    txt='Episode XVIII: Beneath the Sea')
    assert chapters[31] == Chapters(new_href="update_31.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2032/',
                                    txt='Episode XIX: Somewhere Over the Rainbow')
    assert chapters[32] == Chapters(new_href="update_32.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2033/',
                                    txt='Episode XX: Another Brick in the Wall')
    assert chapters[33] == Chapters(new_href="update_33.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2034/',
                                    txt='Episode XXI: Black Dog')
    assert chapters[34] == Chapters(new_href="update_34.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2035/',
                                    txt='Episode XXII: Gotta Get Away')
    assert chapters[35] == Chapters(new_href="update_35.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2036/',
                                    txt='Episode XXIII: Dazed and Confused')
    assert chapters[36] == Chapters(new_href="update_36.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2037/',
                                    txt="Episode XXIV: It Won't Be Long")
    assert chapters[37] == Chapters(new_href="update_37.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2038/',
                                    txt='Episode XV: Comfortably Numb')
    assert chapters[38] == Chapters(new_href="update_38.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2039/',
                                    txt="Episode XXVI: Blowin' in the Wind")
    assert chapters[39] == Chapters(new_href="update_39.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2040/',
                                    txt="Episode XXVII: Don't Stop 'Til You Get Enough")
    assert chapters[40] == Chapters(new_href="update_40.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2041/',
                                    txt='Episode XXVIII: Already Gone')
    assert chapters[41] == Chapters(new_href="update_41.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2042/',
                                    txt='Episode XXIX: Losing my Religion')
    assert chapters[42] == Chapters(new_href="update_42.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2043/',
                                    txt='Episode XXX: Everybody Hurts')
    assert chapters[43] == Chapters(new_href="update_43.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2044/',
                                    txt="Bonus Episode: Wesker's Report II (Part I)")
    assert chapters[44] == Chapters(new_href="update_44.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2045/',
                                    txt='Bonus Episode: Wesker\'s Report II - "Alexia 1"')
    assert chapters[45] == Chapters(new_href="update_45.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2046/',
                                    txt='Bonus Episode: Wesker\'s Report II - "Alexia 2"')
    assert chapters[46] == Chapters(new_href="update_46.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2047/',
                                    txt='Bonus Episode: Wesker\'s Report II - "Nemesis"')
    assert chapters[47] == Chapters(new_href="update_47.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2048/',
                                    txt='Bonus Episode: Wesker\'s Report II - "G-Virus"')
    assert chapters[48] == Chapters(new_href="update_48.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2049/',
                                    txt='Episode XXXI: Weird Science')
    assert chapters[49] == Chapters(new_href="update_49.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2050/',
                                    txt='Episode XXXII: Video Killed the Radio Star')
    assert chapters[50] == Chapters(new_href="update_50.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2051/',
                                    txt='Episode XXXIII: Walking on Sunshine')
    assert chapters[51] == Chapters(new_href="update_51.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2052/',
                                    txt="XXXIV: Singin' in the Rain")
    assert chapters[52] == Chapters(new_href="update_52.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2053/',
                                    txt="Episode XXXV: Knockin' on Heaven's Door")
    assert chapters[53] == Chapters(new_href="update_53.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2054/',
                                    txt='Episode XXXVI: Helter Skelter')
    assert chapters[54] == Chapters(new_href="update_54.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2055/',
                                    txt='Episode XXXVII: Stairway to Heaven')
    assert chapters[55] == Chapters(new_href="update_55.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2056/',
                                    txt='Episode XXXVIII: We Will Rock You')
    assert chapters[56] == Chapters(new_href="update_56.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2057/',
                                    txt="Episode XXXIX: Don't Fear the Reaper")
    assert chapters[57] == Chapters(new_href="update_57.xhtml",
                                    original_href='https://lparchive.org/Resident-Evil-1/Update%2058/',
                                    txt='Episode XL: Paint it, Black')

    b = BeautifulSoup(headshoots, "html.parser")
    chapters = Extractor.all_chapters("whatever", b)
    assert len(chapters) == 90

    b = BeautifulSoup(xcom, "html.parser")
    chapters = Extractor.all_chapters("whatever", b)
    assert len(chapters) == 18


def test_all_images():
    b = BeautifulSoup(re1, "html.parser")
    content = b.find("div", id="content")
    images = Extractor.all_images(content)
    assert len(images) == 0

    b = BeautifulSoup(headshoots, "html.parser")
    content = b.find("div", id="content")
    images = Extractor.all_images(content)
    assert len(images) == 10

    b = BeautifulSoup(xcom, "html.parser")
    content = b.find("div", id="content")
    images = Extractor.all_images(content)
    assert len(images) == 1
