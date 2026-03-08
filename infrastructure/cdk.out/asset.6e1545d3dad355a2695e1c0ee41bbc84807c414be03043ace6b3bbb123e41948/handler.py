"""
rag-query-handler Lambda handler (Python 3.12)
API Gateway 트리거. 자연어 질문 → 임베딩 → Vector Search → Bedrock 답변 생성.
"""
import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "")
TRANSLATION_CACHE_TABLE = os.environ.get("TRANSLATION_CACHE_TABLE", "")


def handler(event: dict, context) -> dict:
    """
    APIGatewayProxyEvent 핸들러.
    TODO: 질문 임베딩 → OpenSearch Vector Search → Bedrock 답변 생성 → 캐시 저장
    환각 최소화: 지식베이스에 없는 내용은 "담임 선생님께 문의" 안내
    """
    logger.info({"message": "rag query received"})

    try:
        body = json.loads(event.get("body") or "{}")
        question = body.get("question", "")
        lang_code = body.get("langCode", "ko")

        if not question:
            return _error_response(400, "question is required", "MISSING_QUESTION")

        # TODO: RAG 파이프라인 실행

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "data": {"answer": "TODO", "sources": []},
                    "meta": {"langCode": lang_code},
                }
            ),
        }
    except Exception as e:
        logger.error({"message": "rag query failed", "error": str(e)})
        return _error_response(500, "internal server error", "INTERNAL_ERROR")


def _error_response(status_code: int, message: str, code: str) -> dict:
    import datetime
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "error": message,
                "code": code,
                "meta": {"timestamp": datetime.datetime.utcnow().isoformat()},
            }
        ),
    }
