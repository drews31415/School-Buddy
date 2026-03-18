"""
rag-query-handler Lambda handler (Python 3.12)

API Gateway HTTP API v2 트리거.
- POST /chat   : 사용자 질문 → Bedrock KB RetrieveAndGenerate → 답변 + ChatHistory 저장
- GET  /chat/history : 사용자 대화 이력 조회 (페이지네이션)

환경변수:
  KB_ID              Bedrock KB ID (.env 파일 또는 Lambda 환경변수로 주입)
  CHAT_HISTORY_TABLE DynamoDB ChatHistory 테이블명
  NOTICES_TABLE      DynamoDB Notices 테이블명
  REGION             AWS 리전 (기본: us-east-1)
"""
from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

from rag.db import (
    save_chat_message,
    get_recent_messages,
    get_chat_history,
    get_notice_by_id,
)
from rag.models import LANGUAGE_NAMES
from rag.retrieval import retrieve_and_generate

_MAX_QUESTION_LEN = 1000


def handler(event: dict, context) -> dict:
    route_key = event.get("routeKey", "")
    logger.info({"message": "rag handler invoked", "routeKey": route_key})

    try:
        if route_key == "POST /chat":
            return _handle_chat(event)
        elif route_key == "GET /chat/history":
            return _handle_history(event)
        else:
            return _error(404, "route not found", "NOT_FOUND")
    except Exception as e:
        logger.error({"message": "unhandled error", "error": str(e)})
        return _error(500, "internal server error", "INTERNAL_ERROR")


# ── POST /chat ─────────────────────────────────────────────────

def _handle_chat(event: dict) -> dict:
    user_id = _get_user_id(event)
    body    = json.loads(event.get("body") or "{}")

    # ── 입력 검증 ──────────────────────────────────────────────
    message = (body.get("message") or "").strip()
    if not message:
        return _error(400, "message is required", "MISSING_MESSAGE")
    if len(message) > _MAX_QUESTION_LEN:
        return _error(400, f"message too long (max {_MAX_QUESTION_LEN} chars)", "MESSAGE_TOO_LONG")

    session_id = body.get("sessionId") or str(uuid.uuid4())
    notice_id  = body.get("noticeId")   # 공지 연계 모드 (optional)
    lang_code  = body.get("langCode", "ko")
    language_name = LANGUAGE_NAMES.get(lang_code, "English")

    # ── 공지 컨텍스트 조회 (noticeId 제공 시) ──────────────────
    notice_context: str | None = None
    if notice_id:
        notice = get_notice_by_id(notice_id)
        if notice:
            summary = notice.get("summary", "")
            title   = notice.get("title", "")
            notice_context = f"제목: {title}\n요약: {summary}" if summary else None
            logger.info({"message": "notice context loaded", "noticeId": notice_id})

    # ── 최근 대화 이력 컨텍스트 구성 ──────────────────────────
    recent = get_recent_messages(user_id, session_id)
    context_prefix = ""
    if recent:
        lines = []
        for msg in recent:
            role    = msg.get("role", "user")
            content = msg.get("content", "")
            lines.append(f"[{role}] {content}")
        context_prefix = "\n".join(lines) + "\n\n"

    # 대화 이력을 질문 앞에 첨부
    full_question = f"{context_prefix}[user] {message}" if context_prefix else message

    # ── Bedrock KB RetrieveAndGenerate ─────────────────────────
    chat_response = retrieve_and_generate(
        question=full_question,
        language_name=language_name,
        session_id=session_id,
        notice_context=notice_context,
    )

    # ── ChatHistory 저장 ────────────────────────────────────────
    save_chat_message(user_id, session_id, "user",      message)
    save_chat_message(user_id, session_id, "assistant", chat_response.answer)

    return _ok({
        "data": chat_response.to_dict(),
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "langCode":  lang_code,
        },
    })


# ── GET /chat/history ─────────────────────────────────────────

def _handle_history(event: dict) -> dict:
    user_id      = _get_user_id(event)
    params       = event.get("queryStringParameters") or {}
    limit_str    = params.get("limit", "20")
    cursor_b64   = params.get("cursor")   # base64url-encoded LastEvaluatedKey

    try:
        limit = max(1, min(int(limit_str), 50))
    except ValueError:
        limit = 20

    # cursor 디코딩
    exclusive_start_key: dict | None = None
    if cursor_b64:
        try:
            raw = base64.urlsafe_b64decode(cursor_b64 + "==")
            exclusive_start_key = json.loads(raw)
        except Exception:
            return _error(400, "invalid cursor", "INVALID_CURSOR")

    items, last_key = get_chat_history(user_id, limit=limit, exclusive_start_key=exclusive_start_key)

    # cursor 인코딩
    next_cursor: str | None = None
    if last_key:
        raw = json.dumps(last_key, separators=(",", ":")).encode()
        next_cursor = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return _ok({
        "data": [
            {
                "sessionId": item.get("sessionId", ""),
                "role":      item.get("role", ""),
                "content":   item.get("content", ""),
                "createdAt": item.get("createdAt", ""),
            }
            for item in items
        ],
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nextCursor": next_cursor,
            "count":     len(items),
        },
    })


# ── 공통 유틸 ──────────────────────────────────────────────────

def _get_user_id(event: dict) -> str:
    try:
        sub = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        if not sub or not isinstance(sub, str):
            raise ValueError("sub is empty")
        return sub
    except (KeyError, TypeError, ValueError) as e:
        raise PermissionError("JWT sub claim 없음") from e


def _ok(body: dict) -> dict:
    return {
        "statusCode": 200,
        "headers":    {"Content-Type": "application/json"},
        "body":       json.dumps(body, ensure_ascii=False),
    }


def _error(status_code: int, message: str, code: str) -> dict:
    return {
        "statusCode": status_code,
        "headers":    {"Content-Type": "application/json"},
        "body":       json.dumps(
            {
                "error": message,
                "code":  code,
                "meta":  {"timestamp": datetime.now(timezone.utc).isoformat()},
            },
            ensure_ascii=False,
        ),
    }
