# School Buddy — 개발 자동화 Makefile
# 사용법: make <target>
# 전제: Docker Desktop, AWS CLI, pnpm, Python 3.11+ 설치

PYTHON := /c/Users/dldls/AppData/Local/Programs/Python/Python311/python.exe
PYTEST  := $(PYTHON) -m pytest

.PHONY: help setup setup-admin teardown \
        test test-python test-node test-infra test-e2e \
        build build-node \
        deploy-dev deploy-prod \
        lint clean

# ── 기본 도움말 ──────────────────────────────────────────────
help:
	@echo ""
	@echo "School Buddy — 사용 가능한 명령어"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  make setup        로컬 환경 초기화 (Docker + DynamoDB + S3 + 시드 데이터)"
	@echo "  make teardown     로컬 컨테이너 중지 및 제거"
	@echo "  make setup-admin  DynamoDB Admin UI 포함 실행 (http://localhost:8001)"
	@echo ""
	@echo "  make test         전체 테스트 실행"
	@echo "  make test-python  Python 서비스 테스트만"
	@echo "  make test-node    Node.js 서비스 테스트만"
	@echo "  make test-infra   CDK synth 검증"
	@echo "  make test-e2e     E2E 테스트 (dev 배포 후 실행, 환경변수 필요)"
	@echo "  make smoke-dev    dev 배포 후 스모크 테스트"
	@echo "  make smoke-prod   prod 배포 후 스모크 테스트"
	@echo ""
	@echo "  make build        전체 빌드"
	@echo "  make deploy-dev   dev 환경 CDK 배포 (확인 없이)"
	@echo "  make deploy-prod  prod 환경 CDK 배포 (확인 프롬프트)"
	@echo "  make lint         린트 (TypeScript + Python)"
	@echo "  make clean        빌드 산출물 정리"
	@echo ""

# ── 로컬 환경 ────────────────────────────────────────────────
setup:
	@echo "[setup] Docker 컨테이너 시작..."
	docker compose up -d dynamodb-local localstack
	@echo "[setup] 서비스 초기화 스크립트 실행..."
	bash scripts/setup-local.sh

setup-admin:
	@echo "[setup] DynamoDB Admin UI 포함 실행..."
	docker compose --profile admin up -d
	bash scripts/setup-local.sh
	@echo "[setup] DynamoDB Admin: http://localhost:8001"

teardown:
	@echo "[teardown] 컨테이너 중지 및 제거..."
	docker compose --profile admin down
	@echo "[teardown] 완료"

# ── 테스트 ───────────────────────────────────────────────────
test: test-python test-node test-infra
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo " 전체 테스트 완료"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test-python:
	@echo "[test] Python 서비스 테스트..."
	@for svc in crawler processor notifier analyzer rag; do \
		echo "  → services/$$svc"; \
		(cd services/$$svc && $(PYTEST) -q --tb=short 2>&1) || exit 1; \
	done

test-node:
	@echo "[test] Node.js 서비스 테스트..."
	@for svc in user school; do \
		echo "  → services/$$svc"; \
		(cd services/$$svc && pnpm test --passWithNoTests 2>&1) || exit 1; \
	done

test-infra:
	@echo "[test] CDK synth 검증..."
	cd infrastructure && npx cdk synth --quiet
	@echo "  ✓ cdk synth 성공"

# E2E 테스트 — dev 스테이지 실제 AWS 환경 필요
# 필수 환경변수: E2E_API_BASE_URL, E2E_ACCESS_TOKEN
# 선택 환경변수: ENVIRONMENT(기본값 dev), E2E_TEST_LANG(기본값 vi)
test-e2e:
	@echo "[e2e] E2E 테스트 실행 (실제 AWS dev 환경)..."
	@if [ -z "$(E2E_API_BASE_URL)" ]; then \
		echo "[e2e] ERROR: E2E_API_BASE_URL 환경변수가 필요합니다."; \
		echo "       export E2E_API_BASE_URL=https://<api-id>.execute-api.us-east-1.amazonaws.com/dev"; \
		exit 1; \
	fi
	@if [ -z "$(E2E_ACCESS_TOKEN)" ]; then \
		echo "[e2e] ERROR: E2E_ACCESS_TOKEN 환경변수가 필요합니다."; \
		echo "       export E2E_ACCESS_TOKEN=\$$(aws cognito-idp initiate-auth ...)"; \
		exit 1; \
	fi
	$(PYTHON) -m pip install -q -r tests/e2e/requirements.txt
	$(PYTEST) tests/e2e/ -v --timeout=120
	@echo "[e2e] 완료"

smoke-dev:
	bash scripts/test-smoke.sh dev

smoke-prod:
	bash scripts/test-smoke.sh prod

# ── 빌드 ────────────────────────────────────────────────────
build: build-node
	@echo "[build] 전체 빌드 완료"

build-node:
	@echo "[build] Node.js 패키지 빌드..."
	cd packages/shared-types && npx tsc
	cd packages/shared-utils && npx tsc
	@for svc in user school; do \
		echo "  → services/$$svc"; \
		(cd services/$$svc && pnpm build 2>&1) || exit 1; \
	done

# ── 배포 ────────────────────────────────────────────────────
deploy-dev:
	@echo "[deploy] dev 환경 배포 시작..."
	@echo "  ⚠️  Cloud9 또는 AWS 자격증명이 설정된 환경에서 실행하세요."
	cd infrastructure && npx cdk deploy --all \
		-c environment=dev \
		--require-approval never \
		--outputs-file cdk-outputs-dev.json
	@echo "[deploy] dev 배포 완료. 출력값: infrastructure/cdk-outputs-dev.json"

deploy-prod:
	@echo "[deploy] ⚠️  운영(prod) 환경 배포"
	@echo "[deploy] 이 작업은 실제 AWS 리소스에 영향을 미칩니다."
	@printf "운영 배포를 진행하시겠습니까? (yes/no): "; \
		read confirm; \
		if [ "$$confirm" != "yes" ]; then \
			echo "[deploy] 취소됨."; \
			exit 1; \
		fi
	cd infrastructure && npx cdk deploy --all \
		-c environment=prod \
		--require-approval broadening \
		--outputs-file cdk-outputs-prod.json
	@echo "[deploy] prod 배포 완료. 출력값: infrastructure/cdk-outputs-prod.json"

# ── 린트 ────────────────────────────────────────────────────
lint:
	@echo "[lint] TypeScript..."
	cd infrastructure && npx tsc --noEmit
	@echo "[lint] Python (flake8)..."
	@for svc in crawler processor notifier analyzer rag kb-sync; do \
		if command -v flake8 > /dev/null 2>&1; then \
			(cd services/$$svc && $(PYTHON) -m flake8 . --max-line-length=120 --exclude=__pycache__,.coverage 2>&1) || true; \
		fi; \
	done

# ── 정리 ────────────────────────────────────────────────────
clean:
	@echo "[clean] 빌드 산출물 정리..."
	find . -type d -name "__pycache__"  -not -path "*/node_modules/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".coverage"    -not -path "*/node_modules/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist"         -not -path "*/node_modules/*" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc"                -not -path "*/node_modules/*" -delete            2>/dev/null || true
	@echo "[clean] 완료"
