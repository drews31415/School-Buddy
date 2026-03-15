"""
Firebase Admin SDK FCM 푸시 알림 발송 모듈.

firebase_admin 앱은 Lambda 컨테이너당 한 번만 초기화된다.
네이티브(fcmToken)와 웹(fcmTokenWeb) 토큰을 모두 지원한다.
"""
from __future__ import annotations

import json
import logging
from typing import NamedTuple

import firebase_admin
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)

# Lambda 컨테이너 재사용 시 중복 초기화 방지
_firebase_app: firebase_admin.App | None = None


class SendResult(NamedTuple):
    success: bool
    token_expired: bool   # True → 호출자가 DB에서 토큰 삭제


def init_firebase(service_account: dict) -> None:
    """
    Firebase Admin SDK 초기화.
    이미 초기화된 경우 건너뛴다 (Lambda 웜 실행 대응).
    """
    global _firebase_app
    if _firebase_app is not None:
        return
    cred = credentials.Certificate(service_account)
    _firebase_app = firebase_admin.initialize_app(cred)
    logger.info({"message": "Firebase Admin SDK 초기화 완료"})


def send_push(
    token: str,
    title: str,
    body: str,
    data: dict[str, str],
) -> SendResult:
    """
    단일 FCM 토큰에 푸시 알림 발송.

    Parameters
    ----------
    token : str   FCM 등록 토큰 (네이티브 또는 웹)
    title : str   알림 제목
    body  : str   알림 본문 (100자 이내 권장)
    data  : dict  추가 데이터 페이로드 (문자열 값만 허용)

    Returns
    -------
    SendResult(success, token_expired)
    """
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data=data,
        token=token,
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                channel_id="school_notices",
                click_action="FLUTTER_NOTIFICATION_CLICK",
            ),
        ),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound="default", badge=1)
            )
        ),
    )

    try:
        messaging.send(message)
        return SendResult(success=True, token_expired=False)

    except messaging.UnregisteredError:
        # 토큰 만료 또는 앱 삭제 — DB에서 토큰 제거 필요
        logger.info({"message": "FCM 토큰 만료", "token_prefix": token[:20]})
        return SendResult(success=False, token_expired=True)

    except messaging.SenderIdMismatchError:
        logger.error({"message": "FCM SenderID 불일치", "token_prefix": token[:20]})
        return SendResult(success=False, token_expired=False)

    except Exception as e:
        logger.error({"message": "FCM 발송 실패", "error": str(e), "token_prefix": token[:20]})
        return SendResult(success=False, token_expired=False)


def send_multicast(
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, str],
) -> tuple[int, list[str]]:
    """
    멀티캐스트 발송 (최대 500개 토큰).
    단일 호출로 여러 토큰에 동일한 메시지를 발송한다.

    Returns
    -------
    (success_count, expired_tokens)
    """
    if not tokens:
        return 0, []

    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data=data,
        tokens=tokens,
    )
    batch_resp = messaging.send_each_for_multicast(message)

    expired: list[str] = []
    for idx, resp in enumerate(batch_resp.responses):
        if not resp.success and resp.exception:
            if isinstance(resp.exception, messaging.UnregisteredError):
                expired.append(tokens[idx])

    return batch_resp.success_count, expired
