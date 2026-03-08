"""
crawler/parser.py 및 crawler/models.py 단위 테스트.
HTTP 의존성 없이 순수 HTML 파싱 로직만 검증한다.
"""
import os
from pathlib import Path

import pytest

from crawler.parser import parse_notices, _extract_date, _clean_text
from crawler.models import RawNotice, SQSNoticePayload

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
BASE_URL = "https://school.example.com/notice"


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


# ── parse_notices ────────────────────────────────────────────

class TestParseNotices:
    def test_normal_html_returns_notices(self):
        html = _load_fixture("normal.html")
        notices = parse_notices(html, BASE_URL)

        assert len(notices) == 3
        assert all(isinstance(n, RawNotice) for n in notices)

    def test_normal_html_titles_are_correct(self):
        html = _load_fixture("normal.html")
        notices = parse_notices(html, BASE_URL)

        titles = [n.title for n in notices]
        assert "10월 현장학습 안내" in titles
        assert "2학기 학사 일정 안내" in titles

    def test_normal_html_urls_are_absolute(self):
        html = _load_fixture("normal.html")
        notices = parse_notices(html, BASE_URL)

        for notice in notices:
            assert notice.url.startswith("https://"), f"절대 URL이 아님: {notice.url}"

    def test_normal_html_dates_extracted(self):
        html = _load_fixture("normal.html")
        notices = parse_notices(html, BASE_URL)

        dated = [n for n in notices if n.published_at is not None]
        assert len(dated) == 3
        # 날짜 형식 YYYY-MM-DD 확인
        for n in dated:
            parts = n.published_at.split("-")
            assert len(parts) == 3
            assert len(parts[0]) == 4  # YYYY

    def test_changed_structure_returns_empty_list(self):
        """파서가 인식 못하는 구조 → 빈 리스트 (E-03, 예외 없음)."""
        html = _load_fixture("changed_structure.html")
        notices = parse_notices(html, BASE_URL)
        assert notices == []

    def test_empty_html_returns_empty_list(self):
        notices = parse_notices("<html><body></body></html>", BASE_URL)
        assert notices == []

    def test_max_50_notices_returned(self):
        """최대 50건 제한 확인."""
        # 60개 행을 가진 HTML 생성
        rows = "\n".join(
            f'<tr><td><a href="/notice/{i}">공지 {i:02d}번</a></td><td>2025-10-{(i%28)+1:02d}</td></tr>'
            for i in range(1, 61)
        )
        html = f"<table class='board-list'><tbody>{rows}</tbody></table>"
        notices = parse_notices(html, BASE_URL)
        assert len(notices) <= 50

    def test_javascript_href_is_skipped(self):
        """javascript: href는 절대 URL 변환 실패로 건너뜀 (E-04)."""
        html = """
        <table class='board-list'><tbody>
          <tr><td><a href="javascript:void(0)">클릭불가</a></td></tr>
          <tr><td><a href="/notice/1">정상 공지</a></td></tr>
          <tr><td><a href="/notice/2">정상 공지 2</a></td></tr>
        </tbody></table>
        """
        notices = parse_notices(html, BASE_URL)
        assert all("javascript" not in n.url for n in notices)


# ── _extract_date ────────────────────────────────────────────

class TestExtractDate:
    @pytest.mark.parametrize("raw, expected", [
        ("2025-10-01", "2025-10-01"),
        ("2025.10.1", "2025-10-01"),
        ("2025/9/5", "2025-09-05"),
        ("등록일: 2025-03-01 공지", "2025-03-01"),
    ])
    def test_date_formats(self, raw, expected):
        from bs4 import BeautifulSoup
        row = BeautifulSoup(f"<tr><td>{raw}</td></tr>", "lxml").find("tr")
        from crawler.parser import _extract_date
        assert _extract_date(row) == expected

    def test_no_date_returns_none(self):
        from bs4 import BeautifulSoup
        row = BeautifulSoup("<tr><td>날짜 없음</td></tr>", "lxml").find("tr")
        from crawler.parser import _extract_date
        assert _extract_date(row) is None


# ── _clean_text ───────────────────────────────────────────────

class TestCleanText:
    def test_collapses_whitespace(self):
        from crawler.parser import _clean_text
        assert _clean_text("  공지   제목  ") == "공지 제목"

    def test_removes_newlines(self):
        from crawler.parser import _clean_text
        assert _clean_text("공지\n제목\n안내") == "공지 제목 안내"

    def test_empty_string(self):
        from crawler.parser import _clean_text
        assert _clean_text("") == ""


# ── SQSNoticePayload.to_dict ──────────────────────────────────

class TestSQSNoticePayload:
    def test_to_dict_contains_all_fields(self):
        payload = SQSNoticePayload(
            noticeId="uuid-1234",
            schoolId="school-001",
            title="공지 제목",
            sourceUrl="https://school.example.com/notice/1",
            originalText="",
            publishedAt="2025-10-01T00:00:00+00:00",
            crawledAt="2025-10-01T03:00:00+00:00",
        )
        d = payload.to_dict()

        assert d["noticeId"] == "uuid-1234"
        assert d["schoolId"] == "school-001"
        assert d["sourceUrl"] == "https://school.example.com/notice/1"
        assert d["originalText"] == ""
        assert set(d.keys()) == {
            "noticeId", "schoolId", "title", "sourceUrl",
            "originalText", "publishedAt", "crawledAt",
        }
