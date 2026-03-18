"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.handler = void 0;
/**
 * school-crawler Lambda handler
 * EventBridge 스케줄에 의해 트리거되어 학교 공지사항을 크롤링한다.
 */
const handler = async (event) => {
    console.log("crawler triggered", JSON.stringify(event));
    // TODO: 학교별 공지사항 크롤링 → SQS 전송
};
exports.handler = handler;
//# sourceMappingURL=index.js.map