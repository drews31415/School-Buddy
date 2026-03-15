"""
analyzer 서브모듈 단위 테스트 (models, storage, ocr, ai)
"""
import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import BUCKET_NAME, MINIMAL_PDF_BYTES, make_event


# ── models.py ─────────────────────────────────────────────────────────────

class TestModels:
    def test_analyze_result_to_dict(self):
        from analyzer.models import AnalyzeResult, ScheduleItem

        r = AnalyzeResult(
            summary="요약",
            materials=["도시락"],
            schedule=[ScheduleItem(date="2025-10-15", description="현장학습")],
            importance="HIGH",
        )
        d = r.to_dict()
        assert d["summary"] == "요약"
        assert d["materials"] == ["도시락"]
        assert d["schedule"][0]["date"] == "2025-10-15"
        assert d["importance"] == "HIGH"

    def test_translated_result_to_dict(self):
        from analyzer.models import TranslatedResult

        r = TranslatedResult(
            translation="번역 결과",
            culturalTip="문화 설명",
            checklistItems=["항목1", "항목2"],
        )
        d = r.to_dict()
        assert d["translation"] == "번역 결과"
        assert len(d["checklistItems"]) == 2

    def test_supported_types_contains_pdf_and_images(self):
        from analyzer.models import SUPPORTED_TYPES

        assert "pdf" in SUPPORTED_TYPES
        assert "jpg" in SUPPORTED_TYPES
        assert "jpeg" in SUPPORTED_TYPES
        assert "png" in SUPPORTED_TYPES
        assert "gif" not in SUPPORTED_TYPES

    def test_language_names_covers_all_8(self):
        from analyzer.models import LANGUAGE_NAMES

        expected = {"vi", "zh-CN", "zh-TW", "en", "ja", "th", "mn", "tl"}
        assert expected == set(LANGUAGE_NAMES.keys())


# ── storage.py ────────────────────────────────────────────────────────────

class TestStorage:
    def test_build_s3_key_format(self):
        from analyzer.storage import build_s3_key

        key = build_s3_key("user-abc", "notice.jpg")
        parts = key.split("/")
        assert parts[0] == "uploads"
        assert parts[1] == "user-abc"
        assert parts[3] == "notice.jpg"
        # 타임스탬프 형식 검증 (예: 20251001T120000Z)
        assert len(parts[2]) == 16

    def test_upload_to_s3_stores_object(self, s3_setup):
        from analyzer.storage import upload_to_s3

        uri = upload_to_s3(b"hello", "uploads/u/ts/test.jpg", "image/jpeg")
        assert uri == f"s3://{BUCKET_NAME}/uploads/u/ts/test.jpg"

        resp = s3_setup.get_object(Bucket=BUCKET_NAME, Key="uploads/u/ts/test.jpg")
        assert resp["Body"].read() == b"hello"

    def test_set_expiry_tag_sets_correct_tags(self, s3_setup):
        from analyzer.storage import set_expiry_tag, upload_to_s3

        upload_to_s3(b"data", "uploads/u/ts/file.pdf", "application/pdf")
        set_expiry_tag("uploads/u/ts/file.pdf", days=7)

        tagging = s3_setup.get_object_tagging(
            Bucket=BUCKET_NAME, Key="uploads/u/ts/file.pdf"
        )
        tag_dict = {t["Key"]: t["Value"] for t in tagging["TagSet"]}
        assert tag_dict["ExpiresAfterDays"] == "7"
        assert "ExpiryDate" in tag_dict
        assert tag_dict["Project"] == "school-buddy"


# ── ocr.py ────────────────────────────────────────────────────────────────

class TestOcr:
    def test_extract_text_joins_lines(self):
        """Textract 응답에서 LINE 블록만 추출해 줄바꿈으로 연결."""
        from analyzer.ocr import extract_text_from_pdf

        mock_response = {
            "Blocks": [
                {"BlockType": "PAGE", "Text": "무시"},
                {"BlockType": "LINE", "Text": "현장학습 안내"},
                {"BlockType": "WORD", "Text": "무시"},
                {"BlockType": "LINE", "Text": "10월 15일"},
            ]
        }
        with patch("analyzer.ocr._textract") as mock_textract:
            mock_textract.detect_document_text.return_value = mock_response
            result = extract_text_from_pdf(b"fake-pdf")

        assert "현장학습 안내" in result
        assert "10월 15일" in result
        assert "무시" not in result

    def test_empty_textract_response_returns_fallback(self):
        """텍스트 없는 PDF → 폴백 메시지."""
        from analyzer.ocr import extract_text_from_pdf

        with patch("analyzer.ocr._textract") as mock_textract:
            mock_textract.detect_document_text.return_value = {"Blocks": []}
            result = extract_text_from_pdf(b"fake-pdf")

        assert "추출할 수 없었습니다" in result

    def test_long_text_truncated(self):
        """8000자 초과 텍스트는 잘린다."""
        from analyzer.ocr import extract_text_from_pdf, _MAX_CHARS

        long_line = "A" * (_MAX_CHARS + 100)
        mock_response = {"Blocks": [{"BlockType": "LINE", "Text": long_line}]}
        with patch("analyzer.ocr._textract") as mock_textract:
            mock_textract.detect_document_text.return_value = mock_response
            result = extract_text_from_pdf(b"fake-pdf")

        assert len(result) <= _MAX_CHARS + 20  # 여유 (생략 메시지 포함)
        assert "생략" in result


# ── ai.py ─────────────────────────────────────────────────────────────────

GOOD_ANALYSIS_JSON = json.dumps(
    {
        "summary":    "10월 15일 현장학습 안내입니다.",
        "materials":  ["도시락", "물통"],
        "schedule":   [{"date": "2025-10-15", "description": "현장학습"}],
        "importance": "HIGH",
    }
)

GOOD_TRANSLATE_JSON = json.dumps(
    {
        "translation":    "Thông báo đi học thực địa ngày 15/10.",
        "culturalTip":    "Học thực địa là hoạt động ngoại khóa.",
        "checklistItems": ["Nộp phí 15.000 won trước ngày 10/10"],
    }
)


class TestAiAnalyzeText:
    def test_analyze_text_returns_correct_result(self):
        """텍스트 분석 → AnalyzeResult 정상 파싱."""
        from analyzer.ai import analyze_text

        with patch("analyzer.ai.invoke_model", return_value=GOOD_ANALYSIS_JSON):
            result = analyze_text("현장학습 안내 텍스트")

        assert result.summary == "10월 15일 현장학습 안내입니다."
        assert result.materials == ["도시락", "물통"]
        assert len(result.schedule) == 1
        assert result.schedule[0].date == "2025-10-15"
        assert result.importance == "HIGH"

    def test_invalid_importance_falls_back_to_medium(self):
        """importance가 유효하지 않으면 MEDIUM으로 대체."""
        from analyzer.ai import analyze_text

        bad_json = json.dumps(
            {"summary": "요약", "materials": [], "schedule": [], "importance": "CRITICAL"}
        )
        with patch("analyzer.ai.invoke_model", return_value=bad_json):
            result = analyze_text("텍스트")

        assert result.importance == "MEDIUM"

    def test_malformed_schedule_items_skipped(self):
        """schedule 항목이 dict가 아니면 건너뛴다."""
        from analyzer.ai import analyze_text

        bad_sched = json.dumps(
            {
                "summary": "요약",
                "materials": [],
                "schedule": ["문자열", None, {"date": "2025-11-01", "description": "수업"}],
                "importance": "LOW",
            }
        )
        with patch("analyzer.ai.invoke_model", return_value=bad_sched):
            result = analyze_text("텍스트")

        assert len(result.schedule) == 1
        assert result.schedule[0].date == "2025-11-01"


class TestAiTranslate:
    def test_translate_result_vi(self):
        """베트남어 번역 결과 정상 파싱."""
        from analyzer.ai import translate_result

        with patch("analyzer.ai.invoke_model", return_value=GOOD_TRANSLATE_JSON):
            result = translate_result("현장학습 안내입니다.", "vi")

        assert "Thông báo" in result.translation
        assert len(result.checklistItems) == 1

    def test_unknown_language_defaults_to_english_name(self):
        """LANGUAGE_NAMES에 없는 코드는 English로 폴백."""
        from analyzer.ai import translate_result

        with patch("analyzer.ai.invoke_model", return_value=GOOD_TRANSLATE_JSON) as mock_invoke:
            translate_result("요약", "xx")
            call_args = mock_invoke.call_args[0]
            # user prompt에 "English"가 삽입되어야 함
            assert "English" in call_args[1]


class TestAiVision:
    def test_analyze_image_calls_vision_api(self):
        """이미지 분석 시 invoke_vision 경로 사용."""
        from analyzer.ai import analyze_image

        with patch("analyzer.ai._invoke_vision", return_value=GOOD_ANALYSIS_JSON) as mock_vision:
            result = analyze_image("base64data", "image/jpeg")

        mock_vision.assert_called_once()
        assert result.importance == "HIGH"

    def test_vision_api_retry_on_throttling(self):
        """ThrottlingException → 재시도 후 성공."""
        import botocore.exceptions
        from analyzer.ai import _invoke_vision, _load_prompt

        throttle_exc = MagicMock()
        throttle_exc.response = {"Error": {"Code": "ThrottlingException"}}
        type(throttle_exc).__name__ = "ThrottlingException"

        # 첫 번째 시도는 실패, 두 번째는 성공
        mock_resp_body = MagicMock()
        mock_resp_body.read.return_value = json.dumps(
            {"content": [{"text": GOOD_ANALYSIS_JSON}]}
        ).encode()

        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                err = Exception("ThrottlingException")
                err.response = {"Error": {"Code": "ThrottlingException"}}
                raise err
            return {"body": mock_resp_body}

        with patch("analyzer.ai._bedrock_runtime") as mock_rt, \
             patch("analyzer.ai.time.sleep"):
            mock_rt.invoke_model.side_effect = side_effect
            result = _invoke_vision("system", "user", "b64", "image/jpeg")

        assert GOOD_ANALYSIS_JSON in result
        assert call_count == 2
