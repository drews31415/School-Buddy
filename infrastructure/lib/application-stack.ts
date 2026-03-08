import * as path from "path";
import * as cdk from "aws-cdk-lib";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as iam from "aws-cdk-lib/aws-iam";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as sns from "aws-cdk-lib/aws-sns";
import * as snsSubscriptions from "aws-cdk-lib/aws-sns-subscriptions";
import * as lambdaEventSources from "aws-cdk-lib/aws-lambda-event-sources";
import * as events from "aws-cdk-lib/aws-events";
import * as eventsTargets from "aws-cdk-lib/aws-events-targets";
import * as apigwv2 from "aws-cdk-lib/aws-apigatewayv2";
import * as apigwv2Integrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as cognito from "aws-cdk-lib/aws-cognito";
import { Construct } from "constructs";
import { StorageStack } from "./storage-stack";

export interface ApplicationStackProps extends cdk.StackProps {
  environment: string;
  storage: StorageStack;
}

/**
 * ApplicationStack
 * Lambda 7개, API Gateway, SQS, SNS, EventBridge, Cognito.
 * 모든 Lambda는 기존 SafeRole-hanyang-pj-1 사용 (새 IAM Role 생성 금지).
 */
export class ApplicationStack extends cdk.Stack {
  public readonly api: apigwv2.HttpApi;
  public readonly userPool: cognito.UserPool;

  // Lambda functions — MonitoringStack에서 참조 가능
  public readonly crawlerFn: lambda.Function;
  public readonly processorFn: lambda.Function;
  public readonly notifierFn: lambda.Function;
  public readonly analyzerFn: lambda.Function;
  public readonly ragFn: lambda.Function;
  public readonly userFn: lambda.Function;
  public readonly schoolFn: lambda.Function;

  constructor(scope: Construct, id: string, props: ApplicationStackProps) {
    super(scope, id, props);

    const { environment, storage } = props;

    cdk.Tags.of(this).add("Project", "school-buddy");
    cdk.Tags.of(this).add("Environment", environment);

    // ──────────────────────────────────────────────────────
    // IAM — 기존 Role 참조 (새 Role 생성 금지)
    // ──────────────────────────────────────────────────────
    const safeRole = iam.Role.fromRoleName(
      this,
      "SafeRole",
      "SafeRole-hanyang-pj-1"
    );

    // ──────────────────────────────────────────────────────
    // Cognito User Pool
    // ──────────────────────────────────────────────────────
    this.userPool = new cognito.UserPool(this, "UserPool", {
      userPoolName: `school-buddy-user-pool-${environment}`,
      selfSignUpEnabled: true,
      signInAliases: { email: true },
      standardAttributes: {
        email: { required: true, mutable: true },
      },
      passwordPolicy: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: false,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // 앱 클라이언트 (모바일)
    const userPoolClient = this.userPool.addClient("MobileClient", {
      userPoolClientName: `school-buddy-mobile-${environment}`,
      authFlows: {
        userSrp: true,
        userPassword: false,
      },
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.PROFILE,
        ],
        callbackUrls: ["schoolbuddy://auth/callback"],
        logoutUrls: ["schoolbuddy://auth/logout"],
      },
      preventUserExistenceErrors: true,
    });

    // TODO: Google / Apple 소셜 로그인 IdP 설정
    // Google Client ID/Secret은 Secrets Manager에서 가져와야 함
    // new cognito.UserPoolIdentityProviderGoogle(this, 'GoogleProvider', { ... });

    // ──────────────────────────────────────────────────────
    // SQS Queues (Dead Letter Queue 포함)
    // ──────────────────────────────────────────────────────
    const noticeDLQ = new sqs.Queue(this, "NoticeDLQ", {
      queueName: `school-buddy-notice-dlq-${environment}`,
      retentionPeriod: cdk.Duration.days(14),
      encryption: sqs.QueueEncryption.SQS_MANAGED,
    });

    const noticeQueue = new sqs.Queue(this, "NoticeQueue", {
      queueName: `school-buddy-notice-queue-${environment}`,
      // visibilityTimeout ≥ processor Lambda timeout (180s) 를 만족해야 함
      visibilityTimeout: cdk.Duration.seconds(300),
      // 메시지 보존 4일 (명시적 설정)
      retentionPeriod: cdk.Duration.days(4),
      encryption: sqs.QueueEncryption.SQS_MANAGED,
      deadLetterQueue: { queue: noticeDLQ, maxReceiveCount: 3 },
    });

    const notificationDLQ = new sqs.Queue(this, "NotificationDLQ", {
      queueName: `school-buddy-notification-dlq-${environment}`,
      retentionPeriod: cdk.Duration.days(14),
      encryption: sqs.QueueEncryption.SQS_MANAGED,
    });

    const notificationQueue = new sqs.Queue(this, "NotificationQueue", {
      queueName: `school-buddy-notification-queue-${environment}`,
      visibilityTimeout: cdk.Duration.seconds(60),
      encryption: sqs.QueueEncryption.SQS_MANAGED,
      deadLetterQueue: { queue: notificationDLQ, maxReceiveCount: 3 },
    });

    // ──────────────────────────────────────────────────────
    // SNS Topic
    // ──────────────────────────────────────────────────────
    const noticeTopic = new sns.Topic(this, "NoticeTopic", {
      topicName: `school-buddy-notice-topic-${environment}`,
      displayName: "School Buddy — New Notice",
    });

    // ──────────────────────────────────────────────────────
    // 공통 Lambda 환경 변수
    // ──────────────────────────────────────────────────────
    const commonEnv: Record<string, string> = {
      ENVIRONMENT: environment,
      REGION: this.region,
      // DynamoDB Table Names
      USERS_TABLE: storage.usersTable.tableName,
      CHILDREN_TABLE: storage.childrenTable.tableName,
      SCHOOLS_TABLE: storage.schoolsTable.tableName,
      NOTICES_TABLE: storage.noticesTable.tableName,
      NOTIFICATIONS_TABLE: storage.notificationsTable.tableName,
      CHAT_HISTORY_TABLE: storage.chatHistoryTable.tableName,
      KB_DOCUMENTS_TABLE: storage.kbDocumentsTable.tableName,
      TRANSLATION_CACHE_TABLE: storage.translationCacheTable.tableName,
      // S3 Bucket Names
      DOCUMENTS_BUCKET: storage.documentsBucket.bucketName,
      KB_SOURCE_BUCKET: storage.kbSourceBucket.bucketName,
      // Messaging
      NOTICE_QUEUE_URL: noticeQueue.queueUrl,
      NOTIFICATION_QUEUE_URL: notificationQueue.queueUrl,
      NOTICE_TOPIC_ARN: noticeTopic.topicArn,
      // Secrets Manager 키 이름 (Lambda가 런타임에 fetch)
      APP_SECRETS_NAME: "school-buddy/app-secrets",
    };

    // ──────────────────────────────────────────────────────
    // Lambda Functions
    // ──────────────────────────────────────────────────────

    // Python Lambda 공통 설정
    const pythonLambdaDefaults = {
      runtime: lambda.Runtime.PYTHON_3_12,
      role: safeRole,
    } as const;

    // Node.js Lambda 공통 설정
    const nodeLambdaDefaults = {
      runtime: lambda.Runtime.NODEJS_20_X,
      role: safeRole,
    } as const;

    // school-crawler (Python) — EventBridge 스케줄 트리거
    // ⚠️ role: 기존 SafeRole 참조 (새 Role 생성 금지)
    // ⚠️ vpc 없음 (Lambda VPC 밖에서 실행)
    // ⚠️ AWS_REGION은 Lambda 예약 환경변수 — 자동 주입되므로 별도 설정 불필요
    this.crawlerFn = new lambda.Function(this, "SchoolCrawler", {
      functionName: `school-buddy-crawler-${environment}`,
      ...pythonLambdaDefaults,     // runtime: PYTHON_3_12, role: SafeRole
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../services/crawler")
      ),
      timeout: cdk.Duration.minutes(5),  // 5분
      memorySize: 512,
      description: "학교 홈페이지 크롤링 → notice-queue 발행",
      environment: {
        // 공통 테이블/버킷 환경변수
        ...commonEnv,
        // 크롤러 전용 환경변수 (handler.py, publisher.py와 이름 일치)
        SQS_QUEUE_URL: noticeQueue.queueUrl,
        SNS_ALARM_TOPIC_ARN: noticeTopic.topicArn,
      },
    });

    // notice-processor (Python) — SQS 트리거
    this.processorFn = new lambda.Function(this, "NoticeProcessor", {
      functionName: `school-buddy-processor-${environment}`,
      ...pythonLambdaDefaults,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../services/processor")
      ),
      timeout: cdk.Duration.seconds(180),
      memorySize: 256,
      description: "공지 중복 제거 → DynamoDB 저장 → Bedrock 번역 → SNS 발행",
      environment: {
        ...commonEnv,
        BEDROCK_MODEL_ID: "anthropic.claude-sonnet-4-20250514-v1:0",
        MAX_TOKENS_SUMMARY: "500",
        MAX_TOKENS_TRANSLATION: "800",
      },
    });
    this.processorFn.addEventSource(
      new lambdaEventSources.SqsEventSource(noticeQueue, {
        batchSize: 10,
        reportBatchItemFailures: true, // 부분 실패 처리
      })
    );

    // notification-sender (Python) — SNS 트리거
    this.notifierFn = new lambda.Function(this, "NotificationSender", {
      functionName: `school-buddy-notifier-${environment}`,
      ...pythonLambdaDefaults,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../services/notifier")
      ),
      timeout: cdk.Duration.seconds(60),
      memorySize: 128,
      description: "FCM / APNs 푸시 알림 발송",
      environment: {
        ...commonEnv,
        FCM_SECRETS_NAME: "school-buddy/fcm-service-account",
      },
    });
    noticeTopic.addSubscription(
      new snsSubscriptions.LambdaSubscription(this.notifierFn)
    );

    // document-analyzer (Python) — 직접 호출 또는 SQS
    this.analyzerFn = new lambda.Function(this, "DocumentAnalyzer", {
      functionName: `school-buddy-analyzer-${environment}`,
      ...pythonLambdaDefaults,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../services/analyzer")
      ),
      timeout: cdk.Duration.seconds(300),
      memorySize: 512,
      description: "이미지/PDF OCR → Bedrock 분류·임베딩 → Vector Store 인덱싱",
      environment: {
        ...commonEnv,
        BEDROCK_MODEL_ID: "anthropic.claude-sonnet-4-20250514-v1:0",
        MAX_TOKENS_SUMMARY: "500",
      },
    });

    // rag-query-handler (Python) — API Gateway 트리거
    this.ragFn = new lambda.Function(this, "RagQueryHandler", {
      functionName: `school-buddy-rag-${environment}`,
      ...pythonLambdaDefaults,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../services/rag")
      ),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      description: "질문 임베딩 → Vector Search → Bedrock 답변 생성",
      environment: {
        ...commonEnv,
        BEDROCK_MODEL_ID: "anthropic.claude-sonnet-4-20250514-v1:0",
        MAX_TOKENS_QA: "1000",
      },
    });

    // user-manager (Node.js) — API Gateway 트리거
    this.userFn = new lambda.Function(this, "UserManager", {
      functionName: `school-buddy-user-${environment}`,
      ...nodeLambdaDefaults,
      handler: "src/index.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../services/user")
      ),
      timeout: cdk.Duration.seconds(30),
      memorySize: 128,
      description: "사용자 및 자녀 정보 CRUD",
      environment: commonEnv,
    });

    // school-registry (Node.js) — API Gateway 트리거
    this.schoolFn = new lambda.Function(this, "SchoolRegistry", {
      functionName: `school-buddy-school-${environment}`,
      ...nodeLambdaDefaults,
      handler: "src/index.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../services/school")
      ),
      timeout: cdk.Duration.seconds(30),
      memorySize: 128,
      description: "학교 등록 및 크롤 설정 관리 CRUD",
      environment: commonEnv,
    });

    // ──────────────────────────────────────────────────────
    // EventBridge — Crawler 30분 스케줄
    // ──────────────────────────────────────────────────────
    const crawlerRule = new events.Rule(this, "CrawlerSchedule", {
      ruleName: `school-buddy-crawler-schedule-${environment}`,
      description: "school-crawler Lambda 30분 주기 트리거",
      schedule: events.Schedule.rate(cdk.Duration.minutes(30)),
    });
    crawlerRule.addTarget(new eventsTargets.LambdaFunction(this.crawlerFn));

    // ──────────────────────────────────────────────────────
    // API Gateway (HTTP API)
    // ──────────────────────────────────────────────────────
    this.api = new apigwv2.HttpApi(this, "HttpApi", {
      apiName: `school-buddy-api-${environment}`,
      description: "School Buddy REST API",
      corsPreflight: {
        allowHeaders: ["Authorization", "Content-Type"],
        allowMethods: [apigwv2.CorsHttpMethod.ANY],
        allowOrigins: ["*"],
        maxAge: cdk.Duration.days(1),
      },
    });

    // Routes
    const userIntegration = new apigwv2Integrations.HttpLambdaIntegration(
      "UserIntegration",
      this.userFn
    );
    const schoolIntegration = new apigwv2Integrations.HttpLambdaIntegration(
      "SchoolIntegration",
      this.schoolFn
    );
    const ragIntegration = new apigwv2Integrations.HttpLambdaIntegration(
      "RagIntegration",
      this.ragFn
    );
    const analyzerIntegration = new apigwv2Integrations.HttpLambdaIntegration(
      "AnalyzerIntegration",
      this.analyzerFn
    );

    // /users
    this.api.addRoutes({
      path: "/users",
      methods: [apigwv2.HttpMethod.POST],
      integration: userIntegration,
    });
    this.api.addRoutes({
      path: "/users/{userId}",
      methods: [apigwv2.HttpMethod.GET, apigwv2.HttpMethod.PUT, apigwv2.HttpMethod.DELETE],
      integration: userIntegration,
    });

    // /schools
    this.api.addRoutes({
      path: "/schools",
      methods: [apigwv2.HttpMethod.GET, apigwv2.HttpMethod.POST],
      integration: schoolIntegration,
    });
    this.api.addRoutes({
      path: "/schools/{schoolId}",
      methods: [apigwv2.HttpMethod.GET, apigwv2.HttpMethod.PUT],
      integration: schoolIntegration,
    });

    // /rag/query
    this.api.addRoutes({
      path: "/rag/query",
      methods: [apigwv2.HttpMethod.POST],
      integration: ragIntegration,
    });

    // /documents/analyze
    this.api.addRoutes({
      path: "/documents/analyze",
      methods: [apigwv2.HttpMethod.POST],
      integration: analyzerIntegration,
    });

    // ──────────────────────────────────────────────────────
    // CloudFormation Outputs
    // ──────────────────────────────────────────────────────
    new cdk.CfnOutput(this, "ApiEndpoint", {
      value: this.api.apiEndpoint,
      description: "HTTP API Endpoint URL",
      exportName: `school-buddy-api-endpoint-${environment}`,
    });
    new cdk.CfnOutput(this, "UserPoolId", {
      value: this.userPool.userPoolId,
      exportName: `school-buddy-user-pool-id-${environment}`,
    });
    new cdk.CfnOutput(this, "UserPoolClientId", {
      value: userPoolClient.userPoolClientId,
      exportName: `school-buddy-user-pool-client-id-${environment}`,
    });
    new cdk.CfnOutput(this, "NoticeQueueUrl", {
      value: noticeQueue.queueUrl,
      exportName: `school-buddy-notice-queue-url-${environment}`,
    });
    new cdk.CfnOutput(this, "NoticeTopicArn", {
      value: noticeTopic.topicArn,
      exportName: `school-buddy-notice-topic-arn-${environment}`,
    });
  }
}
