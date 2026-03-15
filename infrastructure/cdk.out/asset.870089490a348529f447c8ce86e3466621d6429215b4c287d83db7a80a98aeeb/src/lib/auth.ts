import {
  APIGatewayProxyEventV2WithJWTAuthorizer,
  APIGatewayProxyEventV2,
} from "aws-lambda";

/**
 * 보호 라우트: API GW JWT Authorizer가 검증한 claims에서 sub 추출
 */
export function getUserId(
  event: APIGatewayProxyEventV2WithJWTAuthorizer
): string {
  const sub = event.requestContext.authorizer.jwt.claims["sub"];
  if (!sub || typeof sub !== "string") {
    throw new Error("JWT sub claim 없음");
  }
  return sub;
}

/**
 * 공개 라우트 (/auth/register): Authorization 헤더 Bearer 토큰을 직접 디코딩해 sub 추출
 * ⚠️  서명 검증 없음 — Cognito가 발급한 토큰임을 신뢰 (추후 JWKS 검증으로 강화 가능)
 */
export function getUserIdFromHeader(
  headers: APIGatewayProxyEventV2["headers"]
): string | null {
  const auth = headers["authorization"] ?? headers["Authorization"];
  if (!auth?.startsWith("Bearer ")) return null;
  try {
    const payload = auth.split(".")[1];
    const decoded = JSON.parse(
      Buffer.from(payload, "base64url").toString("utf-8")
    ) as Record<string, unknown>;
    const sub = decoded["sub"];
    return typeof sub === "string" ? sub : null;
  } catch {
    return null;
  }
}
