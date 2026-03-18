"""
Bedrock Knowledge Base Retrieve + Claude Sonnet 직접 호출.

변경 내역 (S3 Vectors 전환):
  이전: RetrieveAndGenerate API (단일 호출, Bedrock이 컨텍스트 조립)
  이후: Retrieve API (청크 검색) → Claude converse API (답변 생성) 분리

KB_ID 환경변수에서 직접 Knowledge Base ID를 읽는다.
ThrottlingException / ServiceUnavailableException 발생 시 지수 백오프 최대 3회 재시도.
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Optional

import boto3

from .models import ChatResponse, SourceCitation

logger = logging.getLogger(__name__)

# ── 상수 ──────────────────────────────────────────────────────────────────────
_REGION           = os.environ.get("REGION", "us-east-1")
_BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-5")

_RETRIEVAL_RESULTS = 5      # 검색할 청크 수
_MAX_TOKENS        = 1000   # Q&A 최대 토큰 (CLAUDE.md 규정)
_MAX_RETRIES       = 3

# ── AWS 클라이언트 (cold start 최적화) ───────────────────────────────────────
_bedrock_agent_rt = boto3.client("bedrock-agent-runtime", region_name=_REGION)
_bedrock_rt       = boto3.client("bedrock-runtime",       region_name=_REGION)

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "../prompts/rag_system.txt")

KNOWLEDGE_BASE_ID: str = os.environ["KB_ID"]


# ── 프롬프트 로더 ─────────────────────────────────────────────────────────────
def _load_system_prompt() -> str:
    """rag_system.txt 에서 [SYSTEM]~[USER] 사이 시스템 프롬프트를 로드."""
    with open(_PROMPT_PATH, encoding="utf-8") as f:
        content = f.read()
    m = re.search(r"\[SYSTEM\](.*?)\[USER\]", content, re.DOTALL)
    if not m:
        raise ValueError("rag_system.txt 파싱 실패: [SYSTEM]...[USER] 구간 없음")
    return m.group(1).strip()


# ── KB 검색 ───────────────────────────────────────────────────────────────────
def _retrieve_chunks(query: str) -> list[dict]:
    """
    Bedrock Knowledge Base Retrieve API 호출.
    반환: [{"text": str, "uri": str, "score": float}, ...]
    """
    for attempt in range(_MAX_RETRIES):
        try:
            resp = _bedrock_agent_rt.retrieve(
                knowledgeBaseId=KNOWLEDGE_BASE_ID,
                retrievalQuery={"text": query},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {
                        "numberOfResults": _RETRIEVAL_RESULTS,
                    }
                },
            )
            break
        except Exception as e:
            _code = _err_code(e)
            if _code not in ("ThrottlingException", "ServiceUnavailableException") \
                    or attempt == _MAX_RETRIES - 1:
                logger.error({"message": "KB retrieve 실패", "error": str(e)})
                raise
            wait = 2 ** attempt
            logger.warning({"message": f"KB retrieve 재시도 {attempt + 1}", "wait_sec": wait})
            time.sleep(wait)

    chunks = []
    for result in resp.get("retrievalResults", []):
        text     = result.get("content", {}).get("text", "")
        location = result.get("location", {})
        uri      = location.get("s3Location", {}).get("uri", "") \
                   or location.get("type", "")
        score    = result.get("score", 0.0)
        if text:
            chunks.append({"text": text, "uri": uri, "score": score})
    return chunks


# ── 컨텍스트 조립 ─────────────────────────────────────────────────────────────
def _build_context(chunks: list[dict]) -> str:
    """검색된 청크를 번호 붙인 텍스트 블록으로 조합."""
    if not chunks:
        return "(관련 문서를 찾을 수 없습니다.)"
    lines = []
    for i, chunk in enumerate(chunks, 1):
        lines.append(f"[문서 {i}]\n{chunk['text']}")
    return "\n\n".join(lines)


# ── Claude 호출 ───────────────────────────────────────────────────────────────
def _invoke_claude(
    system_prompt: str,
    user_message: str,
) -> str:
    """
    Bedrock converse API로 Claude Sonnet 4.5에 직접 요청.
    재시도: ThrottlingException / ServiceUnavailableException
    """
    for attempt in range(_MAX_RETRIES):
        try:
            resp = _bedrock_rt.converse(
                modelId=_BEDROCK_MODEL_ID,
                system=[{"text": system_prompt}],
                messages=[{
                    "role":    "user",
                    "content": [{"text": user_message}],
                }],
                inferenceConfig={
                    "maxTokens":   _MAX_TOKENS,
                    "temperature": 0.1,
                },
            )
            break
        except Exception as e:
            _code = _err_code(e)
            if _code not in ("ThrottlingException", "ServiceUnavailableException") \
                    or attempt == _MAX_RETRIES - 1:
                logger.error({"message": "Claude converse 실패", "error": str(e)})
                raise
            wait = 2 ** attempt
            logger.warning({"message": f"Claude 재시도 {attempt + 1}", "wait_sec": wait})
            time.sleep(wait)

    return resp["output"]["message"]["content"][0]["text"]


# ── 공개 인터페이스 ───────────────────────────────────────────────────────────
def retrieve_and_generate(
    question: str,
    language_name: str,
    session_id: Optional[str] = None,
    notice_context: Optional[str] = None,
) -> ChatResponse:
    """
    KB 검색 → 컨텍스트 조립 → Claude 직접 호출 방식의 RAG 답변 생성.

    Parameters
    ----------
    question      : 사용자 질문 (다국어 가능)
    language_name : 답변 언어명 (예: "Tiếng Việt")
    session_id    : 세션 ID (응답에 그대로 반환, 세션 관리는 호출자 담당)
    notice_context: 공지 연계 모드 — 해당 공지 요약 텍스트 (None이면 일반 모드)
    """
    # 1. 시스템 프롬프트 로드 + 언어 치환
    system_prompt = _load_system_prompt()
    system_prompt = system_prompt.replace("{language_name}", language_name)

    # 2. KB 검색
    chunks = _retrieve_chunks(question)
    context_text = _build_context(chunks)

    # 3. 사용자 메시지 조합
    #    공지 컨텍스트가 있으면 앞에 추가
    parts: list[str] = []
    if notice_context:
        parts.append(f"[관련 공지 요약]\n{notice_context}")
    parts.append(f"[참고 문서]\n{context_text}")
    parts.append(f"[질문]\n{question}")
    user_message = "\n\n".join(parts)

    # 4. Claude 직접 호출
    answer = _invoke_claude(system_prompt, user_message)

    # 5. 출처 목록 구성 (score 기준 상위 5개)
    sources = [
        SourceCitation(content=c["text"][:200], location=c["uri"])
        for c in chunks
        if c.get("uri")
    ]

    new_session = session_id or ""
    logger.info({
        "message":   "RAG 답변 생성 완료",
        "sessionId": new_session,
        "chunks":    len(chunks),
        "sources":   len(sources),
    })
    return ChatResponse(answer=answer, session_id=new_session, sources=sources)


# ── 내부 유틸 ─────────────────────────────────────────────────────────────────
def _err_code(exc: Exception) -> str:
    """boto3 예외에서 error code 문자열 추출."""
    response = getattr(exc, "response", None) or {}
    return response.get("Error", {}).get("Code", type(exc).__name__)
