# school-crawler — QA 엔지니어 인계 문서

## 핸들러 시그니처

```python
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]
```

### 입력 (`event`)
EventBridge ScheduledEvent. 핸들러 내부 로직에서 사용하지 않음.

### 출력
```json
{
  "processed": 3,    // 크롤링 성공 학교 수
  "new_notices": 7,  // SQS에 발행된 신규 공지 수
  "errors": 1        // 크롤링 실패 학교 수
}
```

---

## SQS 메시지 페이로드 스키마

`notice-queue`에 발행되는 메시지 `MessageBody` (JSON):

```json
{
  "noticeId":     "uuid4",
  "schoolId":     "school-001",
  "title":        "10월 현장학습 안내",
  "sourceUrl":    "https://school.example.com/notice/123",
  "originalText": "내일 현장학습이 있습니다...",
  "publishedAt":  "2025-10-01T00:00:00+00:00",
  "crawledAt":    "2025-10-01T03:00:00+00:00"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `noticeId` | string (UUID4) | 크롤러가 생성하는 고유 ID |
| `schoolId` | string | DynamoDB Schools PK |
| `title` | string | 공지 제목 (1자 이상 보장) |
| `sourceUrl` | string | 공지 원본 절대 URL |
| `originalText` | string | 공지 본문 (빈 문자열 허용) |
| `publishedAt` | ISO 8601 | 공지 게시일 (없으면 크롤링 시각) |
| `crawledAt` | ISO 8601 | 크롤링 시각 (UTC) |

**MessageAttributes:**
```json
{ "schoolId": { "DataType": "String", "StringValue": "school-001" } }
```

---

## 발생 가능한 예외 케이스

### 케이스 분류

| # | 케이스 | 발생 조건 | 처리 방식 | DynamoDB 기록 |
|---|--------|----------|----------|--------------|
| E-01 | HTTP 타임아웃 | 학교 서버 응답 없음 (5초 connect / 15초 read 초과) | 해당 학교 건너뜀, 계속 진행 | `lastErrorAt`, `lastErrorMessage` 갱신 |
| E-02 | HTTP 4xx/5xx | 학교 서버 오류 응답 | 동일 | 동일 |
| E-03 | 공지 목록 0건 | HTML 구조 변경으로 파싱 실패 | 0건으로 처리, 오류 미기록 | `lastCrawledAt` 갱신 (오류 아님) |
| E-04 | URL 절대화 실패 | `href`가 `javascript:` 등 비정상 값 | 해당 공지 항목 건너뜀 | — |
| E-05 | SQS 발행 실패 | SQS 서비스 장애, 권한 오류 | `PublishError` 발생 → 학교 전체 실패 처리 | `lastErrorAt`, `lastErrorMessage` 갱신 |
| E-06 | DynamoDB 조회 실패 | 테이블 미존재, IAM 권한 부족 | 예외 전파 → 해당 학교 실패 처리 | 업데이트 불가 (CloudWatch 로그에만 기록) |
| E-07 | 연속 3회 실패 | E-01 ~ E-06 중 하나가 연속 3회 | `crawlStatus = ERROR` 변경 + SNS 운영 알람 | `crawlStatus`, `consecutiveErrors` 갱신 |
| E-08 | 인코딩 오류 | EUC-KR 페이지에서 디코딩 실패 | `replace` 모드로 디코딩 (글자 손실 허용) | — |

### 연속 실패 상태 전환

```
[ACTIVE] ─ 실패 1회 → consecutiveErrors=1, crawlStatus=ACTIVE
         ─ 실패 2회 → consecutiveErrors=2, crawlStatus=ACTIVE
         ─ 실패 3회 → consecutiveErrors=3, crawlStatus=ERROR + SNS 알람
[ERROR]  ─ 수동 복구 후 crawlStatus=ACTIVE로 재설정 필요
         ─ 성공 시 consecutiveErrors=0 초기화, crawlStatus=ACTIVE 복원
```

---

## 테스트 픽스처 권장

| 파일 | 설명 |
|------|------|
| `tests/fixtures/sample_school_html/normal.html` | 정상 테이블 구조 공지 목록 |
| `tests/fixtures/sample_school_html/changed_structure.html` | 파서가 인식 못하는 변경된 구조 |
| `tests/fixtures/sample_school_html/euc_kr_encoded.html` | EUC-KR 인코딩 페이지 |
| `tests/fixtures/sample_school_html/empty_list.html` | 공지 0건 페이지 |

---

## 환경변수 목록

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `SCHOOLS_TABLE` | ✅ | DynamoDB Schools 테이블명 |
| `NOTICES_TABLE` | ✅ | DynamoDB Notices 테이블명 |
| `NOTICE_QUEUE_URL` | ✅ | SQS notice-queue URL |
| `NOTICE_TOPIC_ARN` | ✅ | SNS 운영 알람 토픽 ARN |
| `REGION` | ❌ | AWS 리전 (기본: `us-east-1`) |

---

## 알려진 한계

1. **파서 범용성**: 한국 학교 홈페이지 HTML 구조가 학교마다 달라, 일부 학교에서 E-03(파싱 0건) 발생 가능. 해당 학교의 CSS 셀렉터 규칙을 `Schools` 테이블 `crawlConfig` 속성으로 관리하는 방식으로 확장 가능.
2. **상세 본문 미수집**: 현재 목록 페이지 파싱만 수행하며 상세 페이지 크롤링은 미구현. `originalText`는 빈 문자열일 수 있음. notice-processor에서 `sourceUrl`로 재요청하여 본문을 가져오는 방식 권장.
3. **JavaScript 렌더링**: Playwright가 없으므로 JS로 렌더링되는 학교 홈페이지는 파싱 불가.
