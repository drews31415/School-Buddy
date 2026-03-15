"""
notifier/fcm.py 및 notifier/secrets.py 단위 테스트.
firebase_admin은 unittest.mock으로 격리한다.
"""
import json
from unittest.mock import patch, MagicMock

import pytest


# ── notifier/secrets.py ───────────────────────────────────────

class TestSecrets:
    def test_returns_credentials_from_secretsmanager(self, aws_setup):
        """Secrets Manager에서 FCM 자격증명 정상 조회."""
        import notifier.secrets as sec_mod
        # 캐시 초기화
        sec_mod._cached_credentials = None

        creds = sec_mod.get_fcm_credentials()
        assert creds["type"] == "service_account"
        assert creds["project_id"] == "test-project"

    def test_caches_on_second_call(self, aws_setup):
        """두 번째 호출은 캐시 반환 (Secrets Manager 재조회 없음)."""
        import notifier.secrets as sec_mod
        sec_mod._cached_credentials = None

        first  = sec_mod.get_fcm_credentials()
        # Secrets Manager가 없어도 캐시에서 반환되어야 함
        second = sec_mod.get_fcm_credentials()
        assert first is second  # 동일 객체

    def test_raises_on_secretsmanager_error(self, aws_setup):
        """Secrets Manager 조회 실패 → RuntimeError."""
        import notifier.secrets as sec_mod
        sec_mod._cached_credentials = None

        with patch.object(sec_mod._secretsmanager, "get_secret_value",
                          side_effect=Exception("AccessDeniedException")):
            with pytest.raises(RuntimeError, match="FCM 자격증명 로드 실패"):
                sec_mod.get_fcm_credentials()

        sec_mod._cached_credentials = None  # cleanup


# ── notifier/fcm.py ──────────────────────────────────────────

class TestFcmInit:
    def test_init_firebase_called_once(self):
        """init_firebase는 최초 1회만 firebase_admin.initialize_app을 호출한다."""
        import notifier.fcm as fcm_mod
        fcm_mod._firebase_app = None  # reset

        mock_app = MagicMock()
        with patch("notifier.fcm.credentials.Certificate", return_value=MagicMock()), \
             patch("notifier.fcm.firebase_admin.initialize_app", return_value=mock_app) as mock_init:
            fcm_mod.init_firebase({"type": "service_account"})
            fcm_mod.init_firebase({"type": "service_account"})  # 2nd call

            mock_init.assert_called_once()  # initialize_app은 1회만

        fcm_mod._firebase_app = None  # cleanup

    def test_init_firebase_skips_if_already_initialized(self):
        """이미 초기화된 경우 재초기화 안 함."""
        import notifier.fcm as fcm_mod
        fcm_mod._firebase_app = MagicMock()  # 이미 초기화된 상태

        with patch("notifier.fcm.firebase_admin.initialize_app") as mock_init:
            fcm_mod.init_firebase({})
            mock_init.assert_not_called()

        fcm_mod._firebase_app = None


class TestSendPush:
    def test_success_returns_send_result_true(self):
        """FCM 발송 성공 → SendResult(success=True, token_expired=False)."""
        from notifier.fcm import send_push, SendResult

        with patch("notifier.fcm.messaging.send", return_value="msg-id"):
            result = send_push("token", "제목", "본문", {"key": "val"})

        assert result == SendResult(success=True, token_expired=False)

    def test_unregistered_error_returns_expired(self):
        """UnregisteredError → token_expired=True."""
        from notifier.fcm import send_push, SendResult
        from firebase_admin import messaging as fb_msg

        with patch("notifier.fcm.messaging.send",
                   side_effect=fb_msg.UnregisteredError("expired")):
            result = send_push("old-token", "제목", "본문", {})

        assert result == SendResult(success=False, token_expired=True)

    def test_other_error_returns_failed_not_expired(self):
        """기타 예외 → success=False, token_expired=False."""
        from notifier.fcm import send_push, SendResult

        with patch("notifier.fcm.messaging.send",
                   side_effect=Exception("network error")):
            result = send_push("token", "제목", "본문", {})

        assert result == SendResult(success=False, token_expired=False)

    def test_sender_id_mismatch_returns_failed(self):
        """SenderIdMismatchError → failed, not expired."""
        from notifier.fcm import send_push, SendResult
        from firebase_admin import messaging as fb_msg

        with patch("notifier.fcm.messaging.send",
                   side_effect=fb_msg.SenderIdMismatchError("mismatch")):
            result = send_push("token", "제목", "본문", {})

        assert result == SendResult(success=False, token_expired=False)


class TestSendMulticast:
    def test_empty_tokens_returns_zero(self):
        """빈 토큰 목록 → 즉시 (0, []) 반환."""
        from notifier.fcm import send_multicast

        count, expired = send_multicast([], "제목", "본문", {})
        assert count == 0
        assert expired == []

    def test_multicast_success(self):
        """멀티캐스트 발송 성공."""
        from notifier.fcm import send_multicast
        from firebase_admin import messaging as fb_msg

        mock_resp = MagicMock()
        mock_resp.success_count = 2
        mock_resp.responses = [
            MagicMock(success=True, exception=None),
            MagicMock(success=True, exception=None),
        ]

        with patch("notifier.fcm.messaging.send_each_for_multicast", return_value=mock_resp):
            count, expired = send_multicast(["t1", "t2"], "제목", "본문", {})

        assert count == 2
        assert expired == []

    def test_multicast_collects_expired_tokens(self):
        """멀티캐스트에서 만료 토큰 수집."""
        from notifier.fcm import send_multicast
        from firebase_admin import messaging as fb_msg

        mock_resp = MagicMock()
        mock_resp.success_count = 1
        mock_resp.responses = [
            MagicMock(success=True, exception=None),
            MagicMock(success=False, exception=fb_msg.UnregisteredError("expired")),
        ]

        with patch("notifier.fcm.messaging.send_each_for_multicast", return_value=mock_resp):
            count, expired = send_multicast(["t1", "t2-expired"], "제목", "본문", {})

        assert count == 1
        assert "t2-expired" in expired


# ── handler.py: FCM 초기화 경로 ──────────────────────────────

class TestHandlerFcmInit:
    def test_fcm_initialized_on_first_call(self, aws_setup):
        """핸들러 최초 호출 시 FCM 초기화."""
        import handler as h
        import notifier.secrets as sec_mod
        import notifier.fcm as fcm_mod

        sec_mod._cached_credentials = None
        fcm_mod._firebase_app = None
        h._fcm_ready = False

        with patch("notifier.fcm.credentials.Certificate", return_value=MagicMock()), \
             patch("notifier.fcm.firebase_admin.initialize_app", return_value=MagicMock()) as mock_init, \
             patch("handler.send_push", return_value=MagicMock(success=False, token_expired=False)):
            # 구독자 없는 이벤트로 최소 실행
            import json
            event = {"Records": [{"Sns": {"Message": json.dumps({
                "noticeId": "n1", "schoolId": "no-school",
                "title": "t", "sourceUrl": "", "publishedAt": "", "crawledAt": "",
                "summary": "s", "keywords": [], "importance": "LOW", "translations": {},
            })}}]}
            h.handler(event, None)

        mock_init.assert_called_once()
        assert h._fcm_ready is True

        # cleanup
        h._fcm_ready = False
        fcm_mod._firebase_app = None
        sec_mod._cached_credentials = None
