#!/usr/bin/env bash
# =============================================================================
# School Buddy — 배포 후 스모크 테스트
# 기본 인프라 존재 여부 + API Health Check 검증
#
# 사용법:
#   bash scripts/test-smoke.sh dev
#   bash scripts/test-smoke.sh prod
# =============================================================================
set -euo pipefail

# ── 색상 ──────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

PASS=0; FAIL=0

pass() { echo -e "  ${GREEN}[PASS]${RESET} $*"; (( PASS++ )); }
fail() { echo -e "  ${RED}[FAIL]${RESET} $*"; (( FAIL++ )); }
skip() { echo -e "  ${YELLOW}[SKIP]${RESET} $*"; }
section() { echo -e "\n${BOLD}▶ $*${RESET}"; }

# ── 인자 처리 ─────────────────────────────────────────────────────────────────
ENVIRONMENT="${1:-dev}"
if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
  echo "사용법: bash scripts/test-smoke.sh [dev|prod]"
  exit 1
fi

export AWS_DEFAULT_REGION="us-east-1"
export AWS_REGION="us-east-1"

OUTPUTS_FILE="infrastructure/cdk-outputs-${ENVIRONMENT}.json"

echo ""
echo -e "${BOLD}School Buddy [${ENVIRONMENT}] 스모크 테스트${RESET}"
echo -e "리전: us-east-1 | 시각: $(date '+%Y-%m-%d %H:%M:%S')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. DynamoDB 테이블 8개 존재 확인 ──────────────────────────────────────────
section "DynamoDB 테이블 확인 (8개 필수)"

DYNAMO_TABLES=(
  "school-buddy-users-${ENVIRONMENT}"
  "school-buddy-children-${ENVIRONMENT}"
  "school-buddy-schools-${ENVIRONMENT}"
  "school-buddy-notices-${ENVIRONMENT}"
  "school-buddy-notifications-${ENVIRONMENT}"
  "school-buddy-chat-history-${ENVIRONMENT}"
  "school-buddy-kb-documents-${ENVIRONMENT}"
  "school-buddy-translation-cache-${ENVIRONMENT}"
)

for TABLE in "${DYNAMO_TABLES[@]}"; do
  STATUS=$(aws dynamodb describe-table \
    --table-name "$TABLE" \
    --query "Table.TableStatus" \
    --output text 2>/dev/null || echo "NOT_FOUND")
  if [[ "$STATUS" == "ACTIVE" ]]; then
    pass "DynamoDB: $TABLE (ACTIVE)"
  else
    fail "DynamoDB: $TABLE — 상태: $STATUS"
  fi
done

# ── 2. S3 버킷 2개 존재 확인 (hanyang-pj-1- 접두사) ────────────────────────────
section "S3 버킷 확인 (hanyang-pj-1- 접두사, 2개 필수)"

S3_BUCKETS=(
  "hanyang-pj-1-documents-${ENVIRONMENT}"
  "hanyang-pj-1-kb-source-${ENVIRONMENT}"
)

for BUCKET in "${S3_BUCKETS[@]}"; do
  if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
    pass "S3: $BUCKET"
  else
    fail "S3: $BUCKET — 존재하지 않거나 접근 불가"
  fi
done

# ── 3. Lambda 함수 7개 존재 확인 ──────────────────────────────────────────────
section "Lambda 함수 확인 (7개 핵심 함수)"

LAMBDA_FUNCTIONS=(
  "school-buddy-crawler-${ENVIRONMENT}"
  "school-buddy-processor-${ENVIRONMENT}"
  "school-buddy-notifier-${ENVIRONMENT}"
  "school-buddy-analyzer-${ENVIRONMENT}"
  "school-buddy-rag-${ENVIRONMENT}"
  "school-buddy-user-${ENVIRONMENT}"
  "school-buddy-school-${ENVIRONMENT}"
)

for FN in "${LAMBDA_FUNCTIONS[@]}"; do
  STATE=$(aws lambda get-function \
    --function-name "$FN" \
    --query "Configuration.State" \
    --output text 2>/dev/null || echo "NOT_FOUND")
  if [[ "$STATE" == "Active" ]]; then
    pass "Lambda: $FN (Active)"
  else
    fail "Lambda: $FN — 상태: $STATE"
  fi
done

# kb-sync는 선택적 — 없어도 경고만
KB_SYNC_STATE=$(aws lambda get-function \
  --function-name "school-buddy-kb-sync-${ENVIRONMENT}" \
  --query "Configuration.State" \
  --output text 2>/dev/null || echo "NOT_FOUND")
if [[ "$KB_SYNC_STATE" == "Active" ]]; then
  pass "Lambda: school-buddy-kb-sync-${ENVIRONMENT} (Active)"
else
  skip "Lambda: school-buddy-kb-sync-${ENVIRONMENT} — 선택적 함수 (없어도 무방)"
fi

# ── 4. SQS 큐 존재 확인 ──────────────────────────────────────────────────────
section "SQS 큐 확인"

SQS_QUEUES=(
  "school-buddy-notice-queue-${ENVIRONMENT}"
  "school-buddy-notice-dlq-${ENVIRONMENT}"
  "school-buddy-notification-queue-${ENVIRONMENT}"
)

for QUEUE in "${SQS_QUEUES[@]}"; do
  QUEUE_URL=$(aws sqs get-queue-url \
    --queue-name "$QUEUE" \
    --query "QueueUrl" \
    --output text 2>/dev/null || echo "NOT_FOUND")
  if [[ "$QUEUE_URL" != "NOT_FOUND" && -n "$QUEUE_URL" ]]; then
    pass "SQS: $QUEUE"
  else
    fail "SQS: $QUEUE — 존재하지 않음"
  fi
done

# ── 5. Cognito User Pool 확인 ─────────────────────────────────────────────────
section "Cognito User Pool 확인"

USER_POOL_COUNT=$(aws cognito-idp list-user-pools \
  --max-results 20 \
  --query "length(UserPools[?Name=='school-buddy-user-pool-${ENVIRONMENT}'])" \
  --output text 2>/dev/null || echo "0")

if [[ "$USER_POOL_COUNT" -ge 1 ]]; then
  pass "Cognito: school-buddy-user-pool-${ENVIRONMENT}"
else
  fail "Cognito: school-buddy-user-pool-${ENVIRONMENT} — 존재하지 않음"
fi

# ── 6. API Gateway Health Check ───────────────────────────────────────────────
section "API Gateway Health Check"

# CDK outputs에서 API 엔드포인트 추출
API_ENDPOINT=""
if [[ -f "$OUTPUTS_FILE" ]]; then
  API_ENDPOINT=$(python3 -c "
import json, sys
try:
    data = json.load(open('${OUTPUTS_FILE}'))
    key  = 'school-buddy-app-${ENVIRONMENT}'
    print(data.get(key, {}).get('ApiEndpoint', ''))
except Exception as e:
    print('')
" 2>/dev/null)
fi

if [[ -z "$API_ENDPOINT" ]]; then
  # CDK outputs가 없으면 환경변수에서 시도
  API_ENDPOINT="${E2E_API_BASE_URL:-}"
fi

if [[ -z "$API_ENDPOINT" ]]; then
  skip "API_ENDPOINT를 찾을 수 없습니다. CDK outputs 파일($OUTPUTS_FILE)을 확인하거나 E2E_API_BASE_URL을 설정하세요."
else
  # /health 엔드포인트 (인증 불필요)
  HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    --max-time 10 \
    "${API_ENDPOINT}/health" 2>/dev/null || echo "000")

  if [[ "$HTTP_STATUS" == "200" ]]; then
    pass "API Health Check: ${API_ENDPOINT}/health → HTTP $HTTP_STATUS"
  elif [[ "$HTTP_STATUS" == "401" || "$HTTP_STATUS" == "403" ]]; then
    # 인증이 필요한 경우 — API 자체는 살아있음
    pass "API 응답 확인 (인증 필요): ${API_ENDPOINT}/health → HTTP $HTTP_STATUS"
  elif [[ "$HTTP_STATUS" == "404" ]]; then
    # /health 경로가 없는 경우 루트로 시도
    HTTP_STATUS_ROOT=$(curl -s -o /dev/null -w "%{http_code}" \
      --max-time 10 \
      "${API_ENDPOINT}/" 2>/dev/null || echo "000")
    if [[ "$HTTP_STATUS_ROOT" != "000" ]]; then
      pass "API 응답 확인 (루트): ${API_ENDPOINT}/ → HTTP $HTTP_STATUS_ROOT"
    else
      fail "API Health Check 실패: HTTP $HTTP_STATUS — URL: $API_ENDPOINT"
    fi
  else
    fail "API Health Check 실패: HTTP $HTTP_STATUS — URL: ${API_ENDPOINT}/health"
  fi
fi

# ── 7. CloudWatch 대시보드 존재 확인 ──────────────────────────────────────────
section "CloudWatch 대시보드 확인"

DASHBOARD_COUNT=$(aws cloudwatch list-dashboards \
  --query "length(DashboardEntries[?DashboardName=='school-buddy-${ENVIRONMENT}'])" \
  --output text 2>/dev/null || echo "0")

if [[ "$DASHBOARD_COUNT" -ge 1 ]]; then
  pass "CloudWatch Dashboard: school-buddy-${ENVIRONMENT}"
else
  fail "CloudWatch Dashboard: school-buddy-${ENVIRONMENT} — 존재하지 않음"
fi

# ── 결과 요약 ─────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL=$(( PASS + FAIL ))
echo -e "결과: ${GREEN}${PASS}개 통과${RESET} / ${RED}${FAIL}개 실패${RESET} / 전체 ${TOTAL}개"

if [[ $FAIL -eq 0 ]]; then
  echo -e "${GREEN}${BOLD}✓ 스모크 테스트 전체 통과${RESET}"
  echo ""
  echo "다음 단계: E2E 테스트 실행"
  echo "  export E2E_API_BASE_URL=$API_ENDPOINT"
  echo "  export E2E_ACCESS_TOKEN=<Cognito JWT>"
  echo "  make test-e2e"
  exit 0
else
  echo -e "${RED}${BOLD}✗ ${FAIL}개 항목이 실패했습니다.${RESET}"
  echo "  배포 로그를 확인하거나 make deploy-${ENVIRONMENT} 를 다시 실행하세요."
  exit 1
fi
