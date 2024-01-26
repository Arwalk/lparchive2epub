from typing import TextIO, List
import requests
from bs4 import BeautifulSoup, Comment
from ebooklib import epub
from dataclasses import dataclass
from itertools import chain

@dataclass
class Intro:
    title: str
    language: str
    author: str
    intro: str
    images_path: List[str]
    chapter_links: List[str]


@dataclass(order=True)
class Chapters:
    href: str
    txt: str

    def __hash__(self):
        return hash((self.href, self.txt))

    def __post_init__(self):
        self.sort_index = self.href

class Extractor:

    @staticmethod
    def intro(p: BeautifulSoup) -> Intro:
        title = p.title.text
        author = next(x for x in p.find_all("meta") if x.get("name", None) == "author").get("content", None)
        language = "en"
        content = p.find("div", id="content")
        content.find_all()

        return Intro(
            title=title, language=language, author=author, intro="", images_path=[], chapter_links=[]
        )

    @staticmethod
    def all_chapters(p: BeautifulSoup, root: str) -> List[Chapters]:

        content = p.find("div", id="content")

        chapters = content.find_all("a")
        chapters = [x for x in chapters if "Update" in x.get("href", None) and (root in x.get("href", None) or x.get("href", None).startswith("Update"))]
        chapters = [Chapters(href=c.get("href", None), txt=str(c.string)) for c in chapters]

        return chapters

def lparchive2epub(url: str, file: TextIO):
    page = requests.get(url)
    landing = BeautifulSoup(page.content, 'html.parser')
    book = epub.EpubBook()
