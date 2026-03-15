"""
notification-sender 내부 데이터 모델.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SNSNoticeMessage:
    """
    notice-processor가 SNS에 발행한 처리 완료 공지 메시지.
    processor/publisher.py의 message_body와 동일한 스키마.
    """
    noticeId: str
    schoolId: str
    title: str
    sourceUrl: str
    publishedAt: str
    crawledAt: str
    summary: str
    keywords: list
    importance: str                     # HIGH | MEDIUM | LOW
    translations: dict[str, dict]       # {langCode: {translation, culturalTip, checklistItems}}

    @classmethod
    def from_dict(cls, d: dict) -> "SNSNoticeMessage":
        return cls(
            noticeId=d["noticeId"],
            schoolId=d["schoolId"],
            title=d["title"],
            sourceUrl=d.get("sourceUrl", ""),
            publishedAt=d.get("publishedAt", ""),
            crawledAt=d.get("crawledAt", ""),
            summary=d.get("summary", ""),
            keywords=d.get("keywords", []),
            importance=d.get("importance", "MEDIUM"),
            translations=d.get("translations", {}),
        )


@dataclass
class NotificationSettings:
    enabled: bool = True
    importanceThreshold: str = "LOW"    # HIGH | MEDIUM | LOW
    quietHoursStart: Optional[str] = None   # "HH:MM" KST
    quietHoursEnd: Optional[str] = None     # "HH:MM" KST

    @classmethod
    def from_dict(cls, d: dict) -> "NotificationSettings":
        return cls(
            enabled=d.get("enabled", True),
            importanceThreshold=d.get("importanceThreshold", "LOW"),
            quietHoursStart=d.get("quietHoursStart"),
            quietHoursEnd=d.get("quietHoursEnd"),
        )


@dataclass
class UserRecord:
    """DynamoDB Users 테이블 항목."""
    userId: str
    languageCode: str               # LanguageCode enum 값 ("vi", "zh-CN", ...)
    notificationSettings: NotificationSettings
    fcmToken: Optional[str] = None       # 네이티브 앱 토큰
    fcmTokenWeb: Optional[str] = None    # 웹 브라우저 토큰

    @classmethod
    def from_item(cls, item: dict) -> "UserRecord":
        settings_raw = item.get("notificationSettings", {})
        return cls(
            userId=item["userId"],
            languageCode=item.get("languageCode", "en"),
            notificationSettings=NotificationSettings.from_dict(
                settings_raw if isinstance(settings_raw, dict) else {}
            ),
            fcmToken=item.get("fcmToken"),
            fcmTokenWeb=item.get("fcmTokenWeb"),
        )


# 중요도 순위 (높을수록 중요)
IMPORTANCE_RANK: dict[str, int] = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
