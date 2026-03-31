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

const ACCOUNT_ID = "730335373015";
const SAFE_ROLE_ARN = `arn:aws:iam::${ACCOUNT_ID}:role/SafeRole-hanyang-pj-1`;

// StorageStack/MonitoringStack: bootstrap 없이 CLI 크레덴셜로 배포 (이미 배포된 리소스)
const cliSynthesizer = new cdk.CliCredentialsStackSynthesizer({
  fileAssetsBucketName: "hanyang-pj-1-cdk-staging",
  bucketPrefix:         "cdk-assets/",
});

// ApplicationStack: CloudFormation 실행 역할을 SafeRole로 지정
// → CFN 서비스가 SafeRole 권한으로 Lambda 등 리소스 생성 (ControlOnlyOwnResources 우회)
// generateBootstrapVersionRule: false → SSM bootstrap 파라미터 체크 생략
const appSynthesizer = new cdk.DefaultStackSynthesizer({
  fileAssetsBucketName:         "hanyang-pj-1-cdk-staging",
  bucketPrefix:                 "cdk-assets/",
  cloudFormationExecutionRole:  SAFE_ROLE_ARN,
  deployRoleArn:                SAFE_ROLE_ARN,
  fileAssetPublishingRoleArn:   SAFE_ROLE_ARN,
  generateBootstrapVersionRule: false,
});

// StorageStack → ApplicationStack → MonitoringStack 순서로 배포
const storageStack = new StorageStack(app, "SchoolBuddyStorage", {
  env,
  environment,
  synthesizer: cliSynthesizer,
  stackName: `school-buddy-storage-${environment}`,
  description: "School Buddy — DynamoDB Tables & S3 Buckets",
});

const applicationStack = new ApplicationStack(app, "SchoolBuddyApplication", {
  env,
  environment,
  synthesizer: appSynthesizer,
  storage: storageStack,
  stackName: `school-buddy-app-${environment}`,
  description: "School Buddy — Lambda Functions, API Gateway, EventBridge",
});
applicationStack.addDependency(storageStack);

const monitoringStack = new MonitoringStack(app, "SchoolBuddyMonitoring", {
  env,
  environment,
  synthesizer: cliSynthesizer,
  application: applicationStack,
  storage:     storageStack,
  stackName: `school-buddy-monitoring-${environment}`,
  description: "School Buddy — CloudWatch Dashboards & Alarms",
});
monitoringStack.addDependency(applicationStack);
