"""Snapshot every Let's Play landing page on lparchive.org into a zip used by the test suite.

    uv run python util/snapshot_landing_pages.py --cache dist/snapshot-cache

Reads the LP index embedded in the front page, fetches each landing page (politely: a few at a
time, and the run stops if the site answers 429 or 503), and writes tests/resources/landing_pages.zip
containing one HTML file per LP plus index.json. The zip is written deterministically (sorted
entries, fixed timestamps) so refreshing it only changes what really changed on the site.
Re-running with the same --cache file only fetches pages that are not cached yet.
"""
import argparse
import asyncio
import datetime
import json
import re
import sys
import zipfile
from pathlib import Path

from aiohttp_client_cache import CachedSession, SQLiteBackend
from tqdm.asyncio import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lparchive2epub.lib import (CURL_HEADERS, LPARCHIVE_ROOT, FetchError, NonRetryableError, RetriesExhaustedError,  # noqa: E402
                                check_cache_path, fetch_with_retries)

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "tests" / "resources" / "landing_pages.zip"
INDEX_PATTERN = re.compile(r"tocdata\s*=\s*(\[.*?\}\]);", re.DOTALL)
# Statuses that mean "slow down": the whole run stops rather than hammering the site
BACK_OFF_STATUSES = {429, 503}


def read_index(front_page: str) -> list[dict]:
    """The front page embeds the full LP list as a JavaScript array:
    [{t: title, a: author, u: '/Slug/', ty: type, tg: [tags]}, ...].

    One page can be listed several times (a series page such as /Space-Quest-Series/ is listed once
    per game), so entries are grouped by slug and every listing is kept under "listed_as"."""
    m = INDEX_PATTERN.search(front_page)
    if not m:
        raise SystemExit("could not find the LP index (tocdata) in the front page")
    entries = json.loads(m.group(1).replace("'", '"'))
    by_slug: dict[str, dict] = {}
    for entry in entries:
        slug = entry["u"].strip("/")
        record = by_slug.setdefault(slug, {"slug": slug, "url": f"{LPARCHIVE_ROOT}/{slug}", "listed_as": [],
                                           "type": entry.get("ty"), "tags": entry.get("tg", [])})
        record["listed_as"].append({"title": entry.get("t", ""), "author": entry.get("a", "")})
    return [by_slug[slug] for slug in sorted(by_slug)]


async def snapshot(output: Path, cache_file: str, concurrency: int, limit: int | None):
    pages: dict[str, bytes] = {}
    failures: dict[str, str] = {}
    stop = asyncio.Event()
    semaphore = asyncio.Semaphore(concurrency)

    async with CachedSession(cache=SQLiteBackend(cache_file, expire_after=-1, fast_save=True, autoclose=True)) as session:
        async with session.get(f"{LPARCHIVE_ROOT}/", headers=CURL_HEADERS) as r:
            index = read_index(await r.text())
        if limit:
            index = index[:limit]
        listings = sum(len(e["listed_as"]) for e in index)
        print(f"{len(index)} Let's Play pages in the index ({listings} listings)", file=sys.stderr)

        async def fetch(entry: dict):
            if stop.is_set():
                return
            async with semaphore:
                if stop.is_set():
                    return
                try:
                    fetched = await fetch_with_retries(session, entry["url"] + "/")
                    pages[entry["slug"]] = fetched.body
                except (NonRetryableError, RetriesExhaustedError, FetchError) as e:
                    failures[entry["slug"]] = str(e)
                    if getattr(e, "status", None) in BACK_OFF_STATUSES:
                        stop.set()

        await tqdm.gather(*(fetch(entry) for entry in index), desc="landing pages")

    if stop.is_set():
        raise SystemExit("the site asked us to slow down (429/503): nothing written, try again later")

    write_zip(output, index, pages, failures)
    print(f"{len(pages)} pages written to {output} ({output.stat().st_size / 1e6:.1f} MB), {len(failures)} failures",
          file=sys.stderr)
    for slug, reason in sorted(failures.items()):
        print(f"  - {slug}: {reason}", file=sys.stderr)


def write_zip(output: Path, index: list[dict], pages: dict[str, bytes], failures: dict[str, str]):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    manifest = {"snapshot_date": stamp, "lets_plays": []}
    for entry in index:
        record = dict(entry)
        record["file"] = f"landing_pages/{entry['slug']}.html" if entry["slug"] in pages else None
        if entry["slug"] in failures:
            record["error"] = failures[entry["slug"]]
        manifest["lets_plays"].append(record)

    fixed_time = (1980, 1, 1, 0, 0, 0)  # deterministic zip, friendlier to git
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(".zip.part")
    with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        info = zipfile.ZipInfo("index.json", date_time=fixed_time)
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, json.dumps(manifest, indent=1, ensure_ascii=False))
        for slug in sorted(pages):
            info = zipfile.ZipInfo(f"landing_pages/{slug}.html", date_time=fixed_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, pages[slug])
    partial.replace(output)


def main():
    parser = argparse.ArgumentParser(description="Snapshot every lparchive.org landing page for the tests")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=f"zip to write (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--cache", required=True, metavar="FILE",
                        help="SQLite cache for the downloads (re-runs only fetch what is missing)")
    parser.add_argument("--concurrency", type=int, default=4, help="parallel requests (default: 4, be polite)")
    parser.add_argument("--limit", type=int, help="only the first N LPs of the index (for trying the script)")
    args = parser.parse_args()
    cache_file = check_cache_path(args.cache)
    asyncio.run(snapshot(args.output, cache_file, args.concurrency, args.limit))


if __name__ == "__main__":
    main()
