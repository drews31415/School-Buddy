"""
S3 업로드 / 태그 설정
"""
import os
from datetime import datetime, timedelta, timezone

import boto3

DOCUMENTS_BUCKET = os.environ.get("DOCUMENTS_BUCKET", "hanyang-pj-1-documents-dev")
_REGION          = os.environ.get("REGION", "us-east-1")

_s3 = boto3.client("s3", region_name=_REGION)


def build_s3_key(user_id: str, filename: str) -> str:
    """
    업로드 키 형식: uploads/{userId}/{timestamp}/{filename}
    타임스탬프는 ISO 8601 기본 형식 (충돌 방지).
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"uploads/{user_id}/{ts}/{filename}"


def upload_to_s3(file_bytes: bytes, key: str, content_type: str) -> str:
    """S3에 업로드하고 s3:// URI를 반환한다."""
    _s3.put_object(
        Bucket=DOCUMENTS_BUCKET,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
        # 서버 사이드 암호화 (버킷 기본 설정 S3_MANAGED와 일치)
        ServerSideEncryption="AES256",
    )
    return f"s3://{DOCUMENTS_BUCKET}/{key}"


def set_expiry_tag(key: str, days: int = 7) -> None:
    """
    업로드된 파일에 만료 추적 태그를 설정한다.
    버킷 lifecycle rule(uploads/ prefix, 7일 자동 삭제)과 함께 사용.
    """
    expiry_date = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")
    _s3.put_object_tagging(
        Bucket=DOCUMENTS_BUCKET,
        Key=key,
        Tagging={
            "TagSet": [
                {"Key": "ExpiresAfterDays", "Value": str(days)},
                {"Key": "ExpiryDate",       "Value": expiry_date},
                {"Key": "Project",          "Value": "school-buddy"},
            ]
        },
    )
