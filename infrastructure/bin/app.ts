#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { StorageStack } from "../lib/storage-stack";
import { ApplicationStack } from "../lib/application-stack";
import { MonitoringStack } from "../lib/monitoring-stack";

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: "ap-northeast-3", // 한양 프로젝트 제약: ap-northeast-3 (오사카) 고정
};

const environment = app.node.tryGetContext("environment") ?? "dev";

// CloudFormation 실행 역할을 SafeRole-hanyang-pj-1로 지정
// → CFN이 Lambda/ApiGW 등 리소스 API를 SafeRole 권한으로 호출 (ControlOnlyOwnResources 우회)
// generateBootstrapVersionRule: false → SSM bootstrap 파라미터 체크 생략
const ACCOUNT_ID = "730335373015";
const SAFE_ROLE_ARN = `arn:aws:iam::${ACCOUNT_ID}:role/SafeRole-hanyang-pj-1`;

const synthesizer = new cdk.DefaultStackSynthesizer({
  fileAssetsBucketName:       "hanyang-pj-1-cdk-staging",
  bucketPrefix:               "cdk-assets/",
  cloudFormationExecutionRole: SAFE_ROLE_ARN,
  deployRoleArn:              SAFE_ROLE_ARN,
  fileAssetPublishingRoleArn: SAFE_ROLE_ARN,
  generateBootstrapVersionRule: false,
});

// StorageStack → ApplicationStack → MonitoringStack 순서로 배포
const storageStack = new StorageStack(app, "SchoolBuddyStorage", {
  env,
  environment,
  synthesizer,
  stackName: `school-buddy-storage-${environment}`,
  description: "School Buddy — DynamoDB Tables & S3 Buckets",
});

const applicationStack = new ApplicationStack(app, "SchoolBuddyApplication", {
  env,
  environment,
  synthesizer,
  storage: storageStack,
  stackName: `school-buddy-app-${environment}`,
  description: "School Buddy — Lambda Functions, API Gateway, SQS, SNS, Cognito",
});
applicationStack.addDependency(storageStack);

const monitoringStack = new MonitoringStack(app, "SchoolBuddyMonitoring", {
  env,
  environment,
  synthesizer,
  application: applicationStack,
  storage:     storageStack,
  stackName: `school-buddy-monitoring-${environment}`,
  description: "School Buddy — CloudWatch Dashboards & Alarms",
});
monitoringStack.addDependency(applicationStack);
