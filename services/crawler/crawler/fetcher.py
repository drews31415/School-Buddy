"""
학교 홈페이지 HTTP 요청 모듈.
"""
from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# ── HTTP 세션 (모듈 레벨) ─────────────────────────────────
_TIMEOUT = (5, 15)       # (connect_timeout, read_timeout) 초
_MAX_RETRIES = 2

_session = requests.Session()
_retry = Retry(
    total=_MAX_RETRIES,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False,
)
_session.mount("https://", HTTPAdapter(max_retries=_retry))
_session.mount("http://", HTTPAdapter(max_retries=_retry))
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (compatible; SchoolBuddyBot/1.0; "
        "+https://schoolbuddy.kr/bot)"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
})


class FetchError(Exception):
    """HTTP 요청 실패."""


def fetch_html(url: str) -> str:
    """
    URL에서 HTML 본문 반환.
    :raises FetchError: HTTP 오류, 타임아웃, 인코딩 오류 등
    """
    try:
        resp = _session.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        # 한국 사이트는 EUC-KR 인코딩인 경우가 많음
        if resp.encoding and resp.encoding.lower() in ("euc-kr", "cp949"):
            return resp.content.decode("euc-kr", errors="replace")
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except requests.exceptions.Timeout as e:
        raise FetchError(f"Timeout fetching {url}") from e
    except requests.exceptions.HTTPError as e:
        raise FetchError(f"HTTP {e.response.status_code} for {url}") from e
    except requests.exceptions.RequestException as e:
        raise FetchError(f"Request failed for {url}: {e}") from e


def to_absolute_url(base_url: str, href: str) -> Optional[str]:
    """상대 URL을 절대 URL로 변환. 유효하지 않으면 None 반환."""
    if not href or href.startswith(("javascript:", "mailto:", "#")):
        return None
    abs_url = urljoin(base_url, href.strip())
    parsed = urlparse(abs_url)
    return abs_url if parsed.scheme in ("http", "https") else None
