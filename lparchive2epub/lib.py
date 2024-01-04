from typing import TextIO, List
import requests
from bs4 import BeautifulSoup
from ebooklib import epub
from dataclasses import dataclass


@dataclass
class Intro:
    title: str
    language: str
    author: str
    intro: str
    images_path: List[str]
    chapter_links: List[str]


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


def lparchive2epub(url: str, file: TextIO):
    page = requests.get(url)
    landing = BeautifulSoup(page.content, 'html.parser')
    book = epub.EpubBook()
