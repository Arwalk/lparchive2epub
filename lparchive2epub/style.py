"""Stylesheet embedded in every book.

lparchive.org pages are archived forum posts: bare text separated by <br/>, screenshots as
<img class="img"> (thumbnails as <img class="timg">), quotes as <div class="bbc-block"><h4>quote:</h4>
<blockquote>...</blockquote></div> or bare <blockquote class="qb2">, code as <div class="bbc-block code">,
spoilers as <span class="bbc-spoiler">, and the landing page's table of contents as <ul class="toc">.
Update titles are <h3>.

The rules below are deliberately few and conservative: e-ink readers ignore or mangle fancy CSS, the
reader's own font and theme settings must keep working (so no font-family on body, no hard-coded
page colours), and nothing here may reference external resources (epubcheck flags them).
"""

from ebooklib import epub

STYLE_FILE_NAME = "style/lparchive.css"


def get_style_item():
    return epub.EpubItem(uid="style_lparchive",
                         file_name=STYLE_FILE_NAME,
                         media_type="text/css",
                         content=style)


style = """\
/* Let's Play Archive book stylesheet (see lparchive2epub/style.py) */

body {
  line-height: 1.4;
}

h1, h2, h3, h4, h5, h6 {
  font-weight: bold;
  line-height: 1.25;
  margin: 1em 0 0.5em 0;
  page-break-after: avoid;
}
h1 { font-size: 1.6em; }
h2 { font-size: 1.4em; }
h3 { font-size: 1.25em; }   /* update titles: "Part 4: by TouretteDog" */
h4, h5, h6 { font-size: 1.1em; }

p, ul, ol {
  margin: 0.6em 0;
}

/* Screenshots: full width of the screen, never wider, aspect ratio kept, no decoration */
img {
  max-width: 100%;
  height: auto;
}

/* Forum quotes: <div class="bbc-block"><h4>quote:</h4><blockquote>...</blockquote></div> */
.bbc-block {
  margin: 1em 0;
  padding: 0.2em 0 0.2em 0.8em;
  border-left: 3px solid #999999;
}
.bbc-block h4 {
  font-size: 0.85em;
  font-weight: bold;
  margin: 0 0 0.3em 0;
}
.bbc-block blockquote {
  margin: 0;
  padding: 0;
  border: none;
}
blockquote {
  margin: 1em 0;
  padding: 0.2em 0 0.2em 0.8em;
  border-left: 3px solid #999999;
}

/* Code and preformatted blocks */
pre, code, .bbc-block.code, .bbc-block.pre {
  font-family: monospace;
  font-size: 0.85em;
  white-space: pre-wrap;
  word-wrap: break-word;
}

/* Spoilers: on the site they are black on black until hovered, which can't work on a page */
.bbc-spoiler {
  border: 1px dashed #999999;
  padding: 0 0.2em;
}

/* Table of contents on the landing page */
ul.toc {
  list-style: none;
  padding: 0;
}
ul.toc li {
  padding: 0.3em 0;
  border-bottom: 1px solid #cccccc;
}

table {
  border-collapse: collapse;
  margin: 1em 0;
  max-width: 100%;
}
td, th {
  padding: 0.2em 0.5em;
  vertical-align: top;
}
"""
