import json
import logging
import os
import re
from argparse import ArgumentParser
from multiprocessing import Pool

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
    session = requests.Session()

    p = session.get("https://lparchive.org/")

    soup = BeautifulSoup(p.text, "html.parser")

    # now for some "magic"
    # there's a javascript embedded in the page that contains all the content to populate the table at the bottom
    # All archived let's plays are mentioned there.
    # So with a bit of regex we can extract the json that gives us all the let's plays
    scripts = soup.find_all("script")
    toc = scripts[13]
    m = re.search(r'\[.*}];', toc.text)
    data = m.group(0).replace("tocdata=", "")[:-1].replace("'", "\"")
    as_json = json.loads(data)
    urls = [x['u'] for x in as_json]
    # It's ugly, but it works. And I couldn't find a decent api to ask politely for this data somewhere else.

    logging.basicConfig(filename=f"{args.output[0]}{os.path.sep}/errors.log", level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(name)s %(message)s')
    logger = logging.getLogger("all_lp_archive_to_epub")

    pbar = tqdm(total=len(urls))

    failed = []

    with Pool() as pool:
        for url in urls:
            try:
                lparchive2epub(tqdm, session, pool, "https://lparchive.org/" + url,
                               f"{args.output[0]}{os.path.sep}{url.replace('/', '')}.epub")
            except Exception as e:
                pbar.write(f"failed to download {url}")
                logger.error(e)
                failed.append(url)
            pbar.update()

    print(f"downloaded {len(urls) - len(failed)} out of {len(urls)}")
    print(f"failed lps:")
    for url in failed:
        print(failed)