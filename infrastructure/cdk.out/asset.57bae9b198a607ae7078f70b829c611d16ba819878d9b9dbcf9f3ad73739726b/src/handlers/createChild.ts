import { APIGatewayProxyEventV2WithJWTAuthorizer, APIGatewayProxyResultV2 } from "aws-lambda";
import { z } from "zod";
import { putItem, query } from "@school-buddy/shared-utils";
import { ok, clientErr } from "../lib/response";
import { getUserId } from "../lib/auth";

const MAX_CHILDREN   = 3;
const CHILDREN_TABLE = process.env["CHILDREN_TABLE"]!;

const schema = z.object({
  name:      z.string().min(1).max(50),
  schoolId:  z.string().min(1),
  grade:     z.number().int().min(1).max(6),
  className: z.string().min(1).max(20),
});

export async function createChild(
  event: APIGatewayProxyEventV2WithJWTAuthorizer
): Promise<APIGatewayProxyResultV2> {
  const userId = getUserId(event);

  const parsed = schema.safeParse(JSON.parse(event.body ?? "{}"));
  if (!parsed.success) {
    return clientErr(parsed.error.message, "VALIDATION_ERROR", 400);
  }

  // 최대 자녀 수 체크
  const { items } = await query(
    CHILDREN_TABLE,
    "userId = :uid",
    { ":uid": userId },
    { indexName: "userId-index" }
  );
  if (items.length >= MAX_CHILDREN) {
    return clientErr(
      `자녀는 최대 ${MAX_CHILDREN}명까지 등록 가능합니다`,
      "LIMIT_EXCEEDED",
      400
    );
  }

  const childId = crypto.randomUUID();
  const now     = new Date().toISOString();
  const child   = { childId, userId, ...parsed.data, createdAt: now };

  await putItem(CHILDREN_TABLE, child);

  return ok(child, 201);
}
