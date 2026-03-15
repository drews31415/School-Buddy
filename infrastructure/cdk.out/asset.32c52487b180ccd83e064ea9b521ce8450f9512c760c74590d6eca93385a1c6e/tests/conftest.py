"""
pytest 픽스처 — moto AWS 모킹 설정.

모듈 레벨 환경변수는 이 파일 최상단에서 설정한다.
crawler 모듈들이 import 될 때 boto3 클라이언트와 상수가 초기화되므로,
import 이전에 환경변수가 있어야 한다.
"""
import os

# ── 환경변수를 import 전에 설정 (모듈 레벨 상수 초기화용) ──
os.environ.update(
    {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "REGION": "us-east-1",
        "SCHOOLS_TABLE": "test-schools",
        "NOTICES_TABLE": "test-notices",
        "SQS_QUEUE_URL": "",
        "SNS_ALARM_TOPIC_ARN": "",
    }
)

import boto3  # noqa: E402
import pytest  # noqa: E402
from moto import mock_aws  # noqa: E402
from unittest.mock import patch  # noqa: E402

SCHOOLS_TABLE = "test-schools"
NOTICES_TABLE = "test-notices"


@pytest.fixture
def aws_setup():
    """
    DynamoDB / SQS / SNS 리소스를 moto 메모리 백엔드로 생성.
    crawler.db / crawler.publisher 의 모듈 레벨 상수(SQS_QUEUE_URL 등)를
    실제 moto 리소스 URL/ARN으로 패치한다.
    """
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")

        # Schools 테이블 — PK: schoolId (no SK)
        ddb.create_table(
            TableName=SCHOOLS_TABLE,
            KeySchema=[{"AttributeName": "schoolId", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "schoolId", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Notices 테이블 — PK: schoolId  SK: createdAt
        ddb.create_table(
            TableName=NOTICES_TABLE,
            KeySchema=[
                {"AttributeName": "schoolId", "KeyType": "HASH"},
                {"AttributeName": "createdAt", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "schoolId", "AttributeType": "S"},
                {"AttributeName": "createdAt", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        sqs = boto3.client("sqs", region_name="us-east-1")
        queue_url = sqs.create_queue(QueueName="notice-queue")["QueueUrl"]

        sns = boto3.client("sns", region_name="us-east-1")
        topic_arn = sns.create_topic(Name="alarm-topic")["TopicArn"]

        # 모듈 레벨 상수 패치: moto 리소스 주소 적용
        with patch.multiple(
            "crawler.publisher",
            SQS_QUEUE_URL=queue_url,
            SNS_ALARM_TOPIC_ARN=topic_arn,
        ):
            yield {
                "ddb": ddb,
                "sqs": sqs,
                "sns": sns,
                "queue_url": queue_url,
                "topic_arn": topic_arn,
                "schools_table": ddb.Table(SCHOOLS_TABLE),
                "notices_table": ddb.Table(NOTICES_TABLE),
            }
