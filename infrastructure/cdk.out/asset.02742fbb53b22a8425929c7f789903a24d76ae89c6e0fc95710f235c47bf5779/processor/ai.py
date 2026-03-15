"""
Bedrock AI 처리 파이프라인.

프롬프트 템플릿을 ./prompts/ 에서 읽어 invoke_model()을 호출한다.
bedrock.py는 packages/shared-utils/src/bedrock.py 를 참조한다.
Lambda 배포 시 CDK 번들링으로 해당 파일이 /var/task 에 포함되어야 한다.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── shared-utils bedrock.py 임포트 ─────────────────────────────
# 로컬 개발: packages/shared-utils/src/bedrock.py 경로 자동 추가
# Lambda 배포: CDK 번들링으로 /var/task/bedrock.py 가 포함되어야 함
try:
    from bedrock import invoke_model, BedrockResponseError
except ImportError:
    _shared = Path(__file__).parents[3] / "packages" / "shared-utils" / "src"
    if _shared.is_dir() and str(_shared) not in sys.path:
        sys.path.insert(0, str(_shared))
    from bedrock import invoke_model, BedrockResponseError  # type: ignore[no-redef]

from .models import (
    SummaryResult,
    TranslationResult,
    ImportanceResult,
    LANGUAGE_NAMES,
)

# ── 프롬프트 파일 경로 ────────────────────────────────────────
# services/processor/prompts/ — handler.py 기준 상위 디렉터리의 prompts/
_PROMPTS_DIR = Path(__file__).parents[1] / "prompts"

# 모델 설정 (환경변수 오버라이드 가능)
_MAX_TOKENS_SUMMARY     = int(os.environ.get("MAX_TOKENS_SUMMARY", "500"))
_MAX_TOKENS_TRANSLATION = int(os.environ.get("MAX_TOKENS_TRANSLATION", "800"))
_MAX_TOKENS_IMPORTANCE  = 200


# ── 프롬프트 로더 ─────────────────────────────────────────────

def _load_prompt(filename: str) -> tuple[str, str]:
    """
    프롬프트 파일에서 [SYSTEM]과 [USER] 섹션을 파싱한다.
    [VERIFICATION] 이후 내용은 제외한다.

    Returns
    -------
    (system_prompt, user_template) tuple
    """
    content = (_PROMPTS_DIR / filename).read_text(encoding="utf-8")
    # [VERIFICATION] 이후 제거
    content = content.split("[VERIFICATION]")[0]
    system = re.search(r"\[SYSTEM\](.*?)\[USER\]", content, re.DOTALL)
    if not system:
        raise ValueError(f"프롬프트 파일 형식 오류: {filename}")
    system_prompt = system.group(1).strip()
    user_template = content.split("[USER]")[1].strip()
    return system_prompt, user_template


def _fill(template: str, **kwargs: str) -> str:
    """
    {placeholder} 를 kwargs로 치환.
    str.format()과 달리 JSON 예시의 중괄호를 건드리지 않는다.
    """
    result = template
    for key, value in kwargs.items():
        result = result.replace("{" + key + "}", value)
    return result


# ── 공개 AI 함수 ──────────────────────────────────────────────

def summarize(notice_text: str, title: str = "") -> SummaryResult:
    """
    공지 원문을 요약하고 키워드를 추출한다.

    원문이 비어 있으면 제목을 원문으로 사용한다.
    """
    text = notice_text.strip() or title.strip() or "(원문 없음)"
    system, user_tpl = _load_prompt("notice_summary.txt")
    user = _fill(user_tpl, notice_text=text)

    raw = invoke_model(system, user, max_tokens=_MAX_TOKENS_SUMMARY)
    data: dict = json.loads(raw)

    return SummaryResult(
        summary=data.get("summary", ""),
        keywords=data.get("keywords", []),
    )


def judge_importance(summary_text: str) -> ImportanceResult:
    """공지 요약을 보고 중요도(HIGH/MEDIUM/LOW)를 판단한다."""
    system, user_tpl = _load_prompt("importance_judge.txt")
    user = _fill(user_tpl, summary_text=summary_text)

    raw = invoke_model(system, user, max_tokens=_MAX_TOKENS_IMPORTANCE)
    data: dict = json.loads(raw)

    importance = data.get("importance", "MEDIUM").upper()
    if importance not in ("HIGH", "MEDIUM", "LOW"):
        logger.warning(
            {"message": "중요도 값 비정상 — MEDIUM으로 대체", "raw_importance": importance}
        )
        importance = "MEDIUM"

    return ImportanceResult(
        importance=importance,
        reason=data.get("reason", ""),
    )


def translate(summary_text: str, target_language: str) -> TranslationResult:
    """
    공지 요약을 지정 언어로 번역하고 문화 해석을 추가한다.

    Parameters
    ----------
    summary_text : str
        번역할 요약문 (summarize() 결과의 summary 필드)
    target_language : str
        대상 언어 코드 (예: "vi", "zh-CN", "en")
    """
    language_name = LANGUAGE_NAMES.get(target_language, target_language)
    system, user_tpl = _load_prompt("notice_translate.txt")
    user = _fill(
        user_tpl,
        summary_text=summary_text,
        target_language=target_language,
        language_name=language_name,
    )

    raw = invoke_model(system, user, max_tokens=_MAX_TOKENS_TRANSLATION)
    data: dict = json.loads(raw)

    return TranslationResult(
        translation=data.get("translation", ""),
        culturalTip=data.get("culturalTip", ""),
        checklistItems=data.get("checklistItems", []),
    )


def run_full_pipeline(
    original_text: str,
    title: str,
    languages: tuple[str, ...],
) -> tuple[SummaryResult, ImportanceResult, dict[str, dict]]:
    """
    요약 → 중요도 판단 → 다국어 번역을 순서대로 실행한다.

    Parameters
    ----------
    languages : tuple[str, ...]
        번역할 언어 코드 목록

    Returns
    -------
    (SummaryResult, ImportanceResult, translations_dict)
    translations_dict 형식: {"vi": {...}, "en": {...}, ...}
    """
    summary_result     = summarize(original_text, title)
    importance_result  = judge_importance(summary_result.summary)

    translations: dict[str, dict] = {}
    for lang in languages:
        try:
            t = translate(summary_result.summary, lang)
            translations[lang] = t.to_dict()
        except BedrockResponseError as e:
            logger.error(
                {"message": "번역 실패", "lang": lang, "error": str(e)}
            )
            # 번역 실패 시 해당 언어만 빈 값으로 저장 — 전체 중단 없음
            translations[lang] = {
                "translation": "",
                "culturalTip": "",
                "checklistItems": [],
            }

    return summary_result, importance_result, translations
