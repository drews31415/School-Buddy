import { APIGatewayProxyEventV2WithJWTAuthorizer, APIGatewayProxyResultV2 } from "aws-lambda";
import { register }    from "./handlers/register";
import { getMe }       from "./handlers/getMe";
import { updateMe }    from "./handlers/updateMe";
import { createChild } from "./handlers/createChild";
import { getChildren } from "./handlers/getChildren";
import { serverErr }   from "./lib/response";

/**
 * user-manager Lambda — HTTP API Gateway Proxy (payload format 2.0, JWT Authorizer)
 *
 * 라우팅은 event.routeKey ("METHOD /path") 기준.
 * /auth/register 는 공개 라우트이나 동일 Lambda가 처리한다.
 */
export const handler = async (
  event: APIGatewayProxyEventV2WithJWTAuthorizer
): Promise<APIGatewayProxyResultV2> => {
  try {
    switch (event.routeKey) {
      case "POST /auth/register": return register(event);
      case "GET /users/me":       return getMe(event);
      case "PUT /users/me":       return updateMe(event);
      case "POST /children":      return createChild(event);
      case "GET /children":       return getChildren(event);
      default:
        return {
          statusCode: 404,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ error: "Not Found", code: "NOT_FOUND" }),
        };
    }
  } catch (err) {
    console.error("[user-manager] Unhandled error:", err);
    return serverErr();
  }
};
