# @school-buddy/processor

**Lambda: notice-processor**

SQS 트리거. 크롤링된 공지를 받아 중복 제거 후 DynamoDB에 저장, SNS로 알림 이벤트를 발행한다.
