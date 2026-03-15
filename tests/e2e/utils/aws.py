"""
AWS 헬퍼 유틸.
모든 클라이언트는 us-east-1 리전으로 초기화.
"""
import json
import time
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

from tests.e2e.config import AWS_REGION


# ── 클라이언트 팩토리 ─────────────────────────────────────────────────────────
def _dynamodb():
    return boto3.resource("dynamodb", region_name=AWS_REGION)

def _lambda_client():
    return boto3.client("lambda", region_name=AWS_REGION)

def _sqs_client():
    return boto3.client("sqs", region_name=AWS_REGION)


# ── DynamoDB 헬퍼 ─────────────────────────────────────────────────────────────
def dynamo_put(table_name: str, item: dict) -> None:
    _dynamodb().Table(table_name).put_item(Item=item)


def dynamo_get(table_name: str, key: dict) -> Optional[dict]:
    resp = _dynamodb().Table(table_name).get_item(Key=key)
    return resp.get("Item")


def dynamo_delete(table_name: str, key: dict) -> None:
    try:
        _dynamodb().Table(table_name).delete_item(Key=key)
    except ClientError:
        pass  # 이미 없으면 무시


def dynamo_query(
    table_name: str,
    key_condition,
    index_name: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    from boto3.dynamodb.conditions import Key as DKey  # noqa: F401
    kwargs: dict[str, Any] = {
        "KeyConditionExpression": key_condition,
        "Limit": limit,
    }
    if index_name:
        kwargs["IndexName"] = index_name
    resp = _dynamodb().Table(table_name).query(**kwargs)
    return resp.get("Items", [])


# ── Lambda 헬퍼 ───────────────────────────────────────────────────────────────
def invoke_lambda(function_name: str, payload: dict) -> dict:
    """Lambda를 동기 호출하고 응답 페이로드를 반환."""
    resp = _lambda_client().invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode(),
    )
    body = resp["Payload"].read()
    return json.loads(body) if body else {}


# ── SQS 헬퍼 ──────────────────────────────────────────────────────────────────
def get_queue_url(queue_name: str) -> str:
    resp = _sqs_client().get_queue_url(QueueName=queue_name)
    return resp["QueueUrl"]


def wait_for_sqs_message(
    queue_url: str,
    match_fn,
    timeout_sec: int = 60,
    poll_interval_sec: int = 3,
) -> Optional[dict]:
    """
    큐에서 match_fn(message_body_dict) == True 인 메시지가 나타날 때까지 폴링.
    반환: 매칭된 메시지 body dict, 타임아웃 시 None.
    ⚠️ VisibilityTimeout=0 으로 메시지를 peek만 하고 삭제하지 않음.
    """
    deadline = time.monotonic() + timeout_sec
    sqs = _sqs_client()
    while time.monotonic() < deadline:
        resp = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=min(poll_interval_sec, 20),
            VisibilityTimeout=0,
        )
        for msg in resp.get("Messages", []):
            try:
                body = json.loads(msg["Body"])
            except (json.JSONDecodeError, KeyError):
                continue
            if match_fn(body):
                return body
        time.sleep(poll_interval_sec)
    return None


def get_queue_depth(queue_url: str) -> int:
    sqs = _sqs_client()
    resp = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["ApproximateNumberOfMessages"],
    )
    return int(resp["Attributes"].get("ApproximateNumberOfMessages", 0))


# ── 폴링 유틸 ────────────────────────────────────────────────────────────────
def wait_until(
    condition_fn,
    timeout_sec: int,
    poll_interval_sec: int = 3,
    description: str = "condition",
) -> bool:
    """
    condition_fn() 이 True 를 반환할 때까지 폴링.
    타임아웃 전 성공하면 True, 그렇지 않으면 False.
    """
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if condition_fn():
            return True
        time.sleep(poll_interval_sec)
    return False
