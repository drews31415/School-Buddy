import { APIGatewayProxyEventV2WithJWTAuthorizer, APIGatewayProxyResultV2 } from "aws-lambda";
import { query } from "@school-buddy/shared-utils";
import { ok } from "../lib/response";
import { getUserId } from "../lib/auth";

const CHILDREN_TABLE = process.env["CHILDREN_TABLE"]!;

export async function getChildren(
  event: APIGatewayProxyEventV2WithJWTAuthorizer
): Promise<APIGatewayProxyResultV2> {
  const userId = getUserId(event);

  const { items } = await query(
    CHILDREN_TABLE,
    "userId = :uid",
    { ":uid": userId },
    { indexName: "userId-index" }
  );

  return ok(items);
}
