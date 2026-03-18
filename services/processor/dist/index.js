"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.handler = void 0;
/**
 * notice-processor Lambda handler
 * SQS 메시지(크롤링 결과)를 받아 중복 제거 후 DynamoDB에 저장하고 알림을 트리거한다.
 */
const handler = async (event) => {
    console.log("processor triggered", JSON.stringify(event));
    // TODO: 중복 제거 → DynamoDB 저장 → SNS 발행
};
exports.handler = handler;
//# sourceMappingURL=index.js.map