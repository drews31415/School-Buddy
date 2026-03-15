import { APIGatewayProxyEventV2WithJWTAuthorizer, APIGatewayProxyResultV2 } from "aws-lambda";
import { query } from "@school-buddy/shared-utils";
import { ok, clientErr } from "../lib/response";

const NOTICES_TABLE = process.env["NOTICES_TABLE"]!;

/**
 * GET /notices/{noticeId}
 * noticeId-index GSI를 통해 공지 상세 조회.
 */
export async function getNotice(
  event: APIGatewayProxyEventV2WithJWTAuthorizer
): Promise<APIGatewayProxyResultV2> {
  const noticeId = event.pathParameters?.["noticeId"];
  if (!noticeId) {
    return clientErr("noticeId 파라미터가 없습니다", "VALIDATION_ERROR", 400);
  }

  const { items } = await query<Record<string, unknown>>(
    NOTICES_TABLE,
    "noticeId = :nid",
    { ":nid": noticeId },
    { indexName: "noticeId-index", limit: 1 }
  );

  if (!items.length) {
    return clientErr("공지를 찾을 수 없습니다", "NOT_FOUND", 404);
  }

  return ok(items[0]);
}
