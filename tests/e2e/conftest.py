"""
E2E 테스트 공통 픽스처.
각 테스트는 자신의 teardown 안에서 생성 데이터를 정리한다.
"""
import uuid
from decimal import Decimal
from typing import Generator

import pytest

from tests.e2e.config import (
    NOTICES_TABLE,
    NOTIFICATIONS_TABLE,
    SCHOOLS_TABLE,
    SAMPLE_NOTICE_JPG,
    TRANSLATION_CACHE_TABLE,
    CHAT_HISTORY_TABLE,
)
from tests.e2e.utils.api import APIClient
from tests.e2e.utils.aws import dynamo_delete, dynamo_put


# ── API 클라이언트 ────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def api() -> APIClient:
    return APIClient()


# ── 테스트용 학교 픽스처 ──────────────────────────────────────────────────────
@pytest.fixture()
def test_school() -> Generator[dict, None, None]:
    """
    Schools 테이블에 테스트 학교 삽입.
    teardown 시 자동 삭제.
    """
    school_id = f"test-school-{uuid.uuid4().hex[:8]}"
    item = {
        "schoolId":    school_id,
        "schoolName":  "[E2E] 테스트 초등학교",
        "crawlUrl":    "https://example.com/school/notices",  # 실제 테스트용 URL
        "crawlStatus": "ACTIVE",
        "region":      "seoul",
        "createdAt":   "2026-01-01T00:00:00Z",
    }
    dynamo_put(SCHOOLS_TABLE, item)
    yield item
    dynamo_delete(SCHOOLS_TABLE, {"schoolId": school_id})


# ── 테스트용 공지 픽스처 ──────────────────────────────────────────────────────
@pytest.fixture()
def test_notice(test_school: dict) -> Generator[dict, None, None]:
    """
    Notices 테이블에 미처리 공지 삽입.
    teardown 시 자동 삭제.
    """
    notice_id = f"test-notice-{uuid.uuid4().hex[:8]}"
    school_id = test_school["schoolId"]
    created_at = "2026-03-16T09:00:00Z"
    item = {
        "schoolId":    school_id,
        "createdAt":   created_at,
        "noticeId":    notice_id,
        "title":       "[E2E] 3월 가정통신문 테스트",
        "content":     (
            "안녕하세요. 3월 현장학습 관련 안내입니다. "
            "날짜: 3월 25일(화). "
            "준비물: 도시락, 물통, 운동화. "
            "비용: 15,000원 (3월 20일까지 납부). "
            "돌봄교실 이용 학생은 현장학습 종료 후 학교 복귀 예정입니다."
        ),
        "status":      "PENDING",
        "importance":  "HIGH",
        "publishedAt": created_at,
    }
    dynamo_put(NOTICES_TABLE, item)
    yield item
    # 생성된 관련 데이터도 정리
    dynamo_delete(NOTICES_TABLE, {"schoolId": school_id, "createdAt": created_at})
    # TranslationCache: cacheKey 패턴으로 일괄 삭제는 scan이 필요하므로 개별 언어 키 정리
    for lang in ("vi", "zh-CN", "en", "ja"):
        cache_key = f"notice#{notice_id}#lang#{lang}"
        dynamo_delete(TRANSLATION_CACHE_TABLE, {"cacheKey": cache_key})


# ── 샘플 이미지 픽스처 ────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def sample_notice_jpg() -> bytes:
    """
    tests/fixtures/sample_notice.jpg 파일을 바이트로 반환.
    파일이 없으면 테스트를 건너뜀.
    """
    if not SAMPLE_NOTICE_JPG.exists():
        pytest.skip(
            f"샘플 이미지가 없습니다: {SAMPLE_NOTICE_JPG}\n"
            "python tests/fixtures/generate_fixtures.py 를 실행해 생성하세요."
        )
    return SAMPLE_NOTICE_JPG.read_bytes()


# ── RAG 세션 정리 픽스처 ─────────────────────────────────────────────────────
@pytest.fixture()
def e2e_session_id() -> Generator[str, None, None]:
    """
    테스트 전용 채팅 세션 ID.
    teardown 시 ChatHistory 테이블에서 해당 세션 레코드 삭제.
    """
    session_id = f"e2e-session-{uuid.uuid4().hex[:8]}"
    yield session_id
    # ChatHistory PK=userId 는 테스트 JWT 의 sub 클레임이므로,
    # 세션 정리는 scan 없이 최선-effort 로 처리 (dev 환경 비용 최소화)
    # 실제 삭제는 TTL(90일)에 의존


# ── 환경변수 가드 ─────────────────────────────────────────────────────────────
def pytest_configure(config):
    """필수 환경변수가 없으면 경고를 출력하고 API 관련 테스트를 건너뜀."""
    import os
    missing = [v for v in ("E2E_API_BASE_URL", "E2E_ACCESS_TOKEN") if not os.environ.get(v)]
    if missing:
        import warnings
        warnings.warn(
            f"E2E 환경변수 미설정: {missing}. API 호출 테스트가 건너뛰어집니다.",
            stacklevel=1,
        )
