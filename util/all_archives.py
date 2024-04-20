import json
import logging
import os
import re
from argparse import ArgumentParser

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from lparchive2epub.lib import lparchive2epub

if __name__ == '__main__':

    arg_parser = ArgumentParser(
        prog="all_lp_archive_to_epub",
        description="rock and roll"
    )

    arg_parser.add_argument("output", metavar="OUTPUT_FILE", nargs=1, type=str)

    args = arg_parser.parse_args()

    p = requests.get("https://lparchive.org/")

    soup = BeautifulSoup(p.text, "html.parser")

    scripts = soup.find_all("script")

    toc = scripts[13]

    m = re.search(r'\[.*}];', toc.text)

    data = m.group(0).replace("tocdata=", "")[:-1].replace("'", "\"")

    as_json = json.loads(data)
    urls = [x['u'] for x in as_json]

    logging.basicConfig(filename=f"{args.output[0]}{os.path.sep}/errors.log", level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(name)s %(message)s')
    logger = logging.getLogger("all_lp_archive_to_epub")

    pbar = tqdm(total=len(urls))

    for url in urls:
        try:
            lparchive2epub(tqdm, "https://lparchive.org/" + url,
                           f"{args.output[0]}{os.path.sep}{url.replace('/', '')}.epub")
        except Exception as e:
            pbar.write(f"failed to download {url}")
            logger.error(e)
        pbar.update()
