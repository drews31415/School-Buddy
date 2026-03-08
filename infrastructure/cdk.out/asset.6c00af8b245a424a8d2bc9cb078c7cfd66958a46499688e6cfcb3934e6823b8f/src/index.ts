import { Handler, ScheduledEvent } from "aws-lambda";

/**
 * school-crawler Lambda handler
 * EventBridge 스케줄에 의해 트리거되어 학교 공지사항을 크롤링한다.
 */
export const handler: Handler<ScheduledEvent> = async (event) => {
  console.log("crawler triggered", JSON.stringify(event));
  // TODO: 학교별 공지사항 크롤링 → SQS 전송
};
