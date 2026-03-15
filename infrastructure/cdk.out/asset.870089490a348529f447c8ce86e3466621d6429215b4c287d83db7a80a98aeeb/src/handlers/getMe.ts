import { APIGatewayProxyEventV2WithJWTAuthorizer, APIGatewayProxyResultV2 } from "aws-lambda";
import { getItem, query } from "@school-buddy/shared-utils";
import { ok, clientErr } from "../lib/response";
import { getUserId } from "../lib/auth";

const USERS_TABLE    = process.env["USERS_TABLE"]!;
const CHILDREN_TABLE = process.env["CHILDREN_TABLE"]!;

export async function getMe(
  event: APIGatewayProxyEventV2WithJWTAuthorizer
): Promise<APIGatewayProxyResultV2> {
  const userId = getUserId(event);

  const user = await getItem<Record<string, unknown>>(USERS_TABLE, { userId });
  if (!user) {
    return clientErr("사용자를 찾을 수 없습니다", "NOT_FOUND", 404);
  }

  const { items: children } = await query(
    CHILDREN_TABLE,
    "userId = :uid",
    { ":uid": userId },
    { indexName: "userId-index" }
  );

  return ok({ ...user, children });
}
