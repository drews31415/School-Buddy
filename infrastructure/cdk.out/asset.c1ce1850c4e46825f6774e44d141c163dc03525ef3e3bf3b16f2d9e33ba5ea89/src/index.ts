import { Handler, APIGatewayProxyEvent, APIGatewayProxyResult } from "aws-lambda";

/**
 * user-manager Lambda handler
 * 사용자 등록/조회/설정 변경 CRUD를 처리한다.
 */
export const handler: Handler<APIGatewayProxyEvent, APIGatewayProxyResult> = async (event) => {
  console.log("user-manager triggered", JSON.stringify(event));
  // TODO: CRUD 라우팅 → DynamoDB 처리 → 응답 반환
  return { statusCode: 200, body: JSON.stringify({ message: "ok" }) };
};
