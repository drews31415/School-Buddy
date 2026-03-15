"""
kb-sync Lambda
S3 ObjectCreated 이벤트 → Bedrock Knowledge Base StartIngestionJob

새 교육 문서가 hanyang-pj-1-kb-source 버킷에 업로드되면
자동으로 Knowledge Base 동기화(Ingestion)를 시작한다.
"""
import json
import os
import uuid

import boto3

# ── 모듈 레벨 상수 (cold start 최적화) ───────────────────────────────────
KNOWLEDGE_BASE_ID = os.environ["KNOWLEDGE_BASE_ID"]
DATA_SOURCE_ID    = os.environ["DATA_SOURCE_ID"]
_REGION           = os.environ.get("REGION", "us-east-1")

_bedrock_agent = boto3.client("bedrock-agent", region_name=_REGION)


def handler(event: dict, context) -> dict:
    """
    S3 이벤트 기반 Bedrock Knowledge Base 동기화.
    - 여러 S3 이벤트가 배치로 들어와도 ingestion job은 1회만 시작한다.
    - 이미 실행 중인 job이 있어도 새 job을 시작한다 (Bedrock이 큐잉 처리).
    """
    records = event.get("Records", [])
    if not records:
        print("[kb-sync] 처리할 S3 이벤트 없음")
        return {"statusCode": 200, "body": "no records"}

    # 이벤트에서 변경된 키 목록 로그 (개인정보 없음)
    keys = [r.get("s3", {}).get("object", {}).get("key", "?") for r in records]
    print(f"[kb-sync] S3 이벤트 {len(records)}건 수신: {keys[:5]}")  # 최대 5개만 로그

    # StartIngestionJob — 중복 실행 방지용 clientToken
    client_token = str(uuid.uuid4())
    try:
        response = _bedrock_agent.start_ingestion_job(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            dataSourceId=DATA_SOURCE_ID,
            clientToken=client_token,
            description=f"S3 업로드 트리거 자동 동기화 ({len(records)}건)",
        )
        job_id = response.get("ingestionJob", {}).get("ingestionJobId", "?")
        print(f"[kb-sync] Ingestion job 시작: {job_id}")
        return {
            "statusCode": 200,
            "body": json.dumps({"ingestionJobId": job_id}),
        }
    except Exception as e:
        # ingestion job 실패는 치명적 오류 → 재시도를 위해 예외를 다시 던진다
        print(f"[kb-sync] StartIngestionJob 실패: {e}")
        raise
