import asyncio
import json
import logging
import multiprocessing
import os
import re
from argparse import ArgumentParser

import aiohttp
from bs4 import BeautifulSoup

from lparchive2epub.lib import lparchive2epub
from aiohttp import ClientSession
from tqdm.asyncio import tqdm

processes = multiprocessing.cpu_count()


async def do_single(arguments, url, pbar, failed):
    logger = logging.getLogger("all_lp_archive_to_epub")
    exc = None
    for i in range(5):
        try:
            await lparchive2epub("https://lparchive.org/" + url,
                                 f"{arguments.output[0]}{os.path.sep}{url.replace('/', '')}.epub")
        except (aiohttp.client_exceptions.ServerDisconnectedError, TimeoutError, RuntimeError) as disconnected:
            exc = disconnected
            await asyncio.sleep(5)
        except Exception as e:
            exc = e
        else:
            pbar.update(1)
            return None

    pbar.write(f"failed to download {url} : {str(exc)}")
    logger.error("error:", exc_info=exc)
    failed.append(f"url: {url}, exc: {exc}")
    pbar.update(1)
    return url, exc


async def get_frontpage():
    async with ClientSession() as session:
        p = await session.get("https://lparchive.org/")

        soup = BeautifulSoup(await p.text(), "html.parser")
    return soup


async def do(arguments):
    soup = await get_frontpage()

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

    logging.basicConfig(filename=f"{arguments.output[0]}{os.path.sep}/errors.log", level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(name)s %(message)s')

    failed = []

    with tqdm(total=len(urls)) as pbar:
        for url in urls:
            await do_single(arguments, url, pbar, failed)

    for url in failed:
        print(json.dumps(url))
    print(f"downloaded {len(urls) - len(failed)} out of {len(urls)}")


if __name__ == '__main__':
    arg_parser = ArgumentParser(
        prog="all_lp_archive_to_epub",
        description="rock and roll"
    )

    arg_parser.add_argument("output", metavar="OUTPUT_FILE", nargs=1, type=str)

    args = arg_parser.parse_args()
    asyncio.run(do(args))
