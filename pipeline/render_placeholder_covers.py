"""ufodossier // generate typographic placeholder covers for PDFs without page-1 renders

For each source_file with file_type='pdf' and cover_image_url IS NULL, generates
a 1200x1600 JPEG placeholder with the document's title, agency, and page count.

Usage:
    python -m pipeline.render_placeholder_covers [--dry-run]
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import re
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from pipeline.db import get_supabase
from pipeline.storage import upload_to_storage

logger = logging.getLogger(__name__)

WIDTH = 1200
HEIGHT = 1600
BG_COLOR = (0xF3, 0xEF, 0xE4)           # cream
BORDER_COLOR = (0xD8, 0xD4, 0xC8)       # hairline
DARK_TEXT = (0x1A, 0x1A, 0x1A)           # headline
MID_TEXT = (0x5A, 0x58, 0x4F)            # subheader / agency
FAINT_TEXT = (0x8A, 0x87, 0x80)          # footer

BUCKET = "source-files"
COVER_PREFIX = "placeholder-covers"

FONTS_DIR = Path(__file__).parent / "fonts"


def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a font from the fonts directory, with fallback to default."""
    path = FONTS_DIR / name
    if path.is_file():
        try:
            return ImageFont.truetype(str(path), size)
        except Exception as e:
            logger.warning("Failed to load %s at %dpx: %s", name, size, e)
    else:
        logger.warning("Font file not found: %s — using PIL default", path)
    return ImageFont.load_default()


def _parse_title(filename: str) -> tuple[str, str | None]:
    """Parse a filename into (headline, subheader|None).

    Returns human-readable title derived from the raw filename.
    """
    # State Department UAP Cable N, Location, Date
    m = re.match(
        r"State Department UAP Cable (\d+),\s*(.+)",
        filename,
        re.IGNORECASE,
    )
    if m:
        return f"State Department Cable: {m.group(2).strip()}", None

    # NASA-UAP-D3, Gemini 7 Transcript, 1965
    m = re.match(
        r"NASA-UAP-D\d+,\s*(.+?),\s*(\d{4})",
        filename,
        re.IGNORECASE,
    )
    if m:
        return f"{m.group(1).strip()} ({m.group(2)})", None

    # 65_HS1-834228961_62-HQ-83894_Serial_153
    m = re.match(
        r"65_HS1-\d+_(62-HQ-\d+)_Serial_(\d+)",
        filename,
        re.IGNORECASE,
    )
    if m:
        return f"FBI Serial {m.group(2)}", f"Case {m.group(1)}"

    # FBI September 2023 Sighting - Serial N
    m = re.match(
        r"(FBI .+?) - (Serial \d+)",
        filename,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(), m.group(2)

    # 59_64634_711.5612[7-2852  (State Dept decimal classification)
    m = re.match(r"59_\d+_(\d+\.\d+)", filename)
    if m:
        return f"State Department UAP Record {m.group(1)}", None

    # Fallback: use filename as-is
    return filename, None


def _wrap_text(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
               max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    """Wrap text to fit within max_width pixels, up to 5 lines."""
    # Start with a rough character estimate
    avg_char_w = max(1, draw.textlength("M", font=font))
    chars_per_line = max(10, int(max_width / avg_char_w))

    wrapped = textwrap.wrap(text, width=chars_per_line)

    # Refine: if any line is too wide, reduce wrap width
    for _ in range(5):
        too_wide = False
        for line in wrapped:
            if draw.textlength(line, font=font) > max_width:
                too_wide = True
                break
        if not too_wide:
            break
        chars_per_line = max(5, chars_per_line - 3)
        wrapped = textwrap.wrap(text, width=chars_per_line)

    return wrapped[:5]  # max 5 lines


def generate_placeholder(
    filename: str,
    agency: str | None,
    page_count: int | None,
) -> bytes:
    """Generate a 1200x1600 JPEG placeholder cover image."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Fonts
    font_mono_16 = _load_font("JetBrainsMono-Regular.ttf", 16)
    font_mono_17 = _load_font("JetBrainsMono-Regular.ttf", 17)
    font_mono_italic_13 = _load_font("JetBrainsMono-Italic.ttf", 13)
    font_serif_44 = _load_font("Newsreader.ttf", 44)
    font_serif_italic_24 = _load_font("Newsreader-Italic.ttf", 24)

    # Hairline border, inset 40px
    draw.rectangle(
        [40, 40, WIDTH - 41, HEIGHT - 41],
        outline=BORDER_COLOR,
        width=1,
    )

    # "DOCUMENT" header — top-left, 60px from edges
    doc_text = "D O C U M E N T"
    draw.text((60, 60), doc_text, fill=MID_TEXT, font=font_mono_16)

    # Parse headline and subheader
    headline, subheader = _parse_title(filename)

    # Calculate vertical layout for center block
    max_text_width = 1000
    headline_lines = _wrap_text(headline, font_serif_44, max_text_width, draw)
    line_height_44 = 58  # ~44px font + leading
    headline_block_h = len(headline_lines) * line_height_44

    sub_block_h = 0
    if subheader:
        sub_block_h = 24 + 34  # 24px gap + font height

    agency_str = ""
    if agency:
        agency_str = agency
    if page_count and page_count > 0:
        pages_label = "page" if page_count == 1 else "pages"
        if agency_str:
            agency_str += f" \u00b7 {page_count} {pages_label}"
        else:
            agency_str = f"{page_count} {pages_label}"
    agency_block_h = 32 + 22 if agency_str else 0  # 32px gap + font height

    total_block_h = headline_block_h + sub_block_h + agency_block_h
    block_top = (HEIGHT - total_block_h) // 2

    # Draw headline
    y = block_top
    for line in headline_lines:
        draw.text((80, y), line, fill=DARK_TEXT, font=font_serif_44)
        y += line_height_44

    # Draw subheader
    if subheader:
        y += 24
        draw.text((80, y), subheader, fill=MID_TEXT, font=font_serif_italic_24)
        y += 34

    # Draw agency / page count
    if agency_str:
        y += 32
        draw.text((80, y), agency_str, fill=MID_TEXT, font=font_mono_17)

    # Footer — bottom-left, 60px from bottom edge
    footer = "Page 1 preview unavailable"
    draw.text((60, HEIGHT - 60 - 16), footer, fill=FAINT_TEXT, font=font_mono_italic_13)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate placeholder covers for PDFs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    sb = get_supabase()
    supabase_url = os.environ["SUPABASE_URL"]

    # Find PDFs without covers
    result = (
        sb.table("source_files")
        .select("id, filename, agency, page_count")
        .eq("file_type", "pdf")
        .is_("cover_image_url", "null")
        .order("filename")
        .execute()
    )
    files = result.data or []
    logger.info("Found %d PDFs without covers", len(files))

    generated = 0
    errors = 0
    for sf in files:
        fname = sf["filename"]
        logger.info("Generating placeholder for: %s", fname)
        try:
            jpeg_bytes = generate_placeholder(
                filename=fname,
                agency=sf.get("agency"),
                page_count=sf.get("page_count"),
            )

            sha = hashlib.sha256(jpeg_bytes).hexdigest()
            cover_path = f"{COVER_PREFIX}/{sha}.jpg"
            public_url = f"{supabase_url}/storage/v1/object/public/{BUCKET}/{cover_path}"

            if args.dry_run:
                logger.info("  [DRY RUN] Would upload %s", cover_path)
            else:
                upload_to_storage(
                    bucket=BUCKET,
                    path=cover_path,
                    data=jpeg_bytes,
                    content_type="image/jpeg",
                )
                sb.table("source_files").update(
                    {"cover_image_url": public_url}
                ).eq("id", sf["id"]).execute()
                logger.info("  Uploaded -> %s", cover_path)

            generated += 1
        except Exception:
            logger.exception("  Failed for %s", fname)
            errors += 1

    logger.info("Generated %d placeholders (%d errors)", generated, errors)

    # Propagate to incidents
    if not args.dry_run:
        logger.info("Propagating placeholder covers to incidents...")
        inc_result = (
            sb.table("incidents")
            .select("id, source_file_id")
            .is_("cover_image_url", "null")
            .execute()
        )
        all_sf = (
            sb.table("source_files")
            .select("id, cover_image_url")
            .not_.is_("cover_image_url", "null")
            .execute()
        )
        sf_covers = {r["id"]: r["cover_image_url"] for r in (all_sf.data or [])}
        propagated = 0
        for inc in inc_result.data or []:
            cover = sf_covers.get(inc["source_file_id"])
            if cover:
                sb.table("incidents").update({"cover_image_url": cover}).eq(
                    "id", inc["id"]
                ).execute()
                propagated += 1
        logger.info("Propagated cover to %d incidents", propagated)


if __name__ == "__main__":
    main()
