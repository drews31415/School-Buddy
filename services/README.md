# services

각 Lambda 함수 서비스 디렉토리.

| 서비스 | Lambda 이름 | 트리거 | 역할 |
|--------|------------|--------|------|
| crawler | school-crawler | EventBridge 스케줄 | 학교 공지 크롤링 → SQS |
| processor | notice-processor | SQS | 중복 제거 → DynamoDB → SNS |
| notifier | notification-sender | SNS | 사용자 푸시 알림 발송 |
| analyzer | document-analyzer | SQS/직접 호출 | Bedrock 분류/임베딩 |
| rag | rag-query-handler | API Gateway | RAG 질의 처리 |
| user | user-manager | API Gateway | 사용자 CRUD |
| school | school-registry | API Gateway | 학교 CRUD |
