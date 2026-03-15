"""
SNS 발행 모듈 (processor 전용).

처리 완료된 공지를 notice-topic에 발행 → notification-sender Lambda가 구독하여
FCM 푸시 알림을 발송한다.
"""
from __future__ import annotations

import json
import logging
import os

import boto3

from .models import SQSNoticePayload, SummaryResult, ImportanceResult

logger = logging.getLogger(__name__)

# ── 클라이언트 (모듈 레벨) ──────────────────────────────────────
_sns = boto3.client("sns", region_name=os.environ.get("REGION", "us-east-1"))

NOTICE_TOPIC_ARN = os.environ.get("NOTICE_TOPIC_ARN", "")


class PublishError(Exception):
    """SNS 발행 실패."""


def publish_processed_notice(
    payload: SQSNoticePayload,
    summary: SummaryResult,
    importance: ImportanceResult,
    translations: dict[str, dict],
) -> None:
    """
    처리 완료 공지를 SNS notice-topic에 발행.

    notification-sender Lambda가 이 메시지를 수신하여
    구독 사용자에게 FCM 푸시 알림을 발송한다.

    Parameters
    ----------
    payload     : 원본 SQS 메시지
    summary     : 요약 결과 (summary, keywords)
    importance  : 중요도 판단 결과 (HIGH/MEDIUM/LOW)
    translations: {langCode: {"translation": ..., "culturalTip": ..., "checklistItems": ...}}

    Raises
    ------
    PublishError : SNS 호출 실패 시
    """
    if not NOTICE_TOPIC_ARN:
        raise PublishError("NOTICE_TOPIC_ARN 환경변수가 설정되지 않았습니다.")

    message_body = {
        "noticeId":    payload.noticeId,
        "schoolId":    payload.schoolId,
        "title":       payload.title,
        "sourceUrl":   payload.sourceUrl,
        "publishedAt": payload.publishedAt,
        "crawledAt":   payload.crawledAt,
        "summary":     summary.summary,
        "keywords":    summary.keywords,
        "importance":  importance.importance,
        "translations": translations,
    }

    try:
        _sns.publish(
            TopicArn=NOTICE_TOPIC_ARN,
            Subject=f"[SchoolBuddy] 새 공지: {payload.title[:50]}",
            Message=json.dumps(message_body, ensure_ascii=False),
            MessageAttributes={
                "schoolId": {
                    "DataType": "String",
                    "StringValue": payload.schoolId,
                },
                "importance": {
                    "DataType": "String",
                    "StringValue": importance.importance,
                },
            },
        )
        logger.info(
            {
                "message": "processed notice published",
                "noticeId": payload.noticeId,
                "schoolId": payload.schoolId,
                "importance": importance.importance,
            }
        )
    except Exception as e:
        raise PublishError(f"SNS 발행 실패: {e}") from e
