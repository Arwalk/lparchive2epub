# lparchive2pub

this tool (and library) aims at helping people extracting full epubs of Let's Plays from https://lparchive.org/

```
usage: lparchive2epub [-h] [--cache FILE] [--strict] [--allow-missing-updates]
                      [--max-image-size PIXELS] [--jpeg-quality 1-100]
                      URL OUTPUT_FILE

A tool to transform a Let's Play from lparchive.org to epub format.

positional arguments:
  URL          Address of the Let's Play on lparchive.org (any page of it
               will do)
  OUTPUT_FILE

options:
  -h, --help   show this help message and exit
  --cache FILE Keep every downloaded page and image in a SQLite database at
               FILE (created if needed, '.sqlite' added when FILE has no
               extension), so that running again, after a failure or for a
               newer version of the tool, only downloads what is missing. Off
               by default: within one run nothing is fetched twice anyway
  --strict     Fail instead of skipping resources (images...) that can't be
               retrieved
  --allow-missing-updates
               Build the book even if some updates can't be retrieved,
               replacing them with a placeholder page (by default this is an
               error and no book is written)
  --max-image-size PIXELS
               Shrink images wider or taller than PIXELS to fit, and re-encode
               them (JPEG at --jpeg-quality, PNG optimised, WebP/BMP
               converted). Off by default: images are kept as served. 1600
               suits e-readers, 2500 high-resolution tablets
  --jpeg-quality 1-100
               JPEG quality used when --max-image-size re-encodes an image
               (default: 85)
```

The repository also contains the script `util/all_archives.py` that tries to scrape all LPs from lparchive,
and `util/snapshot_landing_pages.py`, which refreshes `tests/resources/landing_pages.zip`: a snapshot of
every Let's Play landing page on the archive, used by the test suite to check the extractor against the
whole archive rather than a handful of pages. `tests/resources/chapters.json` records what the extractor
must find on each of those pages (facts and ordered chapters); `util/generate_chapter_golden.py`
regenerates it after an intended change, and the diff shows exactly which Let's Plays moved.
Run `pytest -m "not archive"` to skip that archive-wide check while iterating.

## Requirements

### Dev

uv, python 3.12

### Users

python >= 3.12

## Installation

`pip install lparchive2epub`

To have it installed in its own separate environment, you can use https://github.com/pypa/pipx

`pipx install lparchive2epub`

A standalone executable is available for releases on windows. See the releases page.

## Building standalone

`uv run --with pyinstaller pyinstaller --onefile --name lparchive2epub lparchive2epub/main.py`

## Cache

Within one run, every image URL is downloaded once however many updates use it, so no cache is
needed for a single book. Pass `--cache FILE` to keep everything downloaded in a SQLite database:
building the same LP again (after a failure, or with a newer version of the tool) then takes seconds
and only fetches what is missing. Failed downloads are never cached, so re-running after a dead host
comes back works as expected. The database keeps a copy of every image it has seen, so it grows with
each LP you build; delete the file to start afresh.

## Image size

By default every image is embedded exactly as lparchive.org serves it, which is the right choice for
tablets and for archiving. Some LPs carry very large pictures (a single 17 MB photo is not unheard of)
that make e-ink readers crawl or crash. `--max-image-size 1600` shrinks anything larger than 1600
pixels on its longest edge, re-encodes JPEGs at `--jpeg-quality` (85 by default), optimises PNGs and
converts WebP and BMP, which many readers can't display, to PNG or JPEG. Animated GIFs are left as they
are. A summary of the saving is printed before the book is written.

## Exit codes

| code | meaning |
|---|---|
| 0 | the book was written (skipped images, if any, are listed in a report) |
| 1 | the book was not written: `--strict` failure, missing update(s), or an unexpected error |
| 2 | invalid command line |
| 3 | the Let's Play was not found on lparchive.org (HTTP 404) |
| 4 | lparchive.org could not be reached or kept failing |
| 5 | the output file could not be written |
| 6 | the `--cache` database could not be used (locked, not a database...) |
| 130 | interrupted with Ctrl-C |

## Known limitations

- ~~Similar images present in multiple pages in the let's play are duplicated, bloating the file. Though recurring images are usually smileys, so not too big.~~ Now handled!
- ~~Links to images are not properly saved.~~ Now working properly!
- LPs that are mostly link to YouTube videos are not very interesting to transform to epub
- Some LPs completely fail to be downloaded.
- Some LPs contain broken links (typos like `hhttp://`, dead image hosts...). Common typos are repaired automatically; resources that still can't be retrieved are left as external links and a report is printed at the end. If a whole update can't be retrieved, no book is written and the failing update(s) are listed; pass `--allow-missing-updates` to build the book anyway with a placeholder page in their place. Please paste that report in a [GitHub issue](https://github.com/Arwalk/lparchive2epub/issues/new) so the case can be handled in a future release. Use `--strict` to fail instead.
