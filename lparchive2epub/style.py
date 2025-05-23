# Courtesy of https://github.com/mattharrison/epub-css-starter-kit

from ebooklib import epub


def get_style_item():
    return epub.EpubItem(uid="style_nav",
                        file_name="style/nav.css",
                        media_type="text/css",
                        content=style)

style = """/* This assumes geometric header shrinkage */
/* Also, it tries to make h2 be 1em */
html, body, div, span, applet, object, iframe, h1, h2, h3, h4, h5, h6, p, blockquote, pre, a, abbr, acronym, address, big, cite, code, del, dfn, em, img, ins, kbd, q, s, samp, small, strike, strong, sub, sup, tt, var, b, u, i, center, dl, dt, dd, fieldset, form, label, legend, table, caption, tbody, tfoot, thead, tr, th, td, article, aside, canvas, details, embed, figure, figcaption, footer, header, hgroup, menu, nav, output, ruby, section, summary, time, mark, audio, video {
  /* Note kindle hates margin:0 ! (or margin-left or margin-top set) it inserts newlines galore */
  /* margin: 0 */
  margin-right: 0;
  padding: 0;
  border: 0;
  font-size: 100%;
  /* font: inherit */
  vertical-align: baseline; }

/* optimal sizing see http://demosthenes.info/blog/578/Crafting-Optimal-Type-Sizes-For-Web-Pages */
/* kobo and nook dislike this */
/*html */
/*  font-size: 62.5% */
/*body */
/*  font-size: 1.6rem */
/*  line-height: 2.56rem */
/*  text-rendering: optimizeLegibility */
table {
  border-collapse: collapse;
  border-spacing: 0; }

/* end reset */
@page {
  margin-top: 30px;
  margin-bottom: 20px; }

div.cover {
  text-align: center;
  page-break-after: always;
  padding: 0px;
  margin: 0px; }
  div.cover img {
    height: 100%;
    max-width: 100%;
    padding: 10px;
    margin: 0px;
    background-color: #cccccc; }

.half {
  max-width: 50%; }

.tenth {
  max-width: 10%;
  width: 10%; }

.cover-img {
  height: 100%;
  max-width: 100%;
  padding: 0px;
  margin: 0px; }

/* font plan- serif text, sans headers */
h1, h2, h3, h4, h5, h6 {
  hyphens: none !important;
  -moz-hyphens: none !important;
  -webkit-hyphens: none !important;
  adobe-hyphenate: none !important;
  page-break-after: avoid;
  page-break-inside: avoid;
  text-indent: 0px;
  text-align: left;
  font-family: Helvetica, Arial, sans-serif; }

h1 {
  font-size: 1.6em;
  margin-bottom: 3.2em; }

.title h1 {
  margin-bottom: 0px;
  margin-top: 3.2em; }

h2 {
  font-size: 1em;
  margin-top: 0.5em;
  margin-bottom: 0.5em; }

h3 {
  font-size: 0.625em; }

h4 {
  font-size: 0.391em; }

h5 {
  font-size: 0.244em; }

h6 {
  font-size: 0.153em; }

/* Do not indent first paragraph. Mobi will need class='first-para' */
h1 + p, h2 + p, h3 + p, h4 + p, h5 + p, h6 + p {
  text-indent: 0; }

p {
  /* paperwhite defaults to sans */
  font-family: "Palatino", "Times New Roman", Caecilia, serif;
  -webkit-hyphens: auto;
  -moz-hyphens: auto;
  hyphens: auto;
  hyphenate-after: 3;
  hyphenate-before: 3;
  hyphenate-lines: 2;
  -webkit-hyphenate-after: 3;
  -webkit-hyphenate-before: 3;
  -webkit-hyphenate-lines: 2;
  line-height: 1.5em;
  margin: 0;
  text-align: justify;
  text-indent: 1em;
  orphans: 2;
  widows: 2; }
  p.first-para, p.first-para-chapter, p.note-p-first {
    text-indent: 0; }
  p.first-para-chapter::first-line {
    /* handle run-in */
    font-variant: small-caps; }
  p.no-indent {
    text-indent: 0; }

.no-hyphens {
  hyphens: none !important;
  -moz-hyphens: none !important;
  -webkit-hyphens: none !important;
  adobe-hyphenate: none !important; }

.rtl {
  direction: rtl;
  float: right; }

.drop {
  overflow: hidden;
  line-height: 89%;
  height: 0.8em;
  font-size: 281%;
  margin-right: 0.075em;
  float: left; }

.dropcap {
  line-height: 100%;
  font-size: 341%;
  margin-right: 0.075em;
  margin-top: -0.22em;
  float: left;
  height: 0.8em; }

/* lists */
ul, ol, dl {
  margin: 1em 0 1em 0;
  text-align: left; }

li {
  font-family: "Palatino", "Times New Roman", Caecilia, serif;
  line-height: 1.5em;
  orphans: 2;
  widows: 2;
  text-align: justify;
  text-indent: 0;
  margin: 0; }
  li p {
    /* Fix paragraph indenting inside of lists */
    text-indent: 0em; }

dt {
  font-weight: bold;
  font-family: Helvetica, Arial, sans-serif; }

dd {
  line-height: 1.5em;
  font-family: "Palatino", "Times New Roman", Caecilia, serif; }
  dd p {
    /* Fix paragraph indenting inside of definition lists */
    text-indent: 0em; }

blockquote {
  margin-left: 1em;
  margin-right: 1em;
  line-height: 1.5em;
  font-style: italic; }
  blockquote p.first-para, blockquote p {
    text-indent: 0; }

pre, tt, code, samp, kbd {
  font-family: "Courier New", Courier, monospace;
  word-wrap: break-word; }

pre {
  font-size: 0.8em;
  line-height: 1.2em;
  margin-left: 1em;
  /* margin-top: 1em */
  margin-bottom: 1em;
  white-space: pre-wrap;
  display: block; }

img {
  border-radius: 0.3em;
  -webkit-border-radius: 0.3em;
  -webkit-box-shadow: rgba(0, 0, 0, 0.15) 0 1px 4px;
  box-shadow: rgba(0, 0, 0, 0.15) 0 1px 4px;
  box-sizing: border-box;
  border: white 0.5em solid;
  /* Don't go too big on images, let reader zoom in if they care to */
  max-width: 80%;
  max-height: 80%; }

img.pwhack {
  /* Paperwhite hack */
  width: 100%; }

.group {
  page-break-inside: avoid; }

.caption {
  text-align: center;
  font-size: 0.8em;
  font-weight: bold; }

p img {
  border-radius: 0;
  border: none; }

figure {
  /* These first 3 should center figures */
  padding: 1em;
  background-color: #cccccc;
  border: 1px solid black;
  text-align: center; }
  figure figcaption {
    text-align: center;
    font-size: 0.8em;
    font-weight: bold; }

div.div-literal-block-admonition {
  margin-left: 1em;
  background-color: #cccccc; }
div.note, div.tip, div.hint {
  margin: 1em 0 1em 0 !important;
  background-color: #cccccc;
  padding: 1em !important;
  /* kindle is finnicky with borders, bottoms dissappear, width is ignored */
  border-top: 0px solid #cccccc;
  border-bottom: 0px dashed #cccccc;
  page-break-inside: avoid; }

/* sidebar */
p.note-title, .admonition-title {
  margin-top: 0;
  /*mobi doesn't like div margins */
  font-variant: small-caps;
  font-size: 0.9em;
  text-align: center;
  font-weight: bold;
  font-style: normal;
  -webkit-hyphens: none;
  -moz-hyphens: none;
  hyphens: none;
  /* margin:0 1em 0 1em */ }

div.note p, .note-p {
  text-indent: 1em;
  margin-left: 0;
  margin-right: 0; }

/*  font-style: italic */
/* Since Kindle doesn't like multiple classes have to have combinations */
div.note p.note-p-first {
  text-indent: 0;
  margin-left: 0;
  margin-right: 0; }

/* Tables */
table {
  /*width: 100% */
  page-break-inside: avoid;
  border: 1px;
  /* centers on kf8 */
  margin: 1em auto;
  border-collapse: collapse;
  border-spacing: 0; }

th {
  font-variant: small-caps;
  padding: 5px !important;
  vertical-align: baseline;
  border-bottom: 1px solid black; }

td {
  font-family: "Palatino", "Times New Roman", Caecilia, serif;
  font-size: small;
  hyphens: none;
  -moz-hyphens: none;
  -webkit-hyphens: none;
  padding: 5px !important;
  page-break-inside: avoid;
  text-align: left;
  text-indent: 0;
  vertical-align: baseline; }

td:nth-last-child {
  border-bottom: 1px solid black; }

.zebra {
  /* shade background by groups of three */ }
  .zebra tr th {
    background-color: white; }
  .zebra tr:nth-child(6n-1), .zebra tr:nth-child(6n+0), .zebra tr:nth-child(6n+1) {
    background-color: #cccccc; }

sup {
  vertical-align: super;
  font-size: 0.5em;
  line-height: 0.5em; }

sub {
  vertical-align: sub;
  font-size: 0.5em;
  line-height: 0.5em; }

table.footnote {
  margin: 0.5em 0em 0em 0em; }

.footnote {
  font-size: 0.8em; }

.footnote-link {
  font-size: 0.8em;
  vertical-align: super; }

.tocEntry-1 a {
  /* empty */
  font-weight: bold;
  text-decoration: none;
  color: black; }

.tocEntry-2 a {
  margin-left: 1em;
  text-indent: 1em;
  text-decoration: none;
  color: black; }

.tocEntry-3 a {
  text-indent: 2em;
  text-decoration: none;
  color: black; }

.tocEntry-4 a {
  text-indent: 3em;
  text-decoration: none;
  color: black; }

.copyright-top {
  margin-top: 6em; }

.page-break-before {
  page-break-before: always; }

.page-break-after {
  page-break-after: always; }

.center {
  text-indent: 0;
  text-align: center;
  margin-left: auto;
  margin-right: auto;
  display: block; }

.right {
  text-align: right; }

.left {
  text-align: left; }

.f-right {
  float: right; }

.f-left {
  float: left; }

/* Samples */
.ingredient {
  page-break-inside: avoid; }

.box-example {
  background-color: #8ae234;
  margin: 2em;
  padding: 1em;
  border: 2px dashed #ef2929; }

.blue {
  background-color: blue; }

.dashed {
  border: 2px dashed #ef2929; }

.padding-only {
  padding: 1em; }

.margin-only {
  margin: 2em; }

.smaller {
  font-size: 0.8em; }

.em1 {
  font-size: 0.5em; }

.em2 {
  font-size: 0.75em; }

.em3 {
  font-size: 1em; }

.em4 {
  font-size: 1.5em; }

.em5 {
  font-size: 2em; }

.per1 {
  font-size: 50%; }

.per2 {
  font-size: 75%; }

.per3 {
  font-size: 100%; }

.per4 {
  font-size: 150%; }

.per5 {
  font-size: 200%; }

.mousepoem p {
  line-height: 0;
  margin-left: 1em; }

.per100 {
  font-size: 100%;
  line-height: 0.9em; }

.per90 {
  font-size: 90%;
  line-height: 0.9em; }

.per80 {
  font-size: 80%;
  line-height: 0.9em; }

.per70 {
  font-size: 70%;
  line-height: 0.9em; }

.per60 {
  font-size: 60%;
  line-height: 0.9em; }

.per50 {
  font-size: 50%;
  line-height: 1.05em; }

.per40 {
  font-size: 40%;
  line-height: 0.9em; }

.size1 {
  font-size: x-small; }

.size2 {
  font-size: small; }

.size3 {
  /* default */
  font-size: medium; }

.size4 {
  font-size: large; }

.size5 {
  font-size: x-large; }

/* Poetic margins */
.stanza {
  margin-top: 1em;
  font-family: serif;
  padding-left: 1em; }
  .stanza p {
    padding-left: 1em; }

.poetry {
  margin: 1em; }

/*line number */
.ln {
  float: left;
  color: #999999;
  font-size: 0.8em;
  font-style: italic; }

.pos1 {
  margin-left: 1em;
  text-indent: -1em; }

.pos2 {
  margin-left: 2em;
  text-indent: -1em; }

.pos3 {
  margin-left: 3em;
  text-indent: -1em; }

.pos4 {
  margin-left: 4em;
  text-indent: -1em; }

@font-face {
  font-family: Inconsolata Mono;
  font-style: normal;
  font-weight: normal;
  src: url("Inconsolata.otf"); }

.normal-mono {
  font-family: "Courier New", Courier, monospace; }

tt, pre, .mono {
  /* Kindle Keyboard has KF8 but no font support, fallback to default mono */
  font-family: "Inconsolata Mono", "Courier New", Courier, monospace;
  font-style: normal; }

@font-face {
  font-family: mgopen modata;
  font-style: normal;
  font-weight: normal;
  font-size: 0.5em;
  src: url("MgOpenModataRegular.ttf"); }

.modata {
  font-family: "mgopen modata"; }

@font-face {
  font-family: hidden;
  font-style: normal;
  font-weight: normal;
  font-size: 1em;
  src: url("invisible1.ttf"); }

.hidden-font {
  font-family: "hidden"; }

/* Nook works to here :) */
/* media queries at bottom to not confuse other platforms */
@media (min-width: 200px) {
  .px200 {
    color: #8ae234; } }
@media (min-width: 400px) {
  .px400 {
    color: #8ae234; } }
@media (min-width: 800px) {
  .px800 {
    color: #8ae234; } }
@media (min-width: 1200px) {
  .px1200 {
    color: #8ae234; } }
/* broke nook! */
/*/* WIP device specific... */
/*@media (min-width: 600px) and (height: 800px) and (amzn-kf8) */
/*  /* Kindle Keyboard w/ KF8 */
/*  .kk */
/*    color: $green */

/*/* @media (min-width: 768px) and (height: 1024px) and (amzn-kf8) */
/*@media (min-width: 748px) and (min-height: 1004px) and (amzn-kf8) */
/*  /* Kindle Paperwhite */
/*  .kpw */
/*    color: $green */
/*@media (width: 600px) and (height: 1024px) and (amzn-kf8) */
/*  /* Kindle Fire */
/*  .kf */
/*    color: $green */
/*/* Retina iPad */
/*@media (-webkit-min-device-pixel-ratio: 1.5), (min-device-pixel-ratio: 1.5) */
/*  .retina */
/*    color: $green */
@media amzn-kf8 {
  span.dropcapold {
    font-size: 300%;
    font-weight: bold;
    height: 1em;
    float: left;
    margin: -0.2em 0.1em 0 0.1em; }

  .dropcap {
    line-height: 100%;
    font-size: 341%;
    margin-right: 0.075em;
    margin-top: -0.22em;
    float: left;
    height: 0.8em; } }
@media amzn-mobi {
  span.dropcap {
    font-size: 1.5em;
    font-weight: bold; }

  /*  tt, pre */
  /*    font-size: 3 */
  /*     Size table */
  /* name     becomes */
  /* x-small  2 */
  /* small    3 */
  /* medium   4 */
  /*     1em  default (nothing) */
  tt {
    /* mobi fun */
    /* font-size: x-small  /* turns into <font size="2" */
    font-family: "Courier New", Courier, monospace; }

  pre {
    margin-left: 1em;
    margin-bottom: 1em;
    /* mobi fun */
    font-size: x-small;
    font-family: "Courier New", Courier, monospace;
    white-space: pre-wrap;
    display: block; }
    pre .no-indent {
      margin-left: 0em;
      text-indent: 0em; }

  div.no-indent {
    margin-left: 0em;
    text-indent: 0em; }

  /* Sass wants to add em to the end..., hardcoded for now */
  h1 {
    font-size: 2em; }

  h2 {
    font-size: 1em; }

  h3 {
    font-size: 2em; }

  h4 {
    font-size: 1em; }

  blockquote {
    /* something in this css causes blockquotes to get doubly indented! (BUG) */
    font-style: italics;
    margin-left: 0em;
    margin-right: 0em; }

  /* descendant selectors don't work in mobi7 infact this will override the preview h1 defintion! */
  /* h1 tt, h2 tt { */
  /*   font-size: 1em; */
  /*   color: green;} */
  div.note {
    border: 1px solid black;
    /*text-indent: 1em */ }

  div.note, .note-p {
    text-indent: 1em;
    margin-left: 0;
    margin-right: 0;
    font-style: italic; }

  /* Since Kindle doesn't like multiple classes have to have combinations (fixed in 2.7) */
  .note-p-first {
    text-indent: 0;
    margin-left: 1em;
    margin-right: 1em; }

  .note-p {
    text-indent: 1em;
    margin-left: 1em;
    margin-right: 1em; }

  /* Poetry handing indent hacks */
  /* see http://ebookarchitects.com/blog/backwards-compatible-poetry-for-kf8mobi/ */
  /* and http://www.pigsgourdsandwikis.com/2012/01/media-queries-for-formatting-poetry-on.html */
  .pos1 {
    text-indent: -1em; }

  .pos2 {
    text-indent: -1em; }

  .pos3 {
    text-indent: -1em; }

  .pos4 {
    text-indent: -1em; } }
/* does nook ignore this? */
.green {
  color: #8ae234; }

/*These break NOOK! */
/*@media (monochrome) */
/*  .monochrome */
/*    color: $green */
/*@media (color) */
/*  .color */
/*    color: $green */
.linked-fullsize-image {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1em 0;
}
"""