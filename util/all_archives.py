"""Build a book for every Let's Play of the archive.

    uv run python util/all_archives.py OUTPUT_DIR [--cache_path DIR] [--errors FILE] [--skip-videos] [--force]
                                       [--max-image-size PIXELS] [--jpeg-quality 1-100] [--no-cover] [--images-in-memory]
                                       [--concurrency N] [--retries N] [--check] [--check-workers N]

Books are written as OUTPUT_DIR/<slug>.epub. Each LP gets its own SQLite cache under the cache
directory (default OUTPUT_DIR/cache), so a failed LP can be retried without downloading again.

The run resumes by default: an LP whose book already exists in OUTPUT_DIR is skipped, so an
interrupted run can simply be started again. --force rebuilds every book.

--skip-videos leaves out the LPs the archive indexes as videos (most of the archive: their pages
hold little more than links to the videos, so the books are near-empty).

--errors FILE keeps everything that went wrong, one JSON object per line, for later analysis:
  {"slug", "url", "time", "kind": "build-failed", "error": "<type>", "message": "...", "report": "..."}
  {"slug", "url", "time", "kind": "skipped-resources", "report": "..."}
  {"slug", "url", "time", "kind": "epubcheck", "report": "...", "messages": [{"severity", "id", "message", "path", "line"}]}
  {"slug", "url", "time", "kind": "check-failed", "error": "<type>", "message": "...", "report": "..."}
"build-failed" is an LP whose book was not written (missing updates, network, not an LP page...),
with the full report the tool prints; "skipped-resources" is a book that was written but with images
the site could not serve, with the tool's report listing them; "epubcheck" (with --check) is a book
epubcheck found fault with, with the tool's report and its findings as epubcheck gave them;
"check-failed" is a book epubcheck could not check (the Java runtime failed, or the check timed out),
which was written all the same.

--max-image-size, --jpeg-quality, --no-cover, --images-in-memory, --concurrency, --retries and --check
mean the same as for the lparchive2epub command and apply to every book. Here the check does not hold
the builds back: a written book is queued, one epubcheck run goes on alongside the builds, and once the
last book is built --check-workers (default 4) run at once to finish the queue. --check also prints, at
the end, how many books epubcheck faulted and its most frequent message IDs.

Progress goes to stderr: one bar for the run, naming the LP in hand, under it the bar of the checks
(with --check), and under those the bar of the step the LP in hand is at (its pages, its images, the
book), so a long LP can be seen advancing.
"""
import asyncio
import datetime
import json
import logging
import os
import sys
from argparse import ArgumentParser
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path

from aiohttp import ClientSession
from tqdm.asyncio import tqdm
from aiohttp_client_cache import CachedSession, SQLiteBackend

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lparchive2epub.lib import lparchive2epub, request_headers, CLIENT_TIMEOUT, DEFAULT_CONCURRENCY, DEFAULT_RETRIES, \
    FetchSettings, ImageProcessing, ExtractionError, CheckError, check_cache_path  # noqa: E402
from lparchive2epub.check import run_epubcheck, format_check_report, unavailable_reason  # noqa: E402
from lparchive2epub.main import positive_int, jpeg_quality  # noqa: E402
from util.snapshot_landing_pages import read_index  # noqa: E402

LPARCHIVE = "https://lparchive.org"
# "ty" in the front page index: 1 screenshot LP, 2 video LP, 3 hybrid, 0 unspecified
VIDEO_TYPE = "2"
DEFAULT_CHECK_WORKERS = 4


class ErrorLog:
    """Appends one JSON line per problem to `path`; does nothing when no path was given."""

    def __init__(self, path: str | None):
        self.path = path
        self.faulted_books = 0                    # --check: books epubcheck found fault with...
        self.finding_ids: Counter[str] = Counter()  # ...and its message IDs, for the end-of-run summary
        self.unchecked_books = 0                  # ...and books it could not check
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            open(path, "a", encoding="utf-8").close()

    def record(self, slug: str, kind: str, report: str, error: Exception | None = None, messages: list[dict] | None = None):
        if messages is not None:
            self.faulted_books += 1
            self.finding_ids.update(m["id"] for m in messages)
        if kind == "check-failed":
            self.unchecked_books += 1
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
            summary = "epubcheck found no fault with any book"
        else:
            frequent = ", ".join(f"{id_} {n}" for id_, n in self.finding_ids.most_common(5))
            summary = f"epubcheck found fault with {self.faulted_books} book(s); most frequent: {frequent}"
        if self.unchecked_books:
            summary += f"; {self.unchecked_books} book(s) could not be checked"
        return summary


class BookChecker:
    """--check, without holding the builds back: written books queue up here and worker tasks run epubcheck
    on them, each in its own thread (a JVM run). `start` adds workers at any time: one alongside the builds,
    more once the last book is built. Same shape as the library's page and image worker pools."""

    def __init__(self, errors: ErrorLog, bar: tqdm):
        self.errors = errors
        self.bar = bar                 # "Checking books": its total grows as books are submitted
        self.queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        self.workers: list[asyncio.Task] = []
        self.busy = 0                  # workers with a check in flight

    def submit(self, slug: str, path: str):
        self.queue.put_nowait((slug, path))
        self.bar.total = (self.bar.total or 0) + 1
        self.bar.refresh()

    def start(self, workers: int):
        self.workers.extend(asyncio.create_task(self._worker()) for _ in range(workers))

    async def drain(self):
        """Wait for every submitted book to be checked, then stop the workers. Safe to call when nothing was
        submitted or started (no --check)."""
        if self.workers:
            await self.queue.join()
        await self.stop()

    async def stop(self) -> int:
        """Stop the workers without waiting for the queue (after an interruption), and say how many books
        were left unchecked: the ones still queued and the ones whose check was cut short. A JVM already
        running finishes in its thread before the process can exit, nothing records what it finds."""
        left = self.queue.qsize() + self.busy
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        return left

    async def _worker(self):
        logger = logging.getLogger("all_lp_archive_to_epub")
        while True:
            slug, path = await self.queue.get()
            self.busy += 1
            try:
                self.bar.set_postfix_str(slug)
                result = await asyncio.to_thread(run_epubcheck, path)   # a JVM run: off the event loop
                if result.findings:
                    report = format_check_report(path, result, "The book was written all the same.")
                    self.errors.record(slug, "epubcheck", report, messages=[asdict(f) for f in result.findings])
            except CheckError as e:
                self.errors.record(slug, "check-failed", str(e), e)
                logger.error("%s: %s", slug, str(e).splitlines()[0])
            except Exception as e:  # noqa: BLE001 - keep checking the other books, but keep the trace
                self.errors.record(slug, "check-failed", str(e), e)
                logger.error("%s: unexpected error while checking", slug, exc_info=e)
            finally:
                self.busy -= 1
                self.bar.update(1)
                self.queue.task_done()


@dataclass
class BuildOptions:
    """What is passed on to every build: the lparchive2epub command's own options."""
    image_processing: ImageProcessing | None = None
    cover: bool = True
    # quiet: the progress messages stay out of the reports; bars: the step in hand still shows under the run's bar
    fetch: FetchSettings = field(default_factory=lambda: FetchSettings(quiet=True, bars=True))
    spool_images: bool = True


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
                             fetch=options.fetch, spool_images=options.spool_images)
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
        spool_images=not arguments.images_in_memory)

    # The front page embeds the whole LP index as JavaScript; read_index knows how to parse it.
    index = read_index(await get_frontpage())
    slugs, videos, done = select(index, output_dir, arguments.skip_videos, arguments.force)
    print(f"{len(index)} Let's Plays in the index, {len(slugs)} to build"
          + (f", {videos} video LPs skipped" if videos else "") + (f", {done} already built" if done else ""))

    failed = []
    # The run's bar first, the checks' bar under it: the build's step bars then nest under both and clear
    # when their step is done, and the checks' bar keeps going once the run's bar is complete.
    with tqdm(total=len(slugs), desc="Building books") as build_bar, \
         tqdm(total=0, desc="Checking books", disable=not arguments.check) as check_bar:
        checker = BookChecker(errors, check_bar)
        try:
            if arguments.check:
                checker.start(1)   # one epubcheck run alongside the builds
            for slug in slugs:
                build_bar.set_postfix_str(slug)
                if await build_one(slug, output_dir, cache_dir, errors, options=options):
                    if arguments.check:
                        checker.submit(slug, book_path(output_dir, slug))
                else:
                    failed.append(slug)
                    build_bar.write(f"failed: {slug}")
                    await asyncio.sleep(5)
                build_bar.update(1)
            build_bar.close()
            if arguments.check:
                checker.start(arguments.check_workers - 1)   # the rest of the workers, to finish the queue
            await checker.drain()
        finally:
            left = await checker.stop()   # nothing after a full drain; the rest of the queue after a Ctrl-C
            if left:
                check_bar.write(f"interrupted: {left} book(s) left unchecked")

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
    arg_parser.add_argument("--check-workers", metavar="N", type=positive_int, default=DEFAULT_CHECK_WORKERS,
                            help=f"epubcheck runs at once after the last book is built (default: {DEFAULT_CHECK_WORKERS}); "
                                 "one runs alongside the builds. Each is a Java runtime: mind the memory")
    arguments = arg_parser.parse_args()
    if arguments.check and unavailable_reason():
        arg_parser.error(unavailable_reason())
    asyncio.run(do(arguments))
