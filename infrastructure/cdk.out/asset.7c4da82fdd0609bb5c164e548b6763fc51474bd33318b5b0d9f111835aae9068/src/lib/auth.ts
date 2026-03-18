import { APIGatewayProxyEventV2WithJWTAuthorizer } from "aws-lambda";

/**
 * API GW JWT Authorizer가 검증한 claims에서 Cognito sub를 추출한다.
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
