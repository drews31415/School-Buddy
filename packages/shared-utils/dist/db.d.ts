import { DynamoDBDocumentClient } from "@aws-sdk/lib-dynamodb";
export declare const docClient: DynamoDBDocumentClient;
export declare class DBError extends Error {
    readonly cause: unknown;
    readonly operation: string;
    constructor(operation: string, cause: unknown);
}
/**
 * 단건 조회
 */
export declare function getItem<T>(tableName: string, key: Record<string, unknown>): Promise<T | null>;
/**
 * 항목 저장 (upsert)
 */
export declare function putItem<T>(tableName: string, item: T): Promise<void>;
/**
 * 항목 부분 업데이트
 * @param updateExpression  예: "SET #name = :name, updatedAt = :updatedAt"
 * @param expressionAttributeNames  예: { "#name": "name" }
 * @param expressionAttributeValues 예: { ":name": "홍길동", ":updatedAt": "2025-..." }
 */
export declare function updateItem(tableName: string, key: Record<string, unknown>, updateExpression: string, expressionAttributeValues: Record<string, unknown>, expressionAttributeNames?: Record<string, string>): Promise<void>;
/**
 * 항목 삭제
 */
export declare function deleteItem(tableName: string, key: Record<string, unknown>): Promise<void>;
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
export declare function query<T>(tableName: string, keyConditionExpression: string, expressionAttributeValues: Record<string, unknown>, options?: QueryOptions): Promise<QueryResult<T>>;
//# sourceMappingURL=db.d.ts.map