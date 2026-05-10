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

GH_TREE_API = "https://api.github.com/repos/DenisSergeevitch/UFO-USA/git/trees/main?recursive=1"
RAW_BASE = "https://raw.githubusercontent.com/DenisSergeevitch/UFO-USA/main"

USER_AGENT = "ufodossier-bot/1.0 (+https://ufodossier.com/methodology)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/vnd.github+json",
}


def build_converted_tree(client: httpx.Client) -> dict[str, list[str]]:
    """
    Fetch the entire repo tree in ONE API call, then extract the
    converted/ folder structure: {folder_name: [page-0001.md, ...]}
    """
    r = client.get(GH_TREE_API, headers=HEADERS)
    r.raise_for_status()
    tree = r.json().get("tree", [])

    folders: dict[str, list[str]] = {}
    for item in tree:
        path = item.get("path", "")
        if not path.startswith("converted/") or item.get("type") != "blob":
            continue
        parts = path.split("/")
        if len(parts) != 3:
            continue
        folder_name = parts[1]
        filename = parts[2]
        if filename.startswith("page-") and filename.endswith(".md"):
            folders.setdefault(folder_name, []).append(filename)

    # sort page lists within each folder
    for pages in folders.values():
        pages.sort()

    logger.info("tree API: found %d converted folders", len(folders))
    return folders


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


def _normalize_name(s: str) -> str:
    """Lowercase, strip non-alnum, collapse to single underscores for comparison."""
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def match_folder_to_source_file(folder_hint: str, source_files: list[dict]) -> dict | None:
    """
    Given a folder name like '65_HS1-834228961_62-HQ-83894_Section_10',
    find the source_files row whose filename or URL best matches.
    Tries exact filename match first, then URL substring, then token fallback.
    """
    hint_norm = _normalize_name(folder_hint)

    # 1. exact match on filename (ignoring extension)
    for sf in source_files:
        fn = _normalize_name(sf.get("filename", ""))
        fn_no_ext = fn.rsplit(".", 1)[0] if "." in fn else fn
        if hint_norm == fn_no_ext:
            return sf

    # 2. full hint appears in URL
    for sf in source_files:
        url_norm = _normalize_name(sf.get("url", ""))
        if hint_norm in url_norm:
            return sf

    # 3. token fallback (longest alphanumeric chunks)
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

    needs_ocr_count = sum(1 for sf in source_files if not sf.get("ocr_text"))
    logger.info("of those, %d still need ocr_text", needs_ocr_count)

    with httpx.Client(timeout=60.0) as client:
        # single API call to get entire repo tree
        converted_tree = build_converted_tree(client)
        folder_names = sorted(converted_tree.keys())

        if limit:
            folder_names = folder_names[:limit]

        matched = skipped = mismatched = 0

        for folder in folder_names:
            hint = folder_to_source_hint(folder)
            # match against ALL source files so exact-name matching always works
            sf = match_folder_to_source_file(hint, source_files)
            if sf is None:
                logger.warning("no source_file matches folder %s", folder)
                mismatched += 1
                continue

            # skip if this file already has OCR text
            if sf.get("ocr_text"):
                logger.debug("skipping %s -> %s (already has ocr_text)", folder, sf["filename"])
                skipped += 1
                continue

            pages = converted_tree[folder]

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

            # mark as populated in memory so duplicate folders don't re-write
            sf["ocr_text"] = full_text

            sb.table("source_files").update({
                "ocr_text": full_text,
                "ocr_method": "imported_ufo_usa_gemini",
                "page_count": len(pages),
                "processed_at": "now()",
            }).eq("id", sf["id"]).execute()

            logger.info("matched %s -> %s (%d pages, %d chars)",
                        folder, sf["filename"], len(pages), len(full_text))
            matched += 1

        logger.info("done // matched=%d skipped=%d mismatched=%d", matched, skipped, mismatched)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="cap folders for smoke testing")
    args = parser.parse_args()
    run(limit=args.limit)
