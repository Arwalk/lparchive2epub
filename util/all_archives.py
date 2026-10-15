import asyncio
import json
import logging
import os
import sys
from argparse import ArgumentParser
from pathlib import Path

import aiohttp
from aiohttp import ClientSession
from tqdm.asyncio import tqdm
from aiohttp_client_cache import CachedSession, SQLiteBackend

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lparchive2epub.lib import lparchive2epub, CURL_HEADERS  # noqa: E402
from util.snapshot_landing_pages import read_index  # noqa: E402


async def do_single(arguments, url, pbar, failed, cache_path):
    logger = logging.getLogger("all_lp_archive_to_epub")
    exc = None
    cache = SQLiteBackend(f"{cache_path}{os.path.sep}{url.replace('/', '')}", expire_after=-1, autoclose=False)
    conn = aiohttp.TCPConnector(force_close=True)
    connection = CachedSession(cache=cache, connector=conn)
    try:
        await lparchive2epub("https://lparchive.org" + url,
                                f"{arguments.output[0]}{os.path.sep}{url.replace('/', '')}.epub",
                                connection)
    except (aiohttp.client_exceptions.ServerDisconnectedError, TimeoutError, RuntimeError) as disconnected:
        exc = disconnected
        await asyncio.sleep(5)
    except Exception as e:
        exc = e
    else:
        pbar.update(1)
        return None
    finally:
        await connection.close()
        await cache.close()

    pbar.write(f"failed to download {url} : {str(exc)}")
    logger.error("error:", exc_info=exc)
    failed.append(f"url: {url}, exc: {exc}")
    pbar.update(1)
    return url, exc


async def get_frontpage() -> str:
    async with ClientSession() as session:
        async with session.get("https://lparchive.org/", headers=CURL_HEADERS) as r:
            return await r.text()


async def do(arguments):
    # The front page embeds the whole LP index as JavaScript; read_index knows how to parse it.
    urls = ["/" + entry["slug"] + "/" for entry in read_index(await get_frontpage())]

    logging.basicConfig(filename=f"{arguments.output[0]}{os.path.sep}/errors.log", level=logging.WARN,
                        format='%(asctime)s %(levelname)s %(name)s %(message)s')

    failed = []

    cache_path = arguments.cache_path
    if not cache_path:
        cache_path = f"{arguments.output[0]}{os.path.sep}/cache"


    with tqdm(total=len(urls)) as pbar:
        for url in urls:
            await do_single(arguments, url, pbar, failed, cache_path)

    for url in failed:
        print(json.dumps(url))
    print(f"downloaded {len(urls) - len(failed)} out of {len(urls)}")


if __name__ == '__main__':
    arg_parser = ArgumentParser(
        prog="all_lp_archive_to_epub",
        description="rock and roll"
    )

    arg_parser.add_argument("output", metavar="OUTPUT_FILE", nargs=1, type=str)
    arg_parser.add_argument("--cache_path", metavar="CACHE_PATH", type=str, help="Path to SQLite cache file")


    args = arg_parser.parse_args()
    asyncio.run(do(args))
