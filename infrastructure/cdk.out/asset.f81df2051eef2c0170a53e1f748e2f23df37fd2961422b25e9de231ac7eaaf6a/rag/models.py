"""
rag-query-handler 도메인 모델
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SourceCitation:
    """검색된 지식베이스 문서 출처."""
    content: str
    location: str  # S3 URI or document title

    def to_dict(self) -> dict[str, str]:
        return {"content": self.content, "location": self.location}


@dataclass
class ChatResponse:
    """Bedrock RetrieveAndGenerate 응답."""
    answer: str
    session_id: str
    sources: list[SourceCitation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer":    self.answer,
            "sessionId": self.session_id,
            "sources":   [s.to_dict() for s in self.sources],
        }


@dataclass
class ChatHistoryItem:
    """DynamoDB ChatHistory 아이템."""
    user_id: str
    session_id: str
    role: str       # "user" | "assistant"
    content: str
    created_at: str  # ISO 8601
    expires_at: int  # Unix timestamp

    def to_dict(self) -> dict[str, Any]:
        return {
            "sessionId": self.session_id,
            "role":      self.role,
            "content":   self.content,
            "createdAt": self.created_at,
        }


LANGUAGE_NAMES: dict[str, str] = {
    "vi":    "Tiếng Việt",
    "zh-CN": "简体中文",
    "zh-TW": "繁體中文",
    "en":    "English",
    "ja":    "日本語",
    "th":    "ภาษาไทย",
    "mn":    "Монгол",
    "tl":    "Filipino",
    "ko":    "한국어",
}
