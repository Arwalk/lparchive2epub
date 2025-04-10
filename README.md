# lparchive2pub

this tool (and library) aims at helping people extracting full epubs of Let's Plays from https://lparchive.org/

```
usage: lparchive2epub [-h] URL OUTPUT_FILE

A tool to transform a Let's Play from lparchive.org to epub format.

positional arguments:
  URL
  OUTPUT_FILE

options:
  -h, --help   show this help message and exit
```

The repository also contains the script `util/all_archives.py` that tries to scrape all LPs from lparchive.

## Requirements

### Dev

Poetry, python 3.12

### Users

python >= 3.12

## Installation

`pip install lparchive2epub`

To have it installed in its own separate environment, you can use https://github.com/pypa/pipx

`pipx install lparchive2epub`

A standalone executable is available for releases on windows. See the releases page.

## Known limitations

- ~~Similar images present in multiple pages in the let's play are duplicated, bloating the file. Though recurring images are usually smileys, so not too big.~~ Now handled!
- ~~Links to images are not properly saved.~~ Now working properly!
- LPs that are mostly link to YouTube videos are not very interesting to transform to epub
- Some LPs completely fail to be downloaded.
