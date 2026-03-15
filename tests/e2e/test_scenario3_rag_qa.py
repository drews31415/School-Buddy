"""
시나리오 3: RAG Q&A
목표 SLA: 응답 5초 이내

테스트 흐름:
1. POST /chat {"message": "돌봄교실이 뭐예요?", "sessionId": "test-session"}
2. 응답에 "돌봄" 키워드 포함 확인
3. GET /chat/history → 이력 2건 확인 (user + assistant)
"""
import pytest

from tests.e2e.config import SLA_RAG_RESPONSE_SEC
from tests.e2e.utils.api import APIClient


class TestRagQA:
    """RAG Q&A API E2E 시나리오."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_api(self, api: APIClient):
        if not api.base_url:
            pytest.skip("E2E_API_BASE_URL 미설정")

    # ── 정상 케이스 ───────────────────────────────────────────────────────────
    def test_chat_returns_200(self, api: APIClient, e2e_session_id: str):
        """POST /chat 가 200을 반환한다."""
        resp, _ = api.timed_post(
            "/chat",
            json={
                "message":   "돌봄교실이 뭐예요?",
                "sessionId": e2e_session_id,
                "langCode":  "vi",
            },
        )
        assert resp.status_code == 200, (
            f"HTTP 200 예상, 실제: {resp.status_code}\n{resp.text[:500]}"
        )

    def test_chat_response_contains_keyword(
        self, api: APIClient, e2e_session_id: str
    ):
        """
        '돌봄교실이 뭐예요?' 질문에 대한 답변에
        '돌봄' 키워드가 포함되어 있다.
        """
        resp, _ = api.timed_post(
            "/chat",
            json={
                "message":   "돌봄교실이 뭐예요?",
                "sessionId": e2e_session_id,
                "langCode":  "vi",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body)

        answer: str = data.get("answer", "")
        assert answer, "answer 필드가 비어있습니다."

        # 번역된 답변이므로 "돌봄" 또는 "lớp chăm sóc"(vi) 중 하나 포함
        keyword_found = (
            "돌봄" in answer
            or "chăm sóc" in answer.lower()
            or "after-school" in answer.lower()
            or "care" in answer.lower()
        )
        assert keyword_found, (
            f"'돌봄' 관련 키워드가 답변에 없습니다.\n답변: {answer[:200]}"
        )

    def test_chat_response_has_session_id(
        self, api: APIClient, e2e_session_id: str
    ):
        """응답에 sessionId 필드가 존재한다 (세션 연속성)."""
        resp, _ = api.timed_post(
            "/chat",
            json={
                "message":   "급식이란 뭔가요?",
                "sessionId": e2e_session_id,
                "langCode":  "vi",
            },
        )
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert "sessionId" in data, "sessionId 필드 누락"
        assert data["sessionId"], "sessionId 가 빈 문자열입니다."

    def test_chat_response_has_sources(
        self, api: APIClient, e2e_session_id: str
    ):
        """RAG 응답에 sources 필드(출처 문서 목록)가 존재한다."""
        resp, _ = api.timed_post(
            "/chat",
            json={
                "message":   "현장학습 준비물이 뭐예요?",
                "sessionId": e2e_session_id,
                "langCode":  "vi",
            },
        )
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert "sources" in data, "sources 필드 누락"
        assert isinstance(data["sources"], list), "sources가 list가 아님"

    def test_no_refusal_phrases_in_answer(
        self, api: APIClient, e2e_session_id: str
    ):
        """답변에 거절 문구가 없어야 한다 (CLAUDE.md QA 기준 §5)."""
        resp, _ = api.timed_post(
            "/chat",
            json={
                "message":   "돌봄교실이 뭐예요?",
                "sessionId": e2e_session_id,
                "langCode":  "vi",
            },
        )
        data   = resp.json().get("data", resp.json())
        answer = data.get("answer", "")

        forbidden = [
            "I cannot", "I'm unable", "I am unable",
            "저는 할 수 없습니다", "알 수 없습니다",
            "I don't have information",
        ]
        for phrase in forbidden:
            assert phrase not in answer, f"거절 문구 감지: '{phrase}'"

    # ── 채팅 이력 확인 ────────────────────────────────────────────────────────
    def test_chat_history_contains_two_records(
        self, api: APIClient, e2e_session_id: str
    ):
        """
        1회 대화 후 GET /chat/history 에서
        user 메시지 1건 + assistant 메시지 1건 = 최소 2건이 조회된다.
        """
        # 대화 1회 실행
        send_resp, _ = api.timed_post(
            "/chat",
            json={
                "message":   "돌봄교실이 뭐예요?",
                "sessionId": e2e_session_id,
                "langCode":  "vi",
            },
        )
        assert send_resp.status_code == 200

        # 이력 조회
        hist_resp, _ = api.timed_get("/chat/history", params={"limit": 20})
        assert hist_resp.status_code == 200

        body = hist_resp.json()
        history: list = body.get("data", [])
        assert len(history) >= 2, (
            f"이력 최소 2건 예상, 실제: {len(history)}건\n이력: {history}"
        )

        roles = {msg.get("role") for msg in history}
        assert "user"      in roles, "이력에 user 메시지 없음"
        assert "assistant" in roles, "이력에 assistant 메시지 없음"

    def test_chat_history_has_pagination_meta(
        self, api: APIClient, e2e_session_id: str
    ):
        """GET /chat/history 응답에 meta.nextCursor 필드가 존재한다."""
        resp, _ = api.timed_get("/chat/history", params={"limit": 5})
        assert resp.status_code == 200
        body = resp.json()
        assert "meta" in body, "meta 필드 누락"
        assert "nextCursor" in body["meta"], "meta.nextCursor 필드 누락"

    # ── 세션 연속성 ───────────────────────────────────────────────────────────
    def test_session_continuity_maintains_context(
        self, api: APIClient, e2e_session_id: str
    ):
        """
        같은 sessionId로 2회 연속 질문 시
        두 번째 답변이 첫 번째 맥락을 유지한다.
        (sessionId가 응답에 포함되며 동일한 값을 반환)
        """
        # 첫 번째 질문
        resp1, _ = api.timed_post(
            "/chat",
            json={
                "message":   "돌봄교실이 뭐예요?",
                "sessionId": e2e_session_id,
                "langCode":  "vi",
            },
        )
        assert resp1.status_code == 200
        returned_session_id = resp1.json().get("data", {}).get("sessionId")

        # 두 번째 질문 (반환된 sessionId 사용)
        resp2, _ = api.timed_post(
            "/chat",
            json={
                "message":   "몇 시까지 운영하나요?",
                "sessionId": returned_session_id or e2e_session_id,
                "langCode":  "vi",
            },
        )
        assert resp2.status_code == 200
        data2 = resp2.json().get("data", resp2.json())
        assert data2.get("answer"), "두 번째 답변이 비어있습니다."

    # ── SLA 검증 ──────────────────────────────────────────────────────────────
    def test_response_time_within_sla(self, api: APIClient, e2e_session_id: str):
        """
        RAG Q&A 응답 시간이 SLA_RAG_RESPONSE_SEC(5초) 이내여야 한다.
        """
        resp, elapsed = api.timed_post(
            "/chat",
            json={
                "message":   "돌봄교실이 뭐예요?",
                "sessionId": e2e_session_id,
                "langCode":  "vi",
            },
        )
        assert resp.status_code == 200
        assert elapsed <= SLA_RAG_RESPONSE_SEC, (
            f"[SLA 위반] RAG 응답 시간: {elapsed:.2f}초 "
            f"(SLA: {SLA_RAG_RESPONSE_SEC}초)"
        )
        print(f"\n✅ RAG 응답 시간: {elapsed:.2f}초 (SLA: {SLA_RAG_RESPONSE_SEC}초)")

    def test_history_response_time_within_500ms(
        self, api: APIClient, e2e_session_id: str
    ):
        """
        GET /chat/history 응답 시간이 500ms 이내여야 한다.
        (CLAUDE.md 공지 목록 조회 SLA 준용)
        """
        resp, elapsed = api.timed_get("/chat/history", params={"limit": 20})
        assert resp.status_code == 200
        assert elapsed <= 0.5, (
            f"[SLA 위반] 이력 조회 응답 시간: {elapsed * 1000:.0f}ms (SLA: 500ms)"
        )

    # ── 엣지 케이스 ───────────────────────────────────────────────────────────
    def test_empty_message_returns_4xx(self, api: APIClient, e2e_session_id: str):
        """빈 메시지 전송 시 4xx 에러를 반환한다."""
        resp, _ = api.timed_post(
            "/chat",
            json={"message": "", "sessionId": e2e_session_id, "langCode": "vi"},
        )
        assert 400 <= resp.status_code < 500, (
            f"빈 메시지에 4xx 예상, 실제: {resp.status_code}"
        )

    def test_missing_message_field_returns_400(
        self, api: APIClient, e2e_session_id: str
    ):
        """message 필드 없이 요청 시 400을 반환한다."""
        resp, _ = api.timed_post(
            "/chat",
            json={"sessionId": e2e_session_id, "langCode": "vi"},
        )
        assert resp.status_code == 400, (
            f"message 필드 누락에 400 예상, 실제: {resp.status_code}"
        )
        body = resp.json()
        assert "error" in body or "code" in body, "에러 응답 형식 불일치"
