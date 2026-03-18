import { Handler, SQSEvent } from "aws-lambda";
/**
 * notice-processor Lambda handler
 * SQS 메시지(크롤링 결과)를 받아 중복 제거 후 DynamoDB에 저장하고 알림을 트리거한다.
 */
export declare const handler: Handler<SQSEvent>;
//# sourceMappingURL=index.d.ts.map