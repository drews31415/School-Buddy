"""
handler.py 단위 테스트 — 5개 핵심 시나리오.

AWS 서비스 (DynamoDB / SQS / SNS) 는 moto 로 모킹한다.
HTTP 요청(fetch_html)과 HTML 파싱(parse_notices)은
unittest.mock.patch 로 격리한다.
"""
import json
from unittest.mock import patch, MagicMock

import pytest

import handler as handler_module
from crawler.fetcher import FetchError
from crawler.models import RawNotice

# ── 공통 상수 ───────────────────────────────────────────────
SCHOOL_ID = "school-001"
NOTICE_URL_1 = "https://school.example.com/notice/1"
NOTICE_URL_2 = "https://school.example.com/notice/2"


def _make_school(consecutive_errors: int = 0, crawl_status: str = "ACTIVE") -> dict:
    return {
        "schoolId": SCHOOL_ID,
        "name": "테스트 학교",
        "noticeUrl": "https://school.example.com/notice",
        "crawlStatus": crawl_status,
        "consecutiveErrors": consecutive_errors,
    }


def _make_raw_notice(url: str = NOTICE_URL_1) -> RawNotice:
    return RawNotice(title="테스트 공지", url=url, published_at="2025-10-01", content="")


def _sqs_message_count(sqs_client, queue_url: str) -> int:
    """SQS 큐의 수신 가능한 메시지 수 반환."""
    resp = sqs_client.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=0,
    )
    return len(resp.get("Messages", []))


# ── 테스트 케이스 ───────────────────────────────────────────

class TestNewNoticeDetectedSendsSqsMessage:
    """TC-1: 신규 공지 감지 → SQS 메시지 발행."""

    def test_new_notice_detected_sends_sqs_message(self, aws_setup):
        schools_table = aws_setup["schools_table"]
        sqs = aws_setup["sqs"]
        queue_url = aws_setup["queue_url"]

        # Given: ACTIVE 학교, 기존 공지 없음
        schools_table.put_item(Item=_make_school())

        with (
            patch("handler.fetch_html", return_value="<html/>"),
            patch("handler.parse_notices", return_value=[_make_raw_notice(NOTICE_URL_1)]),
        ):
            result = handler_module.handler({}, None)

        # Then: SQS에 1건 발행, 요약 결과 정합
        assert result == {"processed": 1, "new_notices": 1, "errors": 0}
        assert _sqs_message_count(sqs, queue_url) == 1

    def test_sqs_message_payload_schema(self, aws_setup):
        """발행된 SQS 메시지가 spec.md 스키마를 만족하는지 확인."""
        schools_table = aws_setup["schools_table"]
        sqs = aws_setup["sqs"]
        queue_url = aws_setup["queue_url"]

        schools_table.put_item(Item=_make_school())

        with (
            patch("handler.fetch_html", return_value="<html/>"),
            patch("handler.parse_notices", return_value=[_make_raw_notice(NOTICE_URL_1)]),
        ):
            handler_module.handler({}, None)

        msgs = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)["Messages"]
        body = json.loads(msgs[0]["Body"])

        required_keys = {"noticeId", "schoolId", "title", "sourceUrl", "originalText", "publishedAt", "crawledAt"}
        assert required_keys.issubset(body.keys())
        assert body["schoolId"] == SCHOOL_ID
        assert body["sourceUrl"] == NOTICE_URL_1


class TestDuplicateNoticeDoesNotSendSqs:
    """TC-2: 이미 수집한 공지 URL → SQS 발행 건너뜀."""

    def test_duplicate_notice_does_not_send_sqs(self, aws_setup):
        schools_table = aws_setup["schools_table"]
        notices_table = aws_setup["notices_table"]
        sqs = aws_setup["sqs"]
        queue_url = aws_setup["queue_url"]

        # Given: ACTIVE 학교, 동일 URL이 Notices 테이블에 이미 존재
        schools_table.put_item(Item=_make_school())
        notices_table.put_item(
            Item={
                "schoolId": SCHOOL_ID,
                "createdAt": "2025-10-01T03:00:00+00:00",
                "sourceUrl": NOTICE_URL_1,
            }
        )

        with (
            patch("handler.fetch_html", return_value="<html/>"),
            patch("handler.parse_notices", return_value=[_make_raw_notice(NOTICE_URL_1)]),
        ):
            result = handler_module.handler({}, None)

        # Then: 중복이므로 SQS 발행 없음
        assert result == {"processed": 1, "new_notices": 0, "errors": 0}
        assert _sqs_message_count(sqs, queue_url) == 0

    def test_only_new_url_is_published(self, aws_setup):
        """기존 URL 1건 + 신규 URL 1건 → 신규 1건만 발행."""
        schools_table = aws_setup["schools_table"]
        notices_table = aws_setup["notices_table"]
        sqs = aws_setup["sqs"]
        queue_url = aws_setup["queue_url"]

        schools_table.put_item(Item=_make_school())
        notices_table.put_item(
            Item={
                "schoolId": SCHOOL_ID,
                "createdAt": "2025-10-01T03:00:00+00:00",
                "sourceUrl": NOTICE_URL_1,
            }
        )

        with (
            patch("handler.fetch_html", return_value="<html/>"),
            patch(
                "handler.parse_notices",
                return_value=[_make_raw_notice(NOTICE_URL_1), _make_raw_notice(NOTICE_URL_2)],
            ),
        ):
            result = handler_module.handler({}, None)

        assert result["new_notices"] == 1
        assert _sqs_message_count(sqs, queue_url) == 1


class TestConnectionErrorSkipsSchoolAndRecordsError:
    """TC-3: HTTP 연결 실패 → 학교 건너뜀, DynamoDB 오류 기록."""

    def test_connection_error_skips_school_and_records_error(self, aws_setup):
        schools_table = aws_setup["schools_table"]

        # Given: consecutiveErrors=0 학교
        schools_table.put_item(Item=_make_school(consecutive_errors=0))

        with patch("handler.fetch_html", side_effect=FetchError("연결 타임아웃")):
            result = handler_module.handler({}, None)

        # Then: errors=1, processed=0, SQS 미발행
        assert result == {"processed": 0, "new_notices": 0, "errors": 1}

        # DynamoDB에 오류 정보 기록 확인
        item = schools_table.get_item(Key={"schoolId": SCHOOL_ID})["Item"]
        assert "lastErrorAt" in item
        assert "연결 타임아웃" in item["lastErrorMessage"]
        assert int(item["consecutiveErrors"]) == 1
        # 1회 실패는 ERROR 상태로 전환되지 않음
        assert item["crawlStatus"] == "ACTIVE"

    def test_connection_error_does_not_raise(self, aws_setup):
        """개별 학교 실패가 핸들러 전체를 중단시키지 않는지 확인."""
        schools_table = aws_setup["schools_table"]
        schools_table.put_item(Item=_make_school())

        with patch("handler.fetch_html", side_effect=FetchError("서버 응답 없음")):
            # 예외 전파 없이 정상 종료해야 함
            result = handler_module.handler({}, None)

        assert isinstance(result, dict)
        assert result["errors"] == 1


class TestParseFailureRecordsErrorKeepsStatus:
    """TC-4: 파싱 중 예외 발생 → 오류 기록, crawlStatus=ACTIVE 유지 (2회 미만)."""

    def test_parse_failure_records_error_keeps_status(self, aws_setup):
        schools_table = aws_setup["schools_table"]

        # Given: consecutiveErrors=1 학교 (아직 임계치 미달)
        schools_table.put_item(Item=_make_school(consecutive_errors=1))

        with (
            patch("handler.fetch_html", return_value="<html/>"),
            patch("handler.parse_notices", side_effect=Exception("HTML 구조 변경으로 파싱 실패")),
        ):
            result = handler_module.handler({}, None)

        # Then: 오류 기록, 상태는 ACTIVE 유지 (2회 연속 실패는 ERROR 미만)
        assert result == {"processed": 0, "new_notices": 0, "errors": 1}

        item = schools_table.get_item(Key={"schoolId": SCHOOL_ID})["Item"]
        assert int(item["consecutiveErrors"]) == 2
        assert item["crawlStatus"] == "ACTIVE"  # ERROR 전환은 3회부터

    def test_empty_parse_result_treated_as_success(self, aws_setup):
        """parse_notices가 빈 리스트 반환 시 성공으로 처리 (E-03)."""
        schools_table = aws_setup["schools_table"]
        schools_table.put_item(Item=_make_school())

        with (
            patch("handler.fetch_html", return_value="<html/>"),
            patch("handler.parse_notices", return_value=[]),
        ):
            result = handler_module.handler({}, None)

        # 0건은 오류가 아니라 성공 처리
        assert result == {"processed": 1, "new_notices": 0, "errors": 0}
        item = schools_table.get_item(Key={"schoolId": SCHOOL_ID})["Item"]
        assert item["crawlStatus"] == "ACTIVE"
        assert int(item["consecutiveErrors"]) == 0


class TestThreeConsecutiveFailuresSetsErrorStatus:
    """TC-5: 연속 3회 실패 → crawlStatus=ERROR + SNS 운영 알람 발송."""

    def test_three_consecutive_failures_sets_error_status(self, aws_setup):
        schools_table = aws_setup["schools_table"]

        # Given: consecutiveErrors=2 학교 (임계치 직전)
        schools_table.put_item(Item=_make_school(consecutive_errors=2))

        with (
            patch("handler.fetch_html", side_effect=FetchError("HTTP 500 오류")),
            patch("handler.publish_ops_alarm") as mock_alarm,
        ):
            result = handler_module.handler({}, None)

        # Then: crawlStatus=ERROR 로 전환
        assert result["errors"] == 1
        item = schools_table.get_item(Key={"schoolId": SCHOOL_ID})["Item"]
        assert item["crawlStatus"] == "ERROR"
        assert int(item["consecutiveErrors"]) == 3

        # SNS 운영 알람 발송 확인
        mock_alarm.assert_called_once_with(
            school_id=SCHOOL_ID,
            school_name="테스트 학교",
            error_message="HTTP 500 오류",
        )

    def test_consecutive_error_threshold_is_three(self, aws_setup):
        """정확히 3회째 실패에서만 ERROR 전환 (2회는 ACTIVE 유지)."""
        schools_table = aws_setup["schools_table"]
        schools_table.put_item(Item=_make_school(consecutive_errors=1))

        with patch("handler.fetch_html", side_effect=FetchError("오류")):
            handler_module.handler({}, None)

        item = schools_table.get_item(Key={"schoolId": SCHOOL_ID})["Item"]
        assert int(item["consecutiveErrors"]) == 2
        assert item["crawlStatus"] == "ACTIVE"  # 아직 ERROR 아님

    def test_success_after_error_resets_consecutive_count(self, aws_setup):
        """성공 시 consecutiveErrors 초기화 및 crawlStatus ACTIVE 복원."""
        schools_table = aws_setup["schools_table"]
        # ERROR 상태 학교 (수동 복구 후 ACTIVE로 재설정된 시나리오)
        schools_table.put_item(
            Item={
                **_make_school(consecutive_errors=2),
                "crawlStatus": "ACTIVE",
            }
        )

        with (
            patch("handler.fetch_html", return_value="<html/>"),
            patch("handler.parse_notices", return_value=[]),
        ):
            result = handler_module.handler({}, None)

        assert result["processed"] == 1
        item = schools_table.get_item(Key={"schoolId": SCHOOL_ID})["Item"]
        assert int(item["consecutiveErrors"]) == 0
        assert item["crawlStatus"] == "ACTIVE"
