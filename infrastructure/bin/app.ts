#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { StorageStack } from "../lib/storage-stack";
import { ApplicationStack } from "../lib/application-stack";
import { MonitoringStack } from "../lib/monitoring-stack";

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: "us-east-1", // 한양 프로젝트 제약: us-east-1 고정
};

const environment = app.node.tryGetContext("environment") ?? "dev";

// StorageStack → ApplicationStack → MonitoringStack 순서로 배포
const storageStack = new StorageStack(app, "SchoolBuddyStorage", {
  env,
  environment,
  stackName: `school-buddy-storage-${environment}`,
  description: "School Buddy — DynamoDB Tables & S3 Buckets",
});

const applicationStack = new ApplicationStack(app, "SchoolBuddyApplication", {
  env,
  environment,
  storage: storageStack,
  stackName: `school-buddy-app-${environment}`,
  description: "School Buddy — Lambda Functions, API Gateway, SQS, SNS, Cognito",
});
applicationStack.addDependency(storageStack);

const monitoringStack = new MonitoringStack(app, "SchoolBuddyMonitoring", {
  env,
  environment,
  application: applicationStack,
  storage:     storageStack,
  stackName: `school-buddy-monitoring-${environment}`,
  description: "School Buddy — CloudWatch Dashboards & Alarms",
});
monitoringStack.addDependency(applicationStack);
