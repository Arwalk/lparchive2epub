"""Build a book for every Let's Play of the archive.

    uv run python util/all_archives.py OUTPUT_DIR [--cache_path DIR] [--errors FILE] [--skip-videos] [--force]
                                       [--max-image-size PIXELS] [--jpeg-quality 1-100] [--no-cover] [--images-in-memory]
                                       [--concurrency N] [--retries N] [--check]

Books are written as OUTPUT_DIR/<slug>.epub. Each LP gets its own SQLite cache under the cache
directory (default OUTPUT_DIR/cache), so a failed LP can be retried without downloading again.

The run resumes by default: an LP whose book already exists in OUTPUT_DIR is skipped, so an
interrupted run can simply be started again. --force rebuilds every book.

--skip-videos leaves out the LPs the archive indexes as videos (most of the archive: their pages
hold little more than links to the videos, so the books are near-empty).

--errors FILE keeps everything that went wrong, one JSON object per line, for later analysis:
  {"slug", "url", "time", "kind": "build-failed", "error": "<type>", "message": "...", "report": "..."}
  {"slug", "url", "time", "kind": "skipped-resources", "report": "..."}
  {"slug", "url", "time", "kind": "epubcheck", "report": "...", "messages": [{"severity", "id", "path", "line", "message"}]}
"build-failed" is an LP whose book was not written (missing updates, network, not an LP page...),
with the full report the tool prints; "skipped-resources" is a book that was written but with images
the site could not serve, with the tool's report listing them; "epubcheck" (with --check) is a book
epubcheck found fault with, with the tool's report and its findings parsed out.

--max-image-size, --jpeg-quality, --no-cover, --images-in-memory, --concurrency, --retries and --check
mean the same as for the lparchive2epub command and apply to every book. --check also prints, at the
end, how many books epubcheck faulted and its most frequent message IDs.

Progress goes to stderr: one bar for the run, naming the LP in hand, and under it the bar of the step
that LP is at (its pages, its images, the book), so a long LP can be seen advancing.
"""
import asyncio
import datetime
import json
import logging
import os
import sys
from argparse import ArgumentParser
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from aiohttp import ClientSession
from tqdm.asyncio import tqdm
from aiohttp_client_cache import CachedSession, SQLiteBackend

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lparchive2epub.lib import lparchive2epub, request_headers, CLIENT_TIMEOUT, DEFAULT_CONCURRENCY, DEFAULT_RETRIES, \
    FetchSettings, ImageProcessing, ExtractionError, check_cache_path  # noqa: E402
from lparchive2epub.check import CHECK_HEADER, parse_check_report, unavailable_reason  # noqa: E402
from lparchive2epub.main import positive_int, jpeg_quality  # noqa: E402
from util.snapshot_landing_pages import read_index  # noqa: E402

LPARCHIVE = "https://lparchive.org"
# "ty" in the front page index: 1 screenshot LP, 2 video LP, 3 hybrid, 0 unspecified
VIDEO_TYPE = "2"


class ErrorLog:
    """Appends one JSON line per problem to `path`; does nothing when no path was given."""

    def __init__(self, path: str | None):
        self.path = path
        self.faulted_books = 0                    # --check: books epubcheck found fault with...
        self.finding_ids: Counter[str] = Counter()  # ...and its message IDs, for the end-of-run summary
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            open(path, "a", encoding="utf-8").close()

    def record(self, slug: str, kind: str, report: str, error: Exception | None = None, messages: list[dict] | None = None):
        if messages is not None:
            self.faulted_books += 1
            self.finding_ids.update(m["id"] for m in messages)
        if not self.path:
            return
        entry = {"slug": slug, "url": f"{LPARCHIVE}/{slug}", "time": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                 "kind": kind}
        if error is not None:
            entry["error"] = type(error).__name__
            entry["message"] = str(error).splitlines()[0] if str(error) else ""
        entry["report"] = report
        if messages is not None:
            entry["messages"] = messages
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def check_summary(self) -> str:
        if not self.faulted_books:
            return "epubcheck found no fault with any book"
        frequent = ", ".join(f"{id_} {n}" for id_, n in self.finding_ids.most_common(5))
        return f"epubcheck found fault with {self.faulted_books} book(s); most frequent: {frequent}"


@dataclass
class BuildOptions:
    """What is passed on to every build: the lparchive2epub command's own options."""
    image_processing: ImageProcessing | None = None
    cover: bool = True
    # quiet: the progress messages stay out of the reports; bars: the step in hand still shows under the run's bar
    fetch: FetchSettings = field(default_factory=lambda: FetchSettings(quiet=True, bars=True))
    spool_images: bool = True
    check: bool = False


def make_session(cache_dir: str, slug: str) -> ClientSession:
    # check_cache_path creates the database and works around filesystems where the first write to a
    # fresh file fails (virtiofs); the CLI goes through the same check
    cache_file = check_cache_path(os.path.join(cache_dir, f"{slug}.sqlite"))
    cache = SQLiteBackend(cache_file, expire_after=-1, fast_save=True, autoclose=True)
    return CachedSession(cache=cache, timeout=CLIENT_TIMEOUT)


def book_path(output_dir: str, slug: str) -> str:
    return os.path.join(output_dir, f"{slug}.epub")


async def build_one(slug: str, output_dir: str, cache_dir: str, errors: ErrorLog, session_factory=make_session,
                    options: BuildOptions | None = None) -> bool:
    """Build one LP. Returns True when the book was written. Everything the tool reports (skipped
    images, failures) goes to the error log."""
    logger = logging.getLogger("all_lp_archive_to_epub")
    options = options or BuildOptions()
    reports: list[str] = []
    try:
        await lparchive2epub(f"{LPARCHIVE}/{slug}", book_path(output_dir, slug), session_factory(cache_dir, slug),
                             writer=reports.append, image_processing=options.image_processing, cover=options.cover,
                             fetch=options.fetch, spool_images=options.spool_images, check=options.check)
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
    for report in (r for r in reports if CHECK_HEADER in r):
        errors.record(slug, "epubcheck", report, messages=parse_check_report(report))
    return True


def select(index: list[dict], output_dir: str, skip_videos: bool, force: bool) -> tuple[list[str], int, int]:
    """The slugs to build, in index order, and how many were left out: (slugs, videos, already built)."""
    slugs, videos, done = [], 0, 0
    for entry in index:
        if skip_videos and str(entry.get("type")) == VIDEO_TYPE:
            videos += 1
        elif not force and os.path.exists(book_path(output_dir, entry["slug"])):
            done += 1
        else:
            slugs.append(entry["slug"])
    return slugs, videos, done


async def get_frontpage() -> str:
    async with ClientSession(timeout=CLIENT_TIMEOUT) as session:
        async with session.get(f"{LPARCHIVE}/", headers=request_headers()) as r:
            return await r.text()


async def do(arguments):
    output_dir = arguments.output
    cache_dir = arguments.cache_path or os.path.join(output_dir, "cache")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)
    logging.basicConfig(filename=os.path.join(output_dir, "errors.log"), level=logging.WARN,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    errors = ErrorLog(arguments.errors)
    options = BuildOptions(
        image_processing=ImageProcessing(arguments.max_image_size, arguments.jpeg_quality) if arguments.max_image_size else None,
        cover=not arguments.no_cover,
        fetch=FetchSettings(concurrency=arguments.concurrency, retries=arguments.retries, quiet=True, bars=True),
        spool_images=not arguments.images_in_memory,
        check=arguments.check)

    # The front page embeds the whole LP index as JavaScript; read_index knows how to parse it.
    index = read_index(await get_frontpage())
    slugs, videos, done = select(index, output_dir, arguments.skip_videos, arguments.force)
    print(f"{len(index)} Let's Plays in the index, {len(slugs)} to build"
          + (f", {videos} video LPs skipped" if videos else "") + (f", {done} already built" if done else ""))

    failed = []
    with tqdm(total=len(slugs), desc="Building books") as pbar:
        for slug in slugs:
            pbar.set_postfix_str(slug)
            if not await build_one(slug, output_dir, cache_dir, errors, options=options):
                failed.append(slug)
                pbar.write(f"failed: {slug}")
                await asyncio.sleep(5)
            pbar.update(1)

    print(f"downloaded {len(slugs) - len(failed)} out of {len(slugs)}")
    if failed:
        print("failed:", ", ".join(failed))
    if arguments.check:
        print(errors.check_summary())
    if arguments.errors:
        print(f"details in {arguments.errors}")


if __name__ == "__main__":
    arg_parser = ArgumentParser(prog="all_lp_archive_to_epub", description="Build a book for every Let's Play of the archive")
    arg_parser.add_argument("output", metavar="OUTPUT_DIR", help="directory for the books (<slug>.epub)")
    arg_parser.add_argument("--cache_path", metavar="DIR", help="directory for the per-LP SQLite caches (default: OUTPUT_DIR/cache)")
    arg_parser.add_argument("--errors", metavar="FILE",
                            help="append every failure and every skipped-resource report to FILE, one JSON object per line")
    arg_parser.add_argument("--skip-videos", action="store_true", help="leave out the LPs the archive indexes as videos")
    arg_parser.add_argument("--force", action="store_true",
                            help="rebuild books that already exist in OUTPUT_DIR (by default they are skipped, so a run resumes)")
    arg_parser.add_argument("--max-image-size", metavar="PIXELS", type=positive_int,
                            help="shrink images wider or taller than PIXELS and re-encode them, as the lparchive2epub command does")
    arg_parser.add_argument("--jpeg-quality", metavar="1-100", type=jpeg_quality, default=85,
                            help="JPEG quality used when --max-image-size re-encodes an image (default: 85)")
    arg_parser.add_argument("--no-cover", action="store_true", help="build the books without a cover image")
    arg_parser.add_argument("--images-in-memory", action="store_true",
                            help="keep each book's images in memory instead of a temporary folder under TMPDIR")
    arg_parser.add_argument("--concurrency", metavar="N", type=positive_int, default=DEFAULT_CONCURRENCY,
                            help=f"downloads in flight at the same time (default: {DEFAULT_CONCURRENCY})")
    arg_parser.add_argument("--retries", metavar="N", type=positive_int, default=DEFAULT_RETRIES,
                            help=f"attempts per download before giving up (default: {DEFAULT_RETRIES})")
    arg_parser.add_argument("--check", action="store_true",
                            help="validate every written book with epubcheck and record its findings (kind 'epubcheck' "
                                 "in --errors FILE); needs the epubcheck package and a Java runtime")
    arguments = arg_parser.parse_args()
    if arguments.check and unavailable_reason():
        arg_parser.error(unavailable_reason())
    asyncio.run(do(arguments))
