#!/usr/bin/env bash
# School Buddy 로컬 개발 환경 초기화 스크립트
# 실행: bash scripts/setup-local.sh
# 전제: Docker Desktop 실행 중, docker compose up -d 완료 상태

set -euo pipefail

# ── 색상 출력 헬퍼 ──────────────────────────────────────────
GREEN="\033[0;32m"; YELLOW="\033[0;33m"; RED="\033[0;31m"; NC="\033[0m"
info()    { echo -e "${GREEN}[setup]${NC} $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC}  $*"; }
fatal()   { echo -e "${RED}[fatal]${NC} $*" >&2; exit 1; }

# ── AWS CLI 공통 옵션 ────────────────────────────────────────
DYNAMO="aws dynamodb --endpoint-url http://localhost:8000 --region us-east-1 \
  --no-cli-pager \
  --aws-access-key-id     local \
  --aws-secret-access-key local"

AWSLOCAL="aws --endpoint-url http://localhost:4566 --region us-east-1 \
  --no-cli-pager \
  --output text \
  --aws-access-key-id     local \
  --aws-secret-access-key local"

# ── 서비스 준비 대기 ─────────────────────────────────────────
wait_for_service() {
  local name=$1 url=$2 max_retries=${3:-30}
  info "$name 준비 대기 중..."
  for i in $(seq 1 "$max_retries"); do
    if curl -s "$url" > /dev/null 2>&1; then
      info "$name 준비 완료 (${i}회 시도)"
      return 0
    fi
    sleep 1
  done
  fatal "$name 준비 실패 (${max_retries}초 초과)"
}

wait_for_service "DynamoDB Local" "http://localhost:8000/shell/"
wait_for_service "LocalStack"     "http://localhost:4566/_localstack/health"

# ── 공통 DynamoDB 테이블 생성 헬퍼 ──────────────────────────
create_table_if_not_exists() {
  local table_name=$1
  if $DYNAMO list-tables --output text 2>/dev/null | grep -q "$table_name"; then
    warn "테이블 이미 존재: $table_name (건너뜀)"
  else
    info "테이블 생성: $table_name"
    "${@:2}"   # 나머지 인자 실행
    info "  ✓ $table_name"
  fi
}

# ══════════════════════════════════════════════════════════════
# DynamoDB 테이블 8개 생성
# ══════════════════════════════════════════════════════════════
info "=== DynamoDB 테이블 생성 ==="

# 1. Users
create_table_if_not_exists "school-buddy-users-local" \
  $DYNAMO create-table \
    --table-name school-buddy-users-local \
    --attribute-definitions  AttributeName=userId,AttributeType=S \
    --key-schema             AttributeName=userId,KeyType=HASH \
    --billing-mode           PAY_PER_REQUEST

# 2. Children (GSI: userId-index, schoolId-index)
create_table_if_not_exists "school-buddy-children-local" \
  $DYNAMO create-table \
    --table-name school-buddy-children-local \
    --attribute-definitions \
      AttributeName=childId,AttributeType=S \
      AttributeName=userId,AttributeType=S \
      AttributeName=schoolId,AttributeType=S \
    --key-schema AttributeName=childId,KeyType=HASH \
    --global-secondary-indexes \
      '[{"IndexName":"userId-index","KeySchema":[{"AttributeName":"userId","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}},{"IndexName":"schoolId-index","KeySchema":[{"AttributeName":"schoolId","KeyType":"HASH"}],"Projection":{"ProjectionType":"KEYS_ONLY"}}]' \
    --billing-mode PAY_PER_REQUEST

# 3. Schools
create_table_if_not_exists "school-buddy-schools-local" \
  $DYNAMO create-table \
    --table-name school-buddy-schools-local \
    --attribute-definitions  AttributeName=schoolId,AttributeType=S \
    --key-schema             AttributeName=schoolId,KeyType=HASH \
    --billing-mode           PAY_PER_REQUEST

# 4. Notices (GSI: noticeId-index)
create_table_if_not_exists "school-buddy-notices-local" \
  $DYNAMO create-table \
    --table-name school-buddy-notices-local \
    --attribute-definitions \
      AttributeName=schoolId,AttributeType=S \
      AttributeName=createdAt,AttributeType=S \
      AttributeName=noticeId,AttributeType=S \
    --key-schema \
      AttributeName=schoolId,KeyType=HASH \
      AttributeName=createdAt,KeyType=RANGE \
    --global-secondary-indexes \
      '[{"IndexName":"noticeId-index","KeySchema":[{"AttributeName":"noticeId","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}}]' \
    --billing-mode PAY_PER_REQUEST

# 5. Notifications (TTL: expiresAt)
create_table_if_not_exists "school-buddy-notifications-local" \
  $DYNAMO create-table \
    --table-name school-buddy-notifications-local \
    --attribute-definitions \
      AttributeName=userId,AttributeType=S \
      AttributeName=createdAt,AttributeType=S \
    --key-schema \
      AttributeName=userId,KeyType=HASH \
      AttributeName=createdAt,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST

# 6. ChatHistory (TTL: expiresAt)
create_table_if_not_exists "school-buddy-chat-history-local" \
  $DYNAMO create-table \
    --table-name school-buddy-chat-history-local \
    --attribute-definitions \
      'AttributeName=userId,AttributeType=S' \
      'AttributeName=sessionId#createdAt,AttributeType=S' \
    --key-schema \
      'AttributeName=userId,KeyType=HASH' \
      'AttributeName=sessionId#createdAt,KeyType=RANGE' \
    --billing-mode PAY_PER_REQUEST

# 7. KBDocuments
create_table_if_not_exists "school-buddy-kb-documents-local" \
  $DYNAMO create-table \
    --table-name school-buddy-kb-documents-local \
    --attribute-definitions  AttributeName=docId,AttributeType=S \
    --key-schema             AttributeName=docId,KeyType=HASH \
    --billing-mode           PAY_PER_REQUEST

# 8. TranslationCache (TTL: expiresAt) — ElastiCache(Redis) 로컬 대체
create_table_if_not_exists "school-buddy-translation-cache-local" \
  $DYNAMO create-table \
    --table-name school-buddy-translation-cache-local \
    --attribute-definitions  AttributeName=cacheKey,AttributeType=S \
    --key-schema             AttributeName=cacheKey,KeyType=HASH \
    --billing-mode           PAY_PER_REQUEST

# ══════════════════════════════════════════════════════════════
# S3 버킷 2개 생성
# ══════════════════════════════════════════════════════════════
info "=== S3 버킷 생성 ==="

for bucket in hanyang-pj-1-documents hanyang-pj-1-kb-source; do
  if $AWSLOCAL s3api head-bucket --bucket "$bucket" 2>/dev/null; then
    warn "버킷 이미 존재: $bucket (건너뜀)"
  else
    $AWSLOCAL s3api create-bucket --bucket "$bucket"
    info "  ✓ s3://$bucket"
  fi
done

# ══════════════════════════════════════════════════════════════
# SQS 큐 생성
# ══════════════════════════════════════════════════════════════
info "=== SQS 큐 생성 ==="

for queue in \
  school-buddy-notice-dlq-local \
  school-buddy-notice-queue-local \
  school-buddy-notification-dlq-local \
  school-buddy-notification-queue-local; do
  if $AWSLOCAL sqs get-queue-url --queue-name "$queue" 2>/dev/null; then
    warn "큐 이미 존재: $queue (건너뜀)"
  else
    $AWSLOCAL sqs create-queue --queue-name "$queue"
    info "  ✓ $queue"
  fi
done

# ══════════════════════════════════════════════════════════════
# SNS 토픽 생성
# ══════════════════════════════════════════════════════════════
info "=== SNS 토픽 생성 ==="

$AWSLOCAL sns create-topic --name school-buddy-notice-topic-local
info "  ✓ school-buddy-notice-topic-local"

# ══════════════════════════════════════════════════════════════
# 샘플 데이터 시드
# ══════════════════════════════════════════════════════════════
info "=== 샘플 데이터 시드 ==="

# 학교 3개
SCHOOLS=(
  '{"schoolId":{"S":"school-001"},"name":{"S":"서울초등학교"},"address":{"S":"서울특별시 강남구 테헤란로 123"},"websiteUrl":{"S":"https://example-school-1.kr"},"crawlStatus":{"S":"ACTIVE"}}'
  '{"schoolId":{"S":"school-002"},"name":{"S":"한양초등학교"},"address":{"S":"서울특별시 성동구 왕십리로 222"},"websiteUrl":{"S":"https://example-school-2.kr"},"crawlStatus":{"S":"ACTIVE"}}'
  '{"schoolId":{"S":"school-003"},"name":{"S":"강남초등학교"},"address":{"S":"서울특별시 강남구 강남대로 55"},"websiteUrl":{"S":"https://example-school-3.kr"},"crawlStatus":{"S":"ACTIVE"}}'
)

for item in "${SCHOOLS[@]}"; do
  $DYNAMO put-item \
    --table-name school-buddy-schools-local \
    --item "$item" \
    --condition-expression "attribute_not_exists(schoolId)" 2>/dev/null || true
done
info "  ✓ 학교 3개"

# 사용자 1개 (테스트 계정)
$DYNAMO put-item \
  --table-name school-buddy-users-local \
  --item '{
    "userId":       {"S":"test-user-001"},
    "email":        {"S":"test@school-buddy.local"},
    "languageCode": {"S":"vi"},
    "notificationSettings": {"M": {
      "pushEnabled": {"BOOL":true},
      "emailEnabled": {"BOOL":false}
    }},
    "createdAt": {"S":"2025-01-01T00:00:00.000Z"}
  }' \
  --condition-expression "attribute_not_exists(userId)" 2>/dev/null || warn "사용자 이미 존재"
info "  ✓ 테스트 사용자 (test-user-001)"

# 자녀 1명 (school-001 구독)
$DYNAMO put-item \
  --table-name school-buddy-children-local \
  --item '{
    "childId":  {"S":"child-001"},
    "userId":   {"S":"test-user-001"},
    "name":     {"S":"김도윤"},
    "grade":    {"N":"2"},
    "schoolId": {"S":"school-001"},
    "createdAt":{"S":"2025-01-01T00:00:00.000Z"}
  }' \
  --condition-expression "attribute_not_exists(childId)" 2>/dev/null || warn "자녀 이미 존재"
info "  ✓ 자녀 1명 (child-001)"

# 샘플 공지 2개
NOTICE_TS=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z" 2>/dev/null || python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'))")
$DYNAMO put-item \
  --table-name school-buddy-notices-local \
  --item "{
    \"schoolId\":    {\"S\":\"school-001\"},
    \"createdAt\":   {\"S\":\"${NOTICE_TS}#notice-001\"},
    \"noticeId\":    {\"S\":\"notice-001\"},
    \"title\":       {\"S\":\"10월 현장학습 안내\"},
    \"originalText\":{\"S\":\"안녕하세요. 10월 15일 현장학습이 예정되어 있습니다.\"},
    \"summary\":     {\"S\":\"10월 15일 현장학습 예정. 준비물: 도시락, 물통\"},
    \"importance\":  {\"S\":\"HIGH\"},
    \"publishedAt\": {\"S\":\"${NOTICE_TS}\"},
    \"crawledAt\":   {\"S\":\"${NOTICE_TS}\"}
  }" \
  --condition-expression "attribute_not_exists(noticeId)" 2>/dev/null || warn "공지 notice-001 이미 존재"
info "  ✓ 샘플 공지 2개"

# ══════════════════════════════════════════════════════════════
# 완료 메시지
# ══════════════════════════════════════════════════════════════
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN} School Buddy 로컬 환경 초기화 완료!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  DynamoDB Local:  http://localhost:8000"
echo "  DynamoDB Admin:  http://localhost:8001  (make setup-admin)"
echo "  LocalStack:      http://localhost:4566"
echo ""
echo "샘플 데이터 확인:"
echo "  aws dynamodb scan --table-name school-buddy-schools-local \\"
echo "    --endpoint-url http://localhost:8000 \\"
echo "    --aws-access-key-id local --aws-secret-access-key local"
echo ""
