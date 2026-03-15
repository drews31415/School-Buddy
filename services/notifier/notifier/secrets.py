"""
AWS Secrets Manager에서 FCM 서비스 계정 키를 조회한다.
Lambda 워밍업 후 재사용을 위해 모듈 레벨에서 캐싱한다.
"""
from __future__ import annotations

import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)

_secretsmanager = boto3.client(
    "secretsmanager", region_name=os.environ.get("REGION", "us-east-1")
)

FCM_SECRETS_NAME = os.environ.get("FCM_SECRETS_NAME", "school-buddy/fcm-service-account")

# Lambda 웜(warm) 실행 시 재조회 방지용 캐시
_cached_credentials: dict | None = None


def get_fcm_credentials() -> dict:
    """
    FCM 서비스 계정 JSON을 Secrets Manager에서 조회한다.
    동일 Lambda 컨테이너 내에서는 캐시를 재사용한다.

    Returns
    -------
    dict : Firebase Admin SDK 서비스 계정 키 딕셔너리

    Raises
    ------
    RuntimeError : Secrets Manager 조회 실패 또는 JSON 파싱 실패
    """
    global _cached_credentials
    if _cached_credentials is not None:
        return _cached_credentials

    try:
        resp = _secretsmanager.get_secret_value(SecretId=FCM_SECRETS_NAME)
        secret_str = resp.get("SecretString") or resp.get("SecretBinary", b"").decode()
        _cached_credentials = json.loads(secret_str)
        logger.info({"message": "FCM 자격증명 로드 완료", "secret": FCM_SECRETS_NAME})
        return _cached_credentials
    except Exception as e:
        raise RuntimeError(f"FCM 자격증명 로드 실패 ({FCM_SECRETS_NAME}): {e}") from e
