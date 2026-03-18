"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.handler = void 0;
/**
 * notification-sender Lambda handler
 * SNS 이벤트를 받아 사용자 디바이스로 푸시 알림을 전송한다.
 */
const handler = async (event) => {
    console.log("notifier triggered", JSON.stringify(event));
    // TODO: 사용자 구독 조회 → FCM/APNs 푸시 발송
};
exports.handler = handler;
//# sourceMappingURL=index.js.map