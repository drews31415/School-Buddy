"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.ApplicationStack = void 0;
const path = __importStar(require("path"));
const cdk = __importStar(require("aws-cdk-lib"));
const lambda = __importStar(require("aws-cdk-lib/aws-lambda"));
const iam = __importStar(require("aws-cdk-lib/aws-iam"));
const sqs = __importStar(require("aws-cdk-lib/aws-sqs"));
const sns = __importStar(require("aws-cdk-lib/aws-sns"));
const snsSubscriptions = __importStar(require("aws-cdk-lib/aws-sns-subscriptions"));
const lambdaEventSources = __importStar(require("aws-cdk-lib/aws-lambda-event-sources"));
const events = __importStar(require("aws-cdk-lib/aws-events"));
const eventsTargets = __importStar(require("aws-cdk-lib/aws-events-targets"));
const apigwv2 = __importStar(require("aws-cdk-lib/aws-apigatewayv2"));
const apigwv2Integrations = __importStar(require("aws-cdk-lib/aws-apigatewayv2-integrations"));
const apigwv2Auth = __importStar(require("aws-cdk-lib/aws-apigatewayv2-authorizers"));
const cognito = __importStar(require("aws-cdk-lib/aws-cognito"));
const logs = __importStar(require("aws-cdk-lib/aws-logs"));
const ssm = __importStar(require("aws-cdk-lib/aws-ssm"));
/**
 * ApplicationStack
 * Lambda 7개, HTTP API Gateway (Cognito JWT 인증), SQS, SNS, EventBridge, Cognito.
 *
 * ⚠️  리전: us-east-1 고정 (bin/app.ts env 설정과 일치)
 * ⚠️  모든 Lambda는 기존 SafeRole-hanyang-pj-1 사용 (새 IAM Role 생성 금지)
 */
class ApplicationStack extends cdk.Stack {
    api;
    userPool;
    userPoolClient;
    // Lambda functions — MonitoringStack에서 참조 가능
    crawlerFn;
    processorFn;
    notifierFn;
    analyzerFn;
    ragFn;
    userFn;
    schoolFn;
    kbSyncFn;
    // SQS — MonitoringStack에서 메트릭 참조용
    noticeQueue;
    noticeDLQ;
    // Knowledge Base
    knowledgeBaseId;
    constructor(scope, id, props) {
        super(scope, id, props);
        const { environment, storage } = props;
        cdk.Tags.of(this).add("Project", "school-buddy");
        cdk.Tags.of(this).add("Environment", environment);
        // ──────────────────────────────────────────────────────
        // IAM — 기존 Role 참조 (새 Role 생성 금지)
        // ──────────────────────────────────────────────────────
        const safeRole = iam.Role.fromRoleName(this, "SafeRole", "SafeRole-hanyang-pj-1");
        // ──────────────────────────────────────────────────────
        // Cognito User Pool
        // ──────────────────────────────────────────────────────
        this.userPool = new cognito.UserPool(this, "UserPool", {
            userPoolName: `school-buddy-user-pool-${environment}`,
            selfSignUpEnabled: true,
            signInAliases: { email: true },
            autoVerify: { email: true }, // 이메일 인증 필수
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
            // 사용자 데이터 보존 — 운영 데이터이므로 RETAIN
            removalPolicy: cdk.RemovalPolicy.RETAIN,
        });
        // ── Cognito Domain (소셜 로그인 OAuth 리다이렉트에 필요) ──
        const userPoolDomain = this.userPool.addDomain("Domain", {
            cognitoDomain: {
                domainPrefix: `school-buddy-${environment}`,
            },
        });
        // ── Google 소셜 로그인 IdP ──────────────────────────────
        // Client ID / Secret은 Secrets Manager school-buddy/app-secrets 에서 참조
        const googleProvider = new cognito.UserPoolIdentityProviderGoogle(this, "GoogleProvider", {
            userPool: this.userPool,
            clientId: cdk.SecretValue.secretsManager("school-buddy/app-secrets", {
                jsonField: "googleClientId",
            }).unsafeUnwrap(),
            clientSecretValue: cdk.SecretValue.secretsManager("school-buddy/app-secrets", { jsonField: "googleClientSecret" }),
            scopes: ["email", "profile", "openid"],
            attributeMapping: {
                email: cognito.ProviderAttribute.GOOGLE_EMAIL,
                givenName: cognito.ProviderAttribute.GOOGLE_GIVEN_NAME,
                familyName: cognito.ProviderAttribute.GOOGLE_FAMILY_NAME,
            },
        });
        // ── Apple 소셜 로그인 IdP ───────────────────────────────
        // Team ID / Key ID / Private Key는 Secrets Manager에서 참조
        const appleProvider = new cognito.UserPoolIdentityProviderApple(this, "AppleProvider", {
            userPool: this.userPool,
            clientId: cdk.SecretValue.secretsManager("school-buddy/app-secrets", {
                jsonField: "appleClientId",
            }).unsafeUnwrap(),
            teamId: cdk.SecretValue.secretsManager("school-buddy/app-secrets", {
                jsonField: "appleTeamId",
            }).unsafeUnwrap(),
            keyId: cdk.SecretValue.secretsManager("school-buddy/app-secrets", {
                jsonField: "appleKeyId",
            }).unsafeUnwrap(),
            privateKeyValue: cdk.SecretValue.secretsManager("school-buddy/app-secrets", {
                jsonField: "applePrivateKey",
            }),
            scopes: ["email", "name"],
            attributeMapping: {
                email: cognito.ProviderAttribute.APPLE_EMAIL,
                givenName: cognito.ProviderAttribute.APPLE_FIRST_NAME,
                familyName: cognito.ProviderAttribute.APPLE_LAST_NAME,
            },
        });
        // ── 앱 클라이언트 (모바일 + 웹) ────────────────────────
        this.userPoolClient = this.userPool.addClient("MobileClient", {
            userPoolClientName: `school-buddy-mobile-${environment}`,
            authFlows: {
                userSrp: true, // 모바일 앱 SRP 인증
                userPassword: false, // 직접 비밀번호 전송 금지
            },
            oAuth: {
                flows: { authorizationCodeGrant: true },
                scopes: [
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.PROFILE,
                ],
                // 모바일 딥링크 + 웹 로컬 개발 콜백
                callbackUrls: [
                    "schoolbuddy://auth/callback",
                    "http://localhost:3000/auth/callback",
                ],
                logoutUrls: [
                    "schoolbuddy://auth/logout",
                    "http://localhost:3000/auth/logout",
                ],
            },
            supportedIdentityProviders: [
                cognito.UserPoolClientIdentityProvider.COGNITO,
                cognito.UserPoolClientIdentityProvider.GOOGLE,
                cognito.UserPoolClientIdentityProvider.APPLE,
            ],
            preventUserExistenceErrors: true,
            // 토큰 유효 기간
            accessTokenValidity: cdk.Duration.hours(1),
            idTokenValidity: cdk.Duration.hours(1),
            refreshTokenValidity: cdk.Duration.days(30),
        });
        // IdP → Client 의존성 명시 (CDK 배포 순서 보장)
        this.userPoolClient.node.addDependency(googleProvider);
        this.userPoolClient.node.addDependency(appleProvider);
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
            // visibilityTimeout ≥ processor Lambda timeout (180 s)
            visibilityTimeout: cdk.Duration.seconds(300),
            retentionPeriod: cdk.Duration.days(4),
            encryption: sqs.QueueEncryption.SQS_MANAGED,
            deadLetterQueue: { queue: noticeDLQ, maxReceiveCount: 3 },
        });
        // 공개 속성 할당 (MonitoringStack에서 메트릭 참조)
        this.noticeDLQ = noticeDLQ;
        this.noticeQueue = noticeQueue;
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
        const commonEnv = {
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
            // Cognito (Lambda에서 토큰 검증 시 참조)
            USER_POOL_ID: this.userPool.userPoolId,
            // Secrets Manager 키 이름
            APP_SECRETS_NAME: "school-buddy/app-secrets",
        };
        // ──────────────────────────────────────────────────────
        // Lambda Functions
        // ──────────────────────────────────────────────────────
        const pythonLambdaDefaults = {
            runtime: lambda.Runtime.PYTHON_3_12,
            role: safeRole,
            tracing: lambda.Tracing.ACTIVE, // X-Ray 활성화 (5% 샘플링 규칙은 MonitoringStack에서 정의)
        };
        const nodeLambdaDefaults = {
            runtime: lambda.Runtime.NODEJS_20_X,
            role: safeRole,
            tracing: lambda.Tracing.ACTIVE,
        };
        // school-crawler — EventBridge 30분 스케줄 트리거
        this.crawlerFn = new lambda.Function(this, "SchoolCrawler", {
            functionName: `school-buddy-crawler-${environment}`,
            ...pythonLambdaDefaults,
            handler: "handler.handler",
            code: lambda.Code.fromAsset(path.join(__dirname, "../../services/crawler")),
            timeout: cdk.Duration.minutes(5),
            memorySize: 512,
            description: "학교 홈페이지 크롤링 → notice-queue 발행",
            environment: {
                ...commonEnv,
                SQS_QUEUE_URL: noticeQueue.queueUrl,
                SNS_ALARM_TOPIC_ARN: noticeTopic.topicArn,
            },
        });
        // notice-processor — SQS 트리거
        this.processorFn = new lambda.Function(this, "NoticeProcessor", {
            functionName: `school-buddy-processor-${environment}`,
            ...pythonLambdaDefaults,
            handler: "handler.handler",
            code: lambda.Code.fromAsset(path.join(__dirname, "../../services/processor")),
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
        this.processorFn.addEventSource(new lambdaEventSources.SqsEventSource(noticeQueue, {
            batchSize: 10,
            reportBatchItemFailures: true,
        }));
        // notification-sender — SNS 트리거
        this.notifierFn = new lambda.Function(this, "NotificationSender", {
            functionName: `school-buddy-notifier-${environment}`,
            ...pythonLambdaDefaults,
            handler: "handler.handler",
            code: lambda.Code.fromAsset(path.join(__dirname, "../../services/notifier")),
            timeout: cdk.Duration.seconds(60),
            memorySize: 128,
            description: "FCM / APNs 푸시 알림 발송",
            environment: {
                ...commonEnv,
                FCM_SECRETS_NAME: "school-buddy/fcm-service-account",
            },
        });
        noticeTopic.addSubscription(new snsSubscriptions.LambdaSubscription(this.notifierFn));
        // document-analyzer — API Gateway / SQS 트리거
        this.analyzerFn = new lambda.Function(this, "DocumentAnalyzer", {
            functionName: `school-buddy-analyzer-${environment}`,
            ...pythonLambdaDefaults,
            handler: "handler.handler",
            code: lambda.Code.fromAsset(path.join(__dirname, "../../services/analyzer")),
            timeout: cdk.Duration.seconds(300),
            memorySize: 512,
            description: "이미지/PDF OCR → Bedrock 분류·임베딩 → Vector Store 인덱싱",
            environment: {
                ...commonEnv,
                BEDROCK_MODEL_ID: "anthropic.claude-sonnet-4-20250514-v1:0",
                MAX_TOKENS_SUMMARY: "500",
            },
        });
        // rag-query-handler — API Gateway 트리거 (/chat, /chat/history)
        this.ragFn = new lambda.Function(this, "RagQueryHandler", {
            functionName: `school-buddy-rag-${environment}`,
            ...pythonLambdaDefaults,
            handler: "handler.handler",
            code: lambda.Code.fromAsset(path.join(__dirname, "../../services/rag")),
            timeout: cdk.Duration.seconds(30),
            memorySize: 256,
            description: "질문 임베딩 → Vector Search → Bedrock 답변 생성",
            environment: {
                ...commonEnv,
                BEDROCK_MODEL_ID: "anthropic.claude-sonnet-4-5",
                MAX_TOKENS_QA: "1000",
                KB_ID: process.env.KB_ID ?? "",
            },
        });
        // user-manager — API Gateway 트리거 (/users/me, /children, /auth/register)
        this.userFn = new lambda.Function(this, "UserManager", {
            functionName: `school-buddy-user-${environment}`,
            ...nodeLambdaDefaults,
            handler: "src/index.handler",
            code: lambda.Code.fromAsset(path.join(__dirname, "../../services/user")),
            timeout: cdk.Duration.seconds(30),
            memorySize: 128,
            description: "사용자·자녀 정보 CRUD, 회원가입",
            environment: {
                ...commonEnv,
                USER_POOL_CLIENT_ID: this.userPoolClient.userPoolClientId,
            },
        });
        // school-registry — API Gateway 트리거 (/schools/search, /schools/subscribe, /notices)
        this.schoolFn = new lambda.Function(this, "SchoolRegistry", {
            functionName: `school-buddy-school-${environment}`,
            ...nodeLambdaDefaults,
            handler: "src/index.handler",
            code: lambda.Code.fromAsset(path.join(__dirname, "../../services/school")),
            timeout: cdk.Duration.seconds(30),
            memorySize: 128,
            description: "학교 검색·구독, 공지 목록 조회",
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
        // API Gateway HTTP API — Cognito JWT Authorizer 적용
        // ──────────────────────────────────────────────────────
        // 액세스 로그 그룹 (CloudWatch)
        const accessLogGroup = new logs.LogGroup(this, "ApiAccessLogs", {
            logGroupName: `/school-buddy/api-access/${environment}`,
            retention: logs.RetentionDays.ONE_MONTH,
            removalPolicy: cdk.RemovalPolicy.DESTROY,
        });
        // HTTP API
        this.api = new apigwv2.HttpApi(this, "HttpApi", {
            apiName: `school-buddy-api-${environment}`,
            description: "School Buddy — Mobile / Web REST API",
            corsPreflight: {
                // 모바일 앱(딥링크)은 Origin 헤더 미전송 → allowOrigins: ['*'] 허용
                // 웹 환경으로 전환 시 실제 도메인으로 제한 권장
                allowHeaders: ["Authorization", "Content-Type", "X-Requested-With"],
                allowMethods: [apigwv2.CorsHttpMethod.ANY],
                allowOrigins: ["*"],
                maxAge: cdk.Duration.hours(24),
            },
        });
        // 기본 스테이지($default)에 액세스 로깅 설정 (L1 escape hatch)
        const cfnDefaultStage = this.api.defaultStage.node
            .defaultChild;
        cfnDefaultStage.accessLogSettings = {
            destinationArn: accessLogGroup.logGroupArn,
            format: JSON.stringify({
                requestId: "$context.requestId",
                ip: "$context.identity.sourceIp",
                method: "$context.httpMethod",
                path: "$context.path",
                routeKey: "$context.routeKey",
                status: "$context.status",
                responseTime: "$context.responseLatency",
                userAgent: "$context.identity.userAgent",
                integrationError: "$context.integrationErrorMessage",
            }),
        };
        // ── JWT Authorizer (Cognito) ────────────────────────────
        const jwtAuthorizer = new apigwv2Auth.HttpJwtAuthorizer("CognitoAuthorizer", 
        // Cognito JWKS 발급자 URL — us-east-1 고정
        `https://cognito-idp.us-east-1.amazonaws.com/${this.userPool.userPoolId}`, {
            jwtAudience: [this.userPoolClient.userPoolClientId],
        });
        // ── Lambda Integrations ─────────────────────────────────
        const userInt = new apigwv2Integrations.HttpLambdaIntegration("UserInt", this.userFn);
        const schoolInt = new apigwv2Integrations.HttpLambdaIntegration("SchoolInt", this.schoolFn);
        const ragInt = new apigwv2Integrations.HttpLambdaIntegration("RagInt", this.ragFn);
        const analyzerInt = new apigwv2Integrations.HttpLambdaIntegration("AnalyzerInt", this.analyzerFn);
        // ── 공개 라우트 (인증 불필요) ────────────────────────────
        // POST /auth/register — 회원가입 (Cognito 토큰 없이 접근)
        this.api.addRoutes({
            path: "/auth/register",
            methods: [apigwv2.HttpMethod.POST],
            integration: userInt,
        });
        // ── 보호 라우트 (Cognito JWT 필수) ──────────────────────
        const protectedRoutes = [
            // 사용자 / 자녀
            { path: "/users/me", methods: [apigwv2.HttpMethod.GET, apigwv2.HttpMethod.PUT], integration: userInt },
            { path: "/children", methods: [apigwv2.HttpMethod.POST, apigwv2.HttpMethod.GET], integration: userInt },
            // 학교
            { path: "/schools/search", methods: [apigwv2.HttpMethod.GET], integration: schoolInt },
            { path: "/schools/subscribe", methods: [apigwv2.HttpMethod.POST], integration: schoolInt },
            // 공지
            { path: "/notices", methods: [apigwv2.HttpMethod.GET], integration: schoolInt },
            { path: "/notices/{noticeId}", methods: [apigwv2.HttpMethod.GET], integration: schoolInt },
            // 문서 분석
            { path: "/documents/analyze", methods: [apigwv2.HttpMethod.POST], integration: analyzerInt },
            // 채팅 (RAG Q&A)
            { path: "/chat", methods: [apigwv2.HttpMethod.POST], integration: ragInt },
            { path: "/chat/history", methods: [apigwv2.HttpMethod.GET], integration: ragInt },
        ];
        for (const route of protectedRoutes) {
            this.api.addRoutes({
                ...route,
                authorizer: jwtAuthorizer,
            });
        }
        // ──────────────────────────────────────────────────────
        // Knowledge Base — SSM Parameter Store에서 KB ID 조회
        // (담당자가 외부에서 S3 Vectors KB를 직접 생성 후 SSM에 등록)
        //
        // ⚠️ 배포 전 SSM에 다음 값을 등록해야 함:
        //   aws ssm put-parameter \
        //     --name /school-buddy/{env}/kb-id \
        //     --value <BEDROCK_KB_ID> --type String --region us-east-1
        //   aws ssm put-parameter \
        //     --name /school-buddy/{env}/kb-data-source-id \
        //     --value <DATA_SOURCE_ID> --type String --region us-east-1
        // ──────────────────────────────────────────────────────
        // CDK CloudFormation 동적 참조 — deploy 시점에 SSM에서 값을 읽음
        const kbId = ssm.StringParameter.valueForStringParameter(this, `/school-buddy/${environment}/kb-id`);
        const kbDataSourceId = ssm.StringParameter.valueForStringParameter(this, `/school-buddy/${environment}/kb-data-source-id`);
        // kb-sync Lambda (S3 업로드 → Ingestion Job 트리거)
        this.kbSyncFn = new lambda.Function(this, "KbSync", {
            functionName: `school-buddy-kb-sync-${environment}`,
            ...pythonLambdaDefaults,
            handler: "handler.handler",
            code: lambda.Code.fromAsset(path.join(__dirname, "../../services/kb-sync")),
            timeout: cdk.Duration.minutes(2),
            memorySize: 128,
            description: "S3 업로드 이벤트 → Bedrock Knowledge Base StartIngestionJob",
            environment: {
                KNOWLEDGE_BASE_ID: kbId,
                DATA_SOURCE_ID: kbDataSourceId,
                REGION: "us-east-1",
            },
        });
        // S3 ObjectCreated → EventBridge → kb-sync Lambda
        const kbSyncRule = new events.Rule(this, "KbSyncRule", {
            ruleName: `school-buddy-kb-sync-${environment}`,
            description: "S3 kb-source 업로드 이벤트 → Knowledge Base 동기화",
            eventPattern: {
                source: ["aws.s3"],
                detailType: ["Object Created"],
                detail: {
                    bucket: { name: [storage.kbSourceBucket.bucketName] },
                },
            },
        });
        kbSyncRule.addTarget(new eventsTargets.LambdaFunction(this.kbSyncFn));
        // SSM 파라미터 이름을 공개 속성으로 노출
        this.knowledgeBaseId = `/school-buddy/${environment}/kb-id`;
        // ──────────────────────────────────────────────────────
        // CloudFormation Outputs
        // ──────────────────────────────────────────────────────
        new cdk.CfnOutput(this, "ApiEndpoint", {
            value: this.api.apiEndpoint,
            description: "HTTP API Base URL (모바일 앱 REACT_APP_API_BASE_URL)",
            exportName: `school-buddy-api-endpoint-${environment}`,
        });
        new cdk.CfnOutput(this, "UserPoolId", {
            value: this.userPool.userPoolId,
            exportName: `school-buddy-user-pool-id-${environment}`,
        });
        new cdk.CfnOutput(this, "UserPoolClientId", {
            value: this.userPoolClient.userPoolClientId,
            exportName: `school-buddy-user-pool-client-id-${environment}`,
        });
        new cdk.CfnOutput(this, "CognitoDomain", {
            value: `https://${userPoolDomain.domainName}.auth.us-east-1.amazoncognito.com`,
            description: "Cognito Hosted UI 기본 도메인 (소셜 로그인 리다이렉트)",
            exportName: `school-buddy-cognito-domain-${environment}`,
        });
        new cdk.CfnOutput(this, "NoticeQueueUrl", {
            value: noticeQueue.queueUrl,
            exportName: `school-buddy-notice-queue-url-${environment}`,
        });
        new cdk.CfnOutput(this, "NoticeTopicArn", {
            value: noticeTopic.topicArn,
            exportName: `school-buddy-notice-topic-arn-${environment}`,
        });
        new cdk.CfnOutput(this, "KbSsmParamName", {
            value: `/school-buddy/${environment}/kb-id`,
            description: "SSM 파라미터 이름 — 담당자가 KB ID를 이 경로에 등록해야 함",
            exportName: `school-buddy-kb-ssm-param-${environment}`,
        });
    }
}
exports.ApplicationStack = ApplicationStack;
//# sourceMappingURL=application-stack.js.map