"""
notice-processor 내부 데이터 모델.
SQS 입력 페이로드, AI 처리 결과, DynamoDB 저장 구조를 정의한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── SQS 입력 (crawler가 발행한 메시지 스키마와 동일) ────────────

@dataclass
class SQSNoticePayload:
    """
    notice-queue SQS 메시지 본문.
    school-crawler의 SQSNoticePayload.to_dict() 결과를 역직렬화한다.
    """
    noticeId: str
    schoolId: str
    title: str
    sourceUrl: str
    originalText: str
    publishedAt: str    # ISO 8601
    crawledAt: str      # ISO 8601

    @classmethod
    def from_dict(cls, d: dict) -> "SQSNoticePayload":
        return cls(
            noticeId=d["noticeId"],
            schoolId=d["schoolId"],
            title=d["title"],
            sourceUrl=d["sourceUrl"],
            originalText=d.get("originalText", ""),
            publishedAt=d["publishedAt"],
            crawledAt=d["crawledAt"],
        )


# ── AI 처리 결과 ────────────────────────────────────────────────

@dataclass
class SummaryResult:
    """Bedrock 요약 결과."""
    summary: str
    keywords: list = field(default_factory=list)


@dataclass
class TranslationResult:
    """Bedrock 번역 + 문화 해석 결과."""
    translation: str
    culturalTip: str
    checklistItems: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "translation": self.translation,
            "culturalTip": self.culturalTip,
            "checklistItems": self.checklistItems,
        }


@dataclass
class ImportanceResult:
    """Bedrock 중요도 판단 결과."""
    importance: str     # HIGH | MEDIUM | LOW
    reason: str


# ── 지원 언어 목록 ────────────────────────────────────────────────

# LanguageCode enum(shared-types)과 동기화 — Python 버전
ALL_LANGUAGE_CODES: tuple[str, ...] = (
    "vi", "zh-CN", "zh-TW", "en", "ja", "th", "mn", "tl"
)

# 언어 코드 → 현지 언어명 (번역 프롬프트 {language_name} 치환용)
LANGUAGE_NAMES: dict[str, str] = {
    "vi":    "Tiếng Việt",
    "zh-CN": "简体中文",
    "zh-TW": "繁體中文",
    "en":    "English",
    "ja":    "日本語",
    "th":    "ภาษาไทย",
    "mn":    "Монгол хэл",
    "tl":    "Filipino",
}
