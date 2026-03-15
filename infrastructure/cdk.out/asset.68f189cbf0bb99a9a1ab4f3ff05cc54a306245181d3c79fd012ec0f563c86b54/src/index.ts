import { APIGatewayProxyEventV2WithJWTAuthorizer, APIGatewayProxyResultV2 } from "aws-lambda";
import { searchSchools } from "./handlers/searchSchools";
import { subscribe }     from "./handlers/subscribe";
import { getNotices }    from "./handlers/getNotices";
import { getNotice }     from "./handlers/getNotice";
import { serverErr }     from "./lib/response";

/**
 * school-registry Lambda — HTTP API Gateway Proxy (payload format 2.0, JWT Authorizer)
 *
 * 라우팅은 event.routeKey ("METHOD /path") 기준.
 */
export const handler = async (
  event: APIGatewayProxyEventV2WithJWTAuthorizer
): Promise<APIGatewayProxyResultV2> => {
  try {
    const { routeKey } = event;
    if (routeKey === "GET /schools/search")       return searchSchools(event);
    if (routeKey === "POST /schools/subscribe")   return subscribe(event);
    if (routeKey === "GET /notices")              return getNotices(event);
    if (routeKey === "GET /notices/{noticeId}")   return getNotice(event);

    return {
      statusCode: 404,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ error: "Not Found", code: "NOT_FOUND" }),
    };
  } catch (err) {
    console.error("[school-registry] Unhandled error:", err);
    return serverErr();
  }
};
