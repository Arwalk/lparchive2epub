from dataclasses import dataclass
from typing import TextIO, List

import requests
from bs4 import BeautifulSoup
from ebooklib import epub


@dataclass(order=True)
class Chapters:
    original_href: str
    txt: str
    new_href: str

    def __hash__(self):
        return hash((self.original_href, self.txt))

    def __post_init__(self):
        self.sort_index = self.original_href


@dataclass
class Image:
    src: str
    media_type: str


@dataclass
class Intro:
    title: str
    language: str
    author: str
    intro: str
    images: List[Image]
    chapters: List[Chapters]


class Extractor:

    @staticmethod
    def intro(p: BeautifulSoup) -> Intro:
        title = p.title.text
        author = next(x for x in p.find_all("meta") if x.get("name", None) == "author").get("content", None)
        language = "en"
        content = p.find("div", id="content")
        chapters = Extractor.all_chapters(p)
        for c in chapters:
            a = content.find("a", text=c.txt)
            a['href'] = c.new_href

        images = Extractor.all_images(content)

        return Intro(
            title=title, language=language, author=author, intro=str(content), images=images, chapters=chapters
        )

    @staticmethod
    def all_chapters(p: BeautifulSoup) -> List[Chapters]:
        content = p.find("div", id="content")

        chapters = content.find_all("a")
        chapters = (x for x in chapters if "Update" in x.get("href", None))
        chapters = [
            Chapters(
                original_href=c.get("href", None),
                txt=str(c.string),
                new_href=f"update_{i}.xhtml") for i, c in enumerate(chapters)
        ]

        return chapters

    @staticmethod
    def all_images(content: BeautifulSoup) -> List[Image]:
        images = content.find_all("img")
        return [Image(src=x['src'], media_type=x["src"][-3:]) for x in images]


def lparchive2epub(url: str, file: TextIO):
    page = requests.get(url)
    landing = BeautifulSoup(page.content, 'html.parser')
    book = epub.EpubBook()
