import { Handler } from "aws-lambda";

/**
 * document-analyzer Lambda handler
 * 공지 문서를 분석하여 카테고리 분류, 키워드 추출, 임베딩 생성 후 Vector Store에 저장한다.
 */
export const handler: Handler = async (event) => {
  console.log("analyzer triggered", JSON.stringify(event));
  // TODO: Bedrock 호출 → 분류/임베딩 → S3/Vector Store 저장
};
