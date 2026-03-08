import {
  DynamoDBClient,
  DynamoDBClientConfig,
} from "@aws-sdk/client-dynamodb";
import {
  DynamoDBDocumentClient,
  GetCommand,
  GetCommandInput,
  PutCommand,
  PutCommandInput,
  UpdateCommand,
  UpdateCommandInput,
  DeleteCommand,
  DeleteCommandInput,
  QueryCommand,
  QueryCommandInput,
} from "@aws-sdk/lib-dynamodb";

// ──────────────────────────────────────────────────────
// Client 초기화 (Lambda cold-start 최적화: 모듈 최상단에서 1회만 생성)
// ──────────────────────────────────────────────────────
const clientConfig: DynamoDBClientConfig = {
  region: process.env.REGION ?? "us-east-1",
};

const rawClient = new DynamoDBClient(clientConfig);

export const docClient = DynamoDBDocumentClient.from(rawClient, {
  marshallOptions: {
    removeUndefinedValues: true, // undefined 속성 자동 제거
    convertEmptyValues: false,
  },
  unmarshallOptions: {
    wrapNumbers: false,
  },
});

// ──────────────────────────────────────────────────────
// 커스텀 에러
// ──────────────────────────────────────────────────────
export class DBError extends Error {
  public readonly cause: unknown;
  public readonly operation: string;

  constructor(operation: string, cause: unknown) {
    const message =
      cause instanceof Error ? cause.message : String(cause);
    super(`[DBError] ${operation}: ${message}`);
    this.name = "DBError";
    this.operation = operation;
    this.cause = cause;
  }
}

// ──────────────────────────────────────────────────────
// 래퍼 함수
// ──────────────────────────────────────────────────────

/**
 * 단건 조회
 */
export async function getItem<T>(
  tableName: string,
  key: Record<string, unknown>
): Promise<T | null> {
  const input: GetCommandInput = { TableName: tableName, Key: key };
  try {
    const { Item } = await docClient.send(new GetCommand(input));
    return (Item as T) ?? null;
  } catch (err) {
    throw new DBError("getItem", err);
  }
}

/**
 * 항목 저장 (upsert)
 */
export async function putItem<T>(
  tableName: string,
  item: T
): Promise<void> {
  const input: PutCommandInput = { TableName: tableName, Item: item as Record<string, unknown> };
  try {
    await docClient.send(new PutCommand(input));
  } catch (err) {
    throw new DBError("putItem", err);
  }
}

/**
 * 항목 부분 업데이트
 * @param updateExpression  예: "SET #name = :name, updatedAt = :updatedAt"
 * @param expressionAttributeNames  예: { "#name": "name" }
 * @param expressionAttributeValues 예: { ":name": "홍길동", ":updatedAt": "2025-..." }
 */
export async function updateItem(
  tableName: string,
  key: Record<string, unknown>,
  updateExpression: string,
  expressionAttributeValues: Record<string, unknown>,
  expressionAttributeNames?: Record<string, string>
): Promise<void> {
  const input: UpdateCommandInput = {
    TableName: tableName,
    Key: key,
    UpdateExpression: updateExpression,
    ExpressionAttributeValues: expressionAttributeValues,
    ExpressionAttributeNames: expressionAttributeNames,
  };
  try {
    await docClient.send(new UpdateCommand(input));
  } catch (err) {
    throw new DBError("updateItem", err);
  }
}

/**
 * 항목 삭제
 */
export async function deleteItem(
  tableName: string,
  key: Record<string, unknown>
): Promise<void> {
  const input: DeleteCommandInput = { TableName: tableName, Key: key };
  try {
    await docClient.send(new DeleteCommand(input));
  } catch (err) {
    throw new DBError("deleteItem", err);
  }
}

export interface QueryOptions {
  indexName?: string;
  filterExpression?: string;
  expressionAttributeNames?: Record<string, string>;
  limit?: number;
  /** 페이지네이션 커서 (LastEvaluatedKey) */
  exclusiveStartKey?: Record<string, unknown>;
  scanIndexForward?: boolean;
}

export interface QueryResult<T> {
  items: T[];
  lastEvaluatedKey?: Record<string, unknown>;
}

/**
 * 쿼리 (PK + 선택적 SK 조건)
 * @param keyConditionExpression 예: "schoolId = :schoolId AND createdAt > :from"
 */
export async function query<T>(
  tableName: string,
  keyConditionExpression: string,
  expressionAttributeValues: Record<string, unknown>,
  options: QueryOptions = {}
): Promise<QueryResult<T>> {
  const input: QueryCommandInput = {
    TableName: tableName,
    KeyConditionExpression: keyConditionExpression,
    ExpressionAttributeValues: expressionAttributeValues,
    IndexName: options.indexName,
    FilterExpression: options.filterExpression,
    ExpressionAttributeNames: options.expressionAttributeNames,
    Limit: options.limit,
    ExclusiveStartKey: options.exclusiveStartKey,
    ScanIndexForward: options.scanIndexForward,
  };
  try {
    const { Items, LastEvaluatedKey } = await docClient.send(
      new QueryCommand(input)
    );
    return {
      items: (Items ?? []) as T[],
      lastEvaluatedKey: LastEvaluatedKey as Record<string, unknown> | undefined,
    };
  } catch (err) {
    throw new DBError("query", err);
  }
}
