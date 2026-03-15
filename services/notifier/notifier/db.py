"""
DynamoDB 접근 유틸 (notifier 전용).

테이블:
  Children       — PK: childId  GSI: schoolId-index (학교별 구독자 조회)
  Users          — PK: userId
  Schools        — PK: schoolId (학교명 조회)
  Notifications  — PK: userId  SK: createdAt (발송 이력)

모듈 레벨 boto3 리소스 초기화 (cold-start 최적화).
"""
from __future__ import annotations

import logging
import math
import os
import time
import uuid
from typing import Optional

import boto3
from boto3.dynamodb.conditions import Key

from .models import UserRecord

logger = logging.getLogger(__name__)

# ── 클라이언트 (모듈 레벨) ──────────────────────────────────────
_dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("REGION", "us-east-1"))

CHILDREN_TABLE_NAME      = os.environ.get("CHILDREN_TABLE", "")
USERS_TABLE_NAME         = os.environ.get("USERS_TABLE", "")
SCHOOLS_TABLE_NAME       = os.environ.get("SCHOOLS_TABLE", "")
NOTIFICATIONS_TABLE_NAME = os.environ.get("NOTIFICATIONS_TABLE", "")


def _children_table():
    return _dynamodb.Table(CHILDREN_TABLE_NAME)


def _users_table():
    return _dynamodb.Table(USERS_TABLE_NAME)


def _schools_table():
    return _dynamodb.Table(SCHOOLS_TABLE_NAME)


def _notifications_table():
    return _dynamodb.Table(NOTIFICATIONS_TABLE_NAME)


# ── 구독자 조회 ────────────────────────────────────────────────

def get_school_subscribers(school_id: str) -> list[UserRecord]:
    """
    schoolId-index GSI로 해당 학교 자녀를 둔 사용자 목록 조회.
    중복 userId는 1회만 포함한다 (한 학교에 여러 자녀 등록 가능).
    """
    # 1. Children GSI로 schoolId에 속한 childId / userId 조회
    user_ids: set[str] = set()
    kwargs: dict = {
        "IndexName": "schoolId-index",
        "KeyConditionExpression": Key("schoolId").eq(school_id),
        "ProjectionExpression": "userId",
    }
    while True:
        resp = _children_table().query(**kwargs)
        for item in resp.get("Items", []):
            if "userId" in item:
                user_ids.add(item["userId"])
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key

    if not user_ids:
        logger.info({"message": "no subscribers for school", "schoolId": school_id})
        return []

    # 2. BatchGetItem으로 Users 레코드 일괄 조회 (최대 100개/배치 DynamoDB 제한)
    users: list[UserRecord] = []
    uid_list = list(user_ids)
    for i in range(0, len(uid_list), 100):
        chunk = uid_list[i : i + 100]
        resp = _dynamodb.batch_get_item(
            RequestItems={
                USERS_TABLE_NAME: {
                    "Keys": [{"userId": uid} for uid in chunk],
                    "ProjectionExpression": (
                        "userId, languageCode, notificationSettings, fcmToken, fcmTokenWeb"
                    ),
                }
            }
        )
        for item in resp.get("Responses", {}).get(USERS_TABLE_NAME, []):
            users.append(UserRecord.from_item(item))

    logger.info(
        {"message": "subscribers loaded", "schoolId": school_id, "count": len(users)}
    )
    return users


# ── 학교명 조회 ────────────────────────────────────────────────

def get_school_name(school_id: str) -> str:
    """Schools 테이블에서 학교명 조회. 실패 시 schoolId 반환."""
    try:
        resp = _schools_table().get_item(
            Key={"schoolId": school_id},
            ProjectionExpression="#n",
            ExpressionAttributeNames={"#n": "name"},
        )
        return resp.get("Item", {}).get("name", school_id)
    except Exception as e:
        logger.warning({"message": "학교명 조회 실패", "schoolId": school_id, "error": str(e)})
        return school_id


# ── 발송 이력 저장 ─────────────────────────────────────────────

def save_notification(
    user_id: str,
    notice_id: str,
    sent_at: str,
) -> None:
    """
    Notifications 테이블에 발송 이력 저장.
    expiresAt = 180일 (TTL — storage-stack.ts 설정과 동일).
    """
    expires_at = math.floor(time.time()) + 180 * 24 * 3600
    try:
        _notifications_table().put_item(
            Item={
                "userId":         user_id,
                "createdAt":      sent_at,
                "notificationId": str(uuid.uuid4()),
                "noticeId":       notice_id,
                "sentAt":         sent_at,
                "isRead":         False,
                "expiresAt":      expires_at,
            }
        )
    except Exception as e:
        # 이력 저장 실패는 알림 발송 성공에 영향을 주지 않음
        logger.error(
            {"message": "발송 이력 저장 실패", "userId": user_id, "noticeId": notice_id, "error": str(e)}
        )


# ── 만료 토큰 삭제 ─────────────────────────────────────────────

def clear_fcm_token(user_id: str, token_field: str) -> None:
    """
    만료된 FCM 토큰을 Users 테이블에서 삭제.

    Parameters
    ----------
    user_id : str
    token_field : str
        "fcmToken" (네이티브) 또는 "fcmTokenWeb" (웹)
    """
    if token_field not in ("fcmToken", "fcmTokenWeb"):
        logger.warning({"message": "잘못된 token_field", "field": token_field})
        return
    try:
        _users_table().update_item(
            Key={"userId": user_id},
            UpdateExpression="REMOVE #f",
            ExpressionAttributeNames={"#f": token_field},
        )
        logger.info(
            {"message": "만료 토큰 삭제", "userId": user_id, "field": token_field}
        )
    except Exception as e:
        logger.error(
            {"message": "토큰 삭제 실패", "userId": user_id, "field": token_field, "error": str(e)}
        )
