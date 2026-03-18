"""
pytest 픽스처 — moto AWS 모킹.
모듈 임포트 전 환경변수를 설정한다.
"""
import os

os.environ.update(
    {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "REGION": "us-east-1",
        "NOTICES_TABLE": "test-notices",
        "TRANSLATION_CACHE_TABLE": "test-cache",
        "NOTICE_TOPIC_ARN": "",
        "BEDROCK_MODEL_ID": "claude-sonnet-4-20250514",
    }
)

import boto3
import pytest
from moto import mock_aws
from unittest.mock import patch

NOTICES_TABLE = "test-notices"
CACHE_TABLE = "test-cache"


@pytest.fixture
def aws_setup():
    """DynamoDB / SNS 리소스를 moto 메모리 백엔드로 생성."""
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")

        # Notices: PK=schoolId, SK=createdAt, GSI=noticeId-index
        ddb.create_table(
            TableName=NOTICES_TABLE,
            KeySchema=[
                {"AttributeName": "schoolId", "KeyType": "HASH"},
                {"AttributeName": "createdAt", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "schoolId", "AttributeType": "S"},
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

        # TranslationCache: PK=cacheKey
        ddb.create_table(
            TableName=CACHE_TABLE,
            KeySchema=[{"AttributeName": "cacheKey", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "cacheKey", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        sns = boto3.client("sns", region_name="us-east-1")
        topic_arn = sns.create_topic(Name="notice-topic")["TopicArn"]

        with patch.multiple("processor.publisher", NOTICE_TOPIC_ARN=topic_arn):
            yield {
                "ddb": ddb,
                "sns": sns,
                "topic_arn": topic_arn,
                "notices_table": ddb.Table(NOTICES_TABLE),
                "cache_table": ddb.Table(CACHE_TABLE),
            }
