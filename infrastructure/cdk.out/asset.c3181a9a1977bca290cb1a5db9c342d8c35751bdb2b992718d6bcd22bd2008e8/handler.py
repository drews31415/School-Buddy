"""
school-crawler Lambda handler (Python 3.12)
EventBridge 스케줄에 의해 트리거. 학교 홈페이지를 크롤링하여 신규 공지를 notice-queue에 발행.
"""
import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

NOTICE_QUEUE_URL = os.environ.get("NOTICE_QUEUE_URL", "")
SCHOOLS_TABLE = os.environ.get("SCHOOLS_TABLE", "")


def handler(event: dict, context) -> dict:
    """
    EventBridge ScheduledEvent 핸들러.
    TODO: BeautifulSoup / Playwright 기반 크롤링 구현
    """
    logger.info({"message": "crawler triggered", "event": event})

    # TODO: 크롤링 대상 학교 목록 조회 → 병렬 크롤링 → SQS 발행

    return {"statusCode": 200, "body": "crawler executed"}
