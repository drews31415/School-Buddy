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
export declare class StorageStack extends cdk.Stack {
    readonly usersTable: dynamodb.Table;
    readonly childrenTable: dynamodb.Table;
    readonly schoolsTable: dynamodb.Table;
    readonly noticesTable: dynamodb.Table;
    readonly notificationsTable: dynamodb.Table;
    readonly chatHistoryTable: dynamodb.Table;
    readonly kbDocumentsTable: dynamodb.Table;
    /** ElastiCache(Redis) 대체 캐시 테이블. cacheKey 형식: notice#{noticeId}#lang#{langCode} */
    readonly translationCacheTable: dynamodb.Table;
    readonly documentsBucket: s3.Bucket;
    readonly kbSourceBucket: s3.Bucket;
    constructor(scope: Construct, id: string, props: StorageStackProps);
}
//# sourceMappingURL=storage-stack.d.ts.map