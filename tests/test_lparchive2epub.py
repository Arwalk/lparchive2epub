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
    intro = Extractor.intro(b)
    assert intro.title == "Resident Evil 1"
    assert intro.author == "The Dark Id"
    assert intro.language == "en"

    b = BeautifulSoup(headshoots, "html.parser")
    intro = Extractor.intro(b)
    assert intro.title == "Dwarf Fortress - Headshoots"
    assert intro.author == "Various"
    assert intro.language == "en"

    b = BeautifulSoup(xcom, "html.parser")
    intro = Extractor.intro(b)
    assert intro.title == "X-COM: Terror from the Deep"
    assert intro.author == "GuavaMoment"
    assert intro.language == "en"

def test_extractor_chapters():
    b = BeautifulSoup(re1, "html.parser")
    chapters = Extractor.all_chapters(b, "https://lparchive.org/Resident-Evil-1")
    assert len(chapters) == 58
    assert chapters[0] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%201/', txt='Foreword:')
    assert chapters[1] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%202/', txt="Episode I: C'mon C'mon")
    assert chapters[2] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%203/', txt='Episode II: Break on Through to the Other Side')
    assert chapters[3] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%204/', txt='Episode III: Monster Mash')
    assert chapters[4] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%205/', txt='Episode IV: Walk This Way')
    assert chapters[5] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%206/', txt='Episode V: With a Little Help from My Friends')
    assert chapters[6] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%207/', txt="Episode VI: You've Got A Friend In Me")
    assert chapters[7] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%208/', txt='Episode VII: The Devil Went Down to Georgia')
    assert chapters[8] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%209/', txt='Episode VIII: Hurt')
    assert chapters[9] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2010/', txt='Episode IX: The Best Things in Life are Free')
    assert chapters[10] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2011/', txt='Episode X: Another One Bites the Dust')
    assert chapters[11] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2012/', txt='Episode XI: Moonlight Sonata')
    assert chapters[12] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2013/', txt="Episode XII: I've Gotta Get a Message to You")
    assert chapters[13] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2014/', txt='Episode XIII: Communication Breakdown')
    assert chapters[14] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2015/', txt='Episode XIV: Thriller')
    assert chapters[15] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2016/', txt='Tangent: Adagio')
    assert chapters[16] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2017/', txt='Tangent: Baroque')
    assert chapters[17] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2018/', txt='Tangent: Cadenza')
    assert chapters[18] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2019/', txt='Tangent: Dissonance')
    assert chapters[19] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2020/', txt='Tangent: Dissonance B')
    assert chapters[20] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2021/', txt='Tangent: Dissonance C')
    assert chapters[21] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2022/', txt='Tangent: Dissonance D')
    assert chapters[22] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2023/', txt='Tangent: Dissonance E')
    assert chapters[23] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2024/', txt='Tangent: Etude')
    assert chapters[24] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2025/', txt='Tangent: Etude B')
    assert chapters[25] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2026/', txt='Tangent: Etude C')
    assert chapters[26] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2027/', txt='Episode XV: Mexican Radio')
    assert chapters[27] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2028/', txt='Episode XVI: Wishing You Were Here')
    assert chapters[28] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2029/', txt='Chapter 29')
    assert chapters[29] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2030/', txt='Episode XVII: Funky Town')
    assert chapters[30] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2031/', txt='Episode XVIII: Beneath the Sea')
    assert chapters[31] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2032/', txt='Episode XIX: Somewhere Over the Rainbow')
    assert chapters[32] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2033/', txt='Episode XX: Another Brick in the Wall')
    assert chapters[33] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2034/', txt='Episode XXI: Black Dog')
    assert chapters[34] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2035/', txt='Episode XXII: Gotta Get Away')
    assert chapters[35] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2036/', txt='Episode XXIII: Dazed and Confused')
    assert chapters[36] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2037/', txt="Episode XXIV: It Won't Be Long")
    assert chapters[37] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2038/', txt='Episode XV: Comfortably Numb')
    assert chapters[38] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2039/', txt="Episode XXVI: Blowin' in the Wind")
    assert chapters[39] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2040/', txt="Episode XXVII: Don't Stop 'Til You Get Enough")
    assert chapters[40] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2041/', txt='Episode XXVIII: Already Gone')
    assert chapters[41] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2042/', txt='Episode XXIX: Losing my Religion')
    assert chapters[42] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2043/', txt='Episode XXX: Everybody Hurts')
    assert chapters[43] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2044/', txt="Bonus Episode: Wesker's Report II (Part I)")
    assert chapters[44] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2045/', txt='Bonus Episode: Wesker\'s Report II - "Alexia 1"')
    assert chapters[45] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2046/', txt='Bonus Episode: Wesker\'s Report II - "Alexia 2"')
    assert chapters[46] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2047/', txt='Bonus Episode: Wesker\'s Report II - "Nemesis"')
    assert chapters[47] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2048/', txt='Bonus Episode: Wesker\'s Report II - "G-Virus"')
    assert chapters[48] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2049/', txt='Episode XXXI: Weird Science')
    assert chapters[49] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2050/', txt='Episode XXXII: Video Killed the Radio Star')
    assert chapters[50] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2051/', txt='Episode XXXIII: Walking on Sunshine')
    assert chapters[51] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2052/', txt="XXXIV: Singin' in the Rain")
    assert chapters[52] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2053/', txt="Episode XXXV: Knockin' on Heaven's Door")
    assert chapters[53] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2054/', txt='Episode XXXVI: Helter Skelter')
    assert chapters[54] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2055/', txt='Episode XXXVII: Stairway to Heaven')
    assert chapters[55] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2056/', txt='Episode XXXVIII: We Will Rock You')
    assert chapters[56] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2057/', txt="Episode XXXIX: Don't Fear the Reaper")
    assert chapters[57] == Chapters(href='https://lparchive.org/Resident-Evil-1/Update%2058/', txt='Episode XL: Paint it, Black')

    b = BeautifulSoup(headshoots, "html.parser")
    chapters = Extractor.all_chapters(b, "None")
    assert len(chapters) == 90

    b = BeautifulSoup(xcom, "html.parser")
    chapters = Extractor.all_chapters(b, "None")
    assert len(chapters) == 18
