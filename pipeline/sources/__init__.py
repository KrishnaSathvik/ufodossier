"""Provider package for UFO Dossier v2 source registry."""

from .base import SourceRecord, DiffClass, identity_key, file_sha256
from . import pursue

__all__ = [
    "SourceRecord",
    "DiffClass",
    "identity_key",
    "file_sha256",
    "pursue",
]
