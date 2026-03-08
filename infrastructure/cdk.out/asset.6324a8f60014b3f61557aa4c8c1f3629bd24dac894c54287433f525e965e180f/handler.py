"""
notification-sender Lambda handler (Python 3.12)
SNS 트리거. 번역된 공지 알림을 사용자 디바이스로 FCM / APNs 푸시 발송.
"""
import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

USERS_TABLE = os.environ.get("USERS_TABLE", "")
NOTIFICATIONS_TABLE = os.environ.get("NOTIFICATIONS_TABLE", "")
FCM_SECRETS_NAME = os.environ.get("FCM_SECRETS_NAME", "")


def handler(event: dict, context) -> None:
    """
    SNSEvent 핸들러.
    TODO: 사용자 FCM 토큰 조회 → Firebase Admin SDK로 푸시 발송 → 발송 이력 저장
    """
    for record in event.get("Records", []):
        try:
            message = json.loads(record["Sns"]["Message"])
            logger.info({"message": "sending notification", "noticeId": message.get("noticeId")})
            # TODO: 실제 FCM 발송 로직
        except Exception as e:
            logger.error({"message": "failed to send notification", "error": str(e)})
            raise  # SNS 재시도를 위해 raise
