"""ufodossier // db helpers (supabase client wrappers)"""
from __future__ import annotations

import os
from datetime import datetime
from functools import lru_cache

from supabase import Client, create_client


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]  # service role for pipeline
    return create_client(url, key)


def upsert_release(sb: Client, *, tranche_number: int, captured_at: datetime) -> dict:
    existing = sb.table("releases").select("*").eq("tranche_number", tranche_number).execute()
    if existing.data:
        return existing.data[0]
    r = sb.table("releases").insert({
        "tranche_number": tranche_number,
        "captured_at": captured_at.isoformat(),
    }).execute()
    return r.data[0]


def upsert_source_file(sb: Client, **kwargs) -> dict:
    r = sb.table("source_files").insert(kwargs).execute()
    return r.data[0]


def upsert_source_file_safe(sb: Client, **kwargs) -> dict | None:
    """Insert a source_file row, skipping if url already exists."""
    url = kwargs.get("url")
    if url:
        existing = sb.table("source_files").select("id").eq("url", url).execute()
        if existing.data:
            return None
    return upsert_source_file(sb, **kwargs)


def upsert_incident(sb: Client, incident: dict) -> dict:
    import logging
    logger = logging.getLogger(__name__)
    # supabase client doesn't accept embedding as python list directly in some setups;
    # cast to string with brackets which postgres parses for vector type
    payload = dict(incident)
    if isinstance(payload.get("embedding"), list):
        payload["embedding"] = "[" + ",".join(str(x) for x in payload["embedding"]) + "]"
    try:
        r = sb.table("incidents").insert(payload).execute()
        return r.data[0]
    except Exception as e:
        if "23505" in str(e) and "case_id" in str(e):
            # case_id hash collision — extend with more hash chars and retry
            import hashlib
            h = hashlib.sha1(payload.get("raw_excerpt", "").encode()).hexdigest()[:8].upper()
            new_id = payload["case_id"] + "-" + h[4:]
            logger.warning("case_id collision %s, retrying as %s", payload["case_id"], new_id)
            payload["case_id"] = new_id
            r = sb.table("incidents").insert(payload).execute()
            return r.data[0]
        raise
