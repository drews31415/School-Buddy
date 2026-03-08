"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ChatRole = exports.CrawlStatus = exports.NoticeImportance = exports.LanguageCode = void 0;
/**
 * 지원 언어 코드 (1차 출시 8개국어)
 * PRD 섹션 10.1 기준
 */
var LanguageCode;
(function (LanguageCode) {
    LanguageCode["VI"] = "vi";
    LanguageCode["ZH_CN"] = "zh-CN";
    LanguageCode["ZH_TW"] = "zh-TW";
    LanguageCode["EN"] = "en";
    LanguageCode["JA"] = "ja";
    LanguageCode["TH"] = "th";
    LanguageCode["MN"] = "mn";
    LanguageCode["TL"] = "tl";
})(LanguageCode || (exports.LanguageCode = LanguageCode = {}));
/**
 * 공지 중요도
 */
var NoticeImportance;
(function (NoticeImportance) {
    NoticeImportance["LOW"] = "LOW";
    NoticeImportance["MEDIUM"] = "MEDIUM";
    NoticeImportance["HIGH"] = "HIGH";
})(NoticeImportance || (exports.NoticeImportance = NoticeImportance = {}));
/**
 * 학교 크롤링 상태
 */
var CrawlStatus;
(function (CrawlStatus) {
    CrawlStatus["ACTIVE"] = "ACTIVE";
    CrawlStatus["ERROR"] = "ERROR";
    CrawlStatus["INACTIVE"] = "INACTIVE";
})(CrawlStatus || (exports.CrawlStatus = CrawlStatus = {}));
/**
 * 채팅 메시지 역할
 */
var ChatRole;
(function (ChatRole) {
    ChatRole["USER"] = "user";
    ChatRole["ASSISTANT"] = "assistant";
})(ChatRole || (exports.ChatRole = ChatRole = {}));
//# sourceMappingURL=enums.js.map