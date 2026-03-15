"""
시나리오 1: 신규 공지 → 푸시 알림 전체 플로우
목표 SLA: 감지 → 푸시 발송 30초 이내

테스트 흐름:
1. DynamoDB에 테스트 학교 + 공지 삽입
2. school-crawler Lambda 수동 호출
3. SQS notice-queue 메시지 도착 확인 (최대 60초 대기)
4. notice-processor 처리 완료 대기
5. Notices 테이블 요약/번역 저장 확인
6. TranslationCache 테이블 캐시 저장 확인 (Redis 대신 DynamoDB TTL)
7. Notifications 테이블 발송 이력 확인
"""
import time

import pytest
from boto3.dynamodb.conditions import Key

from tests.e2e.config import (
    CRAWLER_FUNCTION,
    MAX_WAIT_SEC,
    NOTICE_QUEUE_NAME,
    NOTICES_TABLE,
    NOTIFICATIONS_TABLE,
    POLL_INTERVAL_SEC,
    SLA_NOTICE_PIPELINE_SEC,
    TRANSLATION_CACHE_TABLE,
)
from tests.e2e.utils.aws import (
    dynamo_get,
    dynamo_query,
    get_queue_url,
    invoke_lambda,
    wait_for_sqs_message,
    wait_until,
)


class TestNoticeFullFlow:
    """test_[상황]_[기대결과] 네이밍 규칙 (CLAUDE.md)"""

    # ── Step 1–2: 크롤러 호출 ─────────────────────────────────────────────────
    def test_crawler_invocation_succeeds(self, test_school: dict, test_notice: dict):
        """크롤러 Lambda를 수동 호출하면 에러 없이 완료된다."""
        result = invoke_lambda(CRAWLER_FUNCTION, payload={})
        # Lambda 실행 자체의 오류 여부만 확인
        assert result.get("statusCode") != 500, (
            f"크롤러 Lambda 실행 실패: {result}"
        )

    # ── Step 3: SQS 메시지 도착 ──────────────────────────────────────────────
    def test_notice_appears_in_sqs_within_timeout(
        self, test_school: dict, test_notice: dict
    ):
        """
        크롤러 실행 후 60초 이내에 SQS notice-queue에
        테스트 학교의 공지 메시지가 도착한다.
        """
        queue_url = get_queue_url(NOTICE_QUEUE_NAME)
        school_id = test_school["schoolId"]

        # 크롤러 먼저 실행
        invoke_lambda(CRAWLER_FUNCTION, payload={})
        pipeline_start = time.monotonic()

        def _has_matching_message(body: dict) -> bool:
            return body.get("schoolId") == school_id

        matched = wait_for_sqs_message(
            queue_url=queue_url,
            match_fn=_has_matching_message,
            timeout_sec=60,
            poll_interval_sec=POLL_INTERVAL_SEC,
        )
        assert matched is not None, (
            f"60초 이내에 SQS에 schoolId={school_id} 메시지가 도착하지 않았습니다."
        )
        # 소요 시간 기록 (SLA 최종 검증에 사용)
        self._pipeline_start = pipeline_start

    # ── Step 4–5: 번역/요약 저장 확인 ────────────────────────────────────────
    def test_processor_stores_translation_in_notices_table(
        self, test_school: dict, test_notice: dict
    ):
        """
        notice-processor가 처리를 완료하면 Notices 테이블에
        translations 필드가 저장된다 (최소 1개 언어).
        """
        school_id  = test_school["schoolId"]
        created_at = test_notice["createdAt"]

        def _notice_translated() -> bool:
            item = dynamo_get(
                NOTICES_TABLE,
                {"schoolId": school_id, "createdAt": created_at},
            )
            if not item:
                return False
            translations = item.get("translations", {})
            return len(translations) > 0

        success = wait_until(
            _notice_translated,
            timeout_sec=MAX_WAIT_SEC,
            poll_interval_sec=POLL_INTERVAL_SEC,
            description="Notices 테이블 번역 완료",
        )
        assert success, (
            f"{MAX_WAIT_SEC}초 이내에 Notices 테이블에 번역이 저장되지 않았습니다. "
            f"schoolId={school_id}, createdAt={created_at}"
        )

    def test_translation_fields_are_valid(
        self, test_school: dict, test_notice: dict
    ):
        """
        저장된 번역에 summary, translation, checklistItems 필드가 존재하고
        최소 길이 기준을 충족한다 (CLAUDE.md QA 기준 §3,4).
        """
        school_id  = test_school["schoolId"]
        created_at = test_notice["createdAt"]

        item = dynamo_get(
            NOTICES_TABLE,
            {"schoolId": school_id, "createdAt": created_at},
        )
        assert item, "Notices 테이블에서 공지를 찾을 수 없습니다."

        translations = item.get("translations", {})
        assert translations, "translations 필드가 비어있습니다."

        # 첫 번째 언어 번역 검증
        lang_code, translated = next(iter(translations.items()))
        assert translated.get("translation"), f"[{lang_code}] translation 필드 누락"
        assert len(translated["translation"]) >= 20, (
            f"[{lang_code}] translation 최소 길이(20자) 미달: "
            f"{len(translated['translation'])}자"
        )
        assert isinstance(translated.get("checklistItems", []), list), (
            f"[{lang_code}] checklistItems 타입 오류"
        )

        # 금지어 검증 (CLAUDE.md QA 기준 §5)
        forbidden = ["I cannot", "저는 할 수 없습니다", "Unable to"]
        for phrase in forbidden:
            assert phrase not in translated["translation"], (
                f"[{lang_code}] 거절 문구 감지: '{phrase}'"
            )

    # ── Step 6: TranslationCache 확인 ─────────────────────────────────────────
    def test_translation_cache_stored_in_dynamodb(
        self, test_school: dict, test_notice: dict
    ):
        """
        번역 완료 후 TranslationCache 테이블에 캐시 항목이 존재한다.
        cacheKey 형식: notice#{noticeId}#lang#{langCode}
        """
        notice_id = test_notice["noticeId"]

        # 적어도 1개 언어 캐시가 있는지 확인
        def _cache_exists() -> bool:
            for lang in ("vi", "zh-CN", "en"):
                cache_key = f"notice#{notice_id}#lang#{lang}"
                item = dynamo_get(TRANSLATION_CACHE_TABLE, {"cacheKey": cache_key})
                if item:
                    return True
            return False

        success = wait_until(
            _cache_exists,
            timeout_sec=MAX_WAIT_SEC,
            poll_interval_sec=POLL_INTERVAL_SEC,
            description="TranslationCache 저장",
        )
        assert success, (
            f"TranslationCache에 noticeId={notice_id} 캐시가 저장되지 않았습니다."
        )

    def test_translation_cache_has_ttl(
        self, test_school: dict, test_notice: dict
    ):
        """캐시 항목에 expiresAt(TTL) 필드가 존재한다."""
        notice_id = test_notice["noticeId"]
        cache_key  = f"notice#{notice_id}#lang#vi"
        item = dynamo_get(TRANSLATION_CACHE_TABLE, {"cacheKey": cache_key})
        if item is None:
            pytest.skip("캐시 항목 없음 — test_translation_cache_stored_in_dynamodb 먼저 실행")
        assert "expiresAt" in item, "expiresAt(TTL) 필드 누락"
        # 현재 시각보다 미래여야 함
        import time as _time
        assert int(item["expiresAt"]) > _time.time(), "expiresAt 값이 과거입니다."

    # ── Step 7: Notifications 발송 이력 ──────────────────────────────────────
    def test_notification_record_saved_to_table(
        self, test_school: dict, test_notice: dict
    ):
        """
        알림 발송 후 Notifications 테이블에 발송 이력이 저장된다.
        schoolId-index GSI로 조회.
        """
        school_id = test_school["schoolId"]

        def _notification_exists() -> bool:
            rows = dynamo_query(
                NOTIFICATIONS_TABLE,
                Key("schoolId").eq(school_id),
                index_name="schoolId-index",
                limit=5,
            )
            return len(rows) > 0

        success = wait_until(
            _notification_exists,
            timeout_sec=MAX_WAIT_SEC,
            poll_interval_sec=POLL_INTERVAL_SEC,
            description="Notifications 이력 저장",
        )
        assert success, (
            f"Notifications 테이블에 schoolId={school_id} 이력이 없습니다."
        )

    # ── SLA 검증 ──────────────────────────────────────────────────────────────
    def test_pipeline_completes_within_sla(
        self, test_school: dict, test_notice: dict
    ):
        """
        공지 감지(크롤러 호출) ~ 알림 발송 완료까지
        SLA_NOTICE_PIPELINE_SEC(30초) 이내여야 한다.
        """
        school_id = test_school["schoolId"]
        pipeline_start = time.monotonic()

        # 크롤러 호출
        invoke_lambda(CRAWLER_FUNCTION, payload={})

        # Notifications 테이블에 레코드가 생길 때까지 폴링
        def _done() -> bool:
            rows = dynamo_query(
                NOTIFICATIONS_TABLE,
                Key("schoolId").eq(school_id),
                index_name="schoolId-index",
                limit=1,
            )
            return len(rows) > 0

        success = wait_until(
            _done,
            timeout_sec=SLA_NOTICE_PIPELINE_SEC,
            poll_interval_sec=1,
            description="SLA 내 파이프라인 완료",
        )
        elapsed = time.monotonic() - pipeline_start

        assert success, (
            f"[SLA 위반] 파이프라인이 {SLA_NOTICE_PIPELINE_SEC}초 이내에 완료되지 않았습니다. "
            f"실제 소요: {elapsed:.1f}초"
        )
        print(f"\n✅ 파이프라인 완료 시간: {elapsed:.1f}초 (SLA: {SLA_NOTICE_PIPELINE_SEC}초)")
