# lparchive2epub

this tool (and library) aims at helping people extracting full epubs of Let's Plays from https://lparchive.org/

```
usage: lparchive2epub [-h] [--cache FILE] [--strict] [--allow-missing-updates]
                      [--max-image-size PIXELS] [--jpeg-quality 1-100]
                      [--concurrency N] [--retries N] [--quiet]
                      [--images-in-memory] [--cover IMAGE | --no-cover]
                      URL [OUTPUT]

A tool to transform a Let's Play from lparchive.org to epub format.

positional arguments:
  URL          Address of the Let's Play on lparchive.org (any page of it
               will do)
  OUTPUT       Where to write the book: a file name, or a directory to put
               '<title>.epub' in (default: '<title>.epub' in the current
               directory)

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
  --concurrency N
               Downloads in flight at the same time (default: 32)
  --retries N  Attempts per download before giving up, with increasing waits
               in between (default: 5; 1 means no retry)
  --quiet      No progress bars or progress messages; only the final report
               and errors
  --images-in-memory
               Keep every image in memory until the book is written, instead
               of in a temporary folder (under TMPDIR); for machines with a
               small or slow temporary directory. Needs memory of several
               times the book's size
  --cover IMAGE
               Use this image file as the cover instead of the generated one
               (title and author on a plain background)
  --no-cover   Build the book without a cover image
```

The repository also contains the script `util/all_archives.py` that tries to scrape all LPs from lparchive,
and `util/snapshot_landing_pages.py`, which refreshes `tests/resources/landing_pages.zip`: a snapshot of
every Let's Play landing page on the archive, used by the test suite to check the extractor against the
whole archive rather than a handful of pages. `tests/resources/chapters.json` records what the extractor
must find on each of those pages (facts and ordered chapters); `util/generate_chapter_golden.py`
regenerates it after an intended change, and the diff shows exactly which Let's Plays moved.
Run `pytest -m "not archive"` to skip that archive-wide check while iterating.
`pytest --live` additionally builds five Let's Plays from the site and compares the books byte for byte
with `tests/resources/live_checksums.json`; after an intended change to the output, regenerate that file
with `uv run python util/live_checksums.py`. The books are deterministic, so a mismatch is either the
tool or the site having changed.

## Example

A ready-made book, *Dwarf Fortress - Boatmurdered* (66 updates, 45 MB), is attached to the
[releases page](https://github.com/Arwalk/lparchive2epub/releases) so you can see what the tool
produces before installing it.

## Requirements

### Dev

uv, which installs a supported Python (3.12 to 3.14) by itself if none is present

### Users

python 3.12 to 3.14

### Checks

`uv run pytest` runs the test suite (which includes a `ruff check` for unused imports and names);
`uv run ruff check` runs that lint alone.

## Installation

`pip install lparchive2epub`

To have it installed in its own separate environment, you can use https://github.com/pypa/pipx

`pipx install lparchive2epub`

A standalone executable is available for releases on windows. See the releases page.

## Building standalone

`uv run --with pyinstaller pyinstaller --onefile --name lparchive2epub lparchive2epub/main.py`

## Downloads

At most 32 downloads are in flight at once (`--concurrency`), each one is attempted up to 5 times with
increasing waits (`--retries`), and a connection that stops sending for a minute is given up rather than
waited on. Progress goes to stderr; `--quiet` keeps only the final report and errors, for scripts.

## Cache

Within one run, every image URL is downloaded once however many updates use it, so no cache is
needed for a single book. Pass `--cache FILE` to keep everything downloaded in a SQLite database:
building the same LP again (after a failure, or with a newer version of the tool) then takes seconds
and only fetches what is missing. Failed downloads are never cached, so re-running after a dead host
comes back works as expected. The database keeps a copy of every image it has seen, so it grows with
each LP you build; delete the file to start afresh.

## Cover and title page

Every book gets a generated cover (title and author on a plain background) and a title page with the
facts from the landing page: author, number of updates, when it was posted, tags, archival date,
original thread. `--cover IMAGE` uses your own picture instead, `--no-cover` leaves the cover out.

## Thumbnails

Forum posts often show a small picture linking to the full-size one ("click here for the full image").
A book has no click-to-enlarge, so the full-size picture is shown in place of the thumbnail, fitted
to the screen; only the full picture is downloaded. `--max-image-size` applies to it like to any
other image.

## Image size

By default every image is embedded exactly as lparchive.org serves it, which is the right choice for
tablets and for archiving. Some LPs carry very large pictures (a single 17 MB photo is not unheard of)
that make e-ink readers crawl or crash. `--max-image-size 1600` shrinks anything larger than 1600
pixels on its longest edge, re-encodes JPEGs at `--jpeg-quality` (85 by default), optimises PNGs and
converts WebP and BMP, which many readers can't display, to PNG or JPEG. Animated GIFs are left as they
are. A summary of the saving is printed before the book is written.

## Memory and disk

Memory use does not grow with the size of the Let's Play: as they are downloaded, images are kept in a
folder under the system temporary directory (`TMPDIR` to move it) and only read back, one at a time,
while the book is written; each one is deleted as soon as it is in the book. That directory therefore
needs free space of about the book's size, and the output directory about twice the book's size while
it is written. The folder is removed when the build ends, however it ends; if the process is killed
outright, a leftover `lparchive2epub-*` folder can be deleted by hand. `--images-in-memory` keeps every
image in memory instead, as earlier versions did, which costs several times the book's size.

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
- Some landing pages do not list every update (or list none): the tool follows the pages' own next
  links from the last listed update to find the rest.
- Some LPs completely fail to be downloaded.
- Some LPs contain broken links (typos like `hhttp://`, dead image hosts...). Common typos are repaired automatically; resources that still can't be retrieved are left as external links and a report is printed at the end. If a whole update can't be retrieved, no book is written and the failing update(s) are listed; pass `--allow-missing-updates` to build the book anyway with a placeholder page in their place. Please paste that report in a [GitHub issue](https://github.com/Arwalk/lparchive2epub/issues/new) so the case can be handled in a future release. Use `--strict` to fail instead.
