"""
Bedrock Claude 호출 — 문서 분석 + 번역

이미지 분석: Claude Vision (multimodal) — 직접 bedrock-runtime 호출
텍스트 분석: bedrock.py invoke_model 재사용 (텍스트 전용)
번역:        document_translate.txt 프롬프트 재사용
"""
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import boto3

# ── shared-utils/bedrock.py 임포트 (Local 개발 / Lambda 공용) ─────────────
try:
    from bedrock import invoke_model, BedrockResponseError  # type: ignore[import]
except ImportError:
    _utils_src = Path(__file__).parents[3] / "packages" / "shared-utils" / "src"
    sys.path.insert(0, str(_utils_src))
    from bedrock import invoke_model, BedrockResponseError  # type: ignore[import]

from analyzer.models import (
    AnalyzeResult,
    ScheduleItem,
    TranslatedResult,
    LANGUAGE_NAMES,
)

# ── 상수 ─────────────────────────────────────────────────────────────────
_REGION      = os.environ.get("REGION", "us-east-1")
_MODEL_ID    = os.environ.get(
    "BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250514-v1:0"
)
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

_MAX_TOKENS_ANALYZE   = 800
_MAX_TOKENS_TRANSLATE = 800

_VALID_IMPORTANCE = {"HIGH", "MEDIUM", "LOW"}
_RETRY_DELAYS     = [1, 2, 4]
_RETRYABLE_ERRORS = frozenset({"ThrottlingException", "ServiceUnavailableException"})

_bedrock_runtime = boto3.client("bedrock-runtime", region_name=_REGION)


# ── 프롬프트 유틸 ─────────────────────────────────────────────────────────

def _load_prompt(filename: str) -> tuple[str, str]:
    """[SYSTEM] / [USER] / [VERIFICATION] 섹션 분리."""
    content = (_PROMPTS_DIR / filename).read_text(encoding="utf-8")
    system_match = re.search(r"\[SYSTEM\](.*?)\[USER\]", content, re.DOTALL)
    user_match   = re.search(r"\[USER\](.*?)(?:\[VERIFICATION\]|$)", content, re.DOTALL)
    if not system_match or not user_match:
        raise ValueError(f"프롬프트 파일 형식 오류: {filename}")
    return system_match.group(1).strip(), user_match.group(1).strip()


def _fill(template: str, **kwargs: str) -> str:
    """JSON 중괄호와 충돌하지 않도록 str.replace 방식으로 치환."""
    result = template
    for key, value in kwargs.items():
        result = result.replace("{" + key + "}", value)
    return result


# ── 이미지 Vision 분석 ────────────────────────────────────────────────────

def _invoke_vision(system_prompt: str, user_text: str, image_b64: str, media_type: str) -> str:
    """
    Claude Vision multimodal API 직접 호출.
    bedrock.py는 텍스트 전용이므로 이미지 분석은 직접 invoke.
    재시도 로직은 bedrock.py와 동일한 정책 적용.
    """
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens":        _MAX_TOKENS_ANALYZE,
        "system":            system_prompt,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type":       "base64",
                            "media_type": media_type,
                            "data":       image_b64,
                        },
                    },
                    {"type": "text", "text": user_text},
                ],
            }
        ],
    })

    last_err: Exception | None = None
    for attempt, delay in enumerate([0] + _RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            resp = _bedrock_runtime.invoke_model(
                modelId=_MODEL_ID,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(resp["body"].read())
            return result["content"][0]["text"]
        except Exception as e:
            err_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            if err_code in _RETRYABLE_ERRORS and attempt < len(_RETRY_DELAYS):
                last_err = e
                continue
            raise BedrockResponseError(f"Vision 호출 실패: {e}") from e

    raise BedrockResponseError(f"Vision 재시도 초과: {last_err}")


# ── 분석 결과 파싱 ────────────────────────────────────────────────────────

def _parse_analyze_result(raw: str) -> AnalyzeResult:
    data = json.loads(raw)
    importance = data.get("importance", "MEDIUM")
    if importance not in _VALID_IMPORTANCE:
        importance = "MEDIUM"

    schedule = [
        ScheduleItem(
            date=s.get("date", ""),
            description=s.get("description", ""),
        )
        for s in data.get("schedule", [])
        if isinstance(s, dict)
    ]

    return AnalyzeResult(
        summary=data.get("summary", ""),
        materials=data.get("materials", []),
        schedule=schedule,
        importance=importance,
    )


# ── 공개 API ─────────────────────────────────────────────────────────────

def analyze_image(image_b64: str, media_type: str) -> AnalyzeResult:
    """
    이미지 가정통신문을 Claude Vision으로 직접 분석한다.
    """
    system_prompt, user_tmpl = _load_prompt("document_analyze.txt")
    # 이미지 분석 시 {document_text} 는 Vision 지시문으로 대체
    user_text = _fill(
        user_tmpl,
        document_text="위 이미지에 있는 가정통신문 내용을 읽고 아래 형식에 맞게 분석해주세요.",
    )
    raw = _invoke_vision(system_prompt, user_text, image_b64, media_type)
    return _parse_analyze_result(raw)


def analyze_text(extracted_text: str) -> AnalyzeResult:
    """
    Textract로 추출한 텍스트를 Claude 텍스트 모드로 분석한다.
    """
    system_prompt, user_tmpl = _load_prompt("document_analyze.txt")
    user_text = _fill(user_tmpl, document_text=extracted_text)
    raw = invoke_model(system_prompt, user_text, max_tokens=_MAX_TOKENS_ANALYZE)
    return _parse_analyze_result(raw)


def translate_result(summary: str, language_code: str) -> TranslatedResult:
    """
    분석 결과 요약을 사용자 언어로 번역한다.
    processor의 notice_translate.txt 와 동일한 프롬프트 재사용.
    """
    system_prompt, user_tmpl = _load_prompt("document_translate.txt")
    language_name = LANGUAGE_NAMES.get(language_code, "English")
    user_text = _fill(
        user_tmpl,
        summary_text=summary,
        target_language=language_code,
        language_name=language_name,
    )
    raw = invoke_model(system_prompt, user_text, max_tokens=_MAX_TOKENS_TRANSLATE)
    data = json.loads(raw)

    return TranslatedResult(
        translation=data.get("translation", ""),
        culturalTip=data.get("culturalTip", ""),
        checklistItems=data.get("checklistItems", []),
    )
