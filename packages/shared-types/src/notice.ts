import { LanguageCode, NoticeImportance } from "./enums";

export interface Notice {
  noticeId: string;
  schoolId: string;
  originalText: string;
  summary: string;
  /** 언어 코드별 번역 결과 */
  translations: Partial<Record<LanguageCode, string>>;
  importance: NoticeImportance;
  createdAt: string; // ISO 8601
}
