"""
rag 서브모듈 단위 테스트 (models, db, retrieval)
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import (
    CHAT_HISTORY_TABLE,
    NOTICES_TABLE,
    TEST_USER_ID,
    TEST_SESSION_ID,
    dynamodb_setup,
)


# ── models.py ─────────────────────────────────────────────────

class TestModels:
    def test_chat_response_to_dict(self):
        from rag.models import ChatResponse, SourceCitation

        resp = ChatResponse(
            answer="안녕하세요.",
            session_id="sess-001",
            sources=[SourceCitation(content="내용", location="s3://bucket/doc.pdf")],
        )
        d = resp.to_dict()
        assert d["answer"] == "안녕하세요."
        assert d["sessionId"] == "sess-001"
        assert len(d["sources"]) == 1
        assert d["sources"][0]["location"] == "s3://bucket/doc.pdf"

    def test_source_citation_to_dict(self):
        from rag.models import SourceCitation

        s = SourceCitation(content="텍스트", location="s3://bucket/file.txt")
        d = s.to_dict()
        assert d["content"] == "텍스트"
        assert d["location"] == "s3://bucket/file.txt"

    def test_chat_history_item_to_dict(self):
        from rag.models import ChatHistoryItem

        item = ChatHistoryItem(
            user_id="u1",
            session_id="s1",
            role="user",
            content="질문",
            created_at="2025-10-01T00:00:00+00:00",
            expires_at=9999999999,
        )
        d = item.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "질문"
        assert "sessionId" in d
        assert "userId" not in d  # 개인정보 — userId는 DynamoDB PK이지 응답 필드 아님

    def test_language_names_includes_ko(self):
        from rag.models import LANGUAGE_NAMES

        assert "ko" in LANGUAGE_NAMES
        assert "vi" in LANGUAGE_NAMES
        assert len(LANGUAGE_NAMES) >= 9


# ── db.py ─────────────────────────────────────────────────────

class TestDb:
    def test_save_and_get_recent_messages(self, dynamodb_setup):
        from rag.db import save_chat_message, get_recent_messages

        save_chat_message(TEST_USER_ID, TEST_SESSION_ID, "user",      "안녕하세요")
        save_chat_message(TEST_USER_ID, TEST_SESSION_ID, "assistant", "안녕하세요! 무엇을 도와드릴까요?")

        msgs = get_recent_messages(TEST_USER_ID, TEST_SESSION_ID)
        assert len(msgs) == 2
        # 오래된 순 정렬 확인
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_get_recent_messages_empty_session(self, dynamodb_setup):
        from rag.db import get_recent_messages

        msgs = get_recent_messages(TEST_USER_ID, "non-existent-session")
        assert msgs == []

    def test_save_message_sets_ttl(self, dynamodb_setup):
        import time
        from rag.db import save_chat_message

        item = save_chat_message(TEST_USER_ID, TEST_SESSION_ID, "user", "테스트")
        assert item.expires_at > time.time()
        # TTL이 약 90일 이후인지 확인 (88~92일 허용)
        diff_days = (item.expires_at - time.time()) / 86400
        assert 88 < diff_days < 92

    def test_get_chat_history_pagination(self, dynamodb_setup):
        from rag.db import save_chat_message, get_chat_history

        # 25개 메시지 저장 (다른 세션)
        for i in range(25):
            save_chat_message(TEST_USER_ID, f"sess-{i}", "user", f"질문 {i}")

        items, last_key = get_chat_history(TEST_USER_ID, limit=20)
        assert len(items) == 20
        assert last_key is not None  # 다음 페이지 있음

        items2, last_key2 = get_chat_history(TEST_USER_ID, limit=20, exclusive_start_key=last_key)
        assert len(items2) == 5
        assert last_key2 is None  # 마지막 페이지

    def test_get_notice_by_id_found(self, dynamodb_setup):
        import boto3
        from rag.db import get_notice_by_id

        # Notices 테이블에 아이템 삽입
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        table = ddb.Table(NOTICES_TABLE)
        table.put_item(Item={
            "schoolId":  "school-001",
            "createdAt": "2025-10-01T00:00:00#notice-001",
            "noticeId":  "notice-001",
            "title":     "현장학습 안내",
            "summary":   "10월 15일 현장학습",
        })

        result = get_notice_by_id("notice-001")
        assert result is not None
        assert result["title"] == "현장학습 안내"
        assert result["summary"] == "10월 15일 현장학습"

    def test_get_notice_by_id_not_found(self, dynamodb_setup):
        from rag.db import get_notice_by_id

        result = get_notice_by_id("non-existent-notice")
        assert result is None


# ── retrieval.py ──────────────────────────────────────────────

MOCK_RAG_RESPONSE = {
    "output": {"text": "돌봄교실 신청은 학교 홈페이지에서 하실 수 있습니다."},
    "sessionId": "bedrock-session-001",
    "citations": [
        {
            "retrievedReferences": [
                {
                    "content":  {"text": "돌봄교실 관련 안내 문서"},
                    "location": {"s3Location": {"uri": "s3://kb-source/dolbom.pdf"}},
                }
            ]
        }
    ],
}


class TestRetrieval:
    def test_retrieve_and_generate_success(self):
        from rag.retrieval import retrieve_and_generate

        with patch("rag.retrieval._bedrock_agent_rt") as mock_client:
            mock_client.retrieve_and_generate.return_value = MOCK_RAG_RESPONSE
            result = retrieve_and_generate(
                question="돌봄교실 어떻게 신청해요?",
                language_name="한국어",
            )

        assert "돌봄교실" in result.answer
        assert result.session_id == "bedrock-session-001"
        assert len(result.sources) == 1
        assert "dolbom.pdf" in result.sources[0].location

    def test_retrieve_passes_session_id(self):
        from rag.retrieval import retrieve_and_generate

        with patch("rag.retrieval._bedrock_agent_rt") as mock_client:
            mock_client.retrieve_and_generate.return_value = MOCK_RAG_RESPONSE
            retrieve_and_generate(
                question="질문",
                language_name="English",
                session_id="existing-session",
            )
            call_kwargs = mock_client.retrieve_and_generate.call_args[1]
            assert call_kwargs.get("sessionId") == "existing-session"

    def test_retrieve_no_session_id_omits_key(self):
        from rag.retrieval import retrieve_and_generate

        with patch("rag.retrieval._bedrock_agent_rt") as mock_client:
            mock_client.retrieve_and_generate.return_value = MOCK_RAG_RESPONSE
            retrieve_and_generate(
                question="질문",
                language_name="English",
                session_id=None,
            )
            call_kwargs = mock_client.retrieve_and_generate.call_args[1]
            assert "sessionId" not in call_kwargs

    def test_retrieve_notice_context_prepended(self):
        from rag.retrieval import retrieve_and_generate

        with patch("rag.retrieval._bedrock_agent_rt") as mock_client:
            mock_client.retrieve_and_generate.return_value = MOCK_RAG_RESPONSE
            retrieve_and_generate(
                question="비용은 얼마예요?",
                language_name="Tiếng Việt",
                notice_context="현장학습 비용 15,000원",
            )
            call_kwargs = mock_client.retrieve_and_generate.call_args[1]
            input_text = call_kwargs["input"]["text"]
            assert "현장학습 비용 15,000원" in input_text
            assert "비용은 얼마예요?" in input_text

    def test_retrieve_throttling_retry(self):
        from rag.retrieval import retrieve_and_generate

        call_count = 0
        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                exc = Exception("ThrottlingException")
                exc.response = {"Error": {"Code": "ThrottlingException"}}
                raise exc
            return MOCK_RAG_RESPONSE

        with patch("rag.retrieval._bedrock_agent_rt") as mock_client, \
             patch("rag.retrieval.time.sleep"):
            mock_client.retrieve_and_generate.side_effect = side_effect
            result = retrieve_and_generate(
                question="질문",
                language_name="English",
            )

        assert call_count == 2
        assert result.answer != ""

    def test_retrieve_extracts_multiple_sources(self):
        from rag.retrieval import retrieve_and_generate

        response_multi_src = {
            "output": {"text": "답변"},
            "sessionId": "s",
            "citations": [
                {
                    "retrievedReferences": [
                        {"content": {"text": "문서1"}, "location": {"s3Location": {"uri": "s3://kb/doc1.pdf"}}},
                        {"content": {"text": "문서2"}, "location": {"s3Location": {"uri": "s3://kb/doc2.pdf"}}},
                    ]
                },
                {
                    "retrievedReferences": [
                        {"content": {"text": "문서1 중복"}, "location": {"s3Location": {"uri": "s3://kb/doc1.pdf"}}},
                    ]
                },
            ],
        }

        with patch("rag.retrieval._bedrock_agent_rt") as mock_client:
            mock_client.retrieve_and_generate.return_value = response_multi_src
            result = retrieve_and_generate(question="질문", language_name="English")

        # 중복 URI는 제거되어야 함
        assert len(result.sources) == 2
        uris = [s.location for s in result.sources]
        assert len(set(uris)) == 2

    def test_load_prompt_template_contains_search_results(self):
        from rag.retrieval import _load_prompt_template

        template = _load_prompt_template()
        assert "$search_results$" in template
        assert "{language_name}" in template
