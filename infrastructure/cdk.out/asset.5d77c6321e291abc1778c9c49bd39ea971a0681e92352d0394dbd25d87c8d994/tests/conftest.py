"""pytest 픽스처 — AWS 서비스 moto 모킹."""
import json
import os

# 환경변수는 import 전에 설정 (모듈 레벨 상수 오염 방지)
os.environ.update(
    {
        "AWS_ACCESS_KEY_ID":     "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION":    "us-east-1",
        "REGION":                "us-east-1",
        "KB_ID":                 "test-kb-id",
        "CHAT_HISTORY_TABLE":    "school-buddy-chat-history-test",
        "NOTICES_TABLE":         "school-buddy-notices-test",
    }
)

import boto3
import pytest
from moto import mock_aws

CHAT_HISTORY_TABLE = "school-buddy-chat-history-test"
NOTICES_TABLE      = "school-buddy-notices-test"
TEST_USER_ID       = "user-abc-123"
TEST_SESSION_ID    = "sess-xyz-456"


def make_event(
    method: str,
    path: str,
    body: dict | None = None,
    query_params: dict | None = None,
    user_id: str = TEST_USER_ID,
) -> dict:
    return {
        "version":  "2.0",
        "routeKey": f"{method} {path}",
        "rawPath":  path,
        "headers":  {"content-type": "application/json"},
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {"sub": user_id},
                    "scopes": [],
                }
            },
            "http": {"method": method, "path": path},
        },
        "body":                json.dumps(body) if body else None,
        "queryStringParameters": query_params or {},
        "isBase64Encoded": False,
    }


@pytest.fixture
def dynamodb_setup():
    """ChatHistory 및 Notices DynamoDB 테이블을 moto로 생성."""
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")

        # ChatHistory — PK: userId  SK: sessionId#createdAt
        chat_table = ddb.create_table(
            TableName=CHAT_HISTORY_TABLE,
            KeySchema=[
                {"AttributeName": "userId",              "KeyType": "HASH"},
                {"AttributeName": "sessionId#createdAt", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "userId",              "AttributeType": "S"},
                {"AttributeName": "sessionId#createdAt", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        chat_table.meta.client.get_waiter("table_exists").wait(TableName=CHAT_HISTORY_TABLE)

        # Notices — PK: schoolId  SK: createdAt  GSI: noticeId-index
        notices_table = ddb.create_table(
            TableName=NOTICES_TABLE,
            KeySchema=[
                {"AttributeName": "schoolId",  "KeyType": "HASH"},
                {"AttributeName": "createdAt", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "schoolId",  "AttributeType": "S"},
                {"AttributeName": "createdAt", "AttributeType": "S"},
                {"AttributeName": "noticeId",  "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "noticeId-index",
                    "KeySchema": [{"AttributeName": "noticeId", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        notices_table.meta.client.get_waiter("table_exists").wait(TableName=NOTICES_TABLE)

        yield ddb
