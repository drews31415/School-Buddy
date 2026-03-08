# @school-buddy/crawler

**Lambda: school-crawler**

EventBridge 스케줄로 트리거. 학교 공지사항 페이지를 크롤링하여 신규 공지를 SQS에 전송한다.

## 의존성

- `axios` + `cheerio` — HTML 파싱
- `@aws-sdk/client-sqs` — 크롤링 결과 큐 전송
