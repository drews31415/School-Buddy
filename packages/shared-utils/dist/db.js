"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DBError = exports.docClient = void 0;
exports.getItem = getItem;
exports.putItem = putItem;
exports.updateItem = updateItem;
exports.deleteItem = deleteItem;
exports.query = query;
const client_dynamodb_1 = require("@aws-sdk/client-dynamodb");
const lib_dynamodb_1 = require("@aws-sdk/lib-dynamodb");
// ──────────────────────────────────────────────────────
// Client 초기화 (Lambda cold-start 최적화: 모듈 최상단에서 1회만 생성)
// ──────────────────────────────────────────────────────
const clientConfig = {
    region: process.env.REGION ?? "us-east-1",
};
const rawClient = new client_dynamodb_1.DynamoDBClient(clientConfig);
exports.docClient = lib_dynamodb_1.DynamoDBDocumentClient.from(rawClient, {
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
class DBError extends Error {
    cause;
    operation;
    constructor(operation, cause) {
        const message = cause instanceof Error ? cause.message : String(cause);
        super(`[DBError] ${operation}: ${message}`);
        this.name = "DBError";
        this.operation = operation;
        this.cause = cause;
    }
}
exports.DBError = DBError;
// ──────────────────────────────────────────────────────
// 래퍼 함수
// ──────────────────────────────────────────────────────
/**
 * 단건 조회
 */
async function getItem(tableName, key) {
    const input = { TableName: tableName, Key: key };
    try {
        const { Item } = await exports.docClient.send(new lib_dynamodb_1.GetCommand(input));
        return Item ?? null;
    }
    catch (err) {
        throw new DBError("getItem", err);
    }
}
/**
 * 항목 저장 (upsert)
 */
async function putItem(tableName, item) {
    const input = { TableName: tableName, Item: item };
    try {
        await exports.docClient.send(new lib_dynamodb_1.PutCommand(input));
    }
    catch (err) {
        throw new DBError("putItem", err);
    }
}
/**
 * 항목 부분 업데이트
 * @param updateExpression  예: "SET #name = :name, updatedAt = :updatedAt"
 * @param expressionAttributeNames  예: { "#name": "name" }
 * @param expressionAttributeValues 예: { ":name": "홍길동", ":updatedAt": "2025-..." }
 */
async function updateItem(tableName, key, updateExpression, expressionAttributeValues, expressionAttributeNames) {
    const input = {
        TableName: tableName,
        Key: key,
        UpdateExpression: updateExpression,
        ExpressionAttributeValues: expressionAttributeValues,
        ExpressionAttributeNames: expressionAttributeNames,
    };
    try {
        await exports.docClient.send(new lib_dynamodb_1.UpdateCommand(input));
    }
    catch (err) {
        throw new DBError("updateItem", err);
    }
}
/**
 * 항목 삭제
 */
async function deleteItem(tableName, key) {
    const input = { TableName: tableName, Key: key };
    try {
        await exports.docClient.send(new lib_dynamodb_1.DeleteCommand(input));
    }
    catch (err) {
        throw new DBError("deleteItem", err);
    }
}
/**
 * 쿼리 (PK + 선택적 SK 조건)
 * @param keyConditionExpression 예: "schoolId = :schoolId AND createdAt > :from"
 */
async function query(tableName, keyConditionExpression, expressionAttributeValues, options = {}) {
    const input = {
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
        const { Items, LastEvaluatedKey } = await exports.docClient.send(new lib_dynamodb_1.QueryCommand(input));
        return {
            items: (Items ?? []),
            lastEvaluatedKey: LastEvaluatedKey,
        };
    }
    catch (err) {
        throw new DBError("query", err);
    }
}
//# sourceMappingURL=db.js.map