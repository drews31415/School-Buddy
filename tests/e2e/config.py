"""
E2E 테스트 전역 설정.
모든 값은 환경변수로 주입받음 — 하드코딩 금지 (CLAUDE.md 절대 규칙 §1).
"""
import os

# ── AWS ─────────────────────────────────────────────────────────────────────
AWS_REGION   = "us-east-1"          # ⚠️ 항상 us-east-1 고정
ENVIRONMENT  = os.environ.get("ENVIRONMENT", "dev")

# ── DynamoDB 테이블명 ────────────────────────────────────────────────────────
SCHOOLS_TABLE           = f"school-buddy-schools-{ENVIRONMENT}"
NOTICES_TABLE           = f"school-buddy-notices-{ENVIRONMENT}"
NOTIFICATIONS_TABLE     = f"school-buddy-notifications-{ENVIRONMENT}"
TRANSLATION_CACHE_TABLE = f"school-buddy-translation-cache-{ENVIRONMENT}"
USERS_TABLE             = f"school-buddy-users-{ENVIRONMENT}"
CHAT_HISTORY_TABLE      = f"school-buddy-chat-history-{ENVIRONMENT}"

# ── Lambda 함수명 ─────────────────────────────────────────────────────────────
CRAWLER_FUNCTION   = f"school-buddy-crawler-{ENVIRONMENT}"
PROCESSOR_FUNCTION = f"school-buddy-processor-{ENVIRONMENT}"

# ── SQS ─────────────────────────────────────────────────────────────────────
NOTICE_QUEUE_NAME = f"school-buddy-notice-queue-{ENVIRONMENT}"

# ── API ─────────────────────────────────────────────────────────────────────
API_BASE_URL    = os.environ.get("E2E_API_BASE_URL", "")
ACCESS_TOKEN    = os.environ.get("E2E_ACCESS_TOKEN", "")   # dev Cognito JWT

# ── SLA 기준 (초) ─────────────────────────────────────────────────────────────
SLA_NOTICE_PIPELINE_SEC   = 30   # 감지 → 푸시
SLA_DOCUMENT_ANALYSIS_SEC = 10   # 문서 분석 API
SLA_RAG_RESPONSE_SEC      = 5    # RAG Q&A API

# ── 폴링 설정 ────────────────────────────────────────────────────────────────
POLL_INTERVAL_SEC   = 3
MAX_WAIT_SEC        = 90   # SQS 메시지 + processor 완료 합산 최대 대기

# ── 테스트 픽스처 ─────────────────────────────────────────────────────────────
import pathlib
FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "fixtures"
SAMPLE_NOTICE_JPG = FIXTURES_DIR / "sample_notice.jpg"
