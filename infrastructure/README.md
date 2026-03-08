# @school-buddy/infrastructure

AWS CDK (TypeScript) IaC 코드. 모든 AWS 리소스를 정의한다.

## 주요 리소스 (예정)

- Lambda Functions (각 서비스별)
- DynamoDB Tables
- SQS Queues
- EventBridge Rules
- SNS Topics

## 명령어

```bash
pnpm synth          # CloudFormation 템플릿 생성
pnpm diff           # 변경사항 확인
pnpm deploy         # 전체 스택 배포
pnpm destroy        # 전체 스택 삭제 (주의)
```

## 사전 요구사항

- AWS CLI 설정 완료
- `CDK_DEFAULT_ACCOUNT` / `CDK_DEFAULT_REGION` 환경변수 또는 AWS 프로파일
