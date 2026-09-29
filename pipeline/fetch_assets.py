"""
Download official assets for source_records.

Usage:
  python -m pipeline.fetch_assets --provider pursue --release 2 --dry-run
  python -m pipeline.fetch_assets --provider pursue --release 2 --type pdf --limit 5
  python -m pipeline.fetch_assets --provider pursue --release 2 --type pdf --limit 5 --apply
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import mimetypes
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pipeline.db import get_supabase, upsert_source_file_safe
from pipeline.sources.http import OfficialSourceClient
from pipeline.storage import upload_to_storage

logger = logging.getLogger(__name__)

CACHE_DIR = Path("./.cache/files")
LOG_DIR = Path(__file__).parent / "logs"
BUCKET = "source-files"

MIME_BY_TYPE = {
    "pdf": "application/pdf",
    "image": "image/jpeg",
    "video": "video/mp4",
    "audio": "audio/mp4",
}

EXT_BY_TYPE = {
    "pdf": ".pdf",
    "image": ".jpg",
    "video": ".mp4",
    "audio": ".mp4",
}


def _load_env() -> None:
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _append_log(name: str, line: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with (LOG_DIR / name).open("a") as f:
        f.write(line.rstrip() + "\n")


def _guess_mime(data: bytes, source_type: str, content_type: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct and ct not in ("application/octet-stream", "binary/octet-stream"):
        return ct
    if data[:4] == b"%PDF":
        return "application/pdf"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return MIME_BY_TYPE.get(source_type, "application/octet-stream")


def _validate_mime(source_type: str, mime: str) -> bool:
    mime = mime.lower()
    if source_type == "pdf":
        return "pdf" in mime
    if source_type == "image":
        return mime.startswith("image/")
    if source_type == "video":
        return mime.startswith("video/") or mime in ("application/mp4",)
    if source_type == "audio":
        return mime.startswith("audio/") or mime in ("application/mp4", "video/mp4")
    return True


def fetch_due_records(
    sb,
    *,
    provider: str,
    release: int | None,
    source_type: str | None,
    limit: int | None,
):
    q = sb.table("source_records").select("*").eq("provider", provider).eq("status", "active")
    if release is not None:
        q = q.eq("release_number", release)
    if source_type:
        q = q.eq("source_type", source_type)
    q = q.order("release_number").order("external_id")
    if limit:
        q = q.limit(limit)
    return q.execute().data or []


def process_one(
    sb,
    client: OfficialSourceClient,
    rec: dict,
    *,
    dry_run: bool,
    skip_existing: bool = True,
) -> str:
    """Returns status: skipped|dry-run|downloaded|error"""
    url = rec.get("download_url") or rec.get("original_url")
    if not url:
        _append_log("errors.log", f"{datetime.now(timezone.utc).isoformat()} NO_URL {rec.get('identity_key')}")
        return "error_no_url"

    # skip if already linked source_file with matching sha
    existing_sf = (
        sb.table("source_files")
        .select("id,sha256,url")
        .eq("url", url)
        .limit(1)
        .execute()
        .data
    )
    if skip_existing and existing_sf and existing_sf[0].get("sha256"):
        # ensure link
        if not dry_run:
            sb.table("source_files").update(
                {"source_record_id": rec["id"]}
            ).eq("id", existing_sf[0]["id"]).execute()
            sb.table("source_records").update(
                {
                    "sha256": existing_sf[0]["sha256"],
                    "downloaded_at": datetime.now(timezone.utc).isoformat(),
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", rec["id"]).execute()
        return "skipped_existing"

    if dry_run:
        logger.info("[dry-run] would fetch %s %s", rec.get("source_type"), url[:100])
        return "dry-run"

    try:
        body, meta = client.get_bytes(url)
    except Exception as e:
        _append_log(
            "errors.log",
            f"{datetime.now(timezone.utc).isoformat()} FETCH_FAIL {rec.get('identity_key')} {url} {e}",
        )
        return "error_fetch"

    digest = hashlib.sha256(body).hexdigest()
    mime = _guess_mime(body, rec.get("source_type") or "other", meta.get("content_type") or "")
    if not _validate_mime(rec.get("source_type") or "other", mime):
        _append_log(
            "errors.log",
            f"{datetime.now(timezone.utc).isoformat()} MIME_FAIL {rec.get('identity_key')} got={mime}",
        )
        return "error_mime"

    ext = EXT_BY_TYPE.get(rec.get("source_type") or "", "") or (
        mimetypes.guess_extension(mime) or ".bin"
    )
    safe_name = (rec.get("external_id") or rec.get("identity_key") or "asset").replace("/", "_")
    rel_path = f"pursue/r{rec.get('release_number') or 0}/{safe_name}{ext}"

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    final_path = CACHE_DIR / rel_path
    final_path.parent.mkdir(parents=True, exist_ok=True)

    # atomic write
    with tempfile.NamedTemporaryFile(dir=final_path.parent, delete=False) as tmp:
        tmp.write(body)
        tmp_path = Path(tmp.name)
    tmp_path.replace(final_path)

    storage_path = None
    try:
        storage_path = upload_to_storage(
            bucket=BUCKET, path=rel_path, data=body, content_type=mime
        )
    except Exception as e:
        # Large PDFs may exceed Supabase Storage object limits; keep local cache + DB row.
        logger.warning(
            "storage upload failed for %s (%s); keeping local cache at %s",
            rec.get("identity_key"),
            e,
            final_path,
        )
        _append_log(
            "errors.log",
            f"{datetime.now(timezone.utc).isoformat()} STORAGE_FAIL "
            f"{rec.get('identity_key')} {e}",
        )
        storage_path = f"local:{final_path}"

    file_type = {
        "pdf": "pdf",
        "image": "jpg" if "jpeg" in mime or mime.endswith("/jpg") else "png",
        "video": "mp4",
        "audio": "mp4",
    }.get(rec.get("source_type") or "", "bin")

    row = {
        "url": url,
        "filename": final_path.name,
        "file_type": file_type,
        "agency": rec.get("agency_raw") or rec.get("agency"),
        "sha256": digest,
        "storage_path": storage_path,
        "byte_size": len(body),
        "source_record_id": rec["id"],
    }
    inserted = upsert_source_file_safe(sb, **row)
    if inserted is None:
        # url existed — update link/checksum
        sb.table("source_files").update(
            {
                "sha256": digest,
                "storage_path": storage_path,
                "byte_size": len(body),
                "source_record_id": rec["id"],
            }
        ).eq("url", url).execute()

    sb.table("source_records").update(
        {
            "sha256": digest,
            "byte_size": len(body),
            "mime_type": mime,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", rec["id"]).execute()

    _append_log(
        "fetch.log",
        f"{datetime.now(timezone.utc).isoformat()} OK {rec.get('identity_key')} "
        f"status={meta.get('status')} bytes={len(body)} sha256={digest} "
        f"impersonation={meta.get('used_impersonation')}",
    )
    return "downloaded"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch official PURSUE assets")
    parser.add_argument("--provider", default="pursue")
    parser.add_argument("--release", type=int)
    parser.add_argument("--type", dest="source_type", choices=["pdf", "image", "video", "audio"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    if args.apply:
        args.dry_run = False

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    _load_env()

    sb = get_supabase()
    client = OfficialSourceClient()
    records = fetch_due_records(
        sb,
        provider=args.provider,
        release=args.release,
        source_type=args.source_type,
        limit=args.limit,
    )
    print(f"candidates: {len(records)} (dry_run={args.dry_run})")

    counts: dict[str, int] = {}
    for rec in records:
        status = process_one(sb, client, rec, dry_run=args.dry_run)
        counts[status] = counts.get(status, 0) + 1

    print(json_dumps(counts))
    return 0


def json_dumps(obj) -> str:
    import json

    return json.dumps(obj, indent=2)


if __name__ == "__main__":
    sys.exit(main())
