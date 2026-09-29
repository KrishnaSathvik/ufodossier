"""
Page-level native-text quality scoring for selective OCR.

Categories:
  native_good  — keep pypdf/native text
  native_thin  — short but may be usable (e.g. image caption packet)
  needs_ocr    — garbage/scan; render + OCR
  ocr_failed   — OCR attempted and failed (set by caller)
"""

from __future__ import annotations

import re
import string
from dataclasses import asdict, dataclass
from typing import Literal

PageCategory = Literal["native_good", "native_thin", "needs_ocr", "ocr_failed"]

PRINTABLE = set(string.printable)
# Exclude form-feed / vertical-tab noise from "printable" ratio if desired;
# string.printable is fine for OCR triage.


@dataclass
class PageQuality:
    page_number: int
    native_char_count: int
    printable_ratio: float
    alpha_ratio: float
    word_count: int
    replacement_char_count: int
    category: PageCategory
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


# Thresholds (tuned for R2 smoke: CIA OCR-noise + DOW scans)
NATIVE_GOOD_MIN_CHARS = 120
NATIVE_GOOD_MIN_PRINTABLE = 0.85
NATIVE_GOOD_MIN_ALPHA = 0.45
NATIVE_GOOD_MIN_WORDS = 15

NATIVE_THIN_MIN_CHARS = 40
NATIVE_THIN_MIN_PRINTABLE = 0.70

# Too many U+FFFD or mojibake-ish replacement markers
REPLACEMENT_CHARS = ("\ufffd", "�")
# Tokens with letters interrupted by OCR junk punctuation
_GARBLED_TOKEN_RE = re.compile(r"[A-Za-z][^A-Za-z\s]{1,}[A-Za-z]|[!~\\^`|]|\\\\")


def score_page_text(page_number: int, text: str) -> PageQuality:
    raw = text or ""
    stripped = raw.strip()
    n = len(stripped)

    if n == 0:
        return PageQuality(
            page_number=page_number,
            native_char_count=0,
            printable_ratio=0.0,
            alpha_ratio=0.0,
            word_count=0,
            replacement_char_count=0,
            category="needs_ocr",
            reason="empty native text",
        )

    printable = sum(1 for c in stripped if c in PRINTABLE or c.isspace())
    alpha = sum(1 for c in stripped if c.isalpha())
    printable_ratio = printable / n
    alpha_ratio = alpha / n
    words = re.findall(r"[A-Za-z]{2,}", stripped)
    word_count = len(words)
    replacement_char_count = sum(stripped.count(m) for m in REPLACEMENT_CHARS)
    weird = sum(
        1
        for c in stripped
        if (ord(c) > 127 and c not in "—–…''""°") or c in "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f\xad"
    )
    weird_ratio = weird / n

    tokens = re.findall(r"\S+", stripped)
    garbled = sum(1 for t in tokens if _GARBLED_TOKEN_RE.search(t))
    garbled_ratio = (garbled / len(tokens)) if tokens else 0.0
    # Clean dictionary-ish words (letters only, length>=3) vs total tokens
    clean_words = re.findall(r"\b[A-Za-z]{3,}\b", stripped)
    clean_ratio = (len(clean_words) / len(tokens)) if tokens else 0.0

    base_kwargs = dict(
        page_number=page_number,
        native_char_count=n,
        printable_ratio=round(printable_ratio, 3),
        alpha_ratio=round(alpha_ratio, 3),
        word_count=word_count,
        replacement_char_count=replacement_char_count,
    )

    soft_hyphens = stripped.count("\xad")
    if soft_hyphens >= 2:
        return PageQuality(
            **base_kwargs,
            category="needs_ocr",
            reason=f"soft-hyphen density ({soft_hyphens}) suggests scanned text layer",
        )

    if replacement_char_count >= 3 or weird_ratio > 0.12:
        return PageQuality(
            **base_kwargs,
            category="needs_ocr",
            reason="high replacement/mojibake density",
        )

    if garbled_ratio >= 0.12 or (garbled >= 8 and clean_ratio < 0.55):
        return PageQuality(
            **base_kwargs,
            category="needs_ocr",
            reason=f"garbled OCR tokens (ratio={garbled_ratio:.2f}, clean={clean_ratio:.2f})",
        )

    if (
        n >= NATIVE_GOOD_MIN_CHARS
        and printable_ratio >= NATIVE_GOOD_MIN_PRINTABLE
        and alpha_ratio >= NATIVE_GOOD_MIN_ALPHA
        and word_count >= NATIVE_GOOD_MIN_WORDS
        and clean_ratio >= 0.45
        and garbled_ratio < 0.08
    ):
        return PageQuality(
            **base_kwargs,
            category="native_good",
            reason="sufficient clean native text",
        )

    if n >= NATIVE_THIN_MIN_CHARS and printable_ratio >= NATIVE_THIN_MIN_PRINTABLE and word_count >= 5:
        return PageQuality(
            **base_kwargs,
            category="native_thin",
            reason="thin but printable native text (caption/short page)",
        )

    return PageQuality(
        **base_kwargs,
        category="needs_ocr",
        reason="below native usability thresholds",
    )


def should_ocr(category: PageCategory) -> bool:
    return category == "needs_ocr"
