import { APIGatewayProxyEventV2WithJWTAuthorizer, APIGatewayProxyResultV2 } from "aws-lambda";
import { z } from "zod";
import { updateItem } from "@school-buddy/shared-utils";
import { LanguageCode, NoticeImportance } from "@school-buddy/shared-types";
import { ok, clientErr } from "../lib/response";
import { getUserId } from "../lib/auth";

const USERS_TABLE = process.env["USERS_TABLE"]!;

const schema = z
  .object({
    languageCode:    z.nativeEnum(LanguageCode).optional(),
    fcmToken:        z.string().nullable().optional(),
    fcmTokenWeb:     z.string().nullable().optional(),
    notificationSettings: z
      .object({
        enabled:             z.boolean().optional(),
        importanceThreshold: z.nativeEnum(NoticeImportance).optional(),
        quietHoursStart:     z.string().regex(/^\d{2}:\d{2}$/).nullable().optional(),
        quietHoursEnd:       z.string().regex(/^\d{2}:\d{2}$/).nullable().optional(),
      })
      .optional(),
  })
  .refine((d) => Object.values(d).some((v) => v !== undefined), {
    message: "업데이트할 항목이 없습니다",
  });

export async function updateMe(
  event: APIGatewayProxyEventV2WithJWTAuthorizer
): Promise<APIGatewayProxyResultV2> {
  const userId = getUserId(event);

  const parsed = schema.safeParse(JSON.parse(event.body ?? "{}"));
  if (!parsed.success) {
    return clientErr(parsed.error.message, "VALIDATION_ERROR", 400);
  }

  const data = parsed.data;
  const sets: string[]                = ["updatedAt = :updatedAt"];
  const vals: Record<string, unknown> = { ":updatedAt": new Date().toISOString() };

  if (data.languageCode !== undefined) {
    sets.push("languageCode = :lang");
    vals[":lang"] = data.languageCode;
  }
  if (data.fcmToken !== undefined) {
    sets.push("fcmToken = :fcmToken");
    vals[":fcmToken"] = data.fcmToken;
  }
  if (data.fcmTokenWeb !== undefined) {
    sets.push("fcmTokenWeb = :fcmTokenWeb");
    vals[":fcmTokenWeb"] = data.fcmTokenWeb;
  }
  if (data.notificationSettings !== undefined) {
    sets.push("notificationSettings = :ns");
    vals[":ns"] = data.notificationSettings;
  }

  await updateItem(USERS_TABLE, { userId }, `SET ${sets.join(", ")}`, vals);

  return ok({ userId });
}
