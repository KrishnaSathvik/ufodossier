"""
ufodossier // import_converted

UFO-USA already OCR'd Release 01 with PyMuPDF + Gemini at 200 DPI. Their
converted/ tree has one Markdown file per PDF page, with YAML front matter
naming the source file. This module pulls those Markdown pages directly
into our source_files.ocr_text column, bypassing our local OCR step.

This makes the difference between "ingest takes a weekend" and "ingest
takes 20 minutes" — and we avoid the 2.4GB download + the tesseract
fallback path entirely for Release 01.

We still keep ocr.py around for tranches 2+ where we don't have a community
mirror yet.

Usage:
    # after running ingest_manifest.py, fill in OCR text from UFO-USA:
    python -m pipeline.import_converted
    python -m pipeline.import_converted --limit 10  # smoke test
"""
from __future__ import annotations

import argparse
import logging
import re
from urllib.parse import quote

import httpx

from pipeline.db import get_supabase

logger = logging.getLogger(__name__)

GH_API = "https://api.github.com/repos/DenisSergeevitch/UFO-USA/contents"
RAW_BASE = "https://raw.githubusercontent.com/DenisSergeevitch/UFO-USA/main"

USER_AGENT = "ufodossier-bot/1.0 (+https://ufodossier.com/methodology)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/vnd.github+json",
}


def list_converted_folders(client: httpx.Client) -> list[str]:
    """List folder names under converted/."""
    r = client.get(f"{GH_API}/converted", headers=HEADERS)
    r.raise_for_status()
    items = r.json()
    folders = [it["name"] for it in items if it.get("type") == "dir"]
    logger.info("found %d converted folders", len(folders))
    return folders


def list_pages_in_folder(client: httpx.Client, folder: str) -> list[str]:
    """List page-####.md filenames in a converted/ subfolder."""
    r = client.get(f"{GH_API}/converted/{quote(folder)}", headers=HEADERS)
    r.raise_for_status()
    items = r.json()
    pages = sorted(
        it["name"] for it in items
        if it.get("type") == "file" and it["name"].startswith("page-") and it["name"].endswith(".md")
    )
    return pages


def fetch_page_md(client: httpx.Client, folder: str, page: str) -> str:
    url = f"{RAW_BASE}/converted/{quote(folder)}/{quote(page)}"
    r = client.get(url, timeout=30.0)
    r.raise_for_status()
    return r.text


# folder names look like: 001-65_HS1-834228961_62-HQ-83894_Section_10
# the source file is roughly the part after the leading "NNN-" prefix
def folder_to_source_hint(folder: str) -> str:
    return re.sub(r"^\d+[-_]", "", folder).strip()


def strip_yaml_frontmatter(md: str) -> tuple[dict, str]:
    """
    UFO-USA pages start with YAML front matter:
        ---
        source_file: "..."
        page: 1
        ...
        ---
        # then markdown body
    Returns (front_matter_dict, body).
    """
    if not md.startswith("---"):
        return {}, md
    parts = md.split("---", 2)
    if len(parts) < 3:
        return {}, md
    raw_fm = parts[1]
    body = parts[2].lstrip("\n")

    fm: dict[str, str] = {}
    for line in raw_fm.splitlines():
        m = re.match(r'^\s*([a-z_]+)\s*:\s*"?([^"]*)"?\s*$', line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm, body


def match_folder_to_source_file(folder_hint: str, source_files: list[dict]) -> dict | None:
    """
    Given a folder name like '65_HS1-834228961_62-HQ-83894_Section_10',
    find the source_files row whose filename or URL contains the strongest
    matching token.
    """
    # extract distinctive token (longest alphanumeric chunk)
    tokens = re.findall(r"[A-Za-z0-9]{4,}", folder_hint)
    if not tokens:
        return None
    tokens.sort(key=len, reverse=True)

    for token in tokens[:5]:
        for sf in source_files:
            haystack = (sf.get("filename", "") + " " + sf.get("url", "")).lower()
            if token.lower() in haystack:
                return sf
    return None


def run(limit: int | None = None) -> None:
    sb = get_supabase()

    source_files = (
        sb.table("source_files")
        .select("id,filename,url,ocr_text,file_type")
        .eq("file_type", "pdf")
        .execute()
        .data
    )
    logger.info("found %d PDF source_files in DB", len(source_files))

    # only fill in those without ocr_text
    needs_ocr = [sf for sf in source_files if not sf.get("ocr_text")]
    logger.info("of those, %d still need ocr_text", len(needs_ocr))

    with httpx.Client(timeout=60.0) as client:
        folders = list_converted_folders(client)

        if limit:
            folders = folders[:limit]

        matched = mismatched = 0

        for folder in folders:
            hint = folder_to_source_hint(folder)
            sf = match_folder_to_source_file(hint, needs_ocr)
            if sf is None:
                logger.warning("no source_file matches folder %s", folder)
                mismatched += 1
                continue

            try:
                pages = list_pages_in_folder(client, folder)
            except httpx.HTTPError as e:
                logger.error("failed listing pages in %s: %s", folder, e)
                continue

            page_texts: list[str] = []
            for p in pages:
                try:
                    md = fetch_page_md(client, folder, p)
                except httpx.HTTPError as e:
                    logger.error("failed fetching %s/%s: %s", folder, p, e)
                    continue
                fm, body = strip_yaml_frontmatter(md)
                page_num = fm.get("page") or p.replace("page-", "").replace(".md", "")
                page_texts.append(f"--- PAGE {page_num} ---\n{body.strip()}")

            full_text = "\n\n".join(page_texts)

            sb.table("source_files").update({
                "ocr_text": full_text,
                "ocr_method": "imported_ufo_usa_gemini",
                "page_count": len(pages),
                "processed_at": "now()",
            }).eq("id", sf["id"]).execute()

            logger.info("matched %s -> %s (%d pages, %d chars)",
                        folder, sf["filename"], len(pages), len(full_text))
            matched += 1

        logger.info("done // matched=%d mismatched=%d", matched, mismatched)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="cap folders for smoke testing")
    args = parser.parse_args()
    run(limit=args.limit)
