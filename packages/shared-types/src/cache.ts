/**
 * TranslationCache — DynamoDB TranslationCache 테이블 항목
 * cacheKey 형식: notice#{noticeId}#lang#{langCode}
 * TTL: 24시간 (ElastiCache 대체)
 */
export interface TranslationCache {
  cacheKey: string;
  translation: string;
  culturalTip: string;
  checklistItems: string[];
  expiresAt: number; // Unix timestamp (DynamoDB TTL)
}
