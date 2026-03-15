import { APIGatewayProxyEventV2WithJWTAuthorizer, APIGatewayProxyResultV2 } from "aws-lambda";
import { z } from "zod";
import { getItem, updateItem } from "@school-buddy/shared-utils";
import { ok, clientErr } from "../lib/response";
import { getUserId } from "../lib/auth";

const CHILDREN_TABLE = process.env["CHILDREN_TABLE"]!;
const SCHOOLS_TABLE  = process.env["SCHOOLS_TABLE"]!;

const schema = z.object({
  childId:  z.string().min(1),
  schoolId: z.string().min(1),
});

/**
 * POST /schools/subscribe
 * 자녀를 학교에 연결한다 (Children 테이블의 schoolId 업데이트).
 */
export async function subscribe(
  event: APIGatewayProxyEventV2WithJWTAuthorizer
): Promise<APIGatewayProxyResultV2> {
  const userId = getUserId(event);

  const parsed = schema.safeParse(JSON.parse(event.body ?? "{}"));
  if (!parsed.success) {
    return clientErr(parsed.error.message, "VALIDATION_ERROR", 400);
  }

  const { childId, schoolId } = parsed.data;

  // 자녀 소유권 검증
  const child = await getItem<{ childId: string; userId: string }>(
    CHILDREN_TABLE,
    { childId }
  );
  if (!child) {
    return clientErr("자녀를 찾을 수 없습니다", "NOT_FOUND", 404);
  }
  if (child.userId !== userId) {
    return clientErr("권한이 없습니다", "FORBIDDEN", 403);
  }

  // 학교 존재 여부 검증
  const school = await getItem(SCHOOLS_TABLE, { schoolId });
  if (!school) {
    return clientErr("학교를 찾을 수 없습니다", "NOT_FOUND", 404);
  }

  await updateItem(
    CHILDREN_TABLE,
    { childId },
    "SET schoolId = :sid, updatedAt = :now",
    { ":sid": schoolId, ":now": new Date().toISOString() }
  );

  return ok({ childId, schoolId });
}
