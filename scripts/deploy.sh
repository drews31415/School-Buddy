#!/usr/bin/env bash
# =============================================================================
# School Buddy — CDK 배포 스크립트
# 실행 위치: Cloud9 (SafeRole-hanyang-pj-1 자동 적용)
#
# 사용법:
#   bash scripts/deploy.sh dev
#   bash scripts/deploy.sh prod
#
# 전제조건:
#   - AWS CLI v2, Node.js 20+, pnpm 설치
#   - Cloud9 인스턴스 프로파일에 SafeRole-hanyang-pj-1 연결
#   - CDK bootstrap 완료: npx cdk bootstrap --region us-east-1
# =============================================================================
set -euo pipefail

# ── 색상 ──────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log_info()  { echo -e "${CYAN}[INFO]${RESET}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error() { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
log_step()  { echo -e "\n${BOLD}━━━ $* ━━━${RESET}"; }

# ── 인자 검증 ─────────────────────────────────────────────────────────────────
ENVIRONMENT="${1:-}"
if [[ -z "$ENVIRONMENT" ]]; then
  log_error "환경(dev|prod)을 인자로 전달하세요."
  echo "  사용법: bash scripts/deploy.sh dev"
  echo "          bash scripts/deploy.sh prod"
  exit 1
fi

if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
  log_error "지원하지 않는 환경: '$ENVIRONMENT' (dev 또는 prod만 허용)"
  exit 1
fi

# ── 리전 고정 ─────────────────────────────────────────────────────────────────
export AWS_DEFAULT_REGION="us-east-1"
export AWS_REGION="us-east-1"
OUTPUTS_FILE="infrastructure/cdk-outputs-${ENVIRONMENT}.json"

# ── prod 확인 프롬프트 ────────────────────────────────────────────────────────
if [[ "$ENVIRONMENT" == "prod" ]]; then
  echo -e "${RED}${BOLD}"
  echo "  ╔══════════════════════════════════════════════╗"
  echo "  ║   ⚠️  운영(prod) 환경 배포                     ║"
  echo "  ║   이 작업은 실제 서비스에 영향을 미칩니다.        ║"
  echo "  ╚══════════════════════════════════════════════╝"
  echo -e "${RESET}"
  read -rp "정말 운영 배포를 진행하시겠습니까? (yes/no): " CONFIRM
  if [[ "$CONFIRM" != "yes" ]]; then
    log_warn "배포가 취소되었습니다."
    exit 0
  fi
fi

# ── 사전 점검 ─────────────────────────────────────────────────────────────────
log_step "사전 점검"

# AWS 자격증명 확인 (Cloud9 인스턴스 프로파일)
if ! aws sts get-caller-identity --query "Arn" --output text &>/dev/null; then
  log_error "AWS 자격증명이 없습니다. Cloud9 인스턴스 프로파일을 확인하세요."
  exit 1
fi

CALLER_ARN=$(aws sts get-caller-identity --query "Arn" --output text)
log_ok "AWS 자격증명: $CALLER_ARN"

# SafeRole 포함 여부 확인
if [[ "$CALLER_ARN" != *"SafeRole-hanyang-pj-1"* ]]; then
  log_warn "현재 역할이 SafeRole-hanyang-pj-1이 아닙니다: $CALLER_ARN"
  log_warn "Cloud9 인스턴스 프로파일에 SafeRole-hanyang-pj-1이 연결되어 있어야 합니다."
fi

# Node.js 버전 확인
NODE_VER=$(node --version 2>/dev/null || echo "없음")
log_info "Node.js: $NODE_VER"

# pnpm 확인
if ! command -v pnpm &>/dev/null; then
  log_error "pnpm이 설치되지 않았습니다. npm install -g pnpm 을 실행하세요."
  exit 1
fi
log_ok "pnpm: $(pnpm --version)"

# ── 의존성 설치 ───────────────────────────────────────────────────────────────
log_step "의존성 설치"
pnpm install --frozen-lockfile
log_ok "의존성 설치 완료"

# ── 빌드 ─────────────────────────────────────────────────────────────────────
log_step "공유 패키지 빌드"
(cd packages/shared-types && npx tsc --noEmit 2>&1 | tail -5)
log_ok "shared-types 타입 체크 완료"

# ── CDK synth 사전 검증 ───────────────────────────────────────────────────────
log_step "CDK synth 사전 검증"
(cd infrastructure && npx cdk synth \
  -c environment="$ENVIRONMENT" \
  --quiet 2>&1)
log_ok "CDK synth 성공 — CloudFormation 템플릿 유효"

# ── 배포 시작 ─────────────────────────────────────────────────────────────────
DEPLOY_START=$(date +%s)
log_step "${ENVIRONMENT} 환경 배포 시작 ($(date '+%Y-%m-%d %H:%M:%S'))"

STACK_NAMES=(
  "school-buddy-storage-${ENVIRONMENT}"
  "school-buddy-app-${ENVIRONMENT}"
  "school-buddy-monitoring-${ENVIRONMENT}"
)

# prod는 broadening 권한 변경 승인 요구
APPROVAL_FLAG="--require-approval never"
if [[ "$ENVIRONMENT" == "prod" ]]; then
  APPROVAL_FLAG="--require-approval broadening"
fi

# 스택 순서대로 개별 배포 (StorageStack → ApplicationStack → MonitoringStack)
for STACK in "${STACK_NAMES[@]}"; do
  log_info "배포 중: $STACK ..."
  (cd infrastructure && npx cdk deploy "$STACK" \
    -c environment="$ENVIRONMENT" \
    $APPROVAL_FLAG \
    --outputs-file "../${OUTPUTS_FILE}" \
    --progress events \
    2>&1) || {
      log_error "$STACK 배포 실패"
      exit 1
    }
  log_ok "$STACK 배포 완료"
done

DEPLOY_END=$(date +%s)
DEPLOY_SEC=$(( DEPLOY_END - DEPLOY_START ))

# ── 배포 완료 출력 ────────────────────────────────────────────────────────────
log_step "배포 완료 (소요: ${DEPLOY_SEC}초)"

# CDK outputs JSON에서 주요 엔드포인트 추출
if [[ -f "$OUTPUTS_FILE" ]]; then
  APP_STACK_KEY="school-buddy-app-${ENVIRONMENT}"

  API_ENDPOINT=$(python3 -c "
import json, sys
data = json.load(open('${OUTPUTS_FILE}'))
stack = data.get('${APP_STACK_KEY}', {})
print(stack.get('ApiEndpoint', 'N/A'))
" 2>/dev/null || echo "N/A")

  USER_POOL_ID=$(python3 -c "
import json
data = json.load(open('${OUTPUTS_FILE}'))
stack = data.get('${APP_STACK_KEY}', {})
print(stack.get('UserPoolId', 'N/A'))
" 2>/dev/null || echo "N/A")

  USER_POOL_CLIENT_ID=$(python3 -c "
import json
data = json.load(open('${OUTPUTS_FILE}'))
stack = data.get('${APP_STACK_KEY}', {})
print(stack.get('UserPoolClientId', 'N/A'))
" 2>/dev/null || echo "N/A")

  COGNITO_DOMAIN=$(python3 -c "
import json
data = json.load(open('${OUTPUTS_FILE}'))
stack = data.get('${APP_STACK_KEY}', {})
print(stack.get('CognitoDomain', 'N/A'))
" 2>/dev/null || echo "N/A")

  KB_ID=$(python3 -c "
import json
data = json.load(open('${OUTPUTS_FILE}'))
stack = data.get('${APP_STACK_KEY}', {})
print(stack.get('KnowledgeBaseId', 'N/A'))
" 2>/dev/null || echo "N/A")

  echo ""
  echo -e "${GREEN}${BOLD}┌─────────────────────────────────────────────────────┐${RESET}"
  echo -e "${GREEN}${BOLD}│  School Buddy [${ENVIRONMENT}] 배포 완료                       │${RESET}"
  echo -e "${GREEN}${BOLD}└─────────────────────────────────────────────────────┘${RESET}"
  echo ""
  echo -e "  ${BOLD}API Endpoint${RESET}"
  echo -e "    ${CYAN}$API_ENDPOINT${RESET}"
  echo ""
  echo -e "  ${BOLD}Cognito${RESET}"
  echo -e "    User Pool ID:       $USER_POOL_ID"
  echo -e "    User Pool Client:   $USER_POOL_CLIENT_ID"
  echo -e "    Hosted UI:          $COGNITO_DOMAIN"
  echo ""
  echo -e "  ${BOLD}Bedrock Knowledge Base${RESET}"
  echo -e "    Knowledge Base ID:  $KB_ID"
  echo ""
  echo -e "  ${BOLD}CloudWatch Dashboard${RESET}"
  echo -e "    ${CYAN}https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=school-buddy-${ENVIRONMENT}${RESET}"
  echo ""
  echo -e "  ${BOLD}CDK Outputs 파일${RESET}: $OUTPUTS_FILE"
  echo ""

  # 앱 .env 파일 자동 업데이트 안내
  echo -e "  ${YELLOW}다음 단계:${RESET}"
  echo -e "    1. apps/mobile/.env 에 API_BASE_URL=$API_ENDPOINT 설정"
  echo -e "    2. apps/mobile/.env 에 COGNITO_USER_POOL_ID=$USER_POOL_ID 설정"
  echo -e "    3. bash scripts/test-smoke.sh $ENVIRONMENT 으로 기본 동작 확인"
  echo ""
else
  log_warn "CDK outputs 파일을 찾을 수 없습니다: $OUTPUTS_FILE"
  log_info "AWS 콘솔에서 스택 출력을 직접 확인하세요."
fi
