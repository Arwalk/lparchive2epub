import asyncio
import sys
import traceback
from argparse import ArgumentParser, ArgumentTypeError
from aiohttp_client_cache import CachedSession, SQLiteBackend

import aiohttp

from lparchive2epub.lib import lparchive2epub, ExtractionError, ISSUES_URL, EXIT_FAILURE, EXIT_INTERRUPTED, normalize_lp_url, \
    ImageProcessing, FetchSettings, check_cache_path, CLIENT_TIMEOUT, DEFAULT_CONCURRENCY, DEFAULT_RETRIES


def is_lparchive_url(arg):
    """argparse type: any lparchive.org address, normalised to the Let's Play's own URL."""
    try:
        return normalize_lp_url(arg)
    except ValueError as e:
        raise ArgumentTypeError(str(e)) from e


arg_parser = ArgumentParser(
    prog="lparchive2epub",
    description="A tool to transform a Let's Play from lparchive.org to epub format."
)

arg_parser.add_argument("url", metavar="URL", type=is_lparchive_url,
                        help="Address of the Let's Play on lparchive.org (any page of it will do)")
arg_parser.add_argument("output", metavar="OUTPUT", nargs="?", default=None,
                        help="Where to write the book: a file name, or a directory to put '<title>.epub' in "
                             "(default: '<title>.epub' in the current directory)")
arg_parser.add_argument("--cache", metavar="FILE",
                        help="Keep every downloaded page and image in a SQLite database at FILE (created if "
                             "needed, '.sqlite' added when FILE has no extension), so that running again, after a "
                             "failure or for a newer version of the tool, only downloads what is missing. "
                             "Off by default: within one run nothing is fetched twice anyway")
arg_parser.add_argument("--strict", action="store_true",
                        help="Fail instead of skipping resources (images...) that can't be retrieved")
arg_parser.add_argument("--allow-missing-updates", action="store_true",
                        help="Build the book even if some updates can't be retrieved, replacing them with a "
                             "placeholder page (by default this is an error and no book is written)")


def positive_int(arg):
    try:
        value = int(arg)
    except ValueError:
        raise ArgumentTypeError(f"{arg} is not a whole number") from None
    if value < 1:
        raise ArgumentTypeError(f"{arg} must be at least 1")
    return value


def jpeg_quality(arg):
    value = positive_int(arg)
    if value > 100:
        raise ArgumentTypeError(f"{arg} must be between 1 and 100")
    return value


arg_parser.add_argument("--max-image-size", metavar="PIXELS", type=positive_int,
                        help="Shrink images wider or taller than PIXELS to fit, and re-encode them (JPEG at "
                             "--jpeg-quality, PNG optimised, WebP/BMP converted). Off by default: images are kept "
                             "as served. 1600 suits e-readers, 2500 high-resolution tablets")
arg_parser.add_argument("--jpeg-quality", metavar="1-100", type=jpeg_quality, default=85,
                        help="JPEG quality used when --max-image-size re-encodes an image (default: 85)")
arg_parser.add_argument("--concurrency", metavar="N", type=positive_int, default=DEFAULT_CONCURRENCY,
                        help=f"Downloads in flight at the same time (default: {DEFAULT_CONCURRENCY})")
arg_parser.add_argument("--retries", metavar="N", type=positive_int, default=DEFAULT_RETRIES,
                        help=f"Attempts per download before giving up, with increasing waits in between "
                             f"(default: {DEFAULT_RETRIES}; 1 means no retry)")
arg_parser.add_argument("--quiet", action="store_true",
                        help="No progress bars or progress messages; only the final report and errors")
cover_group = arg_parser.add_mutually_exclusive_group()
cover_group.add_argument("--cover", metavar="IMAGE",
                         help="Use this image file as the cover instead of the generated one (title and author on "
                              "a plain background)")
cover_group.add_argument("--no-cover", action="store_true", help="Build the book without a cover image")

async def amain(args):
    fetch = FetchSettings(concurrency=args.concurrency, retries=args.retries, quiet=args.quiet)
    if args.cache:
        cache_file = check_cache_path(args.cache)
        if not args.quiet:
            print(f"using cache {cache_file}", file=sys.stderr)
        session = CachedSession(cache=SQLiteBackend(cache_file, expire_after=-1, fast_save=True, autoclose=True),
                                timeout=CLIENT_TIMEOUT)
    else:
        session = aiohttp.ClientSession(timeout=CLIENT_TIMEOUT)
    processing = ImageProcessing(args.max_image_size, args.jpeg_quality) if args.max_image_size else None
    cover: bytes | bool = True
    if args.no_cover:
        cover = False
    elif args.cover:
        try:
            with open(args.cover, "rb") as f:
                cover = f.read()
        except OSError as e:
            raise ExtractionError(f"Cannot read the cover image {args.cover}: {e.strerror or e}") from e
    written = await lparchive2epub(args.url, args.output, session, strict=args.strict,
                                   allow_missing_updates=args.allow_missing_updates, image_processing=processing,
                                   cover=cover, fetch=fetch)
    if args.quiet:
        print(written)   # the one thing a script wants from a quiet run

def main(argv=None):
    args = arg_parser.parse_args(argv)
    try:
        asyncio.run(amain(args))
    except ExtractionError as e:
        print(e, file=sys.stderr)
        sys.exit(e.exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted. No book was written.", file=sys.stderr)
        sys.exit(EXIT_INTERRUPTED)
    except Exception as e:  # noqa: BLE001 - last resort: never leave the user with a bare traceback
        print(f"lparchive2epub failed with an unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        print(f"This is a bug. Please open an issue at {ISSUES_URL} with the URL you used and the details below.",
              file=sys.stderr)
        traceback.print_exc()
        sys.exit(EXIT_FAILURE)


if __name__ == '__main__':
    main()
