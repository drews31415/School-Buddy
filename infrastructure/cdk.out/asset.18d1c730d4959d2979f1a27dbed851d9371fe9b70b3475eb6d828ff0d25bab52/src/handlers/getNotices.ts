import { APIGatewayProxyEventV2WithJWTAuthorizer, APIGatewayProxyResultV2 } from "aws-lambda";
import { query } from "@school-buddy/shared-utils";
import { ok, clientErr } from "../lib/response";

const NOTICES_TABLE = process.env["NOTICES_TABLE"]!;

/**
 * GET /notices?schoolId={id}&limit={n}&cursor={base64url}
 * 최신순 공지 목록 조회 (커서 기반 페이지네이션).
 */
export async function getNotices(
  event: APIGatewayProxyEventV2WithJWTAuthorizer
): Promise<APIGatewayProxyResultV2> {
  const qs = event.queryStringParameters;

  const schoolId = qs?.["schoolId"];
  if (!schoolId) {
    return clientErr("schoolId 파라미터가 필요합니다", "VALIDATION_ERROR", 400);
  }

  const limit = Math.min(parseInt(qs?.["limit"] ?? "20", 10), 50);

  const exclusiveStartKey = qs?.["cursor"]
    ? (JSON.parse(
        Buffer.from(qs["cursor"], "base64url").toString("utf-8")
      ) as Record<string, unknown>)
    : undefined;

  const { items, lastEvaluatedKey } = await query<Record<string, unknown>>(
    NOTICES_TABLE,
    "schoolId = :sid",
    { ":sid": schoolId },
    { limit, exclusiveStartKey, scanIndexForward: false }
  );

  const nextCursor = lastEvaluatedKey
    ? Buffer.from(JSON.stringify(lastEvaluatedKey)).toString("base64url")
    : undefined;

  return ok({ items, nextCursor });
}
