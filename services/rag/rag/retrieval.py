"""
Bedrock Knowledge Base RetrieveAndGenerate 래퍼.

bedrock-agent-runtime 클라이언트를 사용하여 RAG 답변을 생성한다.
ThrottlingException 발생 시 지수 백오프로 최대 3회 재시도.
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

_REGION           = os.environ.get("REGION", "us-east-1")
KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID", "")
BEDROCK_MODEL_ARN = (
    f"arn:aws:bedrock:{_REGION}::foundation-model/"
    "anthropic.claude-sonnet-4-20250514-v1:0"
)

_RETRIEVAL_RESULTS = 5      # 검색할 문서 수
_MAX_TOKENS        = 1000   # Q&A 최대 토큰 (CLAUDE.md 규정)
_MAX_RETRIES       = 3

_bedrock_agent_rt = boto3.client("bedrock-agent-runtime", region_name=_REGION)

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "../prompts/rag_system.txt")


def _load_prompt_template() -> str:
    """rag_system.txt에서 [SYSTEM]~[USER] 사이 시스템 프롬프트를 로드."""
    with open(_PROMPT_PATH, encoding="utf-8") as f:
        content = f.read()
    m = re.search(r"\[SYSTEM\](.*?)\[USER\]", content, re.DOTALL)
    if not m:
        raise ValueError("rag_system.txt 파싱 실패: [SYSTEM]...[USER] 구간 없음")
    return m.group(1).strip()


def _extract_sources(citations: list[dict]) -> list[SourceCitation]:
    """Bedrock citations 배열에서 출처 목록을 추출."""
    sources: list[SourceCitation] = []
    seen: set[str] = set()
    for citation in citations:
        for ref in citation.get("retrievedReferences", []):
            content  = ref.get("content", {}).get("text", "")[:200]
            location = ref.get("location", {})
            s3_loc   = location.get("s3Location", {})
            uri      = s3_loc.get("uri", "")
            if uri and uri not in seen:
                seen.add(uri)
                sources.append(SourceCitation(content=content, location=uri))
    return sources


def retrieve_and_generate(
    question: str,
    language_name: str,
    session_id: Optional[str] = None,
    notice_context: Optional[str] = None,
) -> ChatResponse:
    """
    Bedrock Knowledge Base RetrieveAndGenerate 호출.

    Parameters
    ----------
    question      : 사용자 질문 (다국어 가능)
    language_name : 답변 언어명 (예: "Tiếng Việt")
    session_id    : Bedrock 네이티브 세션 ID (None이면 새 세션)
    notice_context: 공지 연계 모드 — 해당 공지 요약 텍스트 (None이면 일반 모드)
    """
    # 프롬프트 템플릿 렌더링
    system_prompt = _load_prompt_template()
    system_prompt = system_prompt.replace("{language_name}", language_name)

    # 공지 컨텍스트가 있으면 질문 앞에 추가
    user_text = question
    if notice_context:
        user_text = (
            f"[관련 공지 요약]\n{notice_context}\n\n"
            f"[질문]\n{question}"
        )
    system_prompt = system_prompt.replace("{user_question}", user_text)

    request: dict = {
        "input":  {"text": user_text},
        "retrieveAndGenerateConfiguration": {
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": KNOWLEDGE_BASE_ID,
                "modelArn":        BEDROCK_MODEL_ARN,
                "retrievalConfiguration": {
                    "vectorSearchConfiguration": {
                        "numberOfResults": _RETRIEVAL_RESULTS,
                    }
                },
                "generationConfiguration": {
                    "promptTemplate": {
                        "textPromptTemplate": system_prompt,
                    },
                    "inferenceConfig": {
                        "textInferenceConfig": {
                            "maxTokens":   _MAX_TOKENS,
                            "temperature": 0.1,
                        }
                    },
                },
            },
        },
    }

    # 기존 세션 연속 시 sessionId 추가
    if session_id:
        request["sessionId"] = session_id

    # 재시도 루프 (ThrottlingException / ServiceUnavailableException)
    for attempt in range(_MAX_RETRIES):
        try:
            response = _bedrock_agent_rt.retrieve_and_generate(**request)
            break
        except Exception as e:
            err_name = type(e).__name__
            err_code = getattr(getattr(e, "response", {}), "get", lambda *_: "")(
                "Error", {}
            ).get("Code", err_name)
            retryable = err_code in ("ThrottlingException", "ServiceUnavailableException")
            if not retryable or attempt == _MAX_RETRIES - 1:
                logger.error(
                    {"message": "retrieve_and_generate 실패", "error": str(e), "attempt": attempt}
                )
                raise
            wait = 2 ** attempt
            logger.warning(
                {"message": f"재시도 {attempt + 1}/{_MAX_RETRIES}", "wait_sec": wait}
            )
            time.sleep(wait)

    answer     = response.get("output", {}).get("text", "")
    new_sess   = response.get("sessionId", session_id or "")
    citations  = response.get("citations", [])
    sources    = _extract_sources(citations)

    logger.info(
        {
            "message":  "RAG 답변 생성 완료",
            "sessionId": new_sess,
            "sources":   len(sources),
        }
    )
    return ChatResponse(answer=answer, session_id=new_sess, sources=sources)
