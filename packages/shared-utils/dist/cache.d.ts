import { TranslationCache } from "@school-buddy/shared-types";
/**
 * TranslationCache 전용 유틸리티
 *
 * cacheKey 형식: notice#{noticeId}#lang#{langCode}
 * TTL: DynamoDB expiresAt 속성 (Unix timestamp)
 */
/**
 * 캐시 조회.
 * 만료된 항목은 DynamoDB TTL이 자동 삭제하므로 별도 만료 체크 불필요.
 * @returns TranslationCache 항목 또는 null (캐시 미스)
 */
export declare function getCache(cacheKey: string): Promise<TranslationCache | null>;
/**
 * 캐시 저장.
 * @param cacheKey  notice#{noticeId}#lang#{langCode}
 * @param data      저장할 번역 결과 (translation, culturalTip, checklistItems)
 * @param ttlHours  TTL 시간 (기본값 24시간)
 */
export declare function setCache(cacheKey: string, data: Omit<TranslationCache, "cacheKey" | "expiresAt">, ttlHours?: number): Promise<void>;
/**
 * cacheKey 생성 헬퍼
 */
export declare function buildCacheKey(noticeId: string, langCode: string): string;
//# sourceMappingURL=cache.d.ts.map