import asyncio
import sys
import traceback
from argparse import ArgumentParser, ArgumentTypeError
from aiohttp_client_cache import CachedSession, SQLiteBackend

from lparchive2epub.lib import lparchive2epub, ExtractionError, ISSUES_URL, EXIT_FAILURE, EXIT_INTERRUPTED, normalize_lp_url, \
    ImageProcessing, check_cache_path


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

arg_parser.add_argument("url", metavar="URL", nargs=1, type=is_lparchive_url,
                        help="Address of the Let's Play on lparchive.org (any page of it will do)")
arg_parser.add_argument("output", metavar="OUTPUT_FILE", nargs=1, type=str)
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

async def amain(args):
    cache = None
    if args.cache:
        cache_file = check_cache_path(args.cache)
        print(f"using cache {cache_file}", file=sys.stderr)
        cache = CachedSession(cache=SQLiteBackend(cache_file, expire_after=-1, fast_save=True, autoclose=True))
    processing = ImageProcessing(args.max_image_size, args.jpeg_quality) if args.max_image_size else None
    await lparchive2epub(args.url[0], args.output[0], cache, strict=args.strict,
                         allow_missing_updates=args.allow_missing_updates, image_processing=processing)

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
