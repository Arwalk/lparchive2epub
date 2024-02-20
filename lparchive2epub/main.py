from argparse import ArgumentParser, ArgumentTypeError
from argparse import FileType
from urllib.parse import urlparse
from lparchive2epub.lib import lparchive2epub


def is_lparchive_url(arg):
    url = urlparse(arg)
    if not "lparchive.org" in url.geturl():
        raise ArgumentTypeError(f"{arg} is not an lparchive.org URL")
    if not url.path or url.path == "/":
        raise ArgumentTypeError(f"{arg} is not a let's play archive")
    return arg


arg_parser = ArgumentParser(
    prog="lparchive2epub",
    description="A tool to transfrom a Let's Play from lparchive.org to epub format."
)

arg_parser.add_argument("url", metavar="URL", nargs=1, type=is_lparchive_url)
arg_parser.add_argument("output", metavar="OUTPUT_FILE", nargs=1, type=str)


def main():
    args = arg_parser.parse_args()
    print(args)
    lparchive2epub(args.url[0], args.output[0])


if __name__ == '__main__':
    main()
