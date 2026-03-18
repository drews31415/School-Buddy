import { APIGatewayProxyEventV2WithJWTAuthorizer, APIGatewayProxyResultV2 } from "aws-lambda";
import { z } from "zod";
import { getItem, putItem } from "@school-buddy/shared-utils";
import { LanguageCode, NoticeImportance } from "@school-buddy/shared-types";
import { ok, clientErr } from "../lib/response";
import { getUserIdFromHeader } from "../lib/auth";

const USERS_TABLE = process.env["USERS_TABLE"]!;

const schema = z.object({
  languageCode: z.nativeEnum(LanguageCode),
});

/**
 * POST /auth/register — 공개 라우트
 * Cognito 가입 직후 호출. Authorization 헤더의 ID 토큰에서 userId(sub)를 추출한다.
 */
export async function register(
  event: APIGatewayProxyEventV2WithJWTAuthorizer
): Promise<APIGatewayProxyResultV2> {
  const userId = getUserIdFromHeader(event.headers);
  if (!userId) {
    return clientErr("Cognito ID 토큰이 필요합니다", "UNAUTHORIZED", 401);
  }

  const parsed = schema.safeParse(JSON.parse(event.body ?? "{}"));
  if (!parsed.success) {
    return clientErr(parsed.error.message, "VALIDATION_ERROR", 400);
  }

  const existing = await getItem(USERS_TABLE, { userId });
  if (existing) {
    return clientErr("이미 등록된 사용자입니다", "CONFLICT", 409);
  }

  const now = new Date().toISOString();
  await putItem(USERS_TABLE, {
    userId,
    languageCode: parsed.data.languageCode,
    notificationSettings: {
      enabled: true,
      importanceThreshold: NoticeImportance.LOW,
    },
    createdAt: now,
    updatedAt: now,
  });

  return ok({ userId }, 201);
}
