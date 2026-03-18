import { Handler, APIGatewayProxyEvent, APIGatewayProxyResult } from "aws-lambda";

/**
 * rag-query-handler Lambda handler
 * 사용자 자연어 질문을 받아 RAG 파이프라인으로 관련 공지를 검색하고 답변을 생성한다.
 */
export const handler: Handler<APIGatewayProxyEvent, APIGatewayProxyResult> = async (event) => {
  console.log("rag triggered", JSON.stringify(event));
  // TODO: 질문 임베딩 → Vector Search → Bedrock 답변 생성 → 응답 반환
  return { statusCode: 200, body: JSON.stringify({ message: "ok" }) };
};
