import * as cdk from "aws-cdk-lib";
import * as cloudwatch from "aws-cdk-lib/aws-cloudwatch";
import * as cloudwatchActions from "aws-cdk-lib/aws-cloudwatch-actions";
import * as sns from "aws-cdk-lib/aws-sns";
import * as snsSubscriptions from "aws-cdk-lib/aws-sns-subscriptions";
import { aws_xray as xray } from "aws-cdk-lib";
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
 * 예상 비용 (ap-northeast-3, 월):
 *   CloudWatch 알람 5개: $0.50
 *   대시보드 1개: $3.00
 *   X-Ray 샘플링 5%: ~$0.50/100만 트레이스
 */
export class MonitoringStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: MonitoringStackProps) {
    super(scope, id, props);

    const { environment, application, storage } = props;

    // Tags 제거: hanyang-pj-1 계정은 TagResource 권한 없음

    // ──────────────────────────────────────────────────────
    // SNS 알람 토픽 (→ 운영팀 이메일)
    // ──────────────────────────────────────────────────────
    const alarmEmail = this.node.tryGetContext("alarmEmail") ?? "ops@school-buddy.example.com";

    const alarmTopic = new sns.Topic(this, "AlarmTopic", {
      topicName:   `school-buddy-alarms-${environment}`,
      displayName: "School Buddy 운영 알람",
    });
    alarmTopic.addSubscription(new snsSubscriptions.EmailSubscription(alarmEmail));
    const alarmAction = new cloudwatchActions.SnsAction(alarmTopic);

    // ──────────────────────────────────────────────────────
    // 알람 1. CrawlerErrorRate — Lambda 에러율 > 10% (5분)
    // ──────────────────────────────────────────────────────
    const crawlerErrors      = application.crawlerFn.metricErrors(
      { period: cdk.Duration.minutes(5), statistic: "Sum" }
    );
    const crawlerInvocations = application.crawlerFn.metricInvocations(
      { period: cdk.Duration.minutes(5), statistic: "Sum" }
    );
    const crawlerErrorRate = new cloudwatch.MathExpression({
      expression:   "errors / MAX([invocations, 1]) * 100",
      usingMetrics: { errors: crawlerErrors, invocations: crawlerInvocations },
      period:       cdk.Duration.minutes(5),
      label:        "크롤러 에러율(%)",
    });
    const crawlerErrorAlarm = new cloudwatch.Alarm(this, "CrawlerErrorRateAlarm", {
      alarmName:          `school-buddy-crawler-error-rate-${environment}`,
      alarmDescription:   "크롤러 Lambda 에러율 > 10% (5분 기준). 학교 사이트 접근 오류 가능성 확인 필요.",
      metric:             crawlerErrorRate,
      threshold:          10,
      evaluationPeriods:  1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData:   cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    crawlerErrorAlarm.addAlarmAction(alarmAction);
    crawlerErrorAlarm.addOkAction(alarmAction);

    // ──────────────────────────────────────────────────────
    // 알람 2. ProcessorDLQDepth — notice-dlq 메시지 > 0 (즉시)
    // ──────────────────────────────────────────────────────
    const dlqDepthAlarm = new cloudwatch.Alarm(this, "ProcessorDLQDepthAlarm", {
      alarmName:          `school-buddy-processor-dlq-depth-${environment}`,
      alarmDescription:   "notice-dlq에 메시지가 쌓였습니다. 공지 처리 실패 — processor Lambda 로그 확인 필요.",
      metric:             application.noticeDLQ.metricApproximateNumberOfMessagesVisible({
        period:    cdk.Duration.minutes(1),
        statistic: "Maximum",
        label:     "DLQ 메시지 수",
      }),
      threshold:          0,
      evaluationPeriods:  1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData:   cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    dlqDepthAlarm.addAlarmAction(alarmAction);
    dlqDepthAlarm.addOkAction(alarmAction);

    // ──────────────────────────────────────────────────────
    // 알람 3. APILatencyP99 — API Gateway P99 > 3000ms
    // ──────────────────────────────────────────────────────
    const apiLatencyP99Alarm = new cloudwatch.Alarm(this, "APILatencyP99Alarm", {
      alarmName:          `school-buddy-api-latency-p99-${environment}`,
      alarmDescription:   "API Gateway P99 레이턴시 > 3000ms. Lambda Cold Start 또는 Bedrock 응답 지연 확인.",
      metric: new cloudwatch.Metric({
        namespace:     "AWS/ApiGateway",
        metricName:    "Latency",
        dimensionsMap: { ApiId: application.api.httpApiId },
        statistic:     "p99",
        period:        cdk.Duration.minutes(5),
        label:         "API P99 레이턴시(ms)",
      }),
      threshold:          3000,
      evaluationPeriods:  3,
      datapointsToAlarm:  2,  // 3번 중 2번 초과 시 알람
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData:   cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    apiLatencyP99Alarm.addAlarmAction(alarmAction);
    apiLatencyP99Alarm.addOkAction(alarmAction);

    // ──────────────────────────────────────────────────────
    // 알람 4. BedrockThrottling — ThrottlingException 발생 즉시
    // ──────────────────────────────────────────────────────
    // 네임스페이스: SchoolBuddy/Bedrock (shared-utils/bedrock.py에서 발행)
    const bedrockThrottlingAlarm = new cloudwatch.Alarm(this, "BedrockThrottlingAlarm", {
      alarmName:          `school-buddy-bedrock-throttling-${environment}`,
      alarmDescription:   "Bedrock API ThrottlingException 발생. Bedrock 서비스 할당량 증가 또는 재시도 로직 검토 필요.",
      metric: new cloudwatch.Metric({
        namespace:     "SchoolBuddy/Bedrock",
        metricName:    "ThrottlingCount",
        statistic:     "Sum",
        period:        cdk.Duration.minutes(1),
        label:         "Bedrock 스로틀 횟수",
      }),
      threshold:          0,
      evaluationPeriods:  1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData:   cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    bedrockThrottlingAlarm.addAlarmAction(alarmAction);

    // ──────────────────────────────────────────────────────
    // 알람 5. DynamoDBErrors — SystemError > 0
    // ──────────────────────────────────────────────────────
    // 핵심 테이블(Notices, ChatHistory, Users) SystemErrors 합산
    const dynamoErrorAlarm = new cloudwatch.Alarm(this, "DynamoDBErrorAlarm", {
      alarmName:          `school-buddy-dynamodb-system-errors-${environment}`,
      alarmDescription:   "DynamoDB SystemError 발생. AWS 서비스 장애 가능성 — AWS Health Dashboard 확인.",
      metric: new cloudwatch.MathExpression({
        expression:   "e_notices + e_chat + e_users + e_cache",
        usingMetrics: {
          e_notices: new cloudwatch.Metric({
            namespace: "AWS/DynamoDB", metricName: "SystemErrors",
            dimensionsMap: { TableName: storage.noticesTable.tableName },
            statistic: "Sum", period: cdk.Duration.minutes(5),
          }),
          e_chat: new cloudwatch.Metric({
            namespace: "AWS/DynamoDB", metricName: "SystemErrors",
            dimensionsMap: { TableName: storage.chatHistoryTable.tableName },
            statistic: "Sum", period: cdk.Duration.minutes(5),
          }),
          e_users: new cloudwatch.Metric({
            namespace: "AWS/DynamoDB", metricName: "SystemErrors",
            dimensionsMap: { TableName: storage.usersTable.tableName },
            statistic: "Sum", period: cdk.Duration.minutes(5),
          }),
          e_cache: new cloudwatch.Metric({
            namespace: "AWS/DynamoDB", metricName: "SystemErrors",
            dimensionsMap: { TableName: storage.translationCacheTable.tableName },
            statistic: "Sum", period: cdk.Duration.minutes(5),
          }),
        },
        period: cdk.Duration.minutes(5),
        label:  "DynamoDB SystemErrors (합산)",
      }),
      threshold:          0,
      evaluationPeriods:  1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
      treatMissingData:   cloudwatch.TreatMissingData.NOT_BREACHING,
    });
    dynamoErrorAlarm.addAlarmAction(alarmAction);

    // ──────────────────────────────────────────────────────
    // CloudWatch 대시보드 (school-buddy-dashboard)
    // ──────────────────────────────────────────────────────
    const dashboard = new cloudwatch.Dashboard(this, "Dashboard", {
      dashboardName: `school-buddy-${environment}`,
      periodOverride: cloudwatch.PeriodOverride.AUTO,
    });

    // ── 위젯 1: Lambda 함수별 에러율 & 호출 수 (전체 너비) ─
    const lambdaFunctions = [
      { fn: application.crawlerFn,   label: "crawler"   },
      { fn: application.processorFn, label: "processor" },
      { fn: application.notifierFn,  label: "notifier"  },
      { fn: application.analyzerFn,  label: "analyzer"  },
      { fn: application.ragFn,       label: "rag"       },
      { fn: application.userFn,      label: "user"      },
      { fn: application.schoolFn,    label: "school"    },
      { fn: application.kbSyncFn,    label: "kb-sync"   },
    ];

    const w1Errors      = lambdaFunctions.map(({ fn, label }) =>
      fn.metricErrors({ label: `${label} 에러`, period: cdk.Duration.minutes(5) })
    );
    const w1Invocations = lambdaFunctions.map(({ fn, label }) =>
      fn.metricInvocations({ label: `${label} 호출`, period: cdk.Duration.minutes(5) })
    );

    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title:  "① Lambda 에러 수 & 호출 수",
        width:  24,
        height: 6,
        left:   w1Errors,
        right:  w1Invocations,
        leftAnnotations: [{ value: 5, label: "에러 임계치", color: "#ff0000" }],
        legendPosition: cloudwatch.LegendPosition.BOTTOM,
        view: cloudwatch.GraphWidgetView.TIME_SERIES,
      })
    );

    // ── 위젯 2: SQS 메시지 수 & DLQ 깊이 ──────────────────
    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title:  "② SQS notice-queue 메시지 수 & DLQ 깊이",
        width:  12,
        height: 6,
        left: [
          application.noticeQueue.metricApproximateNumberOfMessagesVisible({
            label: "notice-queue 대기 수", period: cdk.Duration.minutes(1),
          }),
          application.noticeQueue.metricNumberOfMessagesSent({
            label: "notice-queue 수신", period: cdk.Duration.minutes(1),
          }),
          application.noticeQueue.metricNumberOfMessagesDeleted({
            label: "notice-queue 처리완료", period: cdk.Duration.minutes(1),
          }),
        ],
        right: [
          application.noticeDLQ.metricApproximateNumberOfMessagesVisible({
            label: "DLQ 깊이 ⚠️", period: cdk.Duration.minutes(1),
          }),
        ],
        rightAnnotations: [{ value: 1, label: "DLQ 임계치", color: "#ff6600" }],
        legendPosition: cloudwatch.LegendPosition.BOTTOM,
      }),

      // ── 위젯 3: API Gateway 요청 수 & 레이턴시 ───────────
      new cloudwatch.GraphWidget({
        title:  "③ API Gateway 요청 수 & 레이턴시",
        width:  12,
        height: 6,
        left: [
          new cloudwatch.Metric({
            namespace: "AWS/ApiGateway", metricName: "Count",
            dimensionsMap: { ApiId: application.api.httpApiId },
            statistic: "Sum", period: cdk.Duration.minutes(5),
            label: "요청 수",
          }),
        ],
        right: [
          new cloudwatch.Metric({
            namespace: "AWS/ApiGateway", metricName: "Latency",
            dimensionsMap: { ApiId: application.api.httpApiId },
            statistic: "p50", period: cdk.Duration.minutes(5),
            label: "P50 레이턴시(ms)",
          }),
          new cloudwatch.Metric({
            namespace: "AWS/ApiGateway", metricName: "Latency",
            dimensionsMap: { ApiId: application.api.httpApiId },
            statistic: "p99", period: cdk.Duration.minutes(5),
            label: "P99 레이턴시(ms)",
          }),
        ],
        rightAnnotations: [{ value: 3000, label: "P99 임계치(3s)", color: "#ff0000" }],
        legendPosition: cloudwatch.LegendPosition.BOTTOM,
      })
    );

    // ── 위젯 4: Bedrock 토큰 사용량 & 비용 추정 ──────────
    // SchoolBuddy/Bedrock 네임스페이스 — shared-utils/bedrock.py에서 발행
    // 비용 추산: claude-sonnet-4 입력 $3/1M 토큰, 출력 $15/1M 토큰
    const inputTokenMetric = new cloudwatch.Metric({
      namespace: "SchoolBuddy/Bedrock", metricName: "InputTokenCount",
      statistic: "Sum", period: cdk.Duration.hours(1), label: "입력 토큰",
    });
    const outputTokenMetric = new cloudwatch.Metric({
      namespace: "SchoolBuddy/Bedrock", metricName: "OutputTokenCount",
      statistic: "Sum", period: cdk.Duration.hours(1), label: "출력 토큰",
    });
    const estimatedCost = new cloudwatch.MathExpression({
      expression:   "(input_tokens / 1000000) * 3 + (output_tokens / 1000000) * 15",
      usingMetrics: { input_tokens: inputTokenMetric, output_tokens: outputTokenMetric },
      period:       cdk.Duration.hours(1),
      label:        "Bedrock 비용 추산($)",
    });

    dashboard.addWidgets(
      new cloudwatch.GraphWidget({
        title:  "④ Bedrock 토큰 사용량",
        width:  12,
        height: 6,
        left:   [inputTokenMetric, outputTokenMetric],
        right:  [
          new cloudwatch.Metric({
            namespace: "SchoolBuddy/Bedrock", metricName: "ThrottlingCount",
            statistic: "Sum", period: cdk.Duration.minutes(5), label: "스로틀 횟수",
          }),
        ],
        legendPosition: cloudwatch.LegendPosition.BOTTOM,
      }),

      new cloudwatch.SingleValueWidget({
        title:   "④ Bedrock 시간당 비용 추산($)",
        width:   6,
        height:  6,
        metrics: [estimatedCost],
      }),

      // ── 위젯 5: DynamoDB 읽기/쓰기 소비 용량 ──────────────
      new cloudwatch.GraphWidget({
        title:  "⑤ DynamoDB 소비 용량 (핵심 테이블)",
        width:  18,
        height: 6,
        left: [
          new cloudwatch.Metric({
            namespace: "AWS/DynamoDB", metricName: "ConsumedReadCapacityUnits",
            dimensionsMap: { TableName: storage.noticesTable.tableName },
            statistic: "Sum", period: cdk.Duration.minutes(5), label: "notices 읽기",
          }),
          new cloudwatch.Metric({
            namespace: "AWS/DynamoDB", metricName: "ConsumedWriteCapacityUnits",
            dimensionsMap: { TableName: storage.noticesTable.tableName },
            statistic: "Sum", period: cdk.Duration.minutes(5), label: "notices 쓰기",
          }),
          new cloudwatch.Metric({
            namespace: "AWS/DynamoDB", metricName: "ConsumedReadCapacityUnits",
            dimensionsMap: { TableName: storage.chatHistoryTable.tableName },
            statistic: "Sum", period: cdk.Duration.minutes(5), label: "chat-history 읽기",
          }),
          new cloudwatch.Metric({
            namespace: "AWS/DynamoDB", metricName: "ConsumedWriteCapacityUnits",
            dimensionsMap: { TableName: storage.chatHistoryTable.tableName },
            statistic: "Sum", period: cdk.Duration.minutes(5), label: "chat-history 쓰기",
          }),
          new cloudwatch.Metric({
            namespace: "AWS/DynamoDB", metricName: "ConsumedReadCapacityUnits",
            dimensionsMap: { TableName: storage.translationCacheTable.tableName },
            statistic: "Sum", period: cdk.Duration.minutes(5), label: "translation-cache 읽기",
          }),
          new cloudwatch.Metric({
            namespace: "AWS/DynamoDB", metricName: "ConsumedWriteCapacityUnits",
            dimensionsMap: { TableName: storage.translationCacheTable.tableName },
            statistic: "Sum", period: cdk.Duration.minutes(5), label: "translation-cache 쓰기",
          }),
        ],
        legendPosition: cloudwatch.LegendPosition.BOTTOM,
      })
    );

    // ──────────────────────────────────────────────────────
    // X-Ray 샘플링 규칙 (5% — 운영 비용 제어)
    // ──────────────────────────────────────────────────────
    // X-Ray tracing: Lambda별 active tracing은 application-stack.ts에서 설정.
    // 여기서는 커스텀 샘플링 규칙만 정의한다.
    new xray.CfnSamplingRule(this, "SamplingRule", {
      samplingRule: {
        ruleName:      `school-buddy-${environment}`,
        priority:      10,
        reservoirSize: 5,       // 매초 최대 5 트레이스는 100% 샘플링
        fixedRate:     0.05,    // 그 외 5%
        host:          "*",
        httpMethod:    "*",
        resourceArn:   "*",
        serviceName:   `school-buddy-*`,
        serviceType:   "*",
        urlPath:       "*",
        version:       1,
      },
    });

    // ──────────────────────────────────────────────────────
    // CloudFormation Outputs
    // ──────────────────────────────────────────────────────
    new cdk.CfnOutput(this, "AlarmTopicArn", {
      value:       alarmTopic.topicArn,
      description: "운영 알람 SNS Topic ARN",
      exportName:  `school-buddy-alarm-topic-arn-${environment}`,
    });
    new cdk.CfnOutput(this, "DashboardUrl", {
      value:       `https://${this.region}.console.aws.amazon.com/cloudwatch/home?region=${this.region}#dashboards:name=school-buddy-${environment}`,
      description: "CloudWatch 대시보드 URL",
    });
  }
}
