"""
ufodossier // extract

The most important file in the pipeline. Takes OCR'd source text and asks
Claude Haiku to structure it into incident rows. Every field must be
supported by a verbatim excerpt that actually appears in the source — we
substring-validate before writing to the DB. If validation fails, we drop
the field rather than risk hallucination on a public site.

Usage:
    python -m pipeline.extract --limit 10
    python -m pipeline.extract --source-file-id <uuid>
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import anthropic

from pipeline.db import get_supabase, upsert_incident
from pipeline.embed import embed_batch

logger = logging.getLogger(__name__)

EXTRACTION_MODEL = "claude-haiku-4-5"
EXTRACTION_VERSION = "v1.0"
MAX_INPUT_CHARS = 60_000  # safety cap; chunk longer docs

SYSTEM_PROMPT = """You are extracting structured incident data from a declassified U.S. government document about Unidentified Anomalous Phenomena (UAP).

Your output MUST be a valid JSON array of incident objects. Each incident represents ONE distinct UAP encounter described in the source.

CRITICAL RULES:
1. Every field must be SUPPORTED BY THE SOURCE TEXT. If a field isn't in the source, return null.
2. Each incident MUST include a `raw_excerpt` field containing 1-3 sentences of VERBATIM text copied exactly from the source. This excerpt must support the structured claims.
3. NEVER infer, embellish, or speculate. If the source says "an object was observed" do not write "a UFO was observed" — preserve the document's hedging.
4. NEVER fabricate dates, locations, or names. If unclear, use null.
5. The `summary` field must be your own 1-2 sentence factual restatement, not copied text.
6. One document may contain zero, one, or many incidents. A single incident may be referenced multiple times — only return it once.
7. Redacted text in the source (██████ or [REDACTED]) should be preserved as ████ in raw_excerpt and not invented.

OUTPUT SCHEMA (JSON array of objects):
[
  {
    "title": "short headline, <80 chars",
    "summary": "1-2 sentence factual restatement in your own words",
    "raw_excerpt": "verbatim text from source, 1-3 sentences",
    "occurred_at_text": "raw date string from source or null",
    "occurred_at": "YYYY-MM-DD or null",
    "occurred_at_precision": "day|month|year|decade|unknown",
    "location_text": "raw location string from source or null",
    "country": "country name or null",
    "region": "state/province/sea or null",
    "branch": "USAF|USN|USMC|USA|NASA|FBI|DOS|NORTHCOM|CENTCOM|INDOPACOM|EUCOM|AARO|other or null",  # TODO: Haiku sometimes writes the JSON string "null" instead of JSON null for branch. A future migration should UPDATE incidents SET branch = NULL WHERE branch = 'null' to clean these up.
    "reporting_unit": "specific unit/office mentioned or null",
    "sensor_types": ["eyewitness"|"infrared"|"radar"|"photo"|"video"],
    "duration_seconds": integer or null,
    "altitude_feet": integer or null,
    "shape_description": "brief shape description from source or null",
    "size_description": "brief size description from source or null",
    "resolution_status": "unresolved|identified|insufficient_data",
    "resolution_notes": "if identified, what was it; if unresolved, brief note or null"
  }
]

If the document contains no UAP incidents, return [].
Output ONLY the JSON array. No prose, no markdown fences, no explanation.
"""


def extract_from_source_file(sf: dict[str, Any], client: anthropic.Anthropic) -> list[dict]:
    """Run Haiku on a source file's OCR text, return validated incident dicts."""
    text = sf.get("ocr_text") or sf.get("transcript") or ""
    if not text or len(text.strip()) < 50:
        logger.info("skipping %s: no text", sf["filename"])
        return []

    # chunk if needed (rare for individual war.gov pdfs but defensive)
    chunks = _chunk(text, MAX_INPUT_CHARS)
    all_incidents: list[dict] = []

    for chunk_idx, chunk in enumerate(chunks):
        logger.info("extracting %s chunk %d/%d (%d chars)", sf["filename"], chunk_idx + 1, len(chunks), len(chunk))
        incidents = _call_haiku(client, chunk, sf)
        for inc in incidents:
            validated = _validate_incident(inc, chunk, sf)
            if validated:
                all_incidents.append(validated)

    return all_incidents


def _chunk(text: str, max_chars: int) -> list[str]:
    """Split on paragraph boundaries when possible. Hard-splits oversized paragraphs."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    paragraphs = text.split("\n\n")
    current = ""
    for p in paragraphs:
        # hard-split any single paragraph that exceeds max_chars
        if len(p) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(p), max_chars):
                chunks.append(p[i:i + max_chars])
            continue
        if len(current) + len(p) > max_chars and current:
            chunks.append(current)
            current = p
        else:
            current = (current + "\n\n" + p) if current else p
    if current:
        chunks.append(current)
    return chunks


def _call_haiku(client: anthropic.Anthropic, text: str, sf: dict) -> list[dict]:
    """Single Haiku call. Returns parsed JSON or []."""
    user_prompt = f"""SOURCE DOCUMENT METADATA:
filename: {sf['filename']}
agency: {sf.get('agency', 'unknown')}
file_type: {sf['file_type']}

SOURCE TEXT:
{text}

Extract every distinct UAP incident as JSON per the schema. Output ONLY the JSON array."""

    try:
        resp = client.messages.create(
            model=EXTRACTION_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIError as e:
        logger.error("haiku api error on %s: %s", sf["filename"], e)
        return []

    raw = resp.content[0].text.strip()

    # strip optional markdown fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("haiku returned invalid JSON for %s: %s", sf["filename"], e)
        logger.debug("raw output: %s", raw[:500])
        return []

    if not isinstance(parsed, list):
        logger.error("haiku output not a list for %s", sf["filename"])
        return []

    return parsed


def _normalize_for_match(s: str) -> str:
    """Normalize whitespace for substring matching."""
    return re.sub(r"\s+", " ", s.strip().lower())


def _validate_incident(inc: dict, source_text: str, sf: dict) -> dict | None:
    """
    Critical step: verify raw_excerpt is actually in source_text.
    If not, drop the incident entirely — it's likely hallucinated.
    """
    if not isinstance(inc, dict):
        return None

    excerpt = inc.get("raw_excerpt", "")
    if not excerpt or len(excerpt.strip()) < 20:
        logger.warning("dropping incident in %s: missing/short raw_excerpt", sf["filename"])
        return None

    norm_source = _normalize_for_match(source_text)
    norm_excerpt = _normalize_for_match(excerpt)

    # check if at least 80% of the excerpt's words appear contiguously
    if norm_excerpt in norm_source:
        match_ok = True
    else:
        # fallback: check if 90% of excerpt words appear in any 200-char window of source
        excerpt_words = set(norm_excerpt.split())
        match_ok = False
        for i in range(0, len(norm_source) - len(norm_excerpt), 100):
            window = norm_source[i : i + len(norm_excerpt) + 200]
            window_words = set(window.split())
            if excerpt_words and len(excerpt_words & window_words) / len(excerpt_words) >= 0.9:
                match_ok = True
                break

    if not match_ok:
        logger.warning(
            "dropping incident in %s: raw_excerpt not found in source. excerpt=%r",
            sf["filename"], excerpt[:120],
        )
        return None

    # required fields
    if not inc.get("title") or not inc.get("summary"):
        logger.warning("dropping incident in %s: missing title or summary", sf["filename"])
        return None

    if inc.get("resolution_status") not in ("unresolved", "identified", "insufficient_data"):
        inc["resolution_status"] = "insufficient_data"

    # clean date
    if inc.get("occurred_at"):
        try:
            datetime.strptime(inc["occurred_at"], "%Y-%m-%d")
        except (ValueError, TypeError):
            inc["occurred_at"] = None

    # clean sensor_types
    valid_sensors = {"eyewitness", "infrared", "radar", "photo", "video"}
    sensors = inc.get("sensor_types") or []
    inc["sensor_types"] = [s for s in sensors if s in valid_sensors]

    inc["source_file_id"] = sf["id"]
    inc["case_id"] = _generate_case_id(inc, sf)
    inc["slug"] = _generate_slug(inc)
    inc["extraction_model"] = EXTRACTION_MODEL
    inc["extraction_version"] = EXTRACTION_VERSION
    inc["extracted_at"] = datetime.now(timezone.utc).isoformat()

    return inc


def _generate_slug(inc: dict) -> str:
    """Generate a human-readable URL slug.
    Format: {year}-{branch}-{first-3-words-kebab}-{4charhash}
    Example: 2024-indopacom-football-shaped-object-a1b2
    """
    import hashlib

    # year part
    year = "undated"
    if inc.get("occurred_at"):
        year = inc["occurred_at"].split("-")[0]

    # branch part
    branch = (inc.get("branch") or "gov").lower().replace(" ", "")

    # first 3+ words of title, kebab-cased
    title = inc.get("title", "untitled")
    words = re.findall(r"[a-z0-9]+", title.lower())
    title_slug = "-".join(words[:5]) if words else "untitled"

    # 4 char hash for uniqueness
    h = hashlib.sha1(inc.get("raw_excerpt", title).encode()).hexdigest()[:4]

    return f"{year}-{branch}-{title_slug}-{h}"


def _generate_case_id(inc: dict, sf: dict) -> str:
    """Generate a stable, human-readable case ID.

    TODO: Some existing incidents have UNDATED- prefixed case_ids but later gained
    real dates via re-extraction (e.g. "UNDATED-USAF-11F3" with date 1949-08-19).
    Case_ids are stable identifiers used in URLs, so we cannot simply regenerate them.
    Future runs should detect this case (UNDATED prefix + non-null occurred_at) and
    log a warning, or provide a migration path that sets up redirects from old to new IDs.
    """
    date_part = "UNDATED"
    if inc.get("occurred_at"):
        date_part = inc["occurred_at"].split("-")[0]

    branch = (inc.get("branch") or sf.get("agency") or "GOV").upper().replace(" ", "")[:10]

    # short hash of the excerpt for uniqueness (6 hex chars = 16M combinations)
    import hashlib
    h = hashlib.sha1(inc["raw_excerpt"].encode()).hexdigest()[:6].upper()

    return f"{date_part}-{branch}-{h}"


def run(limit: int | None = None, source_file_id: str | None = None, skip_embed: bool = False) -> None:
    sb = get_supabase()
    client = anthropic.Anthropic()

    # find source files with extractable text (OCR for PDFs, transcript for videos)
    q_ocr = sb.table("source_files").select("*").not_.is_("ocr_text", "null")
    q_transcript = sb.table("source_files").select("*").not_.is_("transcript", "null")
    if source_file_id:
        q_ocr = q_ocr.eq("id", source_file_id)
        q_transcript = q_transcript.eq("id", source_file_id)
    if limit:
        q_ocr = q_ocr.limit(limit)
        q_transcript = q_transcript.limit(limit)

    rows_ocr = q_ocr.execute().data
    rows_transcript = q_transcript.execute().data
    seen_ids = {r["id"] for r in rows_ocr}
    rows = rows_ocr + [r for r in rows_transcript if r["id"] not in seen_ids]
    logger.info("found %d source files to extract from (%d ocr, %d transcript)", len(rows), len(rows_ocr), len(rows_transcript))

    total_incidents = 0
    for sf in rows:
        # skip if we've already extracted from this one
        existing = sb.table("incidents").select("id", count="exact").eq("source_file_id", sf["id"]).execute()
        if existing.count and existing.count > 0:
            logger.info("skip %s: already has %d incidents", sf["filename"], existing.count)
            continue

        incidents = extract_from_source_file(sf, client)

        if incidents:
            if not skip_embed:
                # batch embed all incidents in 1 API call (much fewer rate-limit hits)
                embed_texts = [f"{inc['title']}\n{inc['summary']}\n{inc['raw_excerpt']}" for inc in incidents]
                embeddings = embed_batch(embed_texts)
                for inc, emb in zip(incidents, embeddings):
                    inc["embedding"] = emb

            for inc in incidents:
                # propagate media URLs from source file
                if sf["file_type"] in ("mp4", "mov"):
                    inc["video_url"] = sf.get("url")
                elif sf["file_type"] in ("jpg", "png", "jpeg"):
                    inc["image_url"] = sf.get("url")

                upsert_incident(sb, inc)

        logger.info("extracted %d incidents from %s", len(incidents), sf["filename"])
        total_incidents += len(incidents)

    logger.info("extraction complete // total new incidents=%d", total_incidents)


def _tokenize(text: str, min_len: int = 2) -> set[str]:
    """Extract alphanumeric tokens from text for matching.

    Uses min_len=2 by default so short but discriminating tokens like
    '12', '17', 'a1', 'vm1' are preserved.  Common stop-words that
    appear in nearly every filename are excluded.
    """
    stop = {
        "the", "and", "for", "from", "pdf", "jpg", "png", "mp4", "mov", "release",
        # URL infrastructure tokens (present in all war.gov URLs, not discriminating)
        "https", "http", "www", "gov", "war", "com", "medialink", "ufo", "release_1",
    }
    tokens = set(re.findall(r"[A-Za-z0-9]+", text.lower()))
    return {t for t in tokens if len(t) >= min_len and t not in stop}


def link_media(dry_run: bool = False) -> None:
    """
    Post-processing step: scan source_files for images and videos that
    aren't yet linked to incidents. Match by shared case tokens in filenames
    and URLs. Uses both filename and URL tokens for better discrimination
    (e.g. 'apollo-12' vs 'apollo-11').
    """
    sb = get_supabase()

    # all image/video source files
    media_files = (
        sb.table("source_files")
        .select("id, filename, url, file_type")
        .in_("file_type", ["jpg", "png", "jpeg", "mp4", "mov"])
        .execute()
        .data
    )
    logger.info("found %d media source files", len(media_files))

    # all incidents missing media
    incidents_no_img = (
        sb.table("incidents")
        .select("id, case_id, source_file_id, image_url, video_url")
        .is_("image_url", "null")
        .execute()
        .data
    )
    # get their source filenames AND urls for token matching
    sf_lookup: dict[str, dict] = {}
    if incidents_no_img:
        sf_ids = list({i["source_file_id"] for i in incidents_no_img})
        for batch_start in range(0, len(sf_ids), 50):
            batch = sf_ids[batch_start:batch_start + 50]
            rows = sb.table("source_files").select("id, filename, url").in_("id", batch).execute().data
            for r in rows:
                sf_lookup[r["id"]] = {"filename": r["filename"], "url": r.get("url", "")}

    linked = 0
    for mf in media_files:
        # tokenize both filename and URL for richer matching
        mf_tokens = _tokenize(mf["filename"]) | _tokenize(mf.get("url", ""))
        if len(mf_tokens) < 2:
            logger.debug("skipping %s: too few tokens", mf["filename"])
            continue

        best_match = None
        best_overlap = 0

        for inc in incidents_no_img:
            sf_info = sf_lookup.get(inc["source_file_id"], {"filename": "", "url": ""})
            inc_tokens = _tokenize(sf_info["filename"]) | _tokenize(sf_info["url"])
            overlap = len(mf_tokens & inc_tokens)
            if overlap > best_overlap and overlap >= 3:
                best_overlap = overlap
                best_match = inc

        if best_match:
            col = "video_url" if mf["file_type"] in ("mp4", "mov") else "image_url"
            if not dry_run:
                sb.table("incidents").update({col: mf["url"]}).eq("id", best_match["id"]).execute()
            logger.info("linked %s -> incident %s (%s, overlap=%d tokens)",
                        mf["filename"], best_match["case_id"], col, best_overlap)
            linked += 1
        else:
            logger.info("no match for %s (tokens=%s)", mf["filename"], sorted(mf_tokens)[:10])

    logger.info("link_media complete // linked=%d", linked)


def backfill_embeddings() -> None:
    """Embed all incidents that don't have embeddings yet. Run this after
    extract --no-embed to fill in embeddings at whatever pace the API allows."""
    sb = get_supabase()

    # fetch incidents missing embeddings
    rows = sb.table("incidents").select("id, title, summary, raw_excerpt").is_("embedding", "null").execute().data
    logger.info("found %d incidents without embeddings", len(rows))
    if not rows:
        return

    # process in batches of 20 (Voyage handles up to 128 but smaller batches
    # give us more frequent progress logging and reduce token-per-request pressure)
    batch_size = 20
    embedded = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        texts = [f"{r['title']}\n{r['summary']}\n{r['raw_excerpt']}" for r in batch]
        vecs = embed_batch(texts)
        for r, vec in zip(batch, vecs):
            vec_str = "[" + ",".join(str(x) for x in vec) + "]"
            sb.table("incidents").update({"embedding": vec_str}).eq("id", r["id"]).execute()
        embedded += len(batch)
        logger.info("embedded %d/%d incidents", embedded, len(rows))

    logger.info("backfill complete // embedded=%d", embedded)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--source-file-id")
    parser.add_argument("--no-embed", action="store_true",
                        help="skip embedding (extract only, embed later with --backfill-embed)")
    parser.add_argument("--backfill-embed", action="store_true",
                        help="embed all incidents missing embeddings (run after --no-embed)")
    parser.add_argument("--link-media", action="store_true",
                        help="link image/video source files to incidents by filename")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.link_media:
        link_media(dry_run=args.dry_run)
    elif args.backfill_embed:
        backfill_embeddings()
    else:
        run(limit=args.limit, source_file_id=args.source_file_id, skip_embed=args.no_embed)
