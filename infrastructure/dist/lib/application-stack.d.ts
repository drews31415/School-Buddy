import * as cdk from "aws-cdk-lib";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as apigwv2 from "aws-cdk-lib/aws-apigatewayv2";
import * as cognito from "aws-cdk-lib/aws-cognito";
import { Construct } from "constructs";
import { StorageStack } from "./storage-stack";
export interface ApplicationStackProps extends cdk.StackProps {
    environment: string;
    storage: StorageStack;
}
/**
 * ApplicationStack
 * Lambda 7개, HTTP API Gateway (Cognito JWT 인증), SQS, SNS, EventBridge, Cognito.
 *
 * ⚠️  리전: us-east-1 고정 (bin/app.ts env 설정과 일치)
 * ⚠️  모든 Lambda는 기존 SafeRole-hanyang-pj-1 사용 (새 IAM Role 생성 금지)
 */
export declare class ApplicationStack extends cdk.Stack {
    readonly api: apigwv2.HttpApi;
    readonly userPool: cognito.UserPool;
    readonly userPoolClient: cognito.UserPoolClient;
    readonly crawlerFn: lambda.Function;
    readonly processorFn: lambda.Function;
    readonly notifierFn: lambda.Function;
    readonly analyzerFn: lambda.Function;
    readonly ragFn: lambda.Function;
    readonly userFn: lambda.Function;
    readonly schoolFn: lambda.Function;
    readonly kbSyncFn: lambda.Function;
    readonly noticeQueue: sqs.Queue;
    readonly noticeDLQ: sqs.Queue;
    readonly knowledgeBaseId: string;
    constructor(scope: Construct, id: string, props: ApplicationStackProps);
}
//# sourceMappingURL=application-stack.d.ts.map