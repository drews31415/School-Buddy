"""
BeautifulSoup 기반 공지사항 파싱 모듈.

한국 학교 홈페이지는 표준화된 HTML 구조가 없어
다단계 셀렉터 전략(폭포식)을 사용한다.
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .fetcher import to_absolute_url
from .models import RawNotice

logger = logging.getLogger(__name__)

# ── 공지 목록 후보 셀렉터 (우선순위 순) ────────────────────
# 한국 학교 홈페이지에서 자주 쓰이는 구조 패턴
_LIST_SELECTORS = [
    # 일반적인 게시판 테이블 (neis, 학교알리미 공통)
    "table.board-list tbody tr",
    "table.bbs-list tbody tr",
    "table.list tbody tr",
    "table tbody tr",
    # div/ul 기반 목록
    "ul.board-list li",
    "ul.notice-list li",
    "div.board-list-wrap .item",
    "div.list-wrap .list-item",
    # 일반 목록
    "article",
]

_DATE_PATTERN = re.compile(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}")


def parse_notices(html: str, base_url: str) -> List[RawNotice]:
    """
    HTML에서 공지사항 목록 추출.

    :param html:     학교 공지 목록 페이지 HTML
    :param base_url: 상대 URL → 절대 URL 변환에 사용
    :returns:        RawNotice 리스트 (최대 50건)
    """
    soup = BeautifulSoup(html, "lxml")
    notices: List[RawNotice] = []

    rows = _find_notice_rows(soup)
    if not rows:
        logger.warning("No notice rows found for base_url=%s", base_url)
        return []

    for row in rows[:50]:  # 1회 크롤링 최대 50건
        notice = _extract_notice(row, base_url)
        if notice:
            notices.append(notice)

    logger.info("Parsed %d notices from %s", len(notices), base_url)
    return notices


def _find_notice_rows(soup: BeautifulSoup) -> List[Tag]:
    """우선순위 셀렉터 순서대로 시도, 첫 번째 결과 반환."""
    for selector in _LIST_SELECTORS:
        rows = soup.select(selector)
        if len(rows) >= 2:  # 2건 이상 있어야 실제 목록으로 판단
            return rows
    # 폴백: 모든 <tr> 중 링크가 있는 것
    return [
        tr for tr in soup.find_all("tr")
        if tr.find("a", href=True)
    ]


def _extract_notice(row: Tag, base_url: str) -> Optional[RawNotice]:
    """단일 행(row/item)에서 공지 정보 추출."""
    anchor = row.find("a", href=True)
    if not anchor:
        return None

    title = _clean_text(anchor.get_text())
    if not title or len(title) < 2:
        return None

    href = anchor.get("href", "")
    url = to_absolute_url(base_url, str(href))
    if not url:
        return None

    # 날짜 추출 시도
    published_at = _extract_date(row)

    return RawNotice(title=title, url=url, published_at=published_at)


def _extract_date(row: Tag) -> Optional[str]:
    """행 텍스트에서 날짜 패턴 추출. 못 찾으면 None."""
    text = row.get_text()
    m = _DATE_PATTERN.search(text)
    if not m:
        return None
    raw = m.group()
    # 구분자 통일 → YYYY-MM-DD
    normalized = re.sub(r"[./]", "-", raw)
    parts = normalized.split("-")
    if len(parts) == 3:
        y, mo, d = parts
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    return None


def _clean_text(text: str) -> str:
    """불필요한 공백·특수문자 제거."""
    return re.sub(r"\s+", " ", text).strip()
