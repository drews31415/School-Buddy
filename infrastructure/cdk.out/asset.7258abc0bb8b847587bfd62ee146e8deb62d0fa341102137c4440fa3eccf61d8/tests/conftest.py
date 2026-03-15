"""pytest 픽스처 — AWS 서비스 moto 모킹."""
import base64
import json
import os

# 환경변수는 import 전에 설정 (모듈 레벨 상수 오염 방지)
os.environ.update(
    {
        "AWS_ACCESS_KEY_ID":     "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION":    "us-east-1",
        "REGION":                "us-east-1",
        "DOCUMENTS_BUCKET":      "hanyang-pj-1-documents-test",
        "BEDROCK_MODEL_ID":      "anthropic.claude-sonnet-4-20250514-v1:0",
    }
)

import boto3
import pytest
from moto import mock_aws

BUCKET_NAME = "hanyang-pj-1-documents-test"

# 테스트용 최소 1×1 흰색 JPEG (base64)
TINY_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8U"
    "HRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgN"
    "DRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
    "MjL/wAARCAABAAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAA"
    "AAAAAAAAAAAAAP/EABQBAQAAAAAAAAAAAAAAAAAAAAD/xAAUEQEAAAAAAAAAAAAAAAAAAAAA"
    "/9oADAMBAAIRAxEAPwCwABmX/9k="
)

# 최소 PDF 바이트 (Textract 테스트용)
MINIMAL_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 1\n0000000000 65535 f\ntrailer\n<< /Size 1 /Root 1 0 R >>\nstartxref\n9\n%%EOF"
MINIMAL_PDF_B64   = base64.b64encode(MINIMAL_PDF_BYTES).decode()

# 정상 API Gateway JWT 이벤트 템플릿
def make_event(
    body: dict,
    user_id: str = "user-123",
    method: str = "POST",
    path: str = "/documents/analyze",
) -> dict:
    return {
        "version":    "2.0",
        "routeKey":   f"{method} {path}",
        "rawPath":    path,
        "headers":    {"content-type": "application/json"},
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {"sub": user_id},
                    "scopes": [],
                }
            },
            "http": {"method": method, "path": path},
        },
        "body":           json.dumps(body),
        "isBase64Encoded": False,
    }


@pytest.fixture
def s3_setup():
    """S3 버킷을 moto로 생성한다."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET_NAME)
        yield s3
