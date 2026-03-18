import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import { ApplicationStack } from "./application-stack";
import { StorageStack } from "./storage-stack";
export interface MonitoringStackProps extends cdk.StackProps {
    environment: string;
    application: ApplicationStack;
    storage: StorageStack;
}
/**
 * MonitoringStack
 * CloudWatch 대시보드 5종 + 알람 5개 + X-Ray 샘플링 규칙.
 *
 * 알람 → SNS → 이메일 알림.
 * 알람 수신 이메일: CDK context "alarmEmail" (기본값: ops@school-buddy.example.com)
 *   예) npx cdk deploy -c alarmEmail=you@example.com
 *
 * 예상 비용 (us-east-1, 월):
 *   CloudWatch 알람 5개: $0.50
 *   대시보드 1개: $3.00
 *   X-Ray 샘플링 5%: ~$0.50/100만 트레이스
 */
export declare class MonitoringStack extends cdk.Stack {
    constructor(scope: Construct, id: string, props: MonitoringStackProps);
}
//# sourceMappingURL=monitoring-stack.d.ts.map