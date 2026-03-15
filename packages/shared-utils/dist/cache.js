"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getCache = getCache;
exports.setCache = setCache;
exports.buildCacheKey = buildCacheKey;
const db_1 = require("./db");
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
async function getCache(cacheKey) {
    return (0, db_1.getItem)(CACHE_TABLE, { cacheKey });
}
/**
 * 캐시 저장.
 * @param cacheKey  notice#{noticeId}#lang#{langCode}
 * @param data      저장할 번역 결과 (translation, culturalTip, checklistItems)
 * @param ttlHours  TTL 시간 (기본값 24시간)
 */
async function setCache(cacheKey, data, ttlHours = 24) {
    const expiresAt = Math.floor(Date.now() / 1000) + ttlHours * 60 * 60;
    const item = {
        cacheKey,
        ...data,
        expiresAt,
    };
    await (0, db_1.putItem)(CACHE_TABLE, item);
}
/**
 * cacheKey 생성 헬퍼
 */
function buildCacheKey(noticeId, langCode) {
    return `notice#${noticeId}#lang#${langCode}`;
}
//# sourceMappingURL=cache.js.map