/**
 * 지원 언어 코드 (1차 출시 8개국어)
 * PRD 섹션 10.1 기준
 */
export enum LanguageCode {
  VI = "vi",       // 베트남어
  ZH_CN = "zh-CN", // 중국어 간체
  ZH_TW = "zh-TW", // 중국어 번체
  EN = "en",       // 영어
  JA = "ja",       // 일본어
  TH = "th",       // 태국어
  MN = "mn",       // 몽골어
  TL = "tl",       // 필리핀어
}

/**
 * 공지 중요도
 */
export enum NoticeImportance {
  LOW = "LOW",
  MEDIUM = "MEDIUM",
  HIGH = "HIGH",
}

/**
 * 학교 크롤링 상태
 */
export enum CrawlStatus {
  ACTIVE = "ACTIVE",
  ERROR = "ERROR",
  INACTIVE = "INACTIVE",
}

/**
 * 채팅 메시지 역할
 */
export enum ChatRole {
  USER = "user",
  ASSISTANT = "assistant",
}
