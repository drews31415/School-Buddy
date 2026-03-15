"""
DynamoDB 접근 유틸 (크롤러 전용 Python 래퍼).
boto3 클라이언트는 모듈 최상단에서 초기화 (cold-start 최적화).
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key

from .models import SchoolRecord

logger = logging.getLogger(__name__)

# ── 클라이언트 (모듈 레벨 초기화) ─────────────────────────
_dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("REGION", "us-east-1"))

SCHOOLS_TABLE_NAME = os.environ.get("SCHOOLS_TABLE", "")
NOTICES_TABLE_NAME = os.environ.get("NOTICES_TABLE", "")


def _schools_table():
    return _dynamodb.Table(SCHOOLS_TABLE_NAME)


def _notices_table():
    return _dynamodb.Table(NOTICES_TABLE_NAME)


# ── Schools 테이블 ─────────────────────────────────────────

def get_active_schools() -> List[SchoolRecord]:
    """
    crawlStatus = 'ACTIVE' 인 학교 목록 전체 조회.
    ⚠️ Scan 사용 — 학교 수가 적어 허용. 학교 수가 1,000개 이상이 되면 GSI 도입 검토.
    """
    table = _schools_table()
    items = []
    kwargs = {"FilterExpression": Attr("crawlStatus").eq("ACTIVE")}

    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key

    return [
        SchoolRecord(
            schoolId=item["schoolId"],
            name=item.get("name", ""),
            noticeUrl=item["noticeUrl"],
            crawlStatus=item.get("crawlStatus", "ACTIVE"),
            lastCrawledAt=item.get("lastCrawledAt"),
            consecutiveErrors=int(item.get("consecutiveErrors", 0)),
        )
        for item in items
    ]


def update_school_success(school_id: str, crawled_at: str) -> None:
    """크롤링 성공 시 lastCrawledAt 갱신, consecutiveErrors 초기화."""
    _schools_table().update_item(
        Key={"schoolId": school_id},
        UpdateExpression=(
            "SET lastCrawledAt = :ts, crawlStatus = :status, consecutiveErrors = :zero"
        ),
        ExpressionAttributeValues={
            ":ts": crawled_at,
            ":status": "ACTIVE",
            ":zero": 0,
        },
    )


def update_school_error(
    school_id: str,
    error_at: str,
    error_message: str,
    consecutive_errors: int,
    mark_error: bool,
) -> None:
    """
    크롤링 실패 시 오류 정보 기록.
    mark_error=True 이면 crawlStatus를 'ERROR'로 변경.
    """
    status = "ERROR" if mark_error else "ACTIVE"
    _schools_table().update_item(
        Key={"schoolId": school_id},
        UpdateExpression=(
            "SET lastErrorAt = :ts, lastErrorMessage = :msg, "
            "consecutiveErrors = :cnt, crawlStatus = :status"
        ),
        ExpressionAttributeValues={
            ":ts": error_at,
            ":msg": error_message[:500],  # DynamoDB String 길이 제한 방어
            ":cnt": consecutive_errors,
            ":status": status,
        },
    )


# ── Notices 테이블 ─────────────────────────────────────────

def get_recent_source_urls(school_id: str, limit: int = 100) -> set:
    """
    최근 공지 sourceUrl 목록 조회 → 중복 감지에 사용.
    SK(createdAt) 내림차순 정렬로 최근 limit건만 가져온다.
    """
    resp = _notices_table().query(
        KeyConditionExpression=Key("schoolId").eq(school_id),
        ProjectionExpression="sourceUrl",
        ScanIndexForward=False,
        Limit=limit,
    )
    return {item["sourceUrl"] for item in resp.get("Items", []) if "sourceUrl" in item}
