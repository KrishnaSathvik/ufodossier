"""
HTTP client for official government sources.

Tries normal httpx first; on Akamai/403 falls back to curl_cffi Chrome TLS.
"""

from __future__ import annotations

import logging
import time
from typing import Callable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

USER_AGENT = "ufodossier-bot/2.0 (+https://ufodossier.com/about)"

Retryable = (429, 500, 502, 503, 504)


class OfficialSourceClient:
    def __init__(
        self,
        *,
        timeout: float = 120.0,
        max_retries: int = 5,
        polite_delay: float = 1.5,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.polite_delay = polite_delay
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.polite_delay:
            time.sleep(self.polite_delay - elapsed)
        self._last_request_at = time.monotonic()

    def get_bytes(self, url: str) -> tuple[bytes, dict]:
        """
        Returns (body, meta) where meta includes status, content_type, used_impersonation.
        """
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                body, meta = self._attempt(url, force_cffi=False)
                if meta["status"] == 403 and self._is_akamai_host(url):
                    logger.warning("HTTP 403 for %s — retrying with curl_cffi", url)
                    body, meta = self._attempt(url, force_cffi=True)
                if meta["status"] in Retryable:
                    raise RuntimeError(f"retryable HTTP {meta['status']} for {url}")
                if meta["status"] >= 400:
                    raise RuntimeError(f"HTTP {meta['status']} for {url}")
                return body, meta
            except Exception as e:
                last_err = e
                wait = min(30.0, (2 ** attempt) * 2.0)
                logger.warning(
                    "fetch attempt %d/%d failed for %s: %s; sleep %.1fs",
                    attempt + 1,
                    self.max_retries + 1,
                    url,
                    e,
                    wait,
                )
                if attempt < self.max_retries:
                    time.sleep(wait)
        assert last_err is not None
        raise last_err

    def _is_akamai_host(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return any(h in host for h in ("war.gov", "defense.gov", "aaro.mil"))

    def _attempt(self, url: str, *, force_cffi: bool) -> tuple[bytes, dict]:
        use_cffi = force_cffi or self._is_akamai_host(url)
        if use_cffi:
            return self._cffi_get(url)
        return self._httpx_get(url)

    def _httpx_get(self, url: str) -> tuple[bytes, dict]:
        import httpx

        with httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:
            r = client.get(url)
            return r.content, {
                "status": r.status_code,
                "content_type": r.headers.get("content-type", ""),
                "used_impersonation": False,
                "etag": r.headers.get("etag"),
                "last_modified": r.headers.get("last-modified"),
            }

    def _cffi_get(self, url: str) -> tuple[bytes, dict]:
        try:
            from curl_cffi import requests as cffi_requests
        except ImportError as e:
            raise RuntimeError(
                "curl_cffi required for war.gov fetches. "
                "Install with: pip install curl_cffi"
            ) from e

        # Do NOT override User-Agent when impersonating — mismatched UA breaks
        # Akamai TLS fingerprint checks.
        r = cffi_requests.get(
            url,
            impersonate="chrome",
            timeout=self.timeout,
            headers={
                "Referer": "https://www.war.gov/UFO/",
                "Accept": "*/*",
            },
            allow_redirects=True,
        )
        return r.content, {
            "status": r.status_code,
            "content_type": r.headers.get("content-type", ""),
            "used_impersonation": True,
            "etag": r.headers.get("etag"),
            "last_modified": r.headers.get("last-modified"),
        }


_default_client: OfficialSourceClient | None = None


def get_client() -> OfficialSourceClient:
    global _default_client
    if _default_client is None:
        _default_client = OfficialSourceClient()
    return _default_client


def fetch_bytes(url: str) -> bytes:
    body, _meta = get_client().get_bytes(url)
    return body
