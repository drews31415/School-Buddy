import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";

export class SchoolBuddyStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // TODO: Lambda, DynamoDB, SQS, EventBridge, SNS 리소스 정의
  }
}
