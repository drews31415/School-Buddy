import * as cdk from "aws-cdk-lib";
import * as cloudwatch from "aws-cdk-lib/aws-cloudwatch";
import { Construct } from "constructs";
import { ApplicationStack } from "./application-stack";

export interface MonitoringStackProps extends cdk.StackProps {
  environment: string;
  application: ApplicationStack;
}

/**
 * MonitoringStack
 * CloudWatch 대시보드 및 알람.
 * ⚠️ Phase 7에서 상세 내용 추가 예정 — 현재는 기본 골격만 정의.
 */
export class MonitoringStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: MonitoringStackProps) {
    super(scope, id, props);

    const { environment, application } = props;

    cdk.Tags.of(this).add("Project", "school-buddy");
    cdk.Tags.of(this).add("Environment", environment);

    // ──────────────────────────────────────────────────────
    // CloudWatch Dashboard
    // ──────────────────────────────────────────────────────
    const dashboard = new cloudwatch.Dashboard(this, "Dashboard", {
      dashboardName: `school-buddy-${environment}`,
    });

    // Lambda Error 메트릭 위젯
    const lambdaErrorWidget = new cloudwatch.GraphWidget({
      title: "Lambda Errors",
      width: 24,
      left: [
        application.crawlerFn.metricErrors({ label: "crawler" }),
        application.processorFn.metricErrors({ label: "processor" }),
        application.notifierFn.metricErrors({ label: "notifier" }),
        application.analyzerFn.metricErrors({ label: "analyzer" }),
        application.ragFn.metricErrors({ label: "rag" }),
        application.userFn.metricErrors({ label: "user" }),
        application.schoolFn.metricErrors({ label: "school" }),
      ],
    });

    // Lambda Duration 메트릭 위젯
    const lambdaDurationWidget = new cloudwatch.GraphWidget({
      title: "Lambda Duration (ms)",
      width: 24,
      left: [
        application.crawlerFn.metricDuration({ label: "crawler" }),
        application.processorFn.metricDuration({ label: "processor" }),
        application.ragFn.metricDuration({ label: "rag" }),
      ],
    });

    dashboard.addWidgets(lambdaErrorWidget, lambdaDurationWidget);

    // ──────────────────────────────────────────────────────
    // TODO (Phase 7): 아래 알람 추가 예정
    // - crawler 연속 실패 알람 → SNS 운영 알림
    // - processor 에러율 임계치 초과 알람
    // - API Gateway 5xx 비율 알람
    // - DynamoDB 스로틀링 알람
    // - 비용 이상 탐지 알람 (AWS Cost Explorer)
    // - X-Ray 분산 추적 설정
    // ──────────────────────────────────────────────────────
  }
}
