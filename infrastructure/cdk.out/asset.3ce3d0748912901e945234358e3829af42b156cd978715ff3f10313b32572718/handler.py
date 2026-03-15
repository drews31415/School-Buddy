"""
school-crawler Lambda handler (Python 3.12)

트리거: EventBridge Scheduler (30분 주기)
역할:   학교 공지 페이지 크롤링 → 신규 공지를 SQS notice-queue에 발행

환경변수:
  SCHOOLS_TABLE         DynamoDB Schools 테이블명
  NOTICES_TABLE         DynamoDB Notices 테이블명
  NOTICE_QUEUE_URL      SQS notice-queue URL
  NOTICE_TOPIC_ARN      SNS 운영 알람용 토픽 ARN
  REGION                AWS 리전 (기본: us-east-1)
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from crawler.db import (
    get_active_schools,
    get_recent_source_urls,
    update_school_error,
    update_school_success,
)
from crawler.fetcher import FetchError, fetch_html
from crawler.models import SQSNoticePayload
from crawler.parser import parse_notices
from crawler.publisher import PublishError, publish_notice, publish_ops_alarm

# ── 로거 설정 ─────────────────────────────────────────────
logger = logging.getLogger()
logger.setLevel(logging.INFO)

MAX_CONSECUTIVE_ERRORS = 3  # 연속 실패 임계치 → crawlStatus = ERROR


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda 진입점.

    Parameters
    ----------
    event : dict
        EventBridge ScheduledEvent. 크롤러 로직에서는 사용하지 않음.
    context : LambdaContext
        Lambda 런타임 컨텍스트.

    Returns
    -------
    dict
        실행 결과 요약:
        {
            "processed": int,    # 크롤링 시도 학교 수
            "new_notices": int,  # 발행된 신규 공지 수
            "errors": int        # 실패한 학교 수
        }

    Raises
    ------
    없음 — 개별 학교 오류는 내부에서 처리하며 핸들러 자체는 항상 정상 종료.
    """
    logger.info({"message": "crawler started", "event": event})

    schools = get_active_schools()
    logger.info({"message": f"{len(schools)} active schools found"})

    results = {"processed": 0, "new_notices": 0, "errors": 0}

    for school in schools:
        crawled_at = _now_iso()
        try:
            new_count = _crawl_school(school, crawled_at)
            update_school_success(school.schoolId, crawled_at)
            results["processed"] += 1
            results["new_notices"] += new_count

        except (FetchError, PublishError, Exception) as exc:
            results["errors"] += 1
            next_consecutive = school.consecutiveErrors + 1
            mark_error = next_consecutive >= MAX_CONSECUTIVE_ERRORS

            logger.error(
                {
                    "message": "school crawl failed",
                    "schoolId": school.schoolId,
                    "error": str(exc),
                    "consecutiveErrors": next_consecutive,
                    "markError": mark_error,
                }
            )

            update_school_error(
                school_id=school.schoolId,
                error_at=crawled_at,
                error_message=str(exc),
                consecutive_errors=next_consecutive,
                mark_error=mark_error,
            )

            if mark_error:
                publish_ops_alarm(
                    school_id=school.schoolId,
                    school_name=school.name,
                    error_message=str(exc),
                )

    logger.info({"message": "crawler finished", "results": results})
    return results


# ── 내부 함수 ──────────────────────────────────────────────

def _crawl_school(school, crawled_at: str) -> int:
    """
    단일 학교 크롤링 → 신규 공지 발행.

    Returns
    -------
    int : 발행된 신규 공지 수
    """
    logger.info({"message": "crawling school", "schoolId": school.schoolId, "url": school.noticeUrl})

    # 1. HTML 다운로드
    html = fetch_html(school.noticeUrl)

    # 2. 공지 목록 파싱
    raw_notices = parse_notices(html, school.noticeUrl)

    if not raw_notices:
        logger.info({"message": "no notices found", "schoolId": school.schoolId})
        return 0

    # 3. 기존 공지 URL 조회 → diff
    existing_urls = get_recent_source_urls(school.schoolId)
    new_notices = [n for n in raw_notices if n.url not in existing_urls]

    logger.info(
        {
            "message": "diff result",
            "schoolId": school.schoolId,
            "total": len(raw_notices),
            "new": len(new_notices),
        }
    )

    # 4. 신규 공지 SQS 발행
    for raw in new_notices:
        payload = SQSNoticePayload(
            noticeId=str(uuid.uuid4()),
            schoolId=school.schoolId,
            title=raw.title,
            sourceUrl=raw.url,
            originalText=raw.content,
            publishedAt=raw.published_at or crawled_at,
            crawledAt=crawled_at,
        )
        publish_notice(payload)

    return len(new_notices)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
