"""Build a book for every Let's Play of the archive.

    uv run python util/all_archives.py OUTPUT_DIR [--cache_path DIR] [--errors FILE]

Books are written as OUTPUT_DIR/<slug>.epub. Each LP gets its own SQLite cache under the cache
directory (default OUTPUT_DIR/cache), so a failed LP can be retried without downloading again.

--errors FILE keeps everything that went wrong, one JSON object per line, for later analysis:
  {"slug", "url", "time", "kind": "build-failed", "error": "<type>", "message": "...", "report": "..."}
  {"slug", "url", "time", "kind": "skipped-resources", "report": "..."}
"build-failed" is an LP whose book was not written (missing updates, network, not an LP page...),
with the full report the tool prints; "skipped-resources" is a book that was written but with images
the site could not serve, with the tool's report listing them.
"""
import asyncio
import datetime
import json
import logging
import os
import sys
from argparse import ArgumentParser
from pathlib import Path

from aiohttp import ClientSession
from tqdm.asyncio import tqdm
from aiohttp_client_cache import CachedSession, SQLiteBackend

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lparchive2epub.lib import lparchive2epub, CURL_HEADERS, CLIENT_TIMEOUT, FetchSettings, ExtractionError, check_cache_path  # noqa: E402
from util.snapshot_landing_pages import read_index  # noqa: E402

LPARCHIVE = "https://lparchive.org"


class ErrorLog:
    """Appends one JSON line per problem to `path`; does nothing when no path was given."""

    def __init__(self, path: str | None):
        self.path = path
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            open(path, "a", encoding="utf-8").close()

    def record(self, slug: str, kind: str, report: str, error: Exception | None = None):
        if not self.path:
            return
        entry = {"slug": slug, "url": f"{LPARCHIVE}/{slug}", "time": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                 "kind": kind}
        if error is not None:
            entry["error"] = type(error).__name__
            entry["message"] = str(error).splitlines()[0] if str(error) else ""
        entry["report"] = report
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def make_session(cache_dir: str, slug: str) -> ClientSession:
    # check_cache_path creates the database and works around filesystems where the first write to a
    # fresh file fails (virtiofs); the CLI goes through the same check
    cache_file = check_cache_path(os.path.join(cache_dir, f"{slug}.sqlite"))
    cache = SQLiteBackend(cache_file, expire_after=-1, fast_save=True, autoclose=True)
    return CachedSession(cache=cache, timeout=CLIENT_TIMEOUT)


async def build_one(slug: str, output_dir: str, cache_dir: str, errors: ErrorLog, session_factory=make_session) -> bool:
    """Build one LP. Returns True when the book was written. Everything the tool reports (skipped
    images, failures) goes to the error log."""
    logger = logging.getLogger("all_lp_archive_to_epub")
    reports: list[str] = []
    try:
        await lparchive2epub(f"{LPARCHIVE}/{slug}", os.path.join(output_dir, f"{slug}.epub"),
                             session_factory(cache_dir, slug), writer=reports.append, fetch=FetchSettings(quiet=True))
    except ExtractionError as e:
        errors.record(slug, "build-failed", str(e), e)
        logger.error("%s: %s", slug, str(e).splitlines()[0])
        return False
    except Exception as e:  # noqa: BLE001 - keep going through the archive, but keep the trace
        errors.record(slug, "build-failed", "".join(reports), e)
        logger.error("%s: unexpected error", slug, exc_info=e)
        return False
    # the quiet build only says something when resources were skipped (and for the image summary)
    skipped = [r for r in reports if "could not be retrieved" in r]
    if skipped:
        errors.record(slug, "skipped-resources", "\n".join(skipped))
    return True


async def get_frontpage() -> str:
    async with ClientSession(timeout=CLIENT_TIMEOUT) as session:
        async with session.get(f"{LPARCHIVE}/", headers=CURL_HEADERS) as r:
            return await r.text()


async def do(arguments):
    output_dir = arguments.output
    cache_dir = arguments.cache_path or os.path.join(output_dir, "cache")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)
    logging.basicConfig(filename=os.path.join(output_dir, "errors.log"), level=logging.WARN,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    errors = ErrorLog(arguments.errors)

    # The front page embeds the whole LP index as JavaScript; read_index knows how to parse it.
    slugs = [entry["slug"] for entry in read_index(await get_frontpage())]

    failed = []
    with tqdm(total=len(slugs)) as pbar:
        for slug in slugs:
            if not await build_one(slug, output_dir, cache_dir, errors):
                failed.append(slug)
                pbar.write(f"failed: {slug}")
                await asyncio.sleep(5)
            pbar.update(1)

    print(f"downloaded {len(slugs) - len(failed)} out of {len(slugs)}")
    if failed:
        print("failed:", ", ".join(failed))
    if arguments.errors:
        print(f"details in {arguments.errors}")


if __name__ == "__main__":
    arg_parser = ArgumentParser(prog="all_lp_archive_to_epub", description="Build a book for every Let's Play of the archive")
    arg_parser.add_argument("output", metavar="OUTPUT_DIR", help="directory for the books (<slug>.epub)")
    arg_parser.add_argument("--cache_path", metavar="DIR", help="directory for the per-LP SQLite caches (default: OUTPUT_DIR/cache)")
    arg_parser.add_argument("--errors", metavar="FILE",
                            help="append every failure and every skipped-resource report to FILE, one JSON object per line")
    asyncio.run(do(arg_parser.parse_args()))
