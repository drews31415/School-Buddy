"""
DynamoDB 접근 유틸 (processor 전용).

테이블:
  Notices          — PK: schoolId  SK: createdAt  GSI: noticeId-index
  TranslationCache — PK: cacheKey

모듈 레벨 boto3 리소스 초기화 (cold-start 최적화).
"""
from __future__ import annotations

import logging
import math
import os
import time
from typing import Optional

import boto3
from boto3.dynamodb.conditions import Key

from .models import SQSNoticePayload, SummaryResult, ImportanceResult, TranslationResult

logger = logging.getLogger(__name__)

# ── 클라이언트 (모듈 레벨) ──────────────────────────────────────
_dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("REGION", "us-east-1"))

NOTICES_TABLE_NAME          = os.environ.get("NOTICES_TABLE", "")
TRANSLATION_CACHE_TABLE_NAME = os.environ.get("TRANSLATION_CACHE_TABLE", "")


def _notices_table():
    return _dynamodb.Table(NOTICES_TABLE_NAME)


def _cache_table():
    return _dynamodb.Table(TRANSLATION_CACHE_TABLE_NAME)


# ── Notices 테이블 ─────────────────────────────────────────────

def is_notice_duplicate(notice_id: str) -> bool:
    """
    noticeId-index GSI로 중복 여부 확인.
    SQS at-least-once 재전달 시 멱등성 보장에 사용.
    """
    resp = _notices_table().query(
        IndexName="noticeId-index",
        KeyConditionExpression=Key("noticeId").eq(notice_id),
        Limit=1,
        ProjectionExpression="noticeId",
    )
    return len(resp.get("Items", [])) > 0


def save_notice(
    payload: SQSNoticePayload,
    summary: SummaryResult,
    importance: ImportanceResult,
) -> str:
    """
    처리된 공지를 Notices 테이블에 저장.

    SK 값은 '{crawledAt}#{noticeId}' 복합 문자열로 구성한다.
    같은 학교의 같은 크롤링 배치에서 복수 공지가 들어와도 SK 충돌 없이 저장된다.

    Returns
    -------
    str : 저장에 사용된 SK 값 (translations 업데이트 시 필요)
    """
    # PK(schoolId) + SK(crawledAt#noticeId) 조합으로 유일성 보장
    sort_key = f"{payload.crawledAt}#{payload.noticeId}"

    _notices_table().put_item(
        Item={
            "schoolId":        payload.schoolId,
            "createdAt":       sort_key,          # SK
            "noticeId":        payload.noticeId,  # GSI PK
            "title":           payload.title,
            "sourceUrl":       payload.sourceUrl,
            "originalText":    payload.originalText,
            "publishedAt":     payload.publishedAt,
            "crawledAt":       payload.crawledAt,
            "summary":         summary.summary,
            "keywords":        summary.keywords,
            "importance":      importance.importance,
            "importanceReason": importance.reason,
            "translations":    {},  # 번역 완료 후 update_notice_translations()로 갱신
        },
        ConditionExpression="attribute_not_exists(schoolId) AND attribute_not_exists(createdAt)",
    )
    logger.info(
        {
            "message": "notice saved",
            "noticeId": payload.noticeId,
            "schoolId": payload.schoolId,
            "importance": importance.importance,
        }
    )
    return sort_key


def update_notice_translations(
    school_id: str,
    sort_key: str,
    translations: dict[str, dict],
) -> None:
    """Notices 테이블의 translations 필드를 업데이트."""
    _notices_table().update_item(
        Key={"schoolId": school_id, "createdAt": sort_key},
        UpdateExpression="SET translations = :t",
        ExpressionAttributeValues={":t": translations},
    )


# ── TranslationCache 테이블 ────────────────────────────────────

# cacheKey 형식: notice#{noticeId}#lang#{langCode}
# shared-utils/src/cache.ts buildCacheKey()와 동일한 포맷

def build_cache_key(notice_id: str, lang_code: str) -> str:
    return f"notice#{notice_id}#lang#{lang_code}"


def get_cached_translation(cache_key: str) -> Optional[dict]:
    """
    번역 캐시 조회. 없거나 만료됐으면 None 반환.
    TTL 만료는 DynamoDB가 자동 처리하므로 expiresAt 비교 불필요.
    """
    resp = _cache_table().get_item(Key={"cacheKey": cache_key})
    item = resp.get("Item")
    if not item:
        return None
    return item.get("translationData")


def set_cached_translation(
    cache_key: str,
    translation_data: dict,
    ttl_hours: int = 24,
) -> None:
    """번역 결과를 TranslationCache 테이블에 저장 (TTL: ttl_hours)."""
    expires_at = math.floor(time.time()) + ttl_hours * 3600
    try:
        _cache_table().put_item(
            Item={
                "cacheKey":        cache_key,
                "translationData": translation_data,
                "expiresAt":       expires_at,
            }
        )
    except Exception as e:
        # 캐시 저장 실패는 메인 플로우를 중단하지 않음
        logger.warning({"message": "번역 캐시 저장 실패", "cacheKey": cache_key, "error": str(e)})
