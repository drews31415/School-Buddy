"""
handler.py 단위 테스트.

Bedrock (AI) 호출은 unittest.mock.patch 로 격리한다.
DynamoDB / SNS 는 moto 로 모킹한다.
"""
import json
from unittest.mock import patch, MagicMock

import pytest

import handler as handler_module
from processor.models import SummaryResult, ImportanceResult, TranslationResult

# ── 공통 픽스처 데이터 ─────────────────────────────────────────
SCHOOL_ID  = "school-001"
NOTICE_ID  = "notice-uuid-0001"
SOURCE_URL = "https://school.example.com/notice/1"

SQS_BODY = {
    "noticeId":     NOTICE_ID,
    "schoolId":     SCHOOL_ID,
    "title":        "10월 현장학습 안내",
    "sourceUrl":    SOURCE_URL,
    "originalText": "10월 15일 서울대공원으로 현장학습을 갑니다. 참가비 15,000원.",
    "publishedAt":  "2025-10-01T00:00:00+00:00",
    "crawledAt":    "2025-10-01T03:00:00+00:00",
}

def _make_sqs_event(*bodies: dict) -> dict:
    return {
        "Records": [
            {"messageId": f"msg-{i}", "body": json.dumps(b)}
            for i, b in enumerate(bodies)
        ]
    }

MOCK_SUMMARY    = SummaryResult(summary="현장학습 안내 요약입니다.", keywords=["현장학습", "참가비"])
MOCK_IMPORTANCE = ImportanceResult(importance="HIGH", reason="참가비 납부 및 동의서 제출 필요")
MOCK_TRANSLATION = TranslationResult(
    translation="Thông báo học thực địa",
    culturalTip="Tip văn hóa",
    checklistItems=["Nộp phí 15.000 won"],
)


def _patch_ai(summary=MOCK_SUMMARY, importance=MOCK_IMPORTANCE, translation=MOCK_TRANSLATION):
    """AI 함수 3개를 한 번에 패치하는 컨텍스트 매니저 팩토리."""
    return (
        patch("handler.summarize",        return_value=summary),
        patch("handler.judge_importance", return_value=importance),
        patch("handler.translate",        return_value=translation),
    )


# ── TC-1: 정상 공지 처리 ──────────────────────────────────────

class TestNormalProcessing:
    def test_new_notice_saved_and_published(self, aws_setup):
        """신규 공지: DynamoDB 저장 + SNS 발행."""
        with patch("handler.summarize", return_value=MOCK_SUMMARY), \
             patch("handler.judge_importance", return_value=MOCK_IMPORTANCE), \
             patch("handler.translate", return_value=MOCK_TRANSLATION):

            result = handler_module.handler(_make_sqs_event(SQS_BODY), None)

        assert result == {"batchItemFailures": []}

    def test_notice_stored_in_dynamodb(self, aws_setup):
        """처리된 공지가 DynamoDB에 올바른 필드로 저장되는지 확인."""
        notices_table = aws_setup["notices_table"]

        with patch("handler.summarize", return_value=MOCK_SUMMARY), \
             patch("handler.judge_importance", return_value=MOCK_IMPORTANCE), \
             patch("handler.translate", return_value=MOCK_TRANSLATION):
            handler_module.handler(_make_sqs_event(SQS_BODY), None)

        # GSI(noticeId-index)로 저장 확인
        resp = notices_table.query(
            IndexName="noticeId-index",
            KeyConditionExpression="noticeId = :id",
            ExpressionAttributeValues={":id": NOTICE_ID},
        )
        assert len(resp["Items"]) == 1
        item = resp["Items"][0]
        assert item["schoolId"] == SCHOOL_ID
        assert item["summary"] == MOCK_SUMMARY.summary
        assert item["importance"] == MOCK_IMPORTANCE.importance
        assert "vi" in item["translations"]  # 번역 포함 확인

    def test_translations_cached_after_processing(self, aws_setup):
        """번역 결과가 TranslationCache 테이블에 저장되는지 확인."""
        cache_table = aws_setup["cache_table"]

        with patch("handler.summarize", return_value=MOCK_SUMMARY), \
             patch("handler.judge_importance", return_value=MOCK_IMPORTANCE), \
             patch("handler.translate", return_value=MOCK_TRANSLATION):
            handler_module.handler(_make_sqs_event(SQS_BODY), None)

        # vi 언어 캐시 존재 확인
        cache_key = f"notice#{NOTICE_ID}#lang#vi"
        item = cache_table.get_item(Key={"cacheKey": cache_key}).get("Item")
        assert item is not None
        assert "translationData" in item


# ── TC-2: 중복 메시지 멱등 처리 ──────────────────────────────

class TestDuplicateHandling:
    def test_duplicate_notice_skipped(self, aws_setup):
        """이미 처리된 noticeId → 건너뜀, failures 없음."""
        # 미리 동일 noticeId로 저장
        aws_setup["notices_table"].put_item(
            Item={
                "schoolId":  SCHOOL_ID,
                "createdAt": f"2025-10-01T03:00:00+00:00#{NOTICE_ID}",
                "noticeId":  NOTICE_ID,
            }
        )

        with patch("handler.summarize") as mock_summarize, \
             patch("handler.translate"):
            result = handler_module.handler(_make_sqs_event(SQS_BODY), None)
            # 중복이므로 AI 호출 없어야 함
            mock_summarize.assert_not_called()

        assert result == {"batchItemFailures": []}

    def test_same_message_twice_idempotent(self, aws_setup):
        """동일 메시지 2번 전달 → 두 번째는 무시, 에러 없음."""
        with patch("handler.summarize", return_value=MOCK_SUMMARY), \
             patch("handler.judge_importance", return_value=MOCK_IMPORTANCE), \
             patch("handler.translate", return_value=MOCK_TRANSLATION):
            # 첫 번째
            handler_module.handler(_make_sqs_event(SQS_BODY), None)
            # 두 번째 (동일 messageId, 동일 body)
            result = handler_module.handler(_make_sqs_event(SQS_BODY), None)

        assert result == {"batchItemFailures": []}


# ── TC-3: 부분 실패 처리 ─────────────────────────────────────

class TestPartialFailure:
    def test_ai_failure_adds_to_batch_item_failures(self, aws_setup):
        """Bedrock 호출 실패 → batchItemFailures에 해당 messageId 포함."""
        with patch("handler.summarize", side_effect=Exception("Bedrock 연결 실패")):
            result = handler_module.handler(_make_sqs_event(SQS_BODY), None)

        assert result["batchItemFailures"] == [{"itemIdentifier": "msg-0"}]

    def test_one_failure_does_not_stop_others(self, aws_setup):
        """첫 메시지 실패해도 두 번째 메시지는 정상 처리."""
        body2 = {**SQS_BODY, "noticeId": "notice-uuid-0002", "sourceUrl": "https://s.com/2"}

        call_count = 0
        def summarize_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("첫 번째 실패")
            return MOCK_SUMMARY

        with patch("handler.summarize", side_effect=summarize_side_effect), \
             patch("handler.judge_importance", return_value=MOCK_IMPORTANCE), \
             patch("handler.translate", return_value=MOCK_TRANSLATION):
            result = handler_module.handler(_make_sqs_event(SQS_BODY, body2), None)

        # 첫 번째만 실패
        assert len(result["batchItemFailures"]) == 1
        assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-0"

    def test_translation_failure_does_not_fail_record(self, aws_setup):
        """개별 언어 번역 실패 → 빈값으로 대체, 레코드 전체는 성공."""
        def translate_side_effect(summary, lang):
            if lang == "mn":  # 몽골어만 실패
                raise Exception("번역 실패")
            return MOCK_TRANSLATION

        with patch("handler.summarize", return_value=MOCK_SUMMARY), \
             patch("handler.judge_importance", return_value=MOCK_IMPORTANCE), \
             patch("handler.translate", side_effect=translate_side_effect):
            result = handler_module.handler(_make_sqs_event(SQS_BODY), None)

        # 전체 레코드는 성공
        assert result == {"batchItemFailures": []}

        # mn 번역은 빈값, vi 번역은 정상
        item = aws_setup["notices_table"].query(
            IndexName="noticeId-index",
            KeyConditionExpression="noticeId = :id",
            ExpressionAttributeValues={":id": NOTICE_ID},
        )["Items"][0]
        assert item["translations"]["mn"]["translation"] == ""
        assert item["translations"]["vi"]["translation"] == MOCK_TRANSLATION.translation


# ── TC-4: 번역 캐시 재사용 ─────────────────────────────────────

class TestTranslationCache:
    def test_cached_translation_not_re_requested(self, aws_setup):
        """캐시 히트 시 해당 언어 Bedrock 번역 호출 없어야 함."""
        # vi 캐시 미리 삽입
        cache_key = f"notice#{NOTICE_ID}#lang#vi"
        aws_setup["cache_table"].put_item(
            Item={
                "cacheKey": cache_key,
                "translationData": {
                    "translation": "번역 캐시",
                    "culturalTip": "",
                    "checklistItems": [],
                },
                "expiresAt": 9999999999,
            }
        )

        translate_calls: list[str] = []
        def translate_track(summary, lang):
            translate_calls.append(lang)
            return MOCK_TRANSLATION

        with patch("handler.summarize", return_value=MOCK_SUMMARY), \
             patch("handler.judge_importance", return_value=MOCK_IMPORTANCE), \
             patch("handler.translate", side_effect=translate_track):
            handler_module.handler(_make_sqs_event(SQS_BODY), None)

        # vi는 캐시 히트이므로 translate() 호출 없어야 함
        assert "vi" not in translate_calls
        # 나머지 7개 언어는 translate() 호출됨
        assert len(translate_calls) == 7


# ── TC-5: SNS 발행 ────────────────────────────────────────────

class TestSnsPublishing:
    def test_sns_publish_called_on_success(self, aws_setup):
        """처리 성공 시 publish_processed_notice 호출 확인."""
        with patch("handler.summarize", return_value=MOCK_SUMMARY), \
             patch("handler.judge_importance", return_value=MOCK_IMPORTANCE), \
             patch("handler.translate", return_value=MOCK_TRANSLATION), \
             patch("handler.publish_processed_notice") as mock_pub:
            handler_module.handler(_make_sqs_event(SQS_BODY), None)

        mock_pub.assert_called_once()
        call_kwargs = mock_pub.call_args.kwargs
        assert call_kwargs["importance"].importance == "HIGH"

    def test_sns_failure_fails_the_record(self, aws_setup):
        """SNS 발행 실패 → batchItemFailures에 포함."""
        from processor.publisher import PublishError

        with patch("handler.summarize", return_value=MOCK_SUMMARY), \
             patch("handler.judge_importance", return_value=MOCK_IMPORTANCE), \
             patch("handler.translate", return_value=MOCK_TRANSLATION), \
             patch("handler.publish_processed_notice", side_effect=PublishError("SNS 오류")):
            result = handler_module.handler(_make_sqs_event(SQS_BODY), None)

        assert len(result["batchItemFailures"]) == 1


# ── TC-6: 모델 단위 테스트 ────────────────────────────────────

class TestModels:
    def test_sqs_payload_from_dict(self):
        payload = handler_module.SQSNoticePayload.from_dict(SQS_BODY)
        assert payload.noticeId == NOTICE_ID
        assert payload.originalText == SQS_BODY["originalText"]

    def test_sqs_payload_missing_original_text(self):
        """originalText 없는 경우 빈 문자열 기본값."""
        body = {**SQS_BODY}
        del body["originalText"]
        payload = handler_module.SQSNoticePayload.from_dict(body)
        assert payload.originalText == ""

    def test_translation_result_to_dict(self):
        t = TranslationResult(
            translation="번역문",
            culturalTip="팁",
            checklistItems=["항목1"],
        )
        d = t.to_dict()
        assert set(d.keys()) == {"translation", "culturalTip", "checklistItems"}
