import asyncio
import sys
import traceback
from argparse import ArgumentParser, ArgumentTypeError
from aiohttp_client_cache import CacheBackend, CachedSession

from lparchive2epub.lib import lparchive2epub, ExtractionError, ISSUES_URL, EXIT_FAILURE, EXIT_INTERRUPTED, normalize_lp_url


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
arg_parser.add_argument("--no-cache", action="store_true", help="Don't cache url calls")
arg_parser.add_argument("--strict", action="store_true",
                        help="Fail instead of skipping resources (images...) that can't be retrieved")
arg_parser.add_argument("--allow-missing-updates", action="store_true",
                        help="Build the book even if some updates can't be retrieved, replacing them with a "
                             "placeholder page (by default this is an error and no book is written)")

async def amain(args):
    if args.no_cache:
        cache = None
    else:
        cache = CachedSession(cache=CacheBackend())
    await lparchive2epub(args.url[0], args.output[0], cache, strict=args.strict,
                         allow_missing_updates=args.allow_missing_updates)

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
