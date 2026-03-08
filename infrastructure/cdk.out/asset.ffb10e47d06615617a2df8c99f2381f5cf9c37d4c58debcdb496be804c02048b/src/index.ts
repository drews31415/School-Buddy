import { Handler, APIGatewayProxyEvent, APIGatewayProxyResult } from "aws-lambda";

/**
 * school-registry Lambda handler
 * 학교 등록/조회/크롤 설정 관리 CRUD를 처리한다.
 */
export const handler: Handler<APIGatewayProxyEvent, APIGatewayProxyResult> = async (event) => {
  console.log("school-registry triggered", JSON.stringify(event));
  // TODO: 학교 CRUD 라우팅 → DynamoDB 처리 → 응답 반환
  return { statusCode: 200, body: JSON.stringify({ message: "ok" }) };
};
