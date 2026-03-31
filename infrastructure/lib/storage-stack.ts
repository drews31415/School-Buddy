import * as cdk from "aws-cdk-lib";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as s3 from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";

export interface StorageStackProps extends cdk.StackProps {
  environment: string;
}

/**
 * StorageStack
 * DynamoDB 테이블 8개 + S3 버킷 2개.
 * PRD 섹션 8.1 데이터 설계 기준.
 *
 * 공통 설정: PAY_PER_REQUEST | RETAIN | PointInTimeRecovery | AWS_MANAGED 암호화
 */
export class StorageStack extends cdk.Stack {
  // DynamoDB Tables
  public readonly usersTable: dynamodb.Table;
  public readonly childrenTable: dynamodb.Table;
  public readonly schoolsTable: dynamodb.Table;
  public readonly noticesTable: dynamodb.Table;
  public readonly notificationsTable: dynamodb.Table;
  public readonly chatHistoryTable: dynamodb.Table;
  /** ElastiCache(Redis) 대체 캐시 테이블. cacheKey 형식: notice#{noticeId}#lang#{langCode} */
  public readonly translationCacheTable: dynamodb.Table;

  // S3 Buckets
  public readonly documentsBucket: s3.Bucket;
  public readonly kbSourceBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props: StorageStackProps) {
    super(scope, id, props);

    const { environment } = props;

    // Tags 제거: hanyang-pj-1 계정은 TagResource 권한 없음

    // 공통 DynamoDB 설정
    const commonTableProps = {
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    } as const;

    // ──────────────────────────────────────────────────────
    // 1. Users — PK: userId
    // ──────────────────────────────────────────────────────
    this.usersTable = new dynamodb.Table(this, "UsersTable", {
      ...commonTableProps,
      tableName: `school-buddy-users-${environment}`,
      partitionKey: { name: "userId", type: dynamodb.AttributeType.STRING },
    });

    // ──────────────────────────────────────────────────────
    // 2. Children — PK: childId
    //    GSI1: userId-index  (내 자녀 목록 조회)
    //    GSI2: schoolId-index (학교 구독자 조회 — notification-sender 사용)
    // ──────────────────────────────────────────────────────
    this.childrenTable = new dynamodb.Table(this, "ChildrenTable", {
      ...commonTableProps,
      tableName: `school-buddy-children-${environment}`,
      partitionKey: { name: "childId", type: dynamodb.AttributeType.STRING },
    });
    this.childrenTable.addGlobalSecondaryIndex({
      indexName: "userId-index",
      partitionKey: { name: "userId", type: dynamodb.AttributeType.STRING },
    });
    this.childrenTable.addGlobalSecondaryIndex({
      indexName: "schoolId-index",
      partitionKey: { name: "schoolId", type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.KEYS_ONLY,  // userId만 필요
    });

    // ──────────────────────────────────────────────────────
    // 3. Schools — PK: schoolId
    // ──────────────────────────────────────────────────────
    this.schoolsTable = new dynamodb.Table(this, "SchoolsTable", {
      ...commonTableProps,
      tableName: `school-buddy-schools-${environment}`,
      partitionKey: { name: "schoolId", type: dynamodb.AttributeType.STRING },
    });

    // ──────────────────────────────────────────────────────
    // 4. Notices — PK: schoolId  SK: createdAt
    //    GSI: noticeId (단건 조회용)
    // ──────────────────────────────────────────────────────
    this.noticesTable = new dynamodb.Table(this, "NoticesTable", {
      ...commonTableProps,
      tableName: `school-buddy-notices-${environment}`,
      partitionKey: { name: "schoolId", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "createdAt", type: dynamodb.AttributeType.STRING },
    });
    this.noticesTable.addGlobalSecondaryIndex({
      indexName: "noticeId-index",
      partitionKey: { name: "noticeId", type: dynamodb.AttributeType.STRING },
    });

    // ──────────────────────────────────────────────────────
    // 5. Notifications — PK: userId  SK: createdAt
    //    TTL: expiresAt (180일)
    // ──────────────────────────────────────────────────────
    this.notificationsTable = new dynamodb.Table(this, "NotificationsTable", {
      ...commonTableProps,
      tableName: `school-buddy-notifications-${environment}`,
      partitionKey: { name: "userId", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "createdAt", type: dynamodb.AttributeType.STRING },
      timeToLiveAttribute: "expiresAt",
    });

    // ──────────────────────────────────────────────────────
    // 6. ChatHistory — PK: userId  SK: sessionId#createdAt
    //    TTL: expiresAt (90일)
    // ──────────────────────────────────────────────────────
    this.chatHistoryTable = new dynamodb.Table(this, "ChatHistoryTable", {
      ...commonTableProps,
      tableName: `school-buddy-chat-history-${environment}`,
      partitionKey: { name: "userId", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "sessionId#createdAt", type: dynamodb.AttributeType.STRING },
      timeToLiveAttribute: "expiresAt",
    });

    // ──────────────────────────────────────────────────────
    // 7. TranslationCache — PK: cacheKey
    //    ElastiCache(Redis) 대체. TTL: expiresAt (24시간)
    //    RemovalPolicy: DESTROY (캐시는 재생성 가능)
    // ──────────────────────────────────────────────────────
    this.translationCacheTable = new dynamodb.Table(this, "TranslationCacheTable", {
      ...commonTableProps,
      tableName: `school-buddy-translation-cache-${environment}`,
      partitionKey: { name: "cacheKey", type: dynamodb.AttributeType.STRING },
      timeToLiveAttribute: "expiresAt",
      removalPolicy: cdk.RemovalPolicy.DESTROY, // 캐시 테이블만 DESTROY 허용
    });

    // ──────────────────────────────────────────────────────
    // S3 Buckets (버킷명: hanyang-pj-1- 접두사 필수)
    // ──────────────────────────────────────────────────────

    // 사용자 업로드 문서 — uploads/ 경로 7일 후 자동 삭제 (개인정보 최소화)
    this.documentsBucket = new s3.Bucket(this, "DocumentsBucket", {
      bucketName: `hanyang-pj-1-documents-${environment}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          id: "expire-user-uploads",
          prefix: "uploads/",
          expiration: cdk.Duration.days(7),
        },
      ],
    });

    // Bedrock Knowledge Base 원본 교육 문서 (버전 관리 활성화)
    // ⚠️ eventBridgeEnabled 제거: hanyang-pj-1 계정은 iam:CreateRole 권한 없음
    //    kb-sync Lambda는 수동 호출 또는 AWS Console에서 트리거
    this.kbSourceBucket = new s3.Bucket(this, "KbSourceBucket", {
      bucketName: `hanyang-pj-1-kb-source-${environment}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      versioned: true,
    });

    // ──────────────────────────────────────────────────────
    // CloudFormation Outputs
    // ──────────────────────────────────────────────────────
    const outputs: Array<[string, string, string]> = [
      ["UsersTableName",        this.usersTable.tableName,           `school-buddy-users-table-${environment}`],
      ["ChildrenTableName",     this.childrenTable.tableName,        `school-buddy-children-table-${environment}`],
      ["SchoolsTableName",      this.schoolsTable.tableName,         `school-buddy-schools-table-${environment}`],
      ["NoticesTableName",      this.noticesTable.tableName,         `school-buddy-notices-table-${environment}`],
      ["NotificationsTableName",this.notificationsTable.tableName,   `school-buddy-notifications-table-${environment}`],
      ["ChatHistoryTableName",  this.chatHistoryTable.tableName,     `school-buddy-chat-history-table-${environment}`],
      ["TranslationCacheTableName", this.translationCacheTable.tableName, `school-buddy-translation-cache-table-${environment}`],
      ["DocumentsBucketName",   this.documentsBucket.bucketName,     `school-buddy-documents-bucket-${environment}`],
      ["KbSourceBucketName",    this.kbSourceBucket.bucketName,      `school-buddy-kb-source-bucket-${environment}`],
    ];

    for (const [id, value, exportName] of outputs) {
      new cdk.CfnOutput(this, id, { value, exportName });
    }
  }
}
