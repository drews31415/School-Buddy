"""
SQS / SNS 메시지 발행 모듈.
"""
from __future__ import annotations

import json
import logging
import os

import boto3

from .models import SQSNoticePayload

logger = logging.getLogger(__name__)

# ── 클라이언트 (모듈 레벨) ─────────────────────────────────
_sqs = boto3.client("sqs", region_name=os.environ.get("REGION", "us-east-1"))
_sns = boto3.client("sns", region_name=os.environ.get("REGION", "us-east-1"))

# CDK application-stack.ts 의 crawler Lambda 환경변수 이름과 일치
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "")
SNS_ALARM_TOPIC_ARN = os.environ.get("SNS_ALARM_TOPIC_ARN", "")


class PublishError(Exception):
    """메시지 발행 실패."""


def publish_notice(payload: SQSNoticePayload) -> None:
    """
    신규 공지를 SQS notice-queue에 발행.
    :raises PublishError: SQS 호출 실패 시
    """
    if not SQS_QUEUE_URL:
        raise PublishError("SQS_QUEUE_URL 환경변수가 설정되지 않았습니다.")
    try:
        _sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(payload.to_dict(), ensure_ascii=False),
            MessageAttributes={
                "schoolId": {
                    "DataType": "String",
                    "StringValue": payload.schoolId,
                }
            },
        )
        logger.info(
            {"message": "notice published", "noticeId": payload.noticeId, "schoolId": payload.schoolId}
        )
    except Exception as e:
        raise PublishError(f"SQS 발행 실패: {e}") from e


def publish_ops_alarm(school_id: str, school_name: str, error_message: str) -> None:
    """
    학교 crawlStatus가 ERROR로 변경될 때 운영 알람 발송 (SNS).
    NOTICE_TOPIC_ARN을 재사용하되 Subject로 구분.
    """
    if not SNS_ALARM_TOPIC_ARN:
        logger.warning("SNS_ALARM_TOPIC_ARN 미설정 — 운영 알람 건너뜀")
        return
    try:
        _sns.publish(
            TopicArn=SNS_ALARM_TOPIC_ARN,
            Subject=f"[SchoolBuddy OPS] 크롤러 오류: {school_name}",
            Message=json.dumps(
                {
                    "type": "OPS_ALARM",
                    "schoolId": school_id,
                    "schoolName": school_name,
                    "errorMessage": error_message,
                },
                ensure_ascii=False,
            ),
        )
    except Exception as e:
        # 운영 알람 실패는 크롤링 플로우를 멈추지 않음
        logger.error({"message": "운영 알람 발송 실패", "error": str(e)})
