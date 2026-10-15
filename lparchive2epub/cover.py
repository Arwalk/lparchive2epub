"""Generated cover image and title page.

The cover is drawn with Pillow's bundled scalable font, so no font file ships with the tool.
Rendering is deterministic for a given Pillow version, which is why pyproject.toml pins it:
the same Let's Play must give the same book from one run to the next.
"""
import html
import io
from importlib import metadata

from PIL import Image, ImageDraw, ImageFont

COVER_SIZE = (1600, 2400)
COVER_FILE_NAME = "images/cover.jpg"
TITLE_PAGE_FILE_NAME = "title_page.xhtml"
BACKGROUND = (34, 40, 49)
INK = (238, 238, 238)
ACCENT = (166, 38, 37)        # lparchive's red
PUBLISHER = "The Let's Play Archive"


def tool_version() -> str:
    try:
        return metadata.version("lparchive2epub")
    except metadata.PackageNotFoundError:
        return "dev"


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    """Greedy word wrap on measured widths; a single word wider than the line is split by characters."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}".strip()
            if draw.textlength(candidate, font=font) <= max_width:
                line = candidate
                continue
            if line:
                lines.append(line)
            line = word
            while draw.textlength(line, font=font) > max_width and len(line) > 1:
                cut = next(i for i in range(len(line), 0, -1) if draw.textlength(line[:i], font=font) <= max_width)
                lines.append(line[:cut])
                line = line[cut:]
        lines.append(line)
    return lines


def make_cover(title: str, author: str, size=COVER_SIZE) -> bytes:
    """A plain, legible text cover: title, author, publisher. Returns JPEG bytes."""
    width, height = size
    image = Image.new("RGB", size, BACKGROUND)
    draw = ImageDraw.Draw(image)
    margin = width // 10
    draw.rectangle([0, 0, width, height // 40], fill=ACCENT)

    title_font_size = width // 10
    while True:
        title_font = ImageFont.load_default(size=title_font_size)
        title_lines = _wrap(draw, title, title_font, width - 2 * margin)
        if len(title_lines) <= 6 or title_font_size <= width // 25:
            break
        title_font_size = int(title_font_size * 0.85)
    line_height = int(title_font_size * 1.2)

    y = height // 4
    for line in title_lines:
        draw.text((margin, y), line, font=title_font, fill=INK)
        y += line_height

    author_font = ImageFont.load_default(size=width // 20)
    y += line_height // 2
    for line in _wrap(draw, f"by {author}", author_font, width - 2 * margin):
        draw.text((margin, y), line, font=author_font, fill=INK)
        y += int(width // 20 * 1.3)

    footer_font = ImageFont.load_default(size=width // 28)
    draw.text((margin, height - height // 8), PUBLISHER, font=footer_font, fill=INK)

    out = io.BytesIO()
    image.save(out, "JPEG", quality=85, optimize=True)
    return out.getvalue()


def make_title_page(intro, url: str, description: str) -> str:
    """XHTML body for the title page: the landing page header the book would otherwise lose."""
    def row(label: str, value: str | None, link: str | None = None) -> str:
        if not value:
            return ""
        shown = html.escape(value)
        if link:
            shown = f'<a href="{html.escape(link, quote=True)}">{shown}</a>'
        return f"<p>{html.escape(label)}: {shown}</p>\n"

    period = None
    if intro.began and intro.ended:
        period = intro.began if intro.began == intro.ended else f"{intro.began} to {intro.ended}"
    parts = f"{intro.parts} updates" if intro.parts else None
    tags = ", ".join(intro.tags) if intro.tags else None
    return (
        '<div class="title-page">\n'
        f"<h1>{html.escape(intro.title)}</h1>\n"
        f"<p class=\"author\">by {html.escape(intro.author)}</p>\n"
        + row("Updates", parts)
        + row("Posted", period)
        + row("Tags", tags)
        + row("Added to the archive", intro.published_on)
        + row("Archived at", url, url)
        + row("Original thread", intro.thread_title or intro.thread_url, intro.thread_url)
        + f"<p class=\"colophon\">{html.escape(description)}</p>\n"
        f"<p class=\"colophon\">Converted by lparchive2epub {html.escape(tool_version())}.</p>\n"
        "</div>\n"
    )
