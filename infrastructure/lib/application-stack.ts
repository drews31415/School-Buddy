import * as path from "path";
import * as cdk from "aws-cdk-lib";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as iam from "aws-cdk-lib/aws-iam";
import * as events from "aws-cdk-lib/aws-events";
import * as eventsTargets from "aws-cdk-lib/aws-events-targets";
import * as apigwv2 from "aws-cdk-lib/aws-apigatewayv2";
import * as apigwv2Integrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as logs from "aws-cdk-lib/aws-logs";
import { Construct } from "constructs";
import { StorageStack } from "./storage-stack";

export interface ApplicationStackProps extends cdk.StackProps {
  environment: string;
  storage: StorageStack;
}

/**
 * ApplicationStack
 * Lambda 6개, HTTP API Gateway (인증 없음 — 기능 집중 모드), EventBridge.
 * ℹ️  SQS 제거: ControlOnlyOwnResources 정책이 SQS 전체 explicit deny
 *
 * ⚠️  리전: ap-northeast-3 (오사카) 고정 (bin/app.ts env 설정과 일치)
 * ⚠️  모든 Lambda는 기존 SafeRole-hanyang-pj-1 사용 (새 IAM Role 생성 금지)
 * ℹ️  Cognito/SNS 제거: hanyang-pj-1 계정 권한 제한으로 인증 없이 운영
 */
export class ApplicationStack extends cdk.Stack {
  public readonly api: apigwv2.HttpApi;

  // Lambda functions — MonitoringStack에서 참조 가능
  public readonly crawlerFn:   lambda.Function;
  public readonly processorFn: lambda.Function;
  public readonly analyzerFn:  lambda.Function;
  public readonly ragFn:       lambda.Function;
  public readonly userFn:      lambda.Function;
  public readonly schoolFn:    lambda.Function;
  public readonly kbSyncFn:    lambda.Function;

  // Knowledge Base
  public readonly knowledgeBaseId: string;

  constructor(scope: Construct, id: string, props: ApplicationStackProps) {
    super(scope, id, props);

    const { environment, storage } = props;

    // Tags 제거: hanyang-pj-1 계정은 TagResource 권한 없음

    // ──────────────────────────────────────────────────────
    // IAM — 기존 Role 참조 (새 Role 생성 금지)
    // ──────────────────────────────────────────────────────
    const safeRole = iam.Role.fromRoleName(this, "SafeRole", "SafeRole-hanyang-pj-1");

    // ──────────────────────────────────────────────────────
    // 공통 Lambda 환경 변수
    // ──────────────────────────────────────────────────────
    const commonEnv: Record<string, string> = {
      ENVIRONMENT: environment,
      REGION:      this.region,
      // DynamoDB Table Names
      USERS_TABLE:         storage.usersTable.tableName,
      CHILDREN_TABLE:      storage.childrenTable.tableName,
      SCHOOLS_TABLE:       storage.schoolsTable.tableName,
      NOTICES_TABLE:       storage.noticesTable.tableName,
      NOTIFICATIONS_TABLE: storage.notificationsTable.tableName,
      CHAT_HISTORY_TABLE:  storage.chatHistoryTable.tableName,
      // TRANSLATION_CACHE_TABLE: storage.translationCacheTable.tableName, // TODO: import 완료 후 복원
      // S3 Bucket Names
      DOCUMENTS_BUCKET: storage.documentsBucket.bucketName,
      KB_SOURCE_BUCKET: storage.kbSourceBucket.bucketName,
    };

    // ──────────────────────────────────────────────────────
    // Lambda Functions
    // ──────────────────────────────────────────────────────
    const pythonLambdaDefaults = {
      runtime: lambda.Runtime.PYTHON_3_12,
      role:    safeRole,
      tracing: lambda.Tracing.ACTIVE,
    } as const;

    const nodeLambdaDefaults = {
      runtime: lambda.Runtime.NODEJS_20_X,
      role:    safeRole,
      tracing: lambda.Tracing.ACTIVE,
    } as const;

    // school-crawler — EventBridge 30분 스케줄 트리거
    // 환경변수:
    //   [commonEnv]
    // ℹ️  SQS 제거: 크롤러가 직접 DynamoDB에 저장 (SQS 권한 없음)
    this.crawlerFn = new lambda.Function(this, "SchoolCrawler", {
      functionName: `school-buddy-crawler-${environment}`,
      ...pythonLambdaDefaults,
      handler:    "handler.handler",
      code:       lambda.Code.fromAsset(path.join(__dirname, "../../services/crawler")),
      timeout:    cdk.Duration.minutes(5),
      memorySize: 512,
      description: "학교 홈페이지 크롤링 → DynamoDB 직접 저장",
      environment: commonEnv,
    });

    // notice-processor — SQS 트리거
    // 환경변수:
    //   [commonEnv]
    //   BEDROCK_MODEL_ID       Bedrock 모델 ID (번역·요약)
    //   MAX_TOKENS_SUMMARY     요약 최대 토큰 (500)
    //   MAX_TOKENS_TRANSLATION 번역 최대 토큰 (800)
    this.processorFn = new lambda.Function(this, "NoticeProcessor", {
      functionName: `school-buddy-processor-${environment}`,
      ...pythonLambdaDefaults,
      handler:    "handler.handler",
      code:       lambda.Code.fromAsset(path.join(__dirname, "../../services/processor")),
      timeout:    cdk.Duration.seconds(180),
      memorySize: 256,
      description: "공지 중복 제거 → DynamoDB 저장 → Bedrock 번역",
      environment: {
        ...commonEnv,
        BEDROCK_MODEL_ID:      "anthropic.claude-sonnet-4-20250514-v1:0",
        MAX_TOKENS_SUMMARY:     "500",
        MAX_TOKENS_TRANSLATION: "800",
      },
    });
    // ℹ️  processorFn SQS 트리거 제거: SQS 권한 없음. 수동 호출 또는 별도 트리거 필요

    // document-analyzer — API Gateway 트리거 (/documents/analyze)
    // 환경변수:
    //   [commonEnv]
    //   BEDROCK_MODEL_ID   Bedrock 모델 ID (OCR·분류)
    //   MAX_TOKENS_SUMMARY 분석 요약 최대 토큰 (500)
    this.analyzerFn = new lambda.Function(this, "DocumentAnalyzer", {
      functionName: `school-buddy-analyzer-${environment}`,
      ...pythonLambdaDefaults,
      handler:    "handler.handler",
      code:       lambda.Code.fromAsset(path.join(__dirname, "../../services/analyzer")),
      timeout:    cdk.Duration.seconds(300),
      memorySize: 512,
      description: "이미지/PDF OCR → Bedrock 분류·임베딩",
      environment: {
        ...commonEnv,
        BEDROCK_MODEL_ID:   "anthropic.claude-sonnet-4-20250514-v1:0",
        MAX_TOKENS_SUMMARY: "500",
      },
    });

    // rag-query-handler — API Gateway 트리거 (/chat, /chat/history)
    // 환경변수:
    //   [commonEnv]
    //   KB_ID            Bedrock Knowledge Base ID (export KB_ID=<값> 후 배포)
    //   BEDROCK_MODEL_ID Bedrock 모델 ID (Q&A 답변 생성)
    //   MAX_TOKENS_QA    Q&A 최대 토큰 (1000)
    this.ragFn = new lambda.Function(this, "RagQueryHandler", {
      functionName: `school-buddy-rag-${environment}`,
      ...pythonLambdaDefaults,
      handler:    "handler.handler",
      code:       lambda.Code.fromAsset(path.join(__dirname, "../../services/rag")),
      timeout:    cdk.Duration.seconds(30),
      memorySize: 256,
      description: "질문 임베딩 → Vector Search → Bedrock 답변 생성",
      environment: {
        ...commonEnv,
        KB_ID:            process.env.KB_ID ?? "",
        BEDROCK_MODEL_ID: "anthropic.claude-sonnet-4-20250514-v1:0",
        MAX_TOKENS_QA:    "1000",
      },
    });

    // user-manager — API Gateway 트리거 (/users/me, /children)
    // 환경변수:
    //   [commonEnv]
    this.userFn = new lambda.Function(this, "UserManager", {
      functionName: `school-buddy-user-${environment}`,
      ...nodeLambdaDefaults,
      handler:    "src/index.handler",
      code:       lambda.Code.fromAsset(path.join(__dirname, "../../services/user")),
      timeout:    cdk.Duration.seconds(30),
      memorySize: 128,
      description: "사용자·자녀 정보 CRUD",
      environment: commonEnv,
    });

    // school-registry — API Gateway 트리거 (/schools/search, /notices)
    // 환경변수:
    //   [commonEnv]
    this.schoolFn = new lambda.Function(this, "SchoolRegistry", {
      functionName: `school-buddy-school-${environment}`,
      ...nodeLambdaDefaults,
      handler:    "src/index.handler",
      code:       lambda.Code.fromAsset(path.join(__dirname, "../../services/school")),
      timeout:    cdk.Duration.seconds(30),
      memorySize: 128,
      description: "학교 검색·구독, 공지 목록 조회",
      environment: commonEnv,
    });

    // ──────────────────────────────────────────────────────
    // EventBridge — Crawler 30분 스케줄
    // ──────────────────────────────────────────────────────
    const crawlerRule = new events.Rule(this, "CrawlerSchedule", {
      ruleName:    `school-buddy-crawler-schedule-${environment}`,
      description: "school-crawler Lambda 30분 주기 트리거",
      schedule:    events.Schedule.rate(cdk.Duration.minutes(30)),
    });
    crawlerRule.addTarget(new eventsTargets.LambdaFunction(this.crawlerFn));

    // ──────────────────────────────────────────────────────
    // Knowledge Base (S3 Vectors)
    // ⚠️ 배포 전: export KB_ID=<값> && export KB_DATA_SOURCE_ID=<값>
    // ──────────────────────────────────────────────────────
    // kb-sync Lambda (수동 호출)
    // 환경변수:
    //   KNOWLEDGE_BASE_ID  Bedrock KB ID
    //   DATA_SOURCE_ID     KB Data Source ID
    //   REGION             AWS 리전
    this.kbSyncFn = new lambda.Function(this, "KbSync", {
      functionName: `school-buddy-kb-sync-${environment}`,
      ...pythonLambdaDefaults,
      handler:     "handler.handler",
      code:        lambda.Code.fromAsset(path.join(__dirname, "../../services/kb-sync")),
      timeout:     cdk.Duration.minutes(2),
      memorySize:  128,
      description: "S3 업로드 → Bedrock Knowledge Base StartIngestionJob (수동 호출)",
      environment: {
        KNOWLEDGE_BASE_ID: process.env.KB_ID ?? "",
        DATA_SOURCE_ID:    process.env.KB_DATA_SOURCE_ID ?? "",
        REGION:            this.region,
      },
    });

    this.knowledgeBaseId = process.env.KB_ID ?? "";

    // ──────────────────────────────────────────────────────
    // API Gateway HTTP API — 인증 없음 (기능 집중 모드)
    // ──────────────────────────────────────────────────────
    const accessLogGroup = new logs.LogGroup(this, "ApiAccessLogs", {
      logGroupName:  `/school-buddy/api-access/${environment}`,
      retention:     logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    this.api = new apigwv2.HttpApi(this, "HttpApi", {
      apiName:     `school-buddy-api-${environment}`,
      description: "School Buddy — Mobile / Web REST API (No Auth)",
      corsPreflight: {
        allowHeaders: ["Content-Type", "X-Requested-With"],
        allowMethods: [apigwv2.CorsHttpMethod.ANY],
        allowOrigins: ["*"],
        maxAge:       cdk.Duration.hours(24),
      },
    });

    const cfnDefaultStage = this.api.defaultStage!.node
      .defaultChild as apigwv2.CfnStage;
    cfnDefaultStage.accessLogSettings = {
      destinationArn: accessLogGroup.logGroupArn,
      format: JSON.stringify({
        requestId:        "$context.requestId",
        ip:               "$context.identity.sourceIp",
        method:           "$context.httpMethod",
        path:             "$context.path",
        status:           "$context.status",
        responseTime:     "$context.responseLatency",
        integrationError: "$context.integrationErrorMessage",
      }),
    };

    // Lambda Integrations
    const userInt     = new apigwv2Integrations.HttpLambdaIntegration("UserInt",     this.userFn);
    const schoolInt   = new apigwv2Integrations.HttpLambdaIntegration("SchoolInt",   this.schoolFn);
    const ragInt      = new apigwv2Integrations.HttpLambdaIntegration("RagInt",      this.ragFn);
    const analyzerInt = new apigwv2Integrations.HttpLambdaIntegration("AnalyzerInt", this.analyzerFn);

    // 모든 라우트 공개 (인증 없음)
    const routes: Array<{
      path: string;
      methods: apigwv2.HttpMethod[];
      integration: apigwv2Integrations.HttpLambdaIntegration;
    }> = [
      { path: "/users/me",           methods: [apigwv2.HttpMethod.GET, apigwv2.HttpMethod.PUT], integration: userInt },
      { path: "/children",           methods: [apigwv2.HttpMethod.POST, apigwv2.HttpMethod.GET], integration: userInt },
      { path: "/schools/search",     methods: [apigwv2.HttpMethod.GET],  integration: schoolInt },
      { path: "/schools/subscribe",  methods: [apigwv2.HttpMethod.POST], integration: schoolInt },
      { path: "/notices",            methods: [apigwv2.HttpMethod.GET],  integration: schoolInt },
      { path: "/notices/{noticeId}", methods: [apigwv2.HttpMethod.GET],  integration: schoolInt },
      { path: "/documents/analyze",  methods: [apigwv2.HttpMethod.POST], integration: analyzerInt },
      { path: "/chat",               methods: [apigwv2.HttpMethod.POST], integration: ragInt },
      { path: "/chat/history",       methods: [apigwv2.HttpMethod.GET],  integration: ragInt },
    ];

    for (const route of routes) {
      this.api.addRoutes(route);
    }

    // ──────────────────────────────────────────────────────
    // CloudFormation Outputs
    // ──────────────────────────────────────────────────────
    new cdk.CfnOutput(this, "ApiEndpoint", {
      value:       this.api.apiEndpoint,
      description: "HTTP API Base URL",
      exportName:  `school-buddy-api-endpoint-${environment}`,
    });
    new cdk.CfnOutput(this, "KbIdNote", {
      value:       process.env.KB_ID ?? "(not set)",
      description: "배포 시 주입된 Bedrock Knowledge Base ID",
      exportName:  `school-buddy-kb-id-${environment}`,
    });
  }
}
