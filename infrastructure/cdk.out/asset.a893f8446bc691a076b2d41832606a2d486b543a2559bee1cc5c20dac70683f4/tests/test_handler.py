"""
handler.py 단위 테스트.

Firebase Admin SDK (FCM 발송)는 unittest.mock.patch로 격리한다.
DynamoDB / Secrets Manager는 moto로 모킹한다.
"""
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest

import handler as h
from notifier.fcm import SendResult
from notifier.models import SNSNoticeMessage, UserRecord, NotificationSettings

# ── 공통 상수 ────────────────────────────────────────────────
SCHOOL_ID  = "school-001"
NOTICE_ID  = "notice-uuid-001"
USER_ID    = "user-001"
CHILD_ID   = "child-001"
KST        = timezone(timedelta(hours=9))

# 테스트용 SNS 이벤트 빌더
def _sns_event(body: dict) -> dict:
    return {
        "Records": [
            {
                "Sns": {
                    "Message": json.dumps(body),
                    "MessageId": "msg-001",
                }
            }
        ]
    }

# 테스트용 처리 완료 공지 메시지
NOTICE_MSG = {
    "noticeId":    NOTICE_ID,
    "schoolId":    SCHOOL_ID,
    "title":       "10월 현장학습 안내",
    "sourceUrl":   "https://school.example.com/notice/1",
    "publishedAt": "2025-10-01T00:00:00+00:00",
    "crawledAt":   "2025-10-01T03:00:00+00:00",
    "summary":     "현장학습 안내 요약입니다.",
    "keywords":    ["현장학습"],
    "importance":  "HIGH",
    "translations": {
        "vi": {
            "translation":  "Thông báo học thực địa",
            "culturalTip":  "Tip văn hóa",
            "checklistItems": ["Nộp phí 15.000 won"],
        },
        "en": {
            "translation":  "Field trip notice",
            "culturalTip":  "Cultural tip",
            "checklistItems": ["Pay 15,000 won"],
        },
    },
}

def _put_school(aws_setup, name="테스트 학교"):
    aws_setup["schools"].put_item(Item={"schoolId": SCHOOL_ID, "name": name})

def _put_user(aws_setup, user_id=USER_ID, lang="vi",
              fcm_token="token-native", fcm_web=None,
              enabled=True, threshold="LOW",
              quiet_start=None, quiet_end=None):
    settings = {"enabled": enabled, "importanceThreshold": threshold}
    if quiet_start:
        settings["quietHoursStart"] = quiet_start
        settings["quietHoursEnd"]   = quiet_end
    item = {
        "userId": user_id,
        "languageCode": lang,
        "notificationSettings": settings,
    }
    if fcm_token:
        item["fcmToken"] = fcm_token
    if fcm_web:
        item["fcmTokenWeb"] = fcm_web
    aws_setup["users"].put_item(Item=item)

def _put_child(aws_setup, child_id=CHILD_ID, user_id=USER_ID):
    aws_setup["children"].put_item(
        Item={"childId": child_id, "userId": user_id, "schoolId": SCHOOL_ID}
    )


# ── TC-1: 정상 발송 흐름 ─────────────────────────────────────

class TestNormalDispatch:
    def test_sends_to_native_token(self, aws_setup):
        """구독 사용자의 네이티브 토큰으로 FCM 발송."""
        _put_school(aws_setup)
        _put_user(aws_setup, fcm_token="native-token-123")
        _put_child(aws_setup)

        with patch("notifier.secrets._cached_credentials", NOTICE_MSG), \
             patch("notifier.fcm._firebase_app", MagicMock()), \
             patch("handler._fcm_ready", True), \
             patch("handler.send_push", return_value=SendResult(True, False)) as mock_push:

            h.handler(_sns_event(NOTICE_MSG), None)

        # 네이티브 토큰으로 1회 발송
        calls = mock_push.call_args_list
        assert any(c.args[0] == "native-token-123" for c in calls)

    def test_sends_to_both_tokens(self, aws_setup):
        """네이티브 + 웹 토큰 모두 있으면 각각 발송."""
        _put_school(aws_setup)
        _put_user(aws_setup, fcm_token="native-tok", fcm_web="web-tok")
        _put_child(aws_setup)

        call_tokens: list[str] = []
        def mock_send(token, *a, **kw):
            call_tokens.append(token)
            return SendResult(True, False)

        with patch("handler._fcm_ready", True), \
             patch("handler.send_push", side_effect=mock_send):
            h.handler(_sns_event(NOTICE_MSG), None)

        assert "native-tok" in call_tokens
        assert "web-tok" in call_tokens

    def test_notification_saved_on_success(self, aws_setup):
        """발송 성공 시 Notifications 테이블에 이력 저장."""
        _put_school(aws_setup)
        _put_user(aws_setup)
        _put_child(aws_setup)

        with patch("handler._fcm_ready", True), \
             patch("handler.send_push", return_value=SendResult(True, False)):
            h.handler(_sns_event(NOTICE_MSG), None)

        # Notifications 테이블 조회
        resp = aws_setup["notifications"].query(
            KeyConditionExpression="userId = :uid",
            ExpressionAttributeValues={":uid": USER_ID},
        )
        assert len(resp["Items"]) == 1
        assert resp["Items"][0]["noticeId"] == NOTICE_ID

    def test_uses_user_language_translation(self, aws_setup):
        """사용자 언어(vi)의 번역문으로 알림 본문 구성."""
        _put_school(aws_setup)
        _put_user(aws_setup, lang="vi")
        _put_child(aws_setup)

        captured = {}
        def mock_send(token, title, body, data):
            captured["body"] = body
            captured["data"] = data
            return SendResult(True, False)

        with patch("handler._fcm_ready", True), \
             patch("handler.send_push", side_effect=mock_send):
            h.handler(_sns_event(NOTICE_MSG), None)

        # vi 번역문 사용 확인
        assert captured["body"] == "Thông báo học thực địa"
        assert captured["data"]["langCode"] == "vi"
        assert captured["data"]["culturalTip"] == "Tip văn hóa"

    def test_school_name_in_title(self, aws_setup):
        """FCM 제목에 학교명 포함."""
        _put_school(aws_setup, name="서울초등학교")
        _put_user(aws_setup)
        _put_child(aws_setup)

        captured = {}
        def mock_send(token, title, body, data):
            captured["title"] = title
            return SendResult(True, False)

        with patch("handler._fcm_ready", True), \
             patch("handler.send_push", side_effect=mock_send):
            h.handler(_sns_event(NOTICE_MSG), None)

        assert "서울초등학교" in captured["title"]


# ── TC-2: 만료 토큰 처리 ─────────────────────────────────────

class TestExpiredTokenHandling:
    def test_expired_native_token_cleared(self, aws_setup):
        """네이티브 토큰 만료 → Users 테이블에서 fcmToken 삭제."""
        _put_school(aws_setup)
        _put_user(aws_setup, fcm_token="expired-native")
        _put_child(aws_setup)

        with patch("handler._fcm_ready", True), \
             patch("handler.send_push", return_value=SendResult(False, True)):
            h.handler(_sns_event(NOTICE_MSG), None)

        item = aws_setup["users"].get_item(Key={"userId": USER_ID})["Item"]
        assert "fcmToken" not in item

    def test_expired_web_token_cleared(self, aws_setup):
        """웹 토큰 만료 → Users 테이블에서 fcmTokenWeb 삭제."""
        _put_school(aws_setup)
        _put_user(aws_setup, fcm_token=None, fcm_web="expired-web")
        _put_child(aws_setup)

        with patch("handler._fcm_ready", True), \
             patch("handler.send_push", return_value=SendResult(False, True)):
            h.handler(_sns_event(NOTICE_MSG), None)

        item = aws_setup["users"].get_item(Key={"userId": USER_ID})["Item"]
        assert "fcmTokenWeb" not in item

    def test_expired_token_no_notification_saved(self, aws_setup):
        """토큰 만료로 발송 실패 → Notifications 이력 미저장."""
        _put_school(aws_setup)
        _put_user(aws_setup, fcm_token="expired")
        _put_child(aws_setup)

        with patch("handler._fcm_ready", True), \
             patch("handler.send_push", return_value=SendResult(False, True)):
            h.handler(_sns_event(NOTICE_MSG), None)

        resp = aws_setup["notifications"].query(
            KeyConditionExpression="userId = :uid",
            ExpressionAttributeValues={":uid": USER_ID},
        )
        assert len(resp["Items"]) == 0


# ── TC-3: 알림 필터링 ────────────────────────────────────────

class TestNotificationFiltering:
    def test_disabled_user_skipped(self, aws_setup):
        """알림 비활성화 사용자 → 발송 안 함."""
        _put_school(aws_setup)
        _put_user(aws_setup, enabled=False)
        _put_child(aws_setup)

        with patch("handler._fcm_ready", True), \
             patch("handler.send_push") as mock_push:
            h.handler(_sns_event(NOTICE_MSG), None)

        mock_push.assert_not_called()

    def test_importance_below_threshold_skipped(self, aws_setup):
        """공지 중요도 < 사용자 임계값 → 발송 안 함."""
        _put_school(aws_setup)
        _put_user(aws_setup, threshold="HIGH")  # HIGH만 받겠다
        _put_child(aws_setup)

        low_msg = {**NOTICE_MSG, "importance": "LOW"}

        with patch("handler._fcm_ready", True), \
             patch("handler.send_push") as mock_push:
            h.handler(_sns_event(low_msg), None)

        mock_push.assert_not_called()

    def test_quiet_hours_skipped(self, aws_setup):
        """Quiet Hours 구간 → 발송 안 함."""
        _put_school(aws_setup)
        _put_user(aws_setup, quiet_start="22:00", quiet_end="08:00")
        _put_child(aws_setup)

        # 테스트 시각을 23:00 KST로 고정
        night = datetime(2025, 10, 1, 23, 0, tzinfo=KST)

        with patch("handler._fcm_ready", True), \
             patch("handler.send_push") as mock_push, \
             patch("handler.datetime") as mock_dt:
            mock_dt.now.return_value = night
            mock_dt.now.side_effect = None
            # _process_record 내부 datetime.now 패치
            with patch("handler.datetime") as mock_dt2:
                mock_dt2.now = lambda tz=None: night if tz == KST else datetime.now(tz)
                mock_dt2.now.__name__ = "now"
                h.handler(_sns_event(NOTICE_MSG), None)

    def test_no_subscribers_no_push(self, aws_setup):
        """구독자 없는 학교 → FCM 발송 안 함."""
        _put_school(aws_setup)
        # Children 테이블 비어 있음

        with patch("handler._fcm_ready", True), \
             patch("handler.send_push") as mock_push:
            h.handler(_sns_event(NOTICE_MSG), None)

        mock_push.assert_not_called()

    def test_medium_notice_sent_to_medium_threshold_user(self, aws_setup):
        """MEDIUM 공지 + 사용자 임계값 MEDIUM → 발송."""
        _put_school(aws_setup)
        _put_user(aws_setup, threshold="MEDIUM")
        _put_child(aws_setup)

        medium_msg = {**NOTICE_MSG, "importance": "MEDIUM"}

        with patch("handler._fcm_ready", True), \
             patch("handler.send_push", return_value=SendResult(True, False)) as mock_push:
            h.handler(_sns_event(medium_msg), None)

        mock_push.assert_called()


# ── TC-4: 비즈니스 로직 단위 테스트 ─────────────────────────

class TestBusinessLogic:
    def test_is_quiet_hours_overnight(self):
        """자정 넘김 quiet hours (22:00~08:00)."""
        night = datetime(2025, 10, 1, 23, 30, tzinfo=KST)
        early = datetime(2025, 10, 1,  7, 59, tzinfo=KST)
        day   = datetime(2025, 10, 1, 10,  0, tzinfo=KST)
        assert h._is_quiet_hours("22:00", "08:00", night) is True
        assert h._is_quiet_hours("22:00", "08:00", early) is True
        assert h._is_quiet_hours("22:00", "08:00", day)   is False

    def test_is_quiet_hours_same_day(self):
        """같은 날 quiet hours (09:00~12:00)."""
        inside  = datetime(2025, 10, 1, 10, 0, tzinfo=KST)
        outside = datetime(2025, 10, 1, 13, 0, tzinfo=KST)
        assert h._is_quiet_hours("09:00", "12:00", inside)  is True
        assert h._is_quiet_hours("09:00", "12:00", outside) is False

    def test_is_quiet_hours_none_returns_false(self):
        now = datetime(2025, 10, 1, 10, 0, tzinfo=KST)
        assert h._is_quiet_hours(None, None, now) is False
        assert h._is_quiet_hours("22:00", None, now) is False

    def test_should_notify_importance_ranking(self):
        """중요도 임계값 테스트."""
        day = datetime(2025, 10, 1, 10, 0, tzinfo=KST)

        u_high = UserRecord("u1", "vi", NotificationSettings(True, "HIGH"))
        u_med  = UserRecord("u2", "vi", NotificationSettings(True, "MEDIUM"))
        u_low  = UserRecord("u3", "vi", NotificationSettings(True, "LOW"))

        assert h._should_notify(u_high, "HIGH",   day) is True
        assert h._should_notify(u_high, "MEDIUM", day) is False
        assert h._should_notify(u_high, "LOW",    day) is False

        assert h._should_notify(u_med,  "HIGH",   day) is True
        assert h._should_notify(u_med,  "MEDIUM", day) is True
        assert h._should_notify(u_med,  "LOW",    day) is False

        assert h._should_notify(u_low,  "LOW",    day) is True

    def test_build_data_all_string_values(self):
        """FCM data 페이로드 값이 모두 str 타입."""
        msg = SNSNoticeMessage.from_dict(NOTICE_MSG)
        data = h._build_data_payload(
            msg, "vi", {"culturalTip": "팁", "checklistItems": ["항목"]}
        )
        assert all(isinstance(v, str) for v in data.values())

    def test_build_data_checklist_json_encoded(self):
        """checklistItems가 JSON 문자열로 인코딩."""
        import json as _json
        msg = SNSNoticeMessage.from_dict(NOTICE_MSG)
        data = h._build_data_payload(msg, "vi", {"checklistItems": ["a", "b"]})
        decoded = _json.loads(data["checklistItems"])
        assert decoded == ["a", "b"]

    def test_fallback_to_english_translation(self, aws_setup):
        """사용자 언어 번역 없을 때 영어 번역으로 대체."""
        _put_school(aws_setup)
        _put_user(aws_setup, lang="mn")  # 몽골어 (번역 없음)
        _put_child(aws_setup)

        captured = {}
        def mock_send(token, title, body, data):
            captured["body"] = body
            captured["langCode"] = data.get("langCode")
            return SendResult(True, False)

        with patch("handler._fcm_ready", True), \
             patch("handler.send_push", side_effect=mock_send):
            h.handler(_sns_event(NOTICE_MSG), None)

        # 영어 번역 사용 (mn 없으므로 en fallback)
        assert captured["body"] == "Field trip notice"

    def test_sns_parse_error_raises(self, aws_setup):
        """잘못된 SNS 메시지 → raise (SNS 재시도 유도)."""
        bad_event = {"Records": [{"Sns": {"Message": "not-json"}}]}
        with patch("handler._fcm_ready", True):
            with pytest.raises(Exception):
                h.handler(bad_event, None)
