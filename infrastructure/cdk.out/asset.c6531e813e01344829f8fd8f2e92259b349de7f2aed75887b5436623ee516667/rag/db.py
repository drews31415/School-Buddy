"""
DynamoDB 접근 유틸 (rag 전용).

테이블:
  ChatHistory — PK: userId  SK: sessionId#createdAt  TTL: expiresAt (90일)
  Notices     — PK: schoolId  SK: createdAt  GSI: noticeId-index
"""
from __future__ import annotations

import logging
import math
import os
import time
from datetime import datetime, timezone
from typing import Optional

import boto3
from boto3.dynamodb.conditions import Key

from .models import ChatHistoryItem

logger = logging.getLogger(__name__)

_dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("REGION", "us-east-1"))

CHAT_HISTORY_TABLE_NAME = os.environ.get("CHAT_HISTORY_TABLE", "")
NOTICES_TABLE_NAME      = os.environ.get("NOTICES_TABLE", "")

_TTL_SECONDS_90_DAYS = 90 * 24 * 3600
_HISTORY_LIMIT       = 20   # GET /chat/history 기본 페이지 크기
_CONTEXT_LIMIT       = 5    # 최근 대화 컨텍스트 가져올 교환 수 (user+assistant 각각)


def _chat_table():
    return _dynamodb.Table(CHAT_HISTORY_TABLE_NAME)


def _notices_table():
    return _dynamodb.Table(NOTICES_TABLE_NAME)


# ── ChatHistory 테이블 ──────────────────────────────────────────

def save_chat_message(
    user_id: str,
    session_id: str,
    role: str,
    content: str,
) -> ChatHistoryItem:
    """
    대화 메시지를 ChatHistory 테이블에 저장.

    SK 형식: {sessionId}#{createdAt}  (DynamoDB 스키마의 속성명 그대로 사용)
    """
    now_iso  = datetime.now(timezone.utc).isoformat()
    sort_key = f"{session_id}#{now_iso}"
    expires  = math.floor(time.time()) + _TTL_SECONDS_90_DAYS

    item = ChatHistoryItem(
        user_id=user_id,
        session_id=session_id,
        role=role,
        content=content,
        created_at=now_iso,
        expires_at=expires,
    )

    _chat_table().put_item(
        Item={
            "userId":          user_id,
            "sessionId#createdAt": sort_key,
            "sessionId":       session_id,
            "role":            role,
            "content":         content,
            "createdAt":       now_iso,
            "expiresAt":       expires,
        }
    )
    logger.info({"message": "chat message saved", "role": role, "sessionId": session_id})
    return item


def get_recent_messages(user_id: str, session_id: str, limit: int = _CONTEXT_LIMIT * 2) -> list[dict]:
    """
    특정 세션의 최근 대화 이력 조회 (오래된 순 정렬).

    limit: 가져올 최대 메시지 수 (기본: 10 = 5회 교환)
    """
    # SK 범위: sessionId# 이상 sessionId#~ 미만
    sk_prefix = f"{session_id}#"
    resp = _chat_table().query(
        KeyConditionExpression=(
            Key("userId").eq(user_id) &
            Key("sessionId#createdAt").begins_with(sk_prefix)
        ),
        ScanIndexForward=False,   # 최신 먼저
        Limit=limit,
    )
    items = resp.get("Items", [])
    # 최신 먼저 가져왔으므로 역순으로 반환 (오래된 순)
    return list(reversed(items))


def get_chat_history(
    user_id: str,
    limit: int = _HISTORY_LIMIT,
    exclusive_start_key: Optional[dict] = None,
) -> tuple[list[dict], Optional[dict]]:
    """
    GET /chat/history — 사용자의 전체 대화 이력 (최신 순).

    Returns (items, last_evaluated_key).
    last_evaluated_key가 None이면 마지막 페이지.
    """
    kwargs: dict = {
        "KeyConditionExpression": Key("userId").eq(user_id),
        "ScanIndexForward": False,
        "Limit": limit,
    }
    if exclusive_start_key:
        kwargs["ExclusiveStartKey"] = exclusive_start_key

    resp = _chat_table().query(**kwargs)
    return resp.get("Items", []), resp.get("LastEvaluatedKey")


# ── Notices 테이블 ─────────────────────────────────────────────

def get_notice_by_id(notice_id: str) -> Optional[dict]:
    """
    noticeId-index GSI로 공지 단건 조회.
    공지 연계 모드에서 컨텍스트 제공용으로 사용.
    """
    resp = _notices_table().query(
        IndexName="noticeId-index",
        KeyConditionExpression=Key("noticeId").eq(notice_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None
