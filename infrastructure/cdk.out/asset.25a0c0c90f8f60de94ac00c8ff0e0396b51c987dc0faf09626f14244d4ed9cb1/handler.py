"""
notification-sender Lambda handler (Python 3.12)

트리거: SNS notice-topic (notice-processor가 처리 완료 공지 발행)
역할:   해당 학교 구독 사용자에게 FCM 푸시 알림 발송

처리 흐름:
  1. SNS 메시지 파싱 (SNSNoticeMessage)
  2. FCM 자격증명 초기화 (최초 1회, Secrets Manager)
  3. schoolId-index GSI로 구독 사용자 조회
  4. 사용자별 필터링:
     a. notificationSettings.enabled = False → 건너뜀
     b. importanceThreshold 미달 → 건너뜀
     c. Quiet Hours(KST) 해당 → 건너뜀
  5. 사용자 언어의 번역 결과로 푸시 알림 구성
  6. fcmToken (네이티브) / fcmTokenWeb (웹) 각각 발송
  7. 만료 토큰 DB 삭제, Notifications 테이블에 이력 저장

환경변수:
  CHILDREN_TABLE       DynamoDB Children 테이블명
  USERS_TABLE          DynamoDB Users 테이블명
  SCHOOLS_TABLE        DynamoDB Schools 테이블명
  NOTIFICATIONS_TABLE  DynamoDB Notifications 테이블명
  FCM_SECRETS_NAME     Secrets Manager 키명 (기본: school-buddy/fcm-service-account)
  REGION               AWS 리전 (기본: us-east-1)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger()
logger.setLevel(logging.INFO)

from notifier.models import SNSNoticeMessage, UserRecord, IMPORTANCE_RANK
from notifier.db import (
    get_school_subscribers,
    get_school_name,
    save_notification,
    clear_fcm_token,
)
from notifier.fcm import init_firebase, send_push
from notifier.secrets import get_fcm_credentials

# 한국 표준시 (UTC+9)
_KST = timezone(timedelta(hours=9))

# FCM 초기화 상태 (Lambda 웜 실행 재사용)
_fcm_ready = False


def handler(event: dict, context) -> None:
    """
    SNSEvent 핸들러.

    SNS 트리거이므로 반환값 없음.
    레코드 단위 실패 시 raise → SNS가 재시도(최대 3회).
    """
    global _fcm_ready

    # ── FCM 초기화 (최초 콜드스타트 1회) ──────────────────────
    if not _fcm_ready:
        creds = get_fcm_credentials()
        init_firebase(creds)
        _fcm_ready = True

    for record in event.get("Records", []):
        _process_record(record)


def _process_record(record: dict) -> None:
    """단일 SNS 레코드 처리."""
    try:
        raw = json.loads(record["Sns"]["Message"])
        msg = SNSNoticeMessage.from_dict(raw)
    except (KeyError, json.JSONDecodeError, TypeError) as e:
        logger.error({"message": "SNS 메시지 파싱 실패", "error": str(e)})
        raise  # SNS 재시도

    logger.info(
        {
            "message": "processing notice notification",
            "noticeId": msg.noticeId,
            "schoolId": msg.schoolId,
            "importance": msg.importance,
        }
    )

    school_name = get_school_name(msg.schoolId)
    subscribers = get_school_subscribers(msg.schoolId)

    if not subscribers:
        logger.info(
            {"message": "구독자 없음, 건너뜀", "schoolId": msg.schoolId}
        )
        return

    now_kst = datetime.now(_KST)
    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sent_count = 0

    for user in subscribers:
        if not _should_notify(user, msg.importance, now_kst):
            continue

        # 사용자 언어 번역 → 없으면 영어 → 없으면 요약 원문 사용
        translation = (
            msg.translations.get(user.languageCode)
            or msg.translations.get("en")
            or {}
        )
        push_body = (translation.get("translation") or msg.summary)[:100]

        title = f"[{school_name}] 새 공지: {msg.title}"
        data = _build_data_payload(msg, user.languageCode, translation)

        user_notified = False

        # ── 네이티브 토큰 발송 ───────────────────────────────
        if user.fcmToken:
            result = send_push(user.fcmToken, title, push_body, data)
            if result.token_expired:
                clear_fcm_token(user.userId, "fcmToken")
            elif result.success:
                user_notified = True

        # ── 웹 토큰 발송 ─────────────────────────────────────
        if user.fcmTokenWeb:
            result = send_push(user.fcmTokenWeb, title, push_body, data)
            if result.token_expired:
                clear_fcm_token(user.userId, "fcmTokenWeb")
            elif result.success:
                user_notified = True

        if user_notified:
            save_notification(user.userId, msg.noticeId, sent_at)
            sent_count += 1

    logger.info(
        {
            "message": "notification dispatch complete",
            "noticeId": msg.noticeId,
            "schoolId": msg.schoolId,
            "subscribers": len(subscribers),
            "sent": sent_count,
        }
    )


# ── 내부 유틸 ──────────────────────────────────────────────────

def _should_notify(user: UserRecord, importance: str, now_kst: datetime) -> bool:
    """
    알림 발송 여부 결정.

    1. notificationSettings.enabled = False → 발송 안 함
    2. 공지 중요도 < 사용자 importanceThreshold → 발송 안 함
    3. 현재 KST 시각이 quiet hours 구간 → 발송 안 함
    """
    settings = user.notificationSettings

    if not settings.enabled:
        return False

    if IMPORTANCE_RANK.get(importance, 0) < IMPORTANCE_RANK.get(settings.importanceThreshold, 0):
        return False

    if _is_quiet_hours(settings.quietHoursStart, settings.quietHoursEnd, now_kst):
        return False

    return True


def _is_quiet_hours(
    start: str | None,
    end: str | None,
    now_kst: datetime,
) -> bool:
    """
    현재 KST 시각이 quiet hours 구간인지 확인.

    start/end 형식: "HH:MM" (예: "22:00", "08:00")
    자정 넘김(예: 22:00~08:00)도 처리한다.
    """
    if not start or not end:
        return False

    current = now_kst.strftime("%H:%M")
    if start <= end:
        # 같은 날 구간 (예: 09:00~18:00)
        return start <= current < end
    else:
        # 자정 넘김 구간 (예: 22:00~08:00)
        return current >= start or current < end


def _build_data_payload(
    msg: SNSNoticeMessage,
    lang_code: str,
    translation: dict,
) -> dict[str, str]:
    """
    FCM data 페이로드 구성.
    FCM data 값은 모두 문자열이어야 한다.
    """
    checklist = translation.get("checklistItems", [])
    return {
        "noticeId":      msg.noticeId,
        "schoolId":      msg.schoolId,
        "langCode":      lang_code,
        "sourceUrl":     msg.sourceUrl,
        "importance":    msg.importance,
        "culturalTip":   translation.get("culturalTip", ""),
        "checklistItems": json.dumps(checklist, ensure_ascii=False),
    }
