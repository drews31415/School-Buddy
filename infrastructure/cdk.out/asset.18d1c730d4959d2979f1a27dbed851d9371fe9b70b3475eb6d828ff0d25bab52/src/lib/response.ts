import { APIGatewayProxyResultV2 } from "aws-lambda";

const HEADERS = { "Content-Type": "application/json" };

function meta() {
  return { timestamp: new Date().toISOString() };
}

export function ok(data: unknown, statusCode = 200): APIGatewayProxyResultV2 {
  return {
    statusCode,
    headers: HEADERS,
    body: JSON.stringify({ data, meta: meta() }),
  };
}

export function clientErr(
  message: string,
  code: string,
  statusCode = 400
): APIGatewayProxyResultV2 {
  return {
    statusCode,
    headers: HEADERS,
    body: JSON.stringify({ error: message, code, meta: meta() }),
  };
}

export function serverErr(message = "내부 서버 오류"): APIGatewayProxyResultV2 {
  return {
    statusCode: 500,
    headers: HEADERS,
    body: JSON.stringify({ error: message, code: "INTERNAL_ERROR", meta: meta() }),
  };
}
