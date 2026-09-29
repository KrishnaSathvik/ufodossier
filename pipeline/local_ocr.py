"""
Local selective OCR (PyMuPDF render → Tesseract).

LOCAL ONLY — writes under pipeline/reports/r2_ocr/. Never touches Supabase.

Usage:
  python -m pipeline.local_ocr --pdf .cache/files/pursue/r2/CIA-UAP-D001.pdf
  python -m pipeline.local_ocr --pdfs CIA-UAP-D001 DOW-UAP-D017 --cache .cache/files/pursue/r2
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pypdf

from pipeline.text_quality import PageQuality, score_page_text, should_ocr

logger = logging.getLogger(__name__)

DEFAULT_OUT = Path("pipeline/reports/r2_ocr")
DEFAULT_DPI = 300
# CIA-UAP-009 is a 67×110pt page (embedded JPEG 134×221). Upscaling it
# does not recover text. Anything under ~2 inches on the short side is a thumbnail.
THUMBNAIL_SHORT_SIDE_PT = 144


@dataclass
class PageResult:
    page_number: int
    native_quality: dict
    final_category: str
    text_method: str  # native | tesseract | empty
    char_count: int
    text: str


def _native_pages(pdf_bytes: bytes) -> list[str]:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pages: list[str] = []
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        pages.append(t)
    return pages


def _page_short_side_pt(pdf_path: Path, page_idx: int) -> float | None:
    """Return the short side of the page in PDF points, or None if unreadable."""
    try:
        import pymupdf as fitz
    except ImportError:
        return None
    try:
        doc = fitz.open(pdf_path)
        try:
            rect = doc.load_page(page_idx).rect
            return float(min(rect.width, rect.height))
        finally:
            doc.close()
    except Exception as e:
        logger.warning("could not measure page %d of %s: %s", page_idx + 1, pdf_path.name, e)
        return None


def _render_and_ocr_page(pdf_path: Path, page_idx: int, dpi: int = DEFAULT_DPI) -> str:
    """Render one page with PyMuPDF and OCR with Tesseract."""
    try:
        import pymupdf as fitz
        import pytesseract
        from PIL import Image
    except ImportError as e:
        logger.error("OCR deps missing (pymupdf/pytesseract/Pillow): %s", e)
        return ""

    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_idx)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        doc.close()
        return pytesseract.image_to_string(img) or ""
    except Exception as e:
        logger.exception("OCR failed page %d of %s: %s", page_idx + 1, pdf_path.name, e)
        return ""


def process_pdf(
    pdf_path: Path,
    *,
    out_dir: Path,
    dpi: int = DEFAULT_DPI,
    force_ocr_all: bool = False,
) -> dict[str, Any]:
    pdf_bytes = pdf_path.read_bytes()
    native = _native_pages(pdf_bytes)
    page_count = len(native)

    doc_out = out_dir / pdf_path.stem
    doc_out.mkdir(parents=True, exist_ok=True)

    page_results: list[PageResult] = []
    combined_parts: list[str] = []
    stats = {
        "native_good": 0,
        "native_thin": 0,
        "needs_ocr": 0,
        "ocr_failed": 0,
        "ocr_succeeded": 0,
        "pages_ocrd": 0,
        "ocr_unrecoverable_thumbnail": 0,
    }

    for i, native_text in enumerate(native):
        page_no = i + 1
        quality = score_page_text(page_no, native_text)
        category = quality.category
        method = "native"
        final_text = native_text.strip()

        if force_ocr_all or should_ocr(category):
            if category == "needs_ocr":
                stats["needs_ocr"] += 1
            short_side = _page_short_side_pt(pdf_path, i)
            thumbnail = short_side is not None and short_side < THUMBNAIL_SHORT_SIDE_PT
            if thumbnail:
                stats["ocr_unrecoverable_thumbnail"] += 1
                stats["ocr_failed"] += 1
                category = "ocr_failed"
                quality = PageQuality(
                    page_number=page_no,
                    native_char_count=quality.native_char_count,
                    printable_ratio=quality.printable_ratio,
                    alpha_ratio=quality.alpha_ratio,
                    word_count=quality.word_count,
                    replacement_char_count=quality.replacement_char_count,
                    category="ocr_failed",
                    reason=(
                        f"unrecoverable thumbnail page (short side {short_side:.0f}pt); "
                        "OCR cannot recover text from a postage-stamp render"
                    ),
                )
                method = "native" if final_text else "empty"
            else:
                ocr_text = _render_and_ocr_page(pdf_path, i, dpi=dpi)
                stats["pages_ocrd"] += 1
                if ocr_text.strip():
                    # For needs_ocr / force_ocr_all: always take OCR when non-empty.
                    # Native "length" is not a quality signal for garbled text layers.
                    final_text = ocr_text.strip()
                    method = "tesseract"
                    post = score_page_text(page_no, final_text)
                    category = post.category if post.category != "needs_ocr" else "native_thin"
                    quality = PageQuality(
                        page_number=page_no,
                        native_char_count=quality.native_char_count,
                        printable_ratio=quality.printable_ratio,
                        alpha_ratio=quality.alpha_ratio,
                        word_count=quality.word_count,
                        replacement_char_count=quality.replacement_char_count,
                        category=category,  # type: ignore[arg-type]
                        reason=f"ocr_replaced_native ({quality.reason})",
                    )
                    stats["ocr_succeeded"] += 1
                else:
                    stats["ocr_failed"] += 1
                    category = "ocr_failed"
                    quality = PageQuality(
                        page_number=page_no,
                        native_char_count=quality.native_char_count,
                        printable_ratio=quality.printable_ratio,
                        alpha_ratio=quality.alpha_ratio,
                        word_count=quality.word_count,
                        replacement_char_count=quality.replacement_char_count,
                        category="ocr_failed",
                        reason="ocr returned empty; keeping native",
                    )
                    method = "native" if final_text else "empty"
        else:
            stats[category] = stats.get(category, 0) + 1

        page_path = doc_out / f"page-{page_no:03d}.txt"
        page_path.write_text(final_text + ("\n" if final_text else ""))

        combined_parts.append(f"--- PAGE {page_no} ---\n{final_text}")
        page_results.append(
            PageResult(
                page_number=page_no,
                native_quality=quality.to_dict(),
                final_category=category,
                text_method=method,
                char_count=len(final_text),
                text="",  # omit full text from JSON summary
            )
        )

    combined = "\n\n".join(combined_parts)
    (doc_out / "combined.txt").write_text(combined + "\n")

    report = {
        "filename": pdf_path.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "page_count": page_count,
        "usable_text_chars": len(combined),
        "stats": stats,
        "pages": [asdict(p) for p in page_results],
        "combined_path": str(doc_out / "combined.txt"),
        "production_writes": False,
    }
    (doc_out / "page_report.json").write_text(json.dumps(report, indent=2) + "\n")
    logger.info(
        "%s: pages=%d usable_chars=%d ocr_pages=%d ocr_ok=%d ocr_fail=%d",
        pdf_path.name,
        page_count,
        len(combined),
        stats["pages_ocrd"],
        stats["ocr_succeeded"],
        stats["ocr_failed"],
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local selective OCR (no DB writes)")
    parser.add_argument("--pdf", type=Path, action="append", help="PDF path (repeatable)")
    parser.add_argument(
        "--pdfs",
        nargs="+",
        help="Stems under --cache (e.g. CIA-UAP-D001 DOW-UAP-D017)",
    )
    parser.add_argument("--cache", type=Path, default=Path(".cache/files/pursue/r2"))
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    parser.add_argument("--force-ocr-all", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    paths: list[Path] = list(args.pdf or [])
    if args.pdfs:
        for stem in args.pdfs:
            p = args.cache / f"{stem}.pdf"
            if not p.exists():
                # allow stem already ending in .pdf
                p2 = args.cache / stem
                p = p2 if p2.exists() else p
            if not p.exists():
                logger.error("missing PDF: %s", p)
                return 1
            paths.append(p)

    if not paths:
        logger.error("provide --pdf or --pdfs")
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for pdf in paths:
        reports.append(process_pdf(pdf, out_dir=args.out_dir, dpi=args.dpi, force_ocr_all=args.force_ocr_all))

    quality_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_writes": False,
        "documents": [
            {
                "filename": r["filename"],
                "page_count": r["page_count"],
                "usable_text_chars": r["usable_text_chars"],
                "stats": r["stats"],
                "combined_path": r["combined_path"],
            }
            for r in reports
        ],
    }
    out_path = args.out_dir / "quality_report.json"
    out_path.write_text(json.dumps(quality_report, indent=2) + "\n")
    logger.info("wrote %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
