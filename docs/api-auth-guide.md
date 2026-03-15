# School Buddy — API & 인증 가이드

> React Native (Expo) 개발자를 위한 레퍼런스.
> 배포 후 실제 값은 CDK Output(`cdk deploy`)으로 확인한다.

---

## 1. 환경 변수 설정

`apps/mobile/.env` 에 CDK Output 값을 입력한다:

```env
# CDK Output: ApiEndpoint
EXPO_PUBLIC_API_BASE_URL=https://<api-id>.execute-api.us-east-1.amazonaws.com

# CDK Output: UserPoolId
EXPO_PUBLIC_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX

# CDK Output: UserPoolClientId
EXPO_PUBLIC_COGNITO_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX

# CDK Output: CognitoDomain
EXPO_PUBLIC_COGNITO_DOMAIN=https://school-buddy-dev.auth.us-east-1.amazoncognito.com
```

---

## 2. 인증 아키텍처 개요

```
앱 (React Native)
  │
  ├─ 이메일/비밀번호 ──→ Cognito UserPool (SRP)
  │                          │
  ├─ Google 로그인  ──→ Cognito Hosted UI ──→ Google OAuth
  │                          │
  └─ Apple 로그인   ──→ Cognito Hosted UI ──→ Apple OAuth
                             │
                      ID Token (JWT)
                             │
                    ┌────────▼────────────┐
                    │  HTTP API Gateway   │  (JWT Authorizer)
                    │  Authorization:     │
                    │  Bearer <id_token>  │
                    └─────────────────────┘
```

- **ID Token** 을 `Authorization: Bearer <token>` 헤더로 모든 보호 엔드포인트에 전송
- 토큰 유효기간: **1시간** (Access / ID Token), **30일** (Refresh Token)

---

## 3. 인증 흐름

### 3-1. 이메일/비밀번호 회원가입

```
POST /auth/register          ← 인증 불필요
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "Securepass1",
  "languageCode": "vi"        // vi | zh-CN | zh-TW | en | ja | th | mn | tl
}
```

응답:
```json
{
  "data": { "userId": "uuid", "email": "user@example.com" },
  "meta": { "timestamp": "2025-01-01T00:00:00Z" }
}
```

> Cognito가 인증 이메일을 발송. 이메일 확인 후 로그인 가능.

---

### 3-2. 이메일/비밀번호 로그인 (SRP)

`amazon-cognito-identity-js` 또는 `aws-amplify` 사용 권장:

```typescript
import { CognitoUserPool, CognitoUser, AuthenticationDetails } from 'amazon-cognito-identity-js';

const userPool = new CognitoUserPool({
  UserPoolId: process.env.EXPO_PUBLIC_COGNITO_USER_POOL_ID!,
  ClientId:   process.env.EXPO_PUBLIC_COGNITO_CLIENT_ID!,
});

async function signIn(email: string, password: string) {
  return new Promise<{ idToken: string; refreshToken: string }>((resolve, reject) => {
    const cognitoUser = new CognitoUser({ Username: email, Pool: userPool });
    const authDetails = new AuthenticationDetails({ Username: email, Password: password });

    cognitoUser.authenticateUser(authDetails, {
      onSuccess: (session) => resolve({
        idToken:      session.getIdToken().getJwtToken(),
        refreshToken: session.getRefreshToken().getToken(),
      }),
      onFailure: reject,
    });
  });
}
```

---

### 3-3. Google / Apple 소셜 로그인 (Hosted UI)

`expo-auth-session` + Cognito Hosted UI 방식:

```typescript
import * as AuthSession from 'expo-auth-session';
import * as WebBrowser from 'expo-web-browser';

WebBrowser.maybeCompleteAuthSession();

const COGNITO_DOMAIN  = process.env.EXPO_PUBLIC_COGNITO_DOMAIN!;
const CLIENT_ID       = process.env.EXPO_PUBLIC_COGNITO_CLIENT_ID!;
const REDIRECT_URI    = AuthSession.makeRedirectUri({ scheme: 'schoolbuddy', path: 'auth/callback' });

// Google 로그인 예시
const googleAuthUrl =
  `${COGNITO_DOMAIN}/oauth2/authorize` +
  `?identity_provider=Google` +
  `&response_type=code` +
  `&client_id=${CLIENT_ID}` +
  `&redirect_uri=${encodeURIComponent(REDIRECT_URI)}` +
  `&scope=email+profile+openid`;

async function signInWithGoogle() {
  const result = await WebBrowser.openAuthSessionAsync(googleAuthUrl, REDIRECT_URI);
  if (result.type === 'success') {
    const code = new URL(result.url).searchParams.get('code')!;
    return exchangeCodeForTokens(code);
  }
}

async function exchangeCodeForTokens(code: string) {
  const response = await fetch(`${COGNITO_DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type:   'authorization_code',
      client_id:    CLIENT_ID,
      redirect_uri: REDIRECT_URI,
      code,
    }),
  });
  const { id_token, refresh_token } = await response.json();
  return { idToken: id_token, refreshToken: refresh_token };
}
```

Apple 로그인은 `identity_provider=SignInWithApple` 으로 동일하게 처리.

---

### 3-4. 토큰 갱신

```typescript
async function refreshIdToken(refreshToken: string): Promise<string> {
  const response = await fetch(`${COGNITO_DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type:    'refresh_token',
      client_id:     CLIENT_ID,
      refresh_token: refreshToken,
    }),
  });
  const { id_token } = await response.json();
  return id_token;
}
```

> **권장**: 만료 5분 전에 자동 갱신하거나 API 401 응답 시 갱신 후 재시도.

---

## 4. API 클라이언트 예시

```typescript
const API_BASE = process.env.EXPO_PUBLIC_API_BASE_URL!;

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  idToken: string,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${idToken}`,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error ?? `HTTP ${res.status}`);
  }
  return res.json();
}
```

---

## 5. 엔드포인트 목록

### 공개 (인증 불필요)

| Method | Path             | Lambda       | 설명         |
|--------|------------------|--------------|--------------|
| POST   | `/auth/register` | user-manager | 이메일 회원가입 |

### 보호 (Authorization: Bearer \<id_token\> 필수)

#### 사용자 / 자녀

| Method | Path         | Lambda       | 설명                   |
|--------|--------------|--------------|------------------------|
| GET    | `/users/me`  | user-manager | 내 프로필 조회          |
| PUT    | `/users/me`  | user-manager | 프로필 수정 (언어, FCM 토큰 등) |
| POST   | `/children`  | user-manager | 자녀 등록              |
| GET    | `/children`  | user-manager | 내 자녀 목록           |

#### 학교

| Method | Path                 | Lambda          | 설명              |
|--------|----------------------|-----------------|-------------------|
| GET    | `/schools/search`    | school-registry | 학교 검색 (q=키워드) |
| POST   | `/schools/subscribe` | school-registry | 자녀-학교 연결     |

#### 공지

| Method | Path                    | Lambda          | 설명              |
|--------|-------------------------|-----------------|-------------------|
| GET    | `/notices`              | school-registry | 공지 목록 (schoolId 쿼리) |
| GET    | `/notices/{noticeId}`   | school-registry | 공지 상세 + 번역   |

#### 문서 분석

| Method | Path                  | Lambda            | 설명                   |
|--------|-----------------------|-------------------|------------------------|
| POST   | `/documents/analyze`  | document-analyzer | 이미지/PDF 업로드 → AI 분석 |

#### RAG 채팅

| Method | Path            | Lambda           | 설명               |
|--------|-----------------|------------------|--------------------|
| POST   | `/chat`         | rag-query-handler | 질문 → AI 답변     |
| GET    | `/chat/history` | rag-query-handler | 대화 이력 조회     |

---

## 6. 공통 응답 형식

```typescript
// 성공
interface SuccessResponse<T> {
  data: T;
  meta: { timestamp: string };   // ISO 8601
}

// 실패
interface ErrorResponse {
  error: string;
  code:  string;
  meta:  { timestamp: string };
}
```

### 주요 에러 코드

| HTTP | code                   | 설명                           |
|------|------------------------|--------------------------------|
| 400  | `VALIDATION_ERROR`     | 입력 값 오류                   |
| 401  | `UNAUTHORIZED`         | 토큰 없음 / 만료               |
| 403  | `FORBIDDEN`            | 권한 없음 (다른 사용자 리소스)  |
| 404  | `NOT_FOUND`            | 리소스 없음                    |
| 409  | `CONFLICT`             | 중복 (이미 구독, 이미 등록 등) |
| 500  | `INTERNAL_ERROR`       | 서버 내부 오류                 |

---

## 7. FCM 토큰 등록

푸시 알림 수신을 위해 로그인 후 토큰을 등록한다:

```typescript
import * as Notifications from 'expo-notifications';

async function registerFcmToken(idToken: string) {
  const { data: expoPushToken } = await Notifications.getExpoPushTokenAsync();
  // 또는 네이티브 FCM 토큰:
  // const { data: fcmToken } = await Notifications.getDevicePushTokenAsync();

  await apiFetch('/users/me', {
    method: 'PUT',
    body: JSON.stringify({ fcmToken: expoPushToken }),
  }, idToken);
}
```

---

## 8. 지원 언어 코드

| 코드    | 언어         |
|---------|--------------|
| `vi`    | Tiếng Việt   |
| `zh-CN` | 简体中文      |
| `zh-TW` | 繁體中文      |
| `en`    | English      |
| `ja`    | 日本語        |
| `th`    | ภาษาไทย      |
| `mn`    | Монгол        |
| `tl`    | Filipino     |
