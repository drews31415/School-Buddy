"""
Amazon Bedrock 공통 클라이언트 (shared-utils).

모든 Bedrock 호출은 이 모듈의 invoke_model()을 통해 한다.
직접 boto3 bedrock-runtime 호출 금지 (비용 추적 및 재시도 로직 누락 방지).

환경변수:
  BEDROCK_MODEL_ID  사용할 Claude 모델 ID (기본: claude-sonnet-4-20250514)
  REGION            AWS 리전 (기본: us-east-1)
"""
from __future__ import annotations

import json
import logging
import os
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# ── 클라이언트 (모듈 레벨 초기화 — cold-start 최적화) ──────────
_REGION = os.environ.get("REGION", "us-east-1")
_bedrock = boto3.client("bedrock-runtime", region_name=_REGION)
_cloudwatch = boto3.client("cloudwatch", region_name=_REGION)

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "claude-sonnet-4-20250514")

# 재시도 대기 시간 (초) — exponential backoff: 1s → 2s → 4s
_RETRY_DELAYS = [1, 2, 4]

# ThrottlingException / ServiceUnavailableException 만 재시도 대상
_RETRYABLE_ERRORS = frozenset({"ThrottlingException", "ServiceUnavailableException"})


class BedrockResponseError(Exception):
    """Bedrock 응답이 유효한 JSON 형식이 아닐 때 발생."""


def invoke_model(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1000,
    model_id: str | None = None,
) -> str:
    """
    Bedrock Claude 모델 호출 래퍼.

    Parameters
    ----------
    system_prompt : str
        시스템 프롬프트 — 역할 설정 및 출력 형식 지시
    user_prompt : str
        사용자 프롬프트 — 실제 입력 데이터
    max_tokens : int
        최대 출력 토큰 수 (요약 500 / 번역 800 / Q&A 1000 권장)
    model_id : str, optional
        사용할 모델 ID. None이면 MODULE 상수 MODEL_ID 사용.

    Returns
    -------
    str
        모델 응답 텍스트 (유효한 JSON 문자열 보장)

    Raises
    ------
    BedrockResponseError
        응답이 JSON 파싱 불가능한 경우 (재시도 없이 즉시 전파)
    RuntimeError
        최대 재시도(4회) 후에도 Bedrock 호출 실패
    """
    model = model_id or MODEL_ID
    request_body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        },
        ensure_ascii=False,
    )

    last_error: Exception | None = None

    # 첫 시도 + 최대 3회 재시도 = 총 4회
    attempts = [0] + _RETRY_DELAYS
    for attempt_idx, delay in enumerate(attempts, start=1):
        if delay:
            logger.info(
                {"message": "bedrock retry", "attempt": attempt_idx, "delay_sec": delay}
            )
            time.sleep(delay)

        try:
            response = _bedrock.invoke_model(
                modelId=model,
                contentType="application/json",
                accept="application/json",
                body=request_body,
            )

            raw: dict = json.loads(response["body"].read())
            text: str = raw["content"][0]["text"].strip()

            # CloudWatch 토큰 사용량 기록 (비동기 방화벽 — 실패해도 진행)
            usage = raw.get("usage", {})
            _record_token_usage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                model_id=model,
            )

            # JSON 유효성 검증 — 실패 시 재시도 없이 즉시 예외 전파
            try:
                json.loads(text)
            except json.JSONDecodeError as parse_err:
                raise BedrockResponseError(
                    f"응답이 JSON 형식이 아닙니다. 앞 200자: {text[:200]}"
                ) from parse_err

            logger.info(
                {
                    "message": "bedrock invoke success",
                    "model": model,
                    "attempt": attempt_idx,
                    "input_tokens": usage.get("input_tokens"),
                    "output_tokens": usage.get("output_tokens"),
                }
            )
            return text

        except BedrockResponseError:
            raise  # JSON 오류는 재시도 없이 즉시 전파

        except ClientError as e:
            last_error = e
            error_code = e.response["Error"]["Code"]
            logger.warning(
                {
                    "message": "bedrock call failed",
                    "attempt": attempt_idx,
                    "error_code": error_code,
                    "model": model,
                }
            )
            if error_code not in _RETRYABLE_ERRORS:
                raise  # 재시도 불가 오류는 즉시 전파

    raise RuntimeError(
        f"Bedrock 호출 최대 재시도 초과 ({len(attempts)}회): {last_error}"
    ) from last_error


# ── 내부 함수 ────────────────────────────────────────────────

def _record_token_usage(input_tokens: int, output_tokens: int, model_id: str) -> None:
    """
    토큰 사용량을 CloudWatch 커스텀 메트릭으로 기록.
    네임스페이스: SchoolBuddy/Bedrock
    실패해도 메인 플로우를 중단하지 않는다.
    """
    if input_tokens == 0 and output_tokens == 0:
        return
    try:
        _cloudwatch.put_metric_data(
            Namespace="SchoolBuddy/Bedrock",
            MetricData=[
                {
                    "MetricName": "InputTokens",
                    "Dimensions": [{"Name": "ModelId", "Value": model_id}],
                    "Value": float(input_tokens),
                    "Unit": "Count",
                },
                {
                    "MetricName": "OutputTokens",
                    "Dimensions": [{"Name": "ModelId", "Value": model_id}],
                    "Value": float(output_tokens),
                    "Unit": "Count",
                },
            ],
        )
    except Exception as e:
        logger.warning({"message": "CloudWatch 메트릭 기록 실패", "error": str(e)})
