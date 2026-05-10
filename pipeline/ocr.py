"""
ufodossier // ocr

PDF -> text. Try pypdf first; if a page returns < 100 chars
(probably a scan), fall back to tesseract.

Usage:
    python -m pipeline.ocr --limit 20
"""
from __future__ import annotations

import argparse
import io
import logging
from pathlib import Path

import pypdf

from pipeline.db import get_supabase
from pipeline.storage import download_from_storage

logger = logging.getLogger(__name__)


def extract_pdf_text(pdf_bytes: bytes) -> tuple[str, str, int]:
    """
    Returns (text, method, page_count).
    method: 'pypdf' | 'tesseract' | 'mixed'
    """
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    page_count = len(reader.pages)
    pages_text: list[str] = []
    used_tesseract = False
    used_pypdf = False

    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""

        if len(t.strip()) < 100:
            # likely a scan — fall back to tesseract
            t_ocr = _tesseract_page(pdf_bytes, i)
            if t_ocr:
                t = t_ocr
                used_tesseract = True
        else:
            used_pypdf = True

        pages_text.append(f"--- PAGE {i+1} ---\n{t.strip()}")

    text = "\n\n".join(pages_text)
    method = "mixed" if (used_pypdf and used_tesseract) else ("tesseract" if used_tesseract else "pypdf")
    return text, method, page_count


def _tesseract_page(pdf_bytes: bytes, page_idx: int) -> str:
    """Lazy import; only used for scanned pages."""
    try:
        import pdf2image
        import pytesseract
    except ImportError:
        logger.warning("tesseract dependencies not installed; skipping OCR fallback")
        return ""

    try:
        images = pdf2image.convert_from_bytes(
            pdf_bytes,
            first_page=page_idx + 1,
            last_page=page_idx + 1,
            dpi=300,
        )
        if not images:
            return ""
        return pytesseract.image_to_string(images[0])
    except Exception as e:
        logger.exception("tesseract failed on page %d: %s", page_idx, e)
        return ""


def run(limit: int | None = None) -> None:
    sb = get_supabase()

    # find pdfs without ocr_text
    q = (
        sb.table("source_files")
        .select("*")
        .eq("file_type", "pdf")
        .is_("ocr_text", "null")
    )
    if limit:
        q = q.limit(limit)

    rows = q.execute().data
    logger.info("found %d unprocessed PDFs", len(rows))

    for sf in rows:
        try:
            logger.info("ocr %s (%s)", sf["filename"], sf["id"])
            pdf_bytes = download_from_storage("source-files", sf["storage_path"])

            text, method, pages = extract_pdf_text(pdf_bytes)

            sb.table("source_files").update({
                "ocr_text": text,
                "ocr_method": method,
                "page_count": pages,
                "processed_at": "now()",
            }).eq("id", sf["id"]).execute()

            logger.info("  -> %d chars via %s, %d pages", len(text), method, pages)
        except Exception as e:
            logger.exception("ocr failed on %s: %s", sf["filename"], e)
            sb.table("source_files").update({
                "processing_error": str(e)[:500],
            }).eq("id", sf["id"]).execute()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    run(limit=args.limit)
