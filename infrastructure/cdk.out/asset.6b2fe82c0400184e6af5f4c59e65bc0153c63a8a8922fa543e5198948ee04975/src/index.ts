import { Handler, SNSEvent } from "aws-lambda";

/**
 * notification-sender Lambda handler
 * SNS 이벤트를 받아 사용자 디바이스로 푸시 알림을 전송한다.
 */
export const handler: Handler<SNSEvent> = async (event) => {
  console.log("notifier triggered", JSON.stringify(event));
  // TODO: 사용자 구독 조회 → FCM/APNs 푸시 발송
};
