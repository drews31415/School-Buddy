"""
시나리오 2: 문서 분석 API
목표 SLA: 응답 10초 이내

테스트 흐름:
1. tests/fixtures/sample_notice.jpg 로 POST /documents/analyze
2. summary, checklistItems, dates, translation 필드 존재 확인
3. 번역 언어 일치 확인 (langdetect 사용)
"""
import os
from typing import Any

import pytest

from tests.e2e.config import SLA_DOCUMENT_ANALYSIS_SEC
from tests.e2e.utils.api import APIClient


# langdetect 없으면 언어 검증 스킵
try:
    from langdetect import detect as _lang_detect
    _LANGDETECT_AVAILABLE = True
except ImportError:
    _LANGDETECT_AVAILABLE = False

# 요청에 사용할 테스트 언어 코드
_TEST_LANG = os.environ.get("E2E_TEST_LANG", "vi")

# langdetect 코드 → ISO 639-1 매핑 (주요 지원 언어만)
_LANGDETECT_MAP = {
    "vi":    "vi",
    "zh-CN": "zh-cn",
    "en":    "en",
    "ja":    "ja",
    "th":    "th",
}


class TestDocumentAnalysis:
    """문서 분석 API E2E 시나리오."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_api(self, api: APIClient):
        """API URL이 없으면 전체 클래스 스킵."""
        if not api.base_url:
            pytest.skip("E2E_API_BASE_URL 미설정")

    # ── 정상 케이스 ───────────────────────────────────────────────────────────
    def test_analyze_jpg_returns_200(self, api: APIClient, sample_notice_jpg: bytes):
        """JPG 업로드 시 200 응답을 반환한다."""
        resp, _ = api.post_multipart(
            "/documents/analyze",
            files={"file": ("sample_notice.jpg", sample_notice_jpg, "image/jpeg")},
            data={"langCode": _TEST_LANG},
        )
        assert resp.status_code == 200, (
            f"HTTP 200 예상, 실제: {resp.status_code}\n{resp.text[:500]}"
        )

    def test_analyze_response_has_required_fields(
        self, api: APIClient, sample_notice_jpg: bytes
    ):
        """
        응답 JSON에 summary, checklistItems, translation 필드가 존재한다.
        (CLAUDE.md QA 기준 §1)
        """
        resp, _ = api.post_multipart(
            "/documents/analyze",
            files={"file": ("sample_notice.jpg", sample_notice_jpg, "image/jpeg")},
            data={"langCode": _TEST_LANG},
        )
        assert resp.status_code == 200
        body: dict[str, Any] = resp.json()
        data = body.get("data", body)  # {data: {...}} 또는 직접 {...}

        required_fields = ("summary", "checklistItems", "translation")
        for field in required_fields:
            assert field in data, f"필수 필드 누락: '{field}'\n응답: {data}"
            assert data[field] is not None, f"'{field}' 필드가 null입니다."

    def test_summary_meets_minimum_length(
        self, api: APIClient, sample_notice_jpg: bytes
    ):
        """summary는 20자 이상이어야 한다 (CLAUDE.md QA 기준 §3)."""
        resp, _ = api.post_multipart(
            "/documents/analyze",
            files={"file": ("sample_notice.jpg", sample_notice_jpg, "image/jpeg")},
            data={"langCode": _TEST_LANG},
        )
        data = resp.json().get("data", resp.json())
        summary = data.get("summary", "")
        assert len(summary) >= 20, (
            f"summary 최소 길이(20자) 미달: {len(summary)}자\n'{summary}'"
        )

    def test_checklist_items_is_list(
        self, api: APIClient, sample_notice_jpg: bytes
    ):
        """checklistItems는 리스트 타입이어야 한다."""
        resp, _ = api.post_multipart(
            "/documents/analyze",
            files={"file": ("sample_notice.jpg", sample_notice_jpg, "image/jpeg")},
            data={"langCode": _TEST_LANG},
        )
        data = resp.json().get("data", resp.json())
        assert isinstance(data.get("checklistItems"), list), (
            f"checklistItems가 list가 아님: {type(data.get('checklistItems'))}"
        )

    @pytest.mark.skipif(
        not _LANGDETECT_AVAILABLE,
        reason="langdetect 미설치 — pip install langdetect",
    )
    def test_translation_language_matches_requested(
        self, api: APIClient, sample_notice_jpg: bytes
    ):
        """
        translation 필드의 언어가 요청한 langCode와 일치한다.
        (CLAUDE.md QA 기준 §2)
        """
        resp, _ = api.post_multipart(
            "/documents/analyze",
            files={"file": ("sample_notice.jpg", sample_notice_jpg, "image/jpeg")},
            data={"langCode": _TEST_LANG},
        )
        data = resp.json().get("data", resp.json())
        translation: str = data.get("translation", "")

        if len(translation) < 20:
            pytest.skip("translation이 너무 짧아 언어 감지 불가")

        detected = _lang_detect(translation)
        expected = _LANGDETECT_MAP.get(_TEST_LANG, _TEST_LANG)

        # langdetect는 확률적이므로 zh 계열은 prefix 비교
        if expected.startswith("zh"):
            assert detected.startswith("zh"), (
                f"언어 불일치 — 기대: zh*, 감지: {detected}"
            )
        else:
            assert detected == expected, (
                f"언어 불일치 — 기대: {expected}, 감지: {detected}\n"
                f"번역 텍스트 앞 50자: '{translation[:50]}'"
            )

    def test_no_refusal_phrases_in_response(
        self, api: APIClient, sample_notice_jpg: bytes
    ):
        """응답에 거절 문구가 없어야 한다 (CLAUDE.md QA 기준 §5)."""
        resp, _ = api.post_multipart(
            "/documents/analyze",
            files={"file": ("sample_notice.jpg", sample_notice_jpg, "image/jpeg")},
            data={"langCode": _TEST_LANG},
        )
        data  = resp.json().get("data", resp.json())
        text  = " ".join([
            str(data.get("summary", "")),
            str(data.get("translation", "")),
        ])
        forbidden = [
            "I cannot", "I'm unable", "I am unable",
            "저는 할 수 없습니다", "분석할 수 없습니다",
        ]
        for phrase in forbidden:
            assert phrase not in text, f"거절 문구 감지: '{phrase}'"

    # ── SLA 검증 ──────────────────────────────────────────────────────────────
    def test_response_time_within_sla(
        self, api: APIClient, sample_notice_jpg: bytes
    ):
        """
        문서 분석 API 응답 시간이 SLA_DOCUMENT_ANALYSIS_SEC(10초) 이내여야 한다.
        """
        resp, elapsed = api.post_multipart(
            "/documents/analyze",
            files={"file": ("sample_notice.jpg", sample_notice_jpg, "image/jpeg")},
            data={"langCode": _TEST_LANG},
        )
        assert resp.status_code == 200
        assert elapsed <= SLA_DOCUMENT_ANALYSIS_SEC, (
            f"[SLA 위반] 문서 분석 응답 시간: {elapsed:.2f}초 "
            f"(SLA: {SLA_DOCUMENT_ANALYSIS_SEC}초)"
        )
        print(f"\n✅ 문서 분석 응답 시간: {elapsed:.2f}초 (SLA: {SLA_DOCUMENT_ANALYSIS_SEC}초)")

    # ── 엣지 케이스 ───────────────────────────────────────────────────────────
    def test_empty_file_returns_4xx(self, api: APIClient):
        """빈 파일 업로드 시 4xx 에러를 반환한다."""
        resp, _ = api.post_multipart(
            "/documents/analyze",
            files={"file": ("empty.jpg", b"", "image/jpeg")},
            data={"langCode": _TEST_LANG},
        )
        assert 400 <= resp.status_code < 500, (
            f"빈 파일에 4xx 예상, 실제: {resp.status_code}"
        )

    def test_unsupported_file_type_returns_400(self, api: APIClient):
        """지원하지 않는 파일 형식(.txt) 업로드 시 400을 반환한다."""
        resp, _ = api.post_multipart(
            "/documents/analyze",
            files={"file": ("test.txt", b"hello world", "text/plain")},
            data={"langCode": _TEST_LANG},
        )
        assert resp.status_code == 400, (
            f"지원하지 않는 형식에 400 예상, 실제: {resp.status_code}"
        )
        body = resp.json()
        assert "error" in body or "code" in body, "에러 응답 형식 불일치"

    def test_oversized_file_returns_413(self, api: APIClient):
        """10MB 초과 파일 업로드 시 413을 반환한다."""
        big_file = b"A" * (11 * 1024 * 1024)  # 11MB
        resp, _ = api.post_multipart(
            "/documents/analyze",
            files={"file": ("big.jpg", big_file, "image/jpeg")},
            data={"langCode": _TEST_LANG},
        )
        assert resp.status_code in (413, 400), (
            f"10MB 초과 파일에 413/400 예상, 실제: {resp.status_code}"
        )
