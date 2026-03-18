import { APIGatewayProxyEventV2WithJWTAuthorizer, APIGatewayProxyResultV2 } from "aws-lambda";
import { ScanCommand } from "@aws-sdk/lib-dynamodb";
import { docClient } from "@school-buddy/shared-utils";
import { ok, clientErr } from "../lib/response";

const SCHOOLS_TABLE = process.env["SCHOOLS_TABLE"]!;
const MAX_RESULTS   = 20;

/**
 * GET /schools/search?q={keyword}
 *
 * DynamoDB Scan + FilterExpression으로 학교명·주소 부분 검색.
 * Schools 테이블 규모가 크지 않으므로 Full-scan 허용 (추후 OpenSearch 도입 시 교체).
 */
export async function searchSchools(
  event: APIGatewayProxyEventV2WithJWTAuthorizer
): Promise<APIGatewayProxyResultV2> {
  const q = event.queryStringParameters?.["q"]?.trim();
  if (!q || q.length < 2) {
    return clientErr("검색어는 2자 이상 입력해주세요", "VALIDATION_ERROR", 400);
  }

  const result = await docClient.send(
    new ScanCommand({
      TableName: SCHOOLS_TABLE,
      FilterExpression: "contains(#n, :q) OR contains(#addr, :q)",
      ExpressionAttributeNames: {
        "#n":    "name",
        "#addr": "address",
      },
      ExpressionAttributeValues: { ":q": q },
      ProjectionExpression: "schoolId, #n, #addr, crawlStatus",
    })
  );

  const schools = (result.Items ?? []).slice(0, MAX_RESULTS);
  return ok(schools);
}
