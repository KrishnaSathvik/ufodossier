"""ufodossier // supabase storage helpers"""
from __future__ import annotations

from pipeline.db import get_supabase


def upload_to_storage(*, bucket: str, path: str, data: bytes, content_type: str) -> str:
    sb = get_supabase()
    sb.storage.from_(bucket).upload(
        path=path,
        file=data,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    return path


def download_from_storage(bucket: str, path: str) -> bytes:
    sb = get_supabase()
    return sb.storage.from_(bucket).download(path)
