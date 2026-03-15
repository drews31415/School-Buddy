"""
크롤러 내부 데이터 모델.
DynamoDB 스키마 및 SQS 페이로드 정의.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SchoolRecord:
    """DynamoDB Schools 테이블 항목."""
    schoolId: str
    name: str
    noticeUrl: str
    crawlStatus: str                   # ACTIVE | ERROR | INACTIVE
    lastCrawledAt: Optional[str] = None
    lastErrorAt: Optional[str] = None
    lastErrorMessage: Optional[str] = None
    consecutiveErrors: int = 0


@dataclass
class RawNotice:
    """크롤링으로 추출한 공지 원본 데이터."""
    title: str
    url: str                           # 공지 상세 페이지 URL (절대 URL)
    published_at: Optional[str] = None # 게시일 (없으면 크롤링 시각 사용)
    content: str = ""                  # 상세 페이지 본문 (선택적)


@dataclass
class SQSNoticePayload:
    """
    SQS notice-queue 메시지 페이로드 스키마.

    notice-processor가 이 스키마를 그대로 소비한다.
    """
    noticeId: str       # UUID4 (크롤러가 생성)
    schoolId: str
    title: str
    sourceUrl: str      # 공지 원본 URL
    originalText: str   # 공지 본문 (빈 문자열 허용 — 상세 페이지 접근 실패 시)
    publishedAt: str    # ISO 8601 (공지 게시일 또는 크롤링 시각)
    crawledAt: str      # ISO 8601 (크롤링 시각)

    def to_dict(self) -> dict:
        return {
            "noticeId": self.noticeId,
            "schoolId": self.schoolId,
            "title": self.title,
            "sourceUrl": self.sourceUrl,
            "originalText": self.originalText,
            "publishedAt": self.publishedAt,
            "crawledAt": self.crawledAt,
        }
