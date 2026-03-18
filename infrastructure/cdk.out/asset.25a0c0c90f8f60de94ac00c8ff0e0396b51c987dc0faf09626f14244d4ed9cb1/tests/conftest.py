"""pytest 픽스처 — moto AWS 모킹."""
import json
import os

os.environ.update(
    {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "REGION": "us-east-1",
        "CHILDREN_TABLE": "test-children",
        "USERS_TABLE": "test-users",
        "SCHOOLS_TABLE": "test-schools",
        "NOTIFICATIONS_TABLE": "test-notifications",
        "FCM_SECRETS_NAME": "test/fcm-key",
    }
)

import boto3
import pytest
from moto import mock_aws

CHILDREN_TABLE      = "test-children"
USERS_TABLE         = "test-users"
SCHOOLS_TABLE       = "test-schools"
NOTIFICATIONS_TABLE = "test-notifications"

# 테스트용 FCM 서비스 계정 (실제 키 형식 모방)
FAKE_FCM_CREDS = {
    "type": "service_account",
    "project_id": "test-project",
    "private_key_id": "key-id",
    "private_key": "fake-key",
    "client_email": "test@test-project.iam.gserviceaccount.com",
    "client_id": "123456",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
}


@pytest.fixture
def aws_setup():
    """DynamoDB 4개 테이블 + Secrets Manager를 moto로 생성."""
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")

        # Children: PK=childId, GSI=schoolId-index, GSI=userId-index
        ddb.create_table(
            TableName=CHILDREN_TABLE,
            KeySchema=[{"AttributeName": "childId", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "childId",  "AttributeType": "S"},
                {"AttributeName": "userId",   "AttributeType": "S"},
                {"AttributeName": "schoolId", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "schoolId-index",
                    "KeySchema": [{"AttributeName": "schoolId", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "userId-index",
                    "KeySchema": [{"AttributeName": "userId", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Users: PK=userId
        ddb.create_table(
            TableName=USERS_TABLE,
            KeySchema=[{"AttributeName": "userId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "userId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Schools: PK=schoolId
        ddb.create_table(
            TableName=SCHOOLS_TABLE,
            KeySchema=[{"AttributeName": "schoolId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "schoolId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Notifications: PK=userId SK=createdAt
        ddb.create_table(
            TableName=NOTIFICATIONS_TABLE,
            KeySchema=[
                {"AttributeName": "userId",    "KeyType": "HASH"},
                {"AttributeName": "createdAt", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "userId",    "AttributeType": "S"},
                {"AttributeName": "createdAt", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Secrets Manager에 FCM 자격증명 등록
        sm = boto3.client("secretsmanager", region_name="us-east-1")
        sm.create_secret(
            Name="test/fcm-key",
            SecretString=json.dumps(FAKE_FCM_CREDS),
        )

        yield {
            "ddb": ddb,
            "sm": sm,
            "children": ddb.Table(CHILDREN_TABLE),
            "users":    ddb.Table(USERS_TABLE),
            "schools":  ddb.Table(SCHOOLS_TABLE),
            "notifications": ddb.Table(NOTIFICATIONS_TABLE),
        }
