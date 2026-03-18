"""
document-analyzer Lambda
POST /documents/analyze

처리 흐름:
1. 요청 파싱 + 검증 (10MB, jpg/jpeg/png/pdf)
2. S3 업로드 (uploads/{userId}/{timestamp}/{filename})
3. 파일 타입 분기:
   - 이미지: Claude Vision 직접 분석
   - PDF:    Textract 텍스트 추출 → Claude 텍스트 분석
4. 사용자 언어로 번역 (document_translate.txt)
5. 결과 반환 + S3 만료 태그(7일) 설정
"""
import base64
import json
import os
from datetime import datetime, timezone
from typing import Any

from analyzer.ai import analyze_image, analyze_text, translate_result
from analyzer.models import (
    LANGUAGE_NAMES,
    MAX_FILE_BYTES,
    SUPPORTED_IMAGE_TYPES,
    SUPPORTED_TYPES,
    TranslatedResult,
)
from analyzer.ocr import extract_text_from_pdf
from analyzer.storage import build_s3_key, set_expiry_tag, upload_to_s3

# ── 모듈 레벨 상수 (cold start 최적화) ───────────────────────────────────
_REGION           = os.environ.get("REGION", "us-east-1")
_DOCUMENTS_BUCKET = os.environ.get("DOCUMENTS_BUCKET", "hanyang-pj-1-documents-dev")


# ── 응답 헬퍼 ────────────────────────────────────────────────────────────

def _ok(data: Any, status: int = 200) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {"data": data, "meta": {"timestamp": datetime.now(timezone.utc).isoformat()}},
            ensure_ascii=False,
        ),
    }


def _err(message: str, code: str, status: int = 400) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "error": message,
                "code":  code,
                "meta":  {"timestamp": datetime.now(timezone.utc).isoformat()},
            },
            ensure_ascii=False,
        ),
    }


# ── JWT sub 추출 ─────────────────────────────────────────────────────────

def _get_user_id(event: dict[str, Any]) -> str | None:
    """HTTP API v2 JWT Authorizer claims에서 sub를 추출한다."""
    try:
        return event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
    except (KeyError, TypeError):
        return None


# ── 핸들러 ───────────────────────────────────────────────────────────────

def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    # 1. 인증
    user_id = _get_user_id(event)
    if not user_id:
        return _err("인증이 필요합니다", "UNAUTHORIZED", 401)

    # 2. 요청 파싱
    try:
        body: dict[str, Any] = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _err("요청 본문이 유효하지 않습니다", "VALIDATION_ERROR", 400)

    file_data_b64: str | None = body.get("fileData")
    filename: str             = body.get("filename", "")
    language_code: str        = body.get("languageCode", "vi")

    if not file_data_b64:
        return _err("fileData(base64)가 필요합니다", "VALIDATION_ERROR", 400)
    if not filename:
        return _err("filename이 필요합니다", "VALIDATION_ERROR", 400)
    if language_code not in LANGUAGE_NAMES:
        return _err(
            f"지원하지 않는 언어 코드입니다: {language_code}",
            "VALIDATION_ERROR",
            400,
        )

    # 3. 파일 확장자 확인
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_TYPES:
        return _err(
            f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(sorted(SUPPORTED_TYPES))}",
            "UNSUPPORTED_FILE_TYPE",
            400,
        )

    # 4. base64 디코딩 + 크기 검증
    try:
        file_bytes = base64.b64decode(file_data_b64)
    except Exception:
        return _err("fileData base64 디코딩 실패", "VALIDATION_ERROR", 400)

    if len(file_bytes) > MAX_FILE_BYTES:
        mb = len(file_bytes) // (1024 * 1024)
        return _err(f"파일 크기가 10MB를 초과합니다 ({mb}MB)", "FILE_TOO_LARGE", 400)

    # 5. S3 업로드
    content_type = SUPPORTED_IMAGE_TYPES.get(ext, "application/pdf")
    s3_key = build_s3_key(user_id, filename)
    try:
        s3_uri = upload_to_s3(file_bytes, s3_key, content_type)
    except Exception as e:
        print(f"[analyzer] S3 업로드 실패: {e}")
        return _err("파일 저장 중 오류가 발생했습니다", "INTERNAL_ERROR", 500)

    # 6. 파일 타입에 따라 분석
    try:
        if ext == "pdf":
            extracted_text = extract_text_from_pdf(file_bytes)
            analysis = analyze_text(extracted_text)
        else:
            # jpg / jpeg / png → Claude Vision
            analysis = analyze_image(file_data_b64, content_type)
    except Exception as e:
        print(f"[analyzer] 문서 분석 실패: {e}")
        return _err("문서 분석 중 오류가 발생했습니다", "ANALYSIS_ERROR", 500)

    # 7. 번역 (실패 시 한국어 원문 반환 — 치명적 오류 아님)
    try:
        translated = translate_result(analysis.summary, language_code)
    except Exception as e:
        print(f"[analyzer] 번역 실패 (원문 반환): {e}")
        translated = TranslatedResult(
            translation=analysis.summary,
            culturalTip="",
            checklistItems=[],
        )

    # 8. S3 만료 태그 설정 (bucket lifecycle 백업 — 실패 무시)
    try:
        set_expiry_tag(s3_key, days=7)
    except Exception as e:
        print(f"[analyzer] S3 태그 설정 실패 (무시): {e}")

    # 9. 응답
    return _ok(
        {
            "s3Uri":      s3_uri,
            "fileType":   ext,
            "analysis":   analysis.to_dict(),
            "translated": translated.to_dict(),
        }
    )
