"""
rag-query-handler 핸들러 통합 테스트
"""
import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import (
    TEST_USER_ID,
    TEST_SESSION_ID,
    dynamodb_setup,
    make_event,
)

MOCK_CHAT_RESPONSE_DICT = {
    "answer":    "돌봄교실 신청은 학교 홈페이지에서 가능합니다.",
    "sessionId": "bedrock-sess-001",
    "sources":   [{"content": "관련 문서", "location": "s3://kb/doc.pdf"}],
}


def _mock_chat_response():
    from rag.models import ChatResponse, SourceCitation

    return ChatResponse(
        answer="돌봄교실 신청은 학교 홈페이지에서 가능합니다.",
        session_id="bedrock-sess-001",
        sources=[SourceCitation(content="관련 문서", location="s3://kb/doc.pdf")],
    )


# ── POST /chat ─────────────────────────────────────────────────

class TestHandlerChat:
    def test_chat_success_basic(self, dynamodb_setup):
        from handler import handler

        event = make_event("POST", "/chat", body={"message": "돌봄교실 어떻게 신청해요?"})

        with patch("handler.retrieve_and_generate", return_value=_mock_chat_response()), \
             patch("handler.save_chat_message") as mock_save:
            resp = handler(event, {})

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert "data" in body
        assert body["data"]["answer"] == "돌봄교실 신청은 학교 홈페이지에서 가능합니다."
        assert body["data"]["sessionId"] == "bedrock-sess-001"
        assert len(body["data"]["sources"]) == 1
        assert mock_save.call_count == 2  # user + assistant 저장

    def test_chat_missing_message(self, dynamodb_setup):
        from handler import handler

        event = make_event("POST", "/chat", body={})
        resp = handler(event, {})
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["code"] == "MISSING_MESSAGE"

    def test_chat_message_too_long(self, dynamodb_setup):
        from handler import handler

        event = make_event("POST", "/chat", body={"message": "A" * 1001})
        resp = handler(event, {})
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["code"] == "MESSAGE_TOO_LONG"

    def test_chat_generates_session_id_if_missing(self, dynamodb_setup):
        from handler import handler

        event = make_event("POST", "/chat", body={"message": "질문"})

        with patch("handler.retrieve_and_generate", return_value=_mock_chat_response()) as mock_rag, \
             patch("handler.save_chat_message"):
            resp = handler(event, {})

        # retrieve_and_generate에 session_id가 전달됐는지 확인
        call_kwargs = mock_rag.call_args[1]
        assert call_kwargs["session_id"] is not None
        assert len(call_kwargs["session_id"]) > 0

    def test_chat_uses_provided_session_id(self, dynamodb_setup):
        from handler import handler

        event = make_event("POST", "/chat", body={
            "message": "질문", "sessionId": TEST_SESSION_ID
        })

        with patch("handler.retrieve_and_generate", return_value=_mock_chat_response()) as mock_rag, \
             patch("handler.save_chat_message"):
            handler(event, {})

        call_kwargs = mock_rag.call_args[1]
        assert call_kwargs["session_id"] == TEST_SESSION_ID

    def test_chat_notice_context_loaded(self, dynamodb_setup):
        """noticeId가 있으면 공지 요약이 컨텍스트로 전달된다."""
        import boto3
        from handler import handler

        # Notices 테이블에 아이템 삽입
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        table = ddb.Table("school-buddy-notices-test")
        table.put_item(Item={
            "schoolId":  "school-001",
            "createdAt": "2025-10-01T00:00:00#notice-001",
            "noticeId":  "notice-001",
            "title":     "현장학습 안내",
            "summary":   "10월 15일 현장학습 예정",
        })

        event = make_event("POST", "/chat", body={
            "message":  "비용이 얼마예요?",
            "noticeId": "notice-001",
        })

        with patch("handler.retrieve_and_generate", return_value=_mock_chat_response()) as mock_rag, \
             patch("handler.save_chat_message"):
            handler(event, {})

        call_kwargs = mock_rag.call_args[1]
        assert call_kwargs["notice_context"] is not None
        assert "현장학습" in call_kwargs["notice_context"]

    def test_chat_nonexistent_notice_no_context(self, dynamodb_setup):
        """존재하지 않는 noticeId → notice_context=None으로 정상 진행."""
        from handler import handler

        event = make_event("POST", "/chat", body={
            "message":  "질문",
            "noticeId": "does-not-exist",
        })

        with patch("handler.retrieve_and_generate", return_value=_mock_chat_response()) as mock_rag, \
             patch("handler.save_chat_message"):
            resp = handler(event, {})

        assert resp["statusCode"] == 200
        call_kwargs = mock_rag.call_args[1]
        assert call_kwargs["notice_context"] is None

    def test_chat_uses_lang_code(self, dynamodb_setup):
        from handler import handler

        event = make_event("POST", "/chat", body={
            "message": "Lớp chăm sóc là gì?",
            "langCode": "vi",
        })

        with patch("handler.retrieve_and_generate", return_value=_mock_chat_response()) as mock_rag, \
             patch("handler.save_chat_message"):
            resp = handler(event, {})

        call_kwargs = mock_rag.call_args[1]
        assert call_kwargs["language_name"] == "Tiếng Việt"

    def test_chat_includes_recent_history_in_question(self, dynamodb_setup):
        """이전 대화 이력이 full_question에 포함되는지 확인."""
        from rag.db import save_chat_message
        from handler import handler

        # 기존 대화 저장
        save_chat_message(TEST_USER_ID, TEST_SESSION_ID, "user",      "안녕")
        save_chat_message(TEST_USER_ID, TEST_SESSION_ID, "assistant", "안녕하세요!")

        event = make_event("POST", "/chat", body={
            "message":   "돌봄교실 알려주세요",
            "sessionId": TEST_SESSION_ID,
        })

        with patch("handler.retrieve_and_generate", return_value=_mock_chat_response()) as mock_rag, \
             patch("handler.save_chat_message"):
            handler(event, {})

        call_kwargs = mock_rag.call_args[1]
        # 질문에 이전 대화가 포함되어야 함
        assert "안녕" in call_kwargs["question"]

    def test_chat_no_jwt_returns_500(self, dynamodb_setup):
        from handler import handler

        # JWT 없는 이벤트
        event = {
            "version":  "2.0",
            "routeKey": "POST /chat",
            "rawPath":  "/chat",
            "headers":  {},
            "requestContext": {},
            "body":     json.dumps({"message": "질문"}),
        }
        resp = handler(event, {})
        assert resp["statusCode"] == 500

    def test_chat_bedrock_error_returns_500(self, dynamodb_setup):
        from handler import handler

        event = make_event("POST", "/chat", body={"message": "질문"})

        with patch("handler.retrieve_and_generate", side_effect=Exception("Bedrock error")):
            resp = handler(event, {})

        assert resp["statusCode"] == 500
        body = json.loads(resp["body"])
        assert body["code"] == "INTERNAL_ERROR"


# ── GET /chat/history ─────────────────────────────────────────

class TestHandlerHistory:
    def test_history_empty(self, dynamodb_setup):
        from handler import handler

        event = make_event("GET", "/chat/history")
        resp = handler(event, {})

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["data"] == []
        assert body["meta"]["count"] == 0
        assert body["meta"]["nextCursor"] is None

    def test_history_with_messages(self, dynamodb_setup):
        from rag.db import save_chat_message
        from handler import handler

        save_chat_message(TEST_USER_ID, "sess-a", "user",      "질문1")
        save_chat_message(TEST_USER_ID, "sess-a", "assistant", "답변1")

        event = make_event("GET", "/chat/history")
        resp = handler(event, {})

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["meta"]["count"] == 2
        assert all("role" in item for item in body["data"])

    def test_history_pagination_cursor(self, dynamodb_setup):
        from rag.db import save_chat_message
        from handler import handler

        # 25개 저장
        for i in range(25):
            save_chat_message(TEST_USER_ID, f"sess-{i}", "user", f"질문{i}")

        # 첫 페이지
        event1 = make_event("GET", "/chat/history", query_params={"limit": "20"})
        resp1  = handler(event1, {})
        body1  = json.loads(resp1["body"])
        assert body1["meta"]["count"] == 20
        cursor = body1["meta"]["nextCursor"]
        assert cursor is not None

        # 두 번째 페이지
        event2 = make_event("GET", "/chat/history", query_params={"limit": "20", "cursor": cursor})
        resp2  = handler(event2, {})
        body2  = json.loads(resp2["body"])
        assert body2["meta"]["count"] == 5
        assert body2["meta"]["nextCursor"] is None

    def test_history_invalid_cursor_returns_400(self, dynamodb_setup):
        from handler import handler

        event = make_event("GET", "/chat/history", query_params={"cursor": "!!!invalid!!!"})
        resp  = handler(event, {})
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert body["code"] == "INVALID_CURSOR"

    def test_history_limit_capped_at_50(self, dynamodb_setup):
        from rag.db import save_chat_message
        from handler import handler

        for i in range(60):
            save_chat_message(TEST_USER_ID, f"sess-{i}", "user", f"질문{i}")

        event = make_event("GET", "/chat/history", query_params={"limit": "100"})
        resp  = handler(event, {})
        body  = json.loads(resp["body"])
        # limit 100 요청이지만 50으로 캡핑
        assert body["meta"]["count"] <= 50


# ── 라우팅 ────────────────────────────────────────────────────

class TestRouting:
    def test_unknown_route_returns_404(self, dynamodb_setup):
        from handler import handler

        event = make_event("DELETE", "/chat")
        resp  = handler(event, {})
        assert resp["statusCode"] == 404

    def test_response_has_content_type_header(self, dynamodb_setup):
        from handler import handler

        event = make_event("GET", "/chat/history")
        resp  = handler(event, {})
        assert resp["headers"]["Content-Type"] == "application/json"
