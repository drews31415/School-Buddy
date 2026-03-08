# School Buddy — 프로젝트 공통 지침

## 프로젝트 개요
다문화가정 학부모를 위한 AI 학부모 비서 앱.
자세한 내용은 `/docs/PRD.md` 참고.

## 절대 규칙 (어떤 에이전트도 위반 금지)
1. 비밀값(API 키, 비밀번호, 서비스 계정 JSON) 하드코딩 금지
2. 아동 개인정보(자녀 이름, 학교, 학년)를 로그에 출력 금지
3. `main` 브랜치에 직접 push 금지 (PR 필수)
4. 테스트 없는 비즈니스 로직 추가 금지

## 기술 결정 기록
- AI 모델: Claude (Bedrock) — 번역 품질 + 문화 맥락 이해 이유
- DB: DynamoDB — Serverless, 가변 스키마, 비용 이유
- 앱: React Native (Expo) — iOS/Android 동시 지원, 팀 규모 이유
- IaC: CDK TypeScript — 타입 안전성, 팀 언어 통일 이유

## 모노레포 구조
- `/apps` — 클라이언트 앱
- `/services` — Lambda 함수
- `/packages` — 공유 코드
- `/infrastructure` — CDK
- `/tests` — 통합·E2E 테스트
- `/docs` — 문서

## 브랜치 전략
- `main` — 운영 배포
- `dev` — 개발 통합
- `feat/{feature-name}` — 기능 개발
- `fix/{issue}` — 버그 수정