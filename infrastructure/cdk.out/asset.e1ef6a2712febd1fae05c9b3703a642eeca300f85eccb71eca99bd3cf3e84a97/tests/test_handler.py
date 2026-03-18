"""
handler.py 단위 테스트
AWS 서비스(S3, Textract, Bedrock)는 모두 unittest.mock으로 격리.
"""
import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import BUCKET_NAME, MINIMAL_PDF_B64, TINY_JPEG_B64, make_event

# ── 샘플 Bedrock 응답 ─────────────────────────────────────────────────────
SAMPLE_ANALYSIS_JSON = json.dumps(
    {
        "summary":    "10월 15일 현장학습이 예정되어 있습니다. 참가비 15,000원을 납부해야 합니다.",
        "materials":  ["도시락", "물통"],
        "schedule":   [{"date": "2025-10-15", "description": "현장학습"}],
        "importance": "HIGH",
    }
)
SAMPLE_TRANSLATE_JSON = json.dumps(
    {
        "translation":    "Ngày 15 tháng 10 có chuyến đi học thực địa.",
        "culturalTip":    "Học thực địa là hoạt động ngoại khóa quan trọng.",
        "checklistItems": ["Nộp phí 15.000 won trước ngày 10/10"],
    }
)


def _invoke_model_side_effect(system, user, max_tokens=800, model_id=None):
    """summarize → SAMPLE_ANALYSIS_JSON, translate → SAMPLE_TRANSLATE_JSON."""
    if "번역" in system or "번역" in user:
        return SAMPLE_TRANSLATE_JSON
    return SAMPLE_ANALYSIS_JSON


class TestHandlerValidation:
    """입력 검증 테스트."""

    def test_missing_auth_returns_401(self):
        """requestContext에 authorizer가 없으면 401."""
        import handler as h

        event = {
            "requestContext": {},
            "body": json.dumps({"fileData": TINY_JPEG_B64, "filename": "a.jpg"}),
        }
        resp = h.handler(event, None)
        assert resp["statusCode"] == 401
        assert "UNAUTHORIZED" in resp["body"]

    def test_missing_file_data_returns_400(self):
        """fileData 없으면 400."""
        import handler as h

        resp = h.handler(make_event({"filename": "a.jpg"}), None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["code"] == "VALIDATION_ERROR"

    def test_missing_filename_returns_400(self):
        """filename 없으면 400."""
        import handler as h

        resp = h.handler(make_event({"fileData": TINY_JPEG_B64}), None)
        assert resp["statusCode"] == 400

    def test_unsupported_extension_returns_400(self):
        """gif 확장자는 지원 안 함."""
        import handler as h

        data = base64.b64encode(b"GIF89a").decode()
        resp = h.handler(make_event({"fileData": data, "filename": "anim.gif"}), None)
        assert resp["statusCode"] == 400
        assert "UNSUPPORTED_FILE_TYPE" in resp["body"]

    def test_unsupported_language_returns_400(self):
        """지원하지 않는 언어 코드."""
        import handler as h

        resp = h.handler(
            make_event({"fileData": TINY_JPEG_B64, "filename": "a.jpg", "languageCode": "xx"}),
            None,
        )
        assert resp["statusCode"] == 400

    def test_file_too_large_returns_400(self):
        """11MB 파일 → 400."""
        import handler as h

        large = base64.b64encode(b"X" * (11 * 1024 * 1024)).decode()
        resp = h.handler(
            make_event({"fileData": large, "filename": "big.jpg"}), None
        )
        assert resp["statusCode"] == 400
        assert "FILE_TOO_LARGE" in resp["body"]

    def test_invalid_base64_returns_400(self):
        """base64 디코딩 불가 데이터."""
        import handler as h

        resp = h.handler(
            make_event({"fileData": "not-valid-base64!!!", "filename": "a.jpg"}), None
        )
        assert resp["statusCode"] == 400


class TestHandlerImage:
    """이미지 파일 처리 테스트."""

    @patch("handler.set_expiry_tag")
    @patch("handler.upload_to_s3", return_value="s3://hanyang-pj-1-documents-test/uploads/user-123/key.jpg")
    @patch("handler.translate_result")
    @patch("handler.analyze_image")
    def test_image_success_returns_200(
        self, mock_analyze, mock_translate, mock_upload, mock_tag
    ):
        """JPG 이미지 정상 분석 흐름 → 200."""
        import handler as h
        from analyzer.models import AnalyzeResult, ScheduleItem, TranslatedResult

        mock_analyze.return_value = AnalyzeResult(
            summary="현장학습 안내입니다.",
            materials=["도시락"],
            schedule=[ScheduleItem(date="2025-10-15", description="현장학습")],
            importance="HIGH",
        )
        mock_translate.return_value = TranslatedResult(
            translation="Thông báo đi học thực địa.",
            culturalTip="Học thực địa là...",
            checklistItems=["Nộp phí"],
        )

        event = make_event({"fileData": TINY_JPEG_B64, "filename": "notice.jpg", "languageCode": "vi"})
        resp = h.handler(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["data"]["fileType"] == "jpg"
        assert "s3Uri" in body["data"]
        assert body["data"]["analysis"]["importance"] == "HIGH"
        assert body["data"]["translated"]["translation"] == "Thông báo đi học thực địa."
        mock_analyze.assert_called_once()
        mock_upload.assert_called_once()
        mock_tag.assert_called_once()

    @patch("handler.set_expiry_tag")
    @patch("handler.upload_to_s3", return_value="s3://bucket/key.png")
    @patch("handler.translate_result")
    @patch("handler.analyze_image")
    def test_png_extension_accepted(self, mock_analyze, mock_translate, mock_upload, mock_tag):
        """PNG 확장자도 정상 처리."""
        from analyzer.models import AnalyzeResult, ScheduleItem, TranslatedResult
        import handler as h

        mock_analyze.return_value = AnalyzeResult("요약", [], [], "LOW")
        mock_translate.return_value = TranslatedResult("t", "c", [])
        data = base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()
        resp = h.handler(make_event({"fileData": data, "filename": "a.png"}), None)
        assert resp["statusCode"] == 200

    @patch("handler.set_expiry_tag")
    @patch("handler.upload_to_s3", return_value="s3://bucket/key.jpg")
    @patch("handler.translate_result", side_effect=Exception("번역 서비스 오류"))
    @patch("handler.analyze_image")
    def test_translate_failure_returns_original_summary(
        self, mock_analyze, mock_translate, mock_upload, mock_tag
    ):
        """번역 실패 시 원문 요약을 translation으로 반환 (200)."""
        from analyzer.models import AnalyzeResult, ScheduleItem
        import handler as h

        mock_analyze.return_value = AnalyzeResult("원문 요약입니다.", [], [], "MEDIUM")
        resp = h.handler(make_event({"fileData": TINY_JPEG_B64, "filename": "a.jpg"}), None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["data"]["translated"]["translation"] == "원문 요약입니다."

    @patch("handler.upload_to_s3", side_effect=Exception("S3 연결 오류"))
    def test_s3_upload_failure_returns_500(self, mock_upload):
        """S3 업로드 실패 → 500."""
        import handler as h

        resp = h.handler(make_event({"fileData": TINY_JPEG_B64, "filename": "a.jpg"}), None)
        assert resp["statusCode"] == 500
        assert "INTERNAL_ERROR" in resp["body"]


class TestHandlerPDF:
    """PDF 파일 처리 테스트."""

    @patch("handler.set_expiry_tag")
    @patch("handler.upload_to_s3", return_value="s3://bucket/key.pdf")
    @patch("handler.translate_result")
    @patch("handler.analyze_text")
    @patch("handler.extract_text_from_pdf", return_value="현장학습 안내 텍스트입니다.")
    def test_pdf_uses_textract_then_analyzes(
        self, mock_ocr, mock_analyze, mock_translate, mock_upload, mock_tag
    ):
        """PDF → Textract 추출 → 텍스트 분석 경로."""
        from analyzer.models import AnalyzeResult, TranslatedResult
        import handler as h

        mock_analyze.return_value = AnalyzeResult("급식비 안내", [], [], "HIGH")
        mock_translate.return_value = TranslatedResult("Thông báo phí", "", [])

        resp = h.handler(
            make_event({"fileData": MINIMAL_PDF_B64, "filename": "notice.pdf"}), None
        )
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["data"]["fileType"] == "pdf"
        mock_ocr.assert_called_once()         # Textract 호출
        mock_analyze.assert_called_once()     # 텍스트 분석
        # analyze_image는 호출되지 않아야 함

    @patch("handler.upload_to_s3", return_value="s3://bucket/key.pdf")
    @patch("handler.extract_text_from_pdf", side_effect=Exception("Textract 오류"))
    def test_textract_failure_returns_500(self, mock_ocr, mock_upload):
        """Textract 실패 → 500."""
        import handler as h

        resp = h.handler(
            make_event({"fileData": MINIMAL_PDF_B64, "filename": "notice.pdf"}), None
        )
        assert resp["statusCode"] == 500
        assert "ANALYSIS_ERROR" in resp["body"]


class TestHandlerS3Key:
    """S3 키 포맷 검증."""

    @patch("handler.set_expiry_tag")
    @patch("handler.translate_result")
    @patch("handler.analyze_image")
    @patch("handler.upload_to_s3")
    def test_s3_key_contains_user_id_and_filename(
        self, mock_upload, mock_analyze, mock_translate, mock_tag
    ):
        """S3 키: uploads/{userId}/{timestamp}/{filename} 형식."""
        from analyzer.models import AnalyzeResult, TranslatedResult
        import handler as h

        mock_upload.return_value = "s3://bucket/key"
        mock_analyze.return_value = AnalyzeResult("요약", [], [], "LOW")
        mock_translate.return_value = TranslatedResult("t", "c", [])

        h.handler(make_event({"fileData": TINY_JPEG_B64, "filename": "school.jpg"}, user_id="u-abc"), None)

        call_args = mock_upload.call_args
        key: str = call_args[0][1]  # positional arg 1 = key
        assert key.startswith("uploads/u-abc/")
        assert key.endswith("/school.jpg")
