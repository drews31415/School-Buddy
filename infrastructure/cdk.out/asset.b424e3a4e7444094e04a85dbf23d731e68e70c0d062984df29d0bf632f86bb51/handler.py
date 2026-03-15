"""
notice-processor Lambda handler (Python 3.12)

트리거: SQS notice-queue (batchSize=10, reportBatchItemFailures=true)
역할:   공지 중복 제거 → DynamoDB 저장 → Bedrock 요약/번역/중요도 판단 → SNS 발행

처리 흐름:
  1. SQS 메시지 파싱 (SQSNoticePayload)
  2. noticeId GSI 조회로 중복 확인 (SQS at-least-once 멱등성)
  3. Bedrock AI 파이프라인 (요약 → 중요도 → 8개국어 번역)
     - 번역 전 TranslationCache 조회 → 캐시 히트 시 Bedrock 호출 생략
  4. DynamoDB Notices 테이블에 저장 및 translations 업데이트
  5. SNS notice-topic 발행 → notification-sender Lambda 트리거
  6. 실패한 레코드만 batchItemFailures로 반환 (부분 실패 처리)

환경변수:
  NOTICES_TABLE          DynamoDB Notices 테이블명
  TRANSLATION_CACHE_TABLE DynamoDB TranslationCache 테이블명
  NOTICE_TOPIC_ARN       SNS notice-topic ARN
  BEDROCK_MODEL_ID       Bedrock 모델 ID
  MAX_TOKENS_SUMMARY     최대 요약 토큰 (기본: 500)
  MAX_TOKENS_TRANSLATION 최대 번역 토큰 (기본: 800)
  REGION                 AWS 리전 (기본: us-east-1)
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

from processor.models import SQSNoticePayload, ALL_LANGUAGE_CODES
from processor.db import (
    is_notice_duplicate,
    save_notice,
    update_notice_translations,
    get_cached_translation,
    set_cached_translation,
    build_cache_key,
)
from processor.ai import summarize, judge_importance, translate
from processor.publisher import publish_processed_notice, PublishError


def handler(event: dict, context) -> dict:
    """
    SQSEvent 핸들러.

    Parameters
    ----------
    event : dict
        SQS 이벤트. Records 배열에 최대 10개 메시지.
    context : LambdaContext
        Lambda 런타임 컨텍스트.

    Returns
    -------
    dict
        {"batchItemFailures": [{"itemIdentifier": messageId}, ...]}
        성공한 레코드는 SQS가 자동 삭제. 실패한 레코드는 재전달 또는 DLQ로 이동.
    """
    batch_item_failures: list[dict] = []

    logger.info(
        {
            "message": "processor started",
            "record_count": len(event.get("Records", [])),
        }
    )

    for record in event.get("Records", []):
        message_id = record["messageId"]
        notice_id = "(unknown)"

        try:
            payload = SQSNoticePayload.from_dict(json.loads(record["body"]))
            notice_id = payload.noticeId

            logger.info(
                {
                    "message": "processing notice",
                    "noticeId": notice_id,
                    "schoolId": payload.schoolId,
                }
            )

            # ── 1. 중복 체크 (SQS at-least-once 멱등성) ────────────
            if is_notice_duplicate(notice_id):
                logger.info(
                    {"message": "duplicate notice skipped", "noticeId": notice_id}
                )
                continue  # 중복은 성공으로 처리 (failures에 포함 안 함)

            # ── 2. Bedrock AI 파이프라인: 요약 → 중요도 ────────────
            # 번역은 캐시 체크 후 별도 처리
            summary_result    = summarize(payload.originalText, payload.title)
            importance_result = judge_importance(summary_result.summary)

            # ── 3. DynamoDB 저장 (translations는 빈 맵으로 초기화) ──
            sort_key = save_notice(payload, summary_result, importance_result)

            # ── 4. 번역 (캐시 히트 우선, 미스 시 Bedrock 호출) ──────
            translations: dict[str, dict] = {}
            for lang_code in ALL_LANGUAGE_CODES:
                cache_key = build_cache_key(notice_id, lang_code)

                cached = get_cached_translation(cache_key)
                if cached:
                    logger.info(
                        {"message": "translation cache hit", "lang": lang_code, "noticeId": notice_id}
                    )
                    translations[lang_code] = cached
                else:
                    try:
                        result = translate(summary_result.summary, lang_code)
                        translations[lang_code] = result.to_dict()
                        set_cached_translation(cache_key, result.to_dict())
                    except Exception as e:
                        logger.error(
                            {
                                "message": "translation failed",
                                "lang": lang_code,
                                "noticeId": notice_id,
                                "error": str(e),
                            }
                        )
                        # 개별 언어 번역 실패는 빈값으로 채우고 계속 진행
                        translations[lang_code] = {
                            "translation": "",
                            "culturalTip": "",
                            "checklistItems": [],
                        }

            # ── 5. DynamoDB translations 업데이트 ──────────────────
            update_notice_translations(payload.schoolId, sort_key, translations)

            # ── 6. SNS 발행 ────────────────────────────────────────
            publish_processed_notice(
                payload=payload,
                summary=summary_result,
                importance=importance_result,
                translations=translations,
            )

            logger.info(
                {
                    "message": "notice processed successfully",
                    "noticeId": notice_id,
                    "importance": importance_result.importance,
                    "translated_langs": len(translations),
                }
            )

        except Exception as exc:
            logger.error(
                {
                    "message": "notice processing failed",
                    "noticeId": notice_id,
                    "messageId": message_id,
                    "error": str(exc),
                }
            )
            # 이 레코드만 실패 처리 → SQS가 재전달 또는 DLQ로 이동
            batch_item_failures.append({"itemIdentifier": message_id})

    logger.info(
        {
            "message": "processor finished",
            "total": len(event.get("Records", [])),
            "failures": len(batch_item_failures),
        }
    )
    return {"batchItemFailures": batch_item_failures}
