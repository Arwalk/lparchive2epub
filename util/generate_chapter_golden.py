"""Regenerate tests/resources/chapters.json, the expected extraction result for every landing page.

    uv run python util/generate_chapter_golden.py

For each page in tests/resources/landing_pages.zip, runs Extractor.intro and records the facts and
the ordered chapter list. The test suite (test_every_landing_page_extracts_as_recorded) compares the
current code against this file, so a change in chapter detection anywhere in the archive shows up
as a failing test naming the Let's Play. When such a change is intended, rerun this script and
review the diff of chapters.json: one line per Let's Play, so git shows exactly what moved.
"""
import json
import sys
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lparchive2epub.lib import Extractor  # noqa: E402

RESOURCES = Path(__file__).resolve().parent.parent / "tests" / "resources"
SNAPSHOT = RESOURCES / "landing_pages.zip"
GOLDEN = RESOURCES / "chapters.json"


def extract(url: str, html: bytes) -> dict:
    intro = Extractor.intro(url, BeautifulSoup(html, "html.parser"))
    return {
        "title": intro.title, "author": intro.author, "parts": intro.parts,
        "began": intro.began, "ended": intro.ended, "published_on": intro.published_on,
        "tags": intro.tags, "thread_url": intro.thread_url,
        "chapters": [[c.original_href_slug, c.txt] for c in intro.chapters],
    }


def main():
    with zipfile.ZipFile(SNAPSHOT) as z:
        manifest = json.loads(z.read("index.json"))
        records = {}
        for entry in manifest["lets_plays"]:
            records[entry["slug"]] = {"type": entry["type"], **extract(entry["url"], z.read(entry["file"]))}
    lines = [f'{json.dumps(slug, ensure_ascii=False)}: {json.dumps(record, ensure_ascii=False)}'
             for slug, record in sorted(records.items())]
    GOLDEN.write_text('{\n"snapshot_date": ' + json.dumps(manifest["snapshot_date"]) + ',\n"lets_plays": {\n'
                      + ",\n".join(lines) + "\n}\n}\n", encoding="utf-8")
    chapters = sum(len(r["chapters"]) for r in records.values())
    print(f"{len(records)} Let's Plays, {chapters} chapters -> {GOLDEN} ({GOLDEN.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
