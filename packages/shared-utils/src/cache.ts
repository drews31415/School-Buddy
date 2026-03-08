import { TranslationCache } from "@school-buddy/shared-types";
import { getItem, putItem } from "./db";

const CACHE_TABLE = process.env.TRANSLATION_CACHE_TABLE ?? "";

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
export async function getCache(
  cacheKey: string
): Promise<TranslationCache | null> {
  return getItem<TranslationCache>(CACHE_TABLE, { cacheKey });
}

/**
 * 캐시 저장.
 * @param cacheKey  notice#{noticeId}#lang#{langCode}
 * @param data      저장할 번역 결과 (translation, culturalTip, checklistItems)
 * @param ttlHours  TTL 시간 (기본값 24시간)
 */
export async function setCache(
  cacheKey: string,
  data: Omit<TranslationCache, "cacheKey" | "expiresAt">,
  ttlHours = 24
): Promise<void> {
  const expiresAt = Math.floor(Date.now() / 1000) + ttlHours * 60 * 60;

  const item: TranslationCache = {
    cacheKey,
    ...data,
    expiresAt,
  };

  await putItem<TranslationCache>(CACHE_TABLE, item);
}

/**
 * cacheKey 생성 헬퍼
 */
export function buildCacheKey(noticeId: string, langCode: string): string {
  return `notice#${noticeId}#lang#${langCode}`;
}
