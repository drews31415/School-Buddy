# School Buddy

학교 공지사항 자동 크롤링 및 AI 기반 알림 서비스 모노레포.

## 구조

```
/apps/mobile          — React Native (Expo) 모바일 앱
/packages/shared-types — 공통 TypeScript 타입
/packages/shared-utils — 공통 유틸리티 함수
/infrastructure       — AWS CDK IaC
/services/crawler     — Lambda: 공지 크롤러
/services/processor   — Lambda: 공지 처리기
/services/notifier    — Lambda: 알림 발송기
/services/analyzer    — Lambda: 문서 분석기 (Bedrock)
/services/rag         — Lambda: RAG 질의 핸들러
/services/user        — Lambda: 사용자 관리
/services/school      — Lambda: 학교 레지스트리
/tests                — 단위/통합/E2E 테스트
/docs                 — 문서 (PRD 등)
```

## 빠른 시작

```bash
pnpm install
pnpm build
pnpm test
```
