# 🏫 School Buddy
## 다문화가정 지능형 학부모 비서

**Product Requirements Document**

| 문서 목적 | 대상 독자 |
|---|---|
| School Buddy 서비스의 기획, 설계, 개발, 출시를 위한 종합 제품 요구사항 정의 | PM, 개발팀, 디자인팀, 사업팀, 투자자 및 이해관계자 |

---

## 목차 (Table of Contents)

1. [프로젝트 개요 (Project Overview)](#1-프로젝트-개요-project-overview)
2. [문제 정의 및 시장 분석](#2-문제-정의-및-시장-분석)
3. [서비스 비전 및 핵심 가치](#3-서비스-비전-및-핵심-가치)
4. [타겟 사용자 (Personas)](#4-타겟-사용자-user-personas)
5. [주요 기능 요구사항 (Feature Requirements)](#5-주요-기능-요구사항-feature-requirements)
6. [추가 제안 기능](#6-추가-제안-기능-enhancement-ideas)
7. [기술 아키텍처 (AWS 기반)](#7-기술-아키텍처-aws-기반)
8. [데이터 설계](#8-데이터-설계)
9. [보안 및 규정 준수](#9-보안-및-규정-준수)
10. [다국어 지원 전략](#10-다국어-지원-전략)
11. [성공 지표 (KPIs)](#11-성공-지표-kpis)
12. [로드맵 (Roadmap)](#12-로드맵-product-roadmap)
13. [리스크 분석](#13-리스크-분석)
14. [팀 구성 및 예산](#14-팀-구성-및-예산)
15. [부록: 기술 스택 요약](#부록-기술-스택-요약)
16. [부록: 한양 프로젝트 AWS 제약사항 요약](#부록-한양-프로젝트-aws-제약사항-요약)

---

## 1. 프로젝트 개요 (Project Overview)

### 1.1 서비스 한 줄 정의

> 🎯 **School Buddy란?**
>
> 다문화가정 학부모가 언어 장벽 없이 자녀의 학교 생활을 완벽하게 이해하고 참여할 수 있도록, AI가 학교 공지를 실시간으로 모니터링·번역·해석하고 한국 교육 문화를 친절하게 안내하는 지능형 학부모 비서 앱입니다.
>
> **"단순 번역이 아닌, 한국 교육 문화의 맥락까지 전달하는 정서적 안착 지원 서비스"**

### 1.2 프로젝트 배경

2023년 기준 국내 다문화 학생 수는 18만 명을 돌파하였으며, 매년 10% 이상 증가 추세에 있습니다. 그러나 이들을 위한 디지털 정보 지원 인프라는 현저히 부족한 실정입니다. 학부모가 학교 공지를 이해하지 못해 자녀가 준비물을 챙기지 못하거나, 행사에 참여하지 못하는 사례가 빈번하게 발생하고 있습니다.

School Buddy는 이 문제를 AI 기술로 해결하여, 다문화가정 자녀들이 학교에서 소외되지 않고 동등한 교육 기회를 누릴 수 있도록 지원합니다.

### 1.3 핵심 차별화 포인트

| ❌ 기존 번역 앱 | ✅ School Buddy |
|---|---|
| "내일은 현장학습입니다. 도시락을 지참하세요." | "내일 현장학습이에요! 한국에서는 보통 김밥을 준비하지만, 아이가 좋아하는 음식을 싸주셔도 됩니다. 물통과 편한 신발도 챙겨주세요 😊" |
| 단순 번역만 제공, 문화적 맥락 없음 | 문화 해석 + 실질적 준비 가이드 제공 |

---

## 2. 문제 정의 및 시장 분석

### 2.1 핵심 Pain Points

| 문제 유형 | 구체적 상황 | 영향 |
|---|---|---|
| 언어 장벽 | 한자어·교육 전문 용어가 포함된 가정통신문 이해 불가 | 행사 불참, 준비물 누락 |
| 맥락 부재 | 급식, 돌봄교실, 현장학습 등 한국 특유 제도에 대한 몰이해 | 자녀의 소외감 및 학교 부적응 |
| 정보 비대칭 | 학부모 카카오톡 단체방·커뮤니티 접근 어려움 | 중요 공지 지연 수신 또는 미수신 |
| 심리적 장벽 | 반복 질문에 대한 눈치·부담으로 도움 요청 포기 | 고립감 증가, 자녀 교육 포기 |
| 디지털 격차 | 학교 앱/NEIS 시스템 사용법 미숙지 | 공식 채널을 통한 정보 접근 불가 |

### 2.2 시장 규모 및 기회

- 국내 다문화 학생 수: 181,178명 (2023년, 교육부)
- 연평균 성장률: +12.4% (최근 5년 평균)
- 다문화가정 학부모 추정 수: 약 15~20만 명 (직접 타겟)
- 잠재 확장 시장: 외국인 유학생 학부모, 해외 거주 한국 교육 관심층
- 연관 정부 지원 사업: 다문화가족지원센터 디지털 전환 예산 (연 500억 원 이상)

### 2.3 경쟁 분석

| 서비스 | 강점 | School Buddy와의 차별점 |
|---|---|---|
| Google 번역 | 언어 범위 넓음 | 교육 맥락 해석 없음, 공지 모니터링 없음 |
| 네이버 파파고 | 한국어 번역 품질 높음 | 단방향 번역, 대화형 안내 없음 |
| NEIS 학부모 앱 | 공식 학교 정보 제공 | 한국어 전용, 다문화 지원 전무 |
| 클래스팅 | 학교-학부모 소통 강화 | 다국어 미지원, AI 해석 없음 |
| **School Buddy** | **AI 맥락 해석 + 대화형 안내 + 문화 가이드** | **최초의 다문화 특화 교육 정보 비서** |

---

## 3. 서비스 비전 및 핵심 가치

### 3.1 미션 & 비전

> 🌟 **미션**
>
> 단순 번역을 넘어, 한국 교육 문화를 현지어로 해석하여 다문화가정 자녀의 안정적인 학교 적응을 돕는다.

> 🔭 **비전 (3년)**
>
> 모든 다문화가정 학부모가 언어와 문화의 장벽 없이, 자녀의 교육에 자신 있게 참여할 수 있는 세상을 만든다.

### 3.2 핵심 가치 (Core Values)

| 🤝 포용성 | 💬 친절함 | 🎓 맥락 이해 | 🔒 신뢰성 |
|---|---|---|---|
| 모든 언어, 모든 문화의 학부모를 환영 | 반복 질문도 항상 처음처럼 친절하게 | 정보가 아닌 의미와 문화를 전달 | 검증된 교육부 자료 기반 정확한 정보 |

---

## 4. 타겟 사용자 (User Personas)

### Persona 1 – 응우옌 티 란 (32세, 베트남 출신)

> **프로필**
> - 입국 3년차 | 자녀: 초등학교 1학년 | 한국어 능력: 초급
> - 남편이 일하는 동안 혼자 아이를 돌보며 학교 일을 담당
> - 스마트폰 사용에는 익숙하지만 한국어 앱은 어려움
> - **핵심 니즈:** 가정통신문을 베트남어로 이해하고 싶다. 내 아이가 학교에서 뒤처질까봐 걱정된다.
> - **School Buddy 활용:** 공지 알림 수신 → 베트남어 번역 + 준비물 안내

### Persona 2 – 왕 메이링 (38세, 중국 출신)

> **프로필**
> - 입국 8년차 | 자녀: 유치원, 초등 3학년 | 한국어 능력: 중급 (문어 약함)
> - 한국 교육제도는 어느 정도 알지만 세부 행사·제도 변경사항 파악이 어려움
> - 학부모 단체 카톡방에서 소외감을 느낌
> - **핵심 니즈:** 다른 엄마들이 뭘 알고 있는지 나도 알고 싶다
> - **School Buddy 활용:** RAG 기반 교육 제도 Q&A + 대화형 심화 안내

### Persona 3 – 아흐마드 알리 (45세, 방글라데시 출신)

> **프로필**
> - 입국 1년차 (중도 입국) | 자녀: 초등 5학년 | 한국어 능력: 없음 (영어 가능)
> - 아이가 한국어를 빠르게 익히고 있지만 학부모 소통에서 완전히 단절
> - **핵심 니즈:** 영어로라도 학교 소식을 알고 싶다
> - **School Buddy 활용:** 영어 번역 + 문화 가이드 + 챗봇 Q&A

---

## 5. 주요 기능 요구사항 (Feature Requirements)

### 5.1 기능 F1: 스마트 학교 공지 모니터링

#### 개요
사용자가 자녀가 다니는 학교를 등록하면, 시스템이 해당 학교 홈페이지의 공지사항 페이지를 주기적으로 크롤링하여 신규 공지를 감지합니다.

#### 세부 요구사항
- **학교 검색:** 학교명 또는 지역으로 학교 검색 → 자동으로 공지 URL 매핑
- **크롤링 주기:** 기본 30분 간격, 중요 시기(개학 전후) 10분 간격으로 자동 조정
- **변경 감지:** 기존 크롤링 결과와 diff 비교 → 신규 공지 항목 추출
- **다자녀 지원:** 여러 학교를 동시에 모니터링 가능
- **오류 처리:** 홈페이지 구조 변경 시 자동 감지 → 관리자 알림

#### 기술 방향 (AWS 기반)
- **AWS EventBridge Scheduler:** 크롤링 Lambda 함수 주기적 트리거
- **AWS Lambda (Python):** BeautifulSoup/Playwright 기반 크롤러
- **Amazon DynamoDB:** 크롤링 결과 및 diff 이력 저장
- **Amazon SQS:** 신규 공지 감지 시 처리 큐에 메시지 발행

---

### 5.2 기능 F2: 대화형 AI 푸시 알림

#### 개요
신규 공지 감지 시 단순 알림이 아닌, AI가 공지 내용을 요약하고 사용자 언어로 번역한 뒤, '무엇을 준비해야 하는지'까지 대화형으로 안내합니다.

#### 알림 플로우
1. 공지 감지 → SQS 큐 수신
2. Claude AI: 공지 요약 + 사용자 언어 번역 + 문화 해석 생성
3. FCM(Firebase Cloud Messaging) / APNs를 통한 푸시 알림 발송
4. 앱에서 알림 탭 → '더 알고 싶어요' 선택 시 대화형 Q&A 모드 진입
5. 사용자가 원하는 만큼 후속 질문 가능

#### 알림 메시지 예시

> 📣 **알림 예시 (베트남어 사용자 기준)**
>
> [학교명] 새 공지: 10월 현장학습 안내
>
> 📌 **핵심 내용:** 10월 15일(화) 전교생 현장학습. 도시락, 물통, 편한 복장 필요
>
> 🇰🇷 **문화 TIP:** 한국에서는 보통 김밥을 싸가지만, 아이가 좋아하는 음식이면 무엇이든 괜찮아요!
>
> [더 알아보기] [준비물 체크리스트] [번역 보기]

#### 기술 방향
- **Amazon Bedrock (Claude Sonnet 4.5):** 요약·번역·문화해석 생성
- **AWS Lambda:** 알림 생성 로직 처리
- **Amazon SNS + Firebase Admin SDK:** 멀티플랫폼 푸시 발송
- **Amazon Pinpoint:** 알림 발송 이력 및 분석

---

### 5.3 기능 F3: 비전 기반 공문 요약

#### 개요
학교에서 종이로 배포되거나 이미지/PDF 형태로 전달되는 가정통신문을 사용자가 직접 촬영·업로드하면, AI가 OCR 및 Vision 기술로 내용을 추출하고 요약·번역합니다.

#### 세부 요구사항
- **입력 형식:** 카메라 촬영, 갤러리 이미지 선택, PDF 첨부
- **처리 기능:** OCR → 텍스트 추출 → AI 요약 → 번역 → 문화 해석
- **출력 형식:** 핵심 요약 (3~5줄) + 체크리스트 형태 준비물 + 날짜·일정 자동 캘린더 등록 제안
- **지원 해상도:** 일반 스마트폰 카메라 수준 (800×600 이상)
- **처리 시간:** 10초 이내 결과 반환 목표

#### 기술 방향
- **Amazon Textract:** 이미지/PDF에서 한국어 텍스트 정확 추출 (OCR)
- **Amazon Bedrock Multimodal (Claude 3 Vision):** 이미지 직접 이해 및 요약
- **Amazon S3:** 업로드 이미지 임시 저장 (7일 후 자동 삭제)
- **AWS Lambda:** 처리 파이프라인 오케스트레이션

---

### 5.4 기능 F4: RAG 기반 한국 교육 제도 Q&A

#### 개요
교육부 공식 가이드, 학교생활 안내서 등을 Knowledge Base로 구축하여, 사용자가 한국 교육 제도에 대해 자유롭게 질문할 수 있는 AI 튜터를 제공합니다.

#### 커버 주제 (지식베이스)
- **학사 일정:** 개학, 방학, 시험 기간
- **급식 제도:** 급식 신청, 결식 처리, 알러지 신청 방법
- **돌봄교실:** 신청 방법, 운영 시간, 비용
- **현장학습:** 동의서, 비용, 준비물
- **방과후 학교:** 프로그램 종류, 신청 방법
- **알림장 & 가정통신문:** 주요 용어 설명
- **다문화 지원 제도:** 정부 지원 프로그램, 한국어 교육 연계

#### 예시 Q&A

> 💬 **대화 예시**
>
> **학부모:** '돌봄교실이 뭐예요?'
>
> **School Buddy:** '돌봄교실은 맞벌이 가정의 초등학생을 위해 수업 후 학교에서 돌봐주는 제도예요. 보통 오후 1시~6시까지 운영되고, 숙제도 도와주고 간식도 줘요. 신청은 매 학기 초에 담임 선생님을 통해 하시면 돼요. 더 궁금한 점이 있으신가요? 😊'

#### 기술 방향
- **Amazon Bedrock Knowledge Bases:** 문서 청킹 + 임베딩 + 벡터 검색
- **Amazon OpenSearch Serverless:** 벡터 스토어 (FAISS 알고리즘)
- **Amazon S3:** 원본 교육 문서 저장소
- **Claude Sonnet 4.5:** RAG 결과 기반 답변 생성 + 다국어 응답
- **정기 업데이트:** 교육부 공지사항 모니터링 → 지식베이스 자동 갱신 파이프라인

---

### 5.5 기능 F5: 온보딩 및 사용자 설정

- **언어 선택:** 베트남어, 중국어(간체/번체), 영어, 일본어, 태국어, 몽골어, 필리핀어, 러시아어 (1차 출시 8개국어)
- **자녀 등록:** 이름, 학교, 학년 등록 (최대 3명)
- **알림 설정:** 알림 빈도, 시간대, 언어별 ON/OFF
- **문화 가이드 레벨:** 초급(많은 설명) / 중급 / 고급(간략) 선택

---

## 6. 추가 제안 기능 (Enhancement Ideas)

### 6.1 감정 지원 AI (Emotional Support Mode)

> 💡 **아이디어**
>
> 학부모가 학교 생활에 대한 불안이나 고민을 털어놓을 수 있는 공감형 대화 모드. '우리 아이가 친구를 못 사귀는 것 같아요...'와 같은 질문에 공감 + 실질적 도움 제공. 한국 학부모 커뮤니티 용어 설명 (예: '치맛바람'이 뭔지 이해하도록 도움)

### 6.2 준비물 체크리스트 & 캘린더 동기화

- 공지에서 추출한 날짜/준비물을 자동으로 캘린더 이벤트 생성
- Google Calendar / Apple Calendar 연동
- D-1, D-Day 전일 리마인더 알림

### 6.3 다문화가정 커뮤니티 허브

- 같은 학교 또는 같은 언어권 다문화 학부모 연결 (선택적)
- 익명 게시판: 질문/답변을 AI가 번역하여 언어 장벽 없이 소통
- '이 학교 다니는 베트남어 사용 학부모' 매칭 기능

### 6.4 음성 인터페이스 (Voice UI)

- 문자 입력이 어려운 사용자를 위한 음성 질문 → TTS 답변 기능
- Amazon Transcribe (STT) + Amazon Polly (TTS) 활용
- 한국어 음성 인식 + 모국어 음성 답변

### 6.5 학교별 문화 가이드북

- 지역별 학교 행사 특성 데이터 축적 → 맞춤형 가이드 생성
- 예: '○○초등학교는 운동회 때 이런 복장을 많이 입어요'
- 크라우드소싱 방식으로 선배 학부모들의 팁 수집 및 AI 검증 후 제공

### 6.6 학부모 회의 실시간 통역 지원

- 학부모 총회, 상담 등에서 실시간 통역이 필요한 경우를 위한 음성 통역 기능
- Amazon Transcribe → Claude 번역 → Polly TTS 실시간 파이프라인

---

## 7. 기술 아키텍처 (AWS 기반)

### 7.1 전체 아키텍처 개요

> 🏗️ **아키텍처 철학**
>
> - **Serverless First:** 초기 비용 최소화, 트래픽에 따른 자동 스케일링
> - **AI-Native:** Amazon Bedrock을 핵심 AI 엔진으로 활용
> - **리전:** us-east-1 (버지니아 북부) — 한양 프로젝트 제약 기준, Bedrock 미국 리전 활용
> - **비용 최적화:** Lambda + DynamoDB On-Demand + Bedrock 종량제

### 7.2 레이어별 아키텍처

#### Layer 1: 클라이언트 (Mobile App)
- **플랫폼:** React Native + Expo SDK 51 (iOS + Android 동시 지원)
- **상태관리:** TanStack Query (서버 상태) + Zustand (클라이언트 상태)
- **푸시 알림:** Firebase Cloud Messaging (FCM) 통합
- **오프라인 지원:** 최근 공지 30건 로컬 캐시

#### Layer 2: API Gateway & 인증
- **Amazon API Gateway (HTTP API):** REST 엔드포인트
- **Amazon Cognito:** 소셜 로그인 (Google, Apple) + 자체 회원가입
- **AWS Secrets Manager:** API 키, FCM 서비스 계정 등 비밀값 관리

#### Layer 3: 비즈니스 로직 (Lambda Functions)

| Lambda 함수명 | 역할 |
|---|---|
| school-crawler | 학교 홈페이지 크롤링, 신규 공지 diff 감지 |
| notice-processor | SQS 수신 → AI 요약/번역/문화해석 생성 |
| notification-sender | FCM/APNs 푸시 알림 발송 |
| document-analyzer | 이미지/PDF OCR → AI 요약 파이프라인 |
| rag-query-handler | RAG Knowledge Base 쿼리 + 답변 생성 |
| user-manager | 회원가입/설정/자녀 등록 관리 |
| school-registry | 학교 DB 관리 및 검색 |

#### Layer 4: AI 엔진 (Amazon Bedrock)
- **기본 모델:** Claude Sonnet 4.5 (claude-sonnet-4-20250514) — 번역 품질 + 문화 맥락 이해 최적
- **Knowledge Base:** Amazon Bedrock Knowledge Bases + OpenSearch Serverless
- **임베딩 모델:** Amazon Titan Embeddings V2 (한국어 지원)
- **멀티모달:** Claude Vision (이미지 기반 문서 이해)
- **Guardrails:** Bedrock Guardrails로 유해 콘텐츠 필터링

#### Layer 5: 데이터 저장소
- **Amazon DynamoDB:** 사용자 프로필, 알림 이력, 크롤링 결과, 번역 캐시 (NoSQL, 서버리스)
- **Amazon S3:** 업로드 문서, 교육 가이드 원본 PDF (버킷명: hanyang-pj-1- 접두사)
- **Amazon OpenSearch Serverless:** RAG 벡터 스토어
- ~~Amazon ElastiCache (Redis)~~ → **DynamoDB TranslationCache 테이블로 대체** (한양 프로젝트 제약)

#### Layer 6: 모니터링 & 운영
- **Amazon CloudWatch:** 로그, 메트릭, 알람
- **AWS X-Ray:** 분산 추적 (Lambda 간 레이턴시 분석)
- **Amazon SNS:** 운영 알람 (크롤러 오류, API 에러율 급증)
- **AWS Cost Explorer:** 비용 이상 탐지 및 예산 알람

### 7.3 크롤링 파이프라인 상세

> 🔄 **크롤링 플로우**
>
> 1. EventBridge Scheduler → Lambda (school-crawler) 트리거 [30분 주기]
> 2. Lambda → 학교 홈페이지 HTTP 요청 (Playwright Headless Chrome Layer)
> 3. 신규 공지 감지 시 → Amazon SQS (notice-queue) 메시지 발행
> 4. SQS → Lambda (notice-processor) 자동 트리거
> 5. notice-processor → Bedrock Claude Sonnet 4.5 API 호출 (요약 + 번역 + 문화해석)
> 6. 번역 결과 → DynamoDB TranslationCache 저장 (24시간 TTL)
> 7. 결과 → DynamoDB Notices 저장 + SNS → Lambda (notification-sender)
> 8. notification-sender → Firebase Admin SDK → FCM → 사용자 기기

### 7.4 RAG 파이프라인 상세

> 🧠 **RAG 플로우**
>
> 1. 관리자: S3에 교육부 PDF/문서 업로드
> 2. Bedrock Knowledge Base: 자동 청킹 → Titan Embeddings → OpenSearch 인덱싱
> 3. 사용자 질문 → API Gateway → Lambda (rag-query-handler)
> 4. 질문 임베딩 → OpenSearch 벡터 유사도 검색 → Top-K 청크 추출
> 5. 컨텍스트 + 질문 → Claude Sonnet 4.5 → 다국어 답변 생성
> 6. 답변 → DynamoDB 캐시 저장 (동일 질문 재사용) → 클라이언트 반환

### 7.5 배포 방식
- **소스 관리:** GitHub (mono-repo: frontend/backend/infrastructure)
- **IaC:** AWS CDK (TypeScript) — 모든 인프라 코드화
- **배포 환경:** AWS Cloud9 (IAM Role: SafeRole-hanyang-pj-1)
- **배포 방식:** Cloud9에서 `cdk deploy` 수동 실행 (Access Key 발급 불가 제약)
- **코드 품질:** GitHub Actions CI — PR 시 테스트·타입 체크·CDK synth 자동 실행
- **앱 배포:** Expo EAS Build → App Store / Play Store

---

## 8. 데이터 설계

### 8.1 핵심 DynamoDB 테이블

| 테이블명 | 파티션키 / 정렬키 | 주요 속성 |
|---|---|---|
| Users | userId (PK) | 언어설정, 자녀목록, 알림설정, fcmToken, 가입일 |
| Children | childId (PK) | 이름, 학교ID, 학년, 학급 |
| Schools | schoolId (PK) | 학교명, 주소, 공지URL, crawlStatus, lastCrawledAt |
| Notices | schoolId (PK) / createdAt (SK) | 원문, 요약, 번역JSON, 중요도 (GSI: noticeId) |
| Notifications | userId (PK) / createdAt (SK) | 공지ID, 발송상태, 읽음여부, TTL(180일) |
| ChatHistory | userId (PK) / sessionId#createdAt (SK) | 메시지목록, 공지ID(연결), TTL(90일) |
| KBDocuments | docId (PK) | S3키, 청킹상태, 마지막갱신일 |
| **TranslationCache** | **cacheKey (PK)** | **번역결과, 문화TIP, 준비물목록, TTL(24시간)** |

> ℹ️ **TranslationCache 테이블은 ElastiCache(Redis) 대체재입니다.**
> cacheKey 형식: `notice#{noticeId}#lang#{langCode}`
> 한양 프로젝트 AWS 제약(ElastiCache 사용 불가)에 따라 DynamoDB TTL 방식으로 구현합니다.

### 8.2 데이터 보존 정책
- **사용자 업로드 이미지:** S3 → 처리 완료 후 7일 보존 후 자동 삭제 (개인정보 최소화)
- **공지 원문/번역:** 2년 보존 (학년 단위 활용 가능성)
- **채팅 이력:** 90일 보존 (DynamoDB TTL 설정)
- **크롤링 로그:** 30일 보존 (CloudWatch Logs)

---

## 9. 보안 및 규정 준수

### 9.1 개인정보 보호 (PIPA 준수)
- 한국 개인정보보호법(PIPA) 완전 준수
- 수집 항목 최소화: 서비스 운영에 필요한 최소 정보만 수집
- 아동 개인정보: 자녀 정보는 학부모 동의 하에만 수집, 별도 암호화 저장
- 데이터 삭제권: 탈퇴 시 모든 개인정보 30일 이내 완전 삭제
- 국외 이전: AWS us-east-1 리전 사용, Bedrock API 호출 시 개인식별정보 제거 후 전송

### 9.2 AWS 보안 설정
- **암호화:** S3 SSE-S3, DynamoDB 암호화 at-rest, API Gateway HTTPS only
- **IAM:** Lambda 전용 역할 SafeRole-hanyang-pj-1 사용, AWS Secrets Manager로 API 키 관리
- **네트워크:** Lambda VPC 외부 실행 (한양 프로젝트 제약), HTTPS 통신으로 전송 구간 암호화
- **감사:** AWS CloudTrail로 모든 API 호출 기록

### 9.3 AI 안전성
- **Amazon Bedrock Guardrails:** 부적절한 콘텐츠 자동 차단
- **프롬프트 인젝션 방어:** 사용자 입력 → 시스템 프롬프트 분리 처리
- **환각(Hallucination) 최소화:** RAG 답변 시 출처 문서 명시

---

## 10. 다국어 지원 전략

### 10.1 1차 출시 지원 언어 (8개국어)

| 언어 | 선택 이유 (국내 다문화가정 비율 기준) |
|---|---|
| 베트남어 (vi) | 국내 결혼이민자 1위 (전체의 약 30%) |
| 중국어 간체 (zh-CN) | 중국 출신 결혼이민자 2위 |
| 중국어 번체 (zh-TW) | 대만 출신 및 화교 커뮤니티 |
| 영어 (en) | 중도 입국 자녀 학부모 공용어 |
| 일본어 (ja) | 일본 출신 결혼이민자 |
| 태국어 (th) | 동남아 커뮤니티 지원 |
| 몽골어 (mn) | 몽골 출신 이민자 증가 추세 |
| 필리핀어 (tl) | 필리핀 출신 결혼이민자 |

### 10.2 번역 품질 관리
- **1차:** Claude AI 자동 번역 (속도 우선)
- **중요 교육 용어:** 사전 정의된 용어집(Glossary) 적용 → AI에 컨텍스트로 제공
- **커뮤니티 피드백:** '번역이 어색해요' 신고 기능 → 수동 검토 후 품질 개선
- **2차 목표:** 원어민 검수자 파트타임 채용 또는 다문화지원센터 협력

---

## 11. 성공 지표 (KPIs)

### 11.1 Product KPIs

| 지표 | 목표 (출시 후 6개월) | 측정 방법 |
|---|---|---|
| MAU | 5,000명 이상 | Cognito 로그인 기록 |
| DAU/MAU 비율 | 40% 이상 | CloudWatch 커스텀 메트릭 |
| 알림 오픈율 | 60% 이상 (업계 평균 20%) | Firebase Analytics |
| 공지 번역 만족도 | 4.2/5.0 이상 | 인앱 피드백 별점 |
| RAG Q&A 답변 만족도 | 4.0/5.0 이상 | 챗봇 피드백 |
| 앱 스토어 평점 | 4.3 이상 | App Store / Play Store |
| 공지 처리 레이턴시 | 30초 이내 (감지→푸시) | X-Ray 분산 추적 |

### 11.2 Impact KPIs (사회적 영향 지표)
- **학교 행사 참여율 변화:** 사용 전후 학부모 설문 비교
- **정보 이해도:** '공지를 완전히 이해했다' 응답 비율
- **심리적 안정감:** 격월 설문 (불안 지수 감소 측정)
- **자녀 학교 적응도:** 교사/학부모 연계 평가 (장기)

---

## 12. 로드맵 (Product Roadmap)

| 단계 | 기간 및 목표 | 주요 산출물 |
|---|---|---|
| **Phase 0** 기반 구축 | M1~M2 · AWS 인프라 셋업 · 핵심 팀 구성 · 파일럿 학교 5개 섭외 | CDK 인프라 코드 · 크롤러 MVP · 베타 사용자 100명 |
| **Phase 1** MVP 출시 | M3~M5 · F1 크롤링 + F2 알림 · 4개 언어 지원 · 안드로이드 베타 | Play Store 출시 · MAU 500명 · 언론 보도 3건 |
| **Phase 2** 풀 런칭 | M6~M8 · F3 문서 분석 추가 · F4 RAG Q&A 추가 · iOS 출시 + 8개 언어 | 양 플랫폼 출시 · MAU 2,000명 · 정부 협력 MOU |
| **Phase 3** 성장 | M9~M12 · 커뮤니티 기능 · 음성 UI · 캘린더 동기화 | MAU 5,000명 · 유료화 전환 · 시리즈 A 준비 |
| **Phase 4** 확장 | Y2+ · 중학교 확장 · B2G (지자체 계약) · 동남아 시장 진출 | MAU 50,000명 · 정부 조달 등록 · 해외 파트너십 |

---

## 13. 리스크 분석

| 리스크 | 영향도 / 가능성 | 대응 전략 |
|---|---|---|
| 학교 홈페이지 구조 변경으로 크롤러 오류 | 높음 / 높음 | 모니터링 알람 + 신속 대응 팀 + 학교별 크롤러 규칙 버전 관리 |
| AI 번역 오류로 중요 정보 왜곡 | 높음 / 중간 | 중요 공지는 인간 검수 옵션 제공, 원문 항상 함께 표시 |
| 개인정보 유출 (아동 정보 포함) | 매우 높음 / 낮음 | 암호화 강화, 보안 감사, 사이버보험 가입 |
| AI API 비용 급증 | 중간 / 중간 | 답변 캐싱, 요약 길이 제한, 비용 알람 설정 |
| 학교 측의 크롤링 차단 (robots.txt) | 중간 / 낮음 | 교육부/교육청과 공식 데이터 제공 협약 추진 (장기) |
| 다문화가정 디지털 접근성 부족 | 중간 / 중간 | 오프라인 연계 (다문화가족지원센터 협력) + 심플한 UX |

---

## 14. 팀 구성 및 예산

### 14.1 권장 팀 구성 (Phase 0~1)

| 역할 | 주요 책임 |
|---|---|
| Product Manager (1명) | PRD 관리, 로드맵 조율, 파트너십, 사용자 리서치 |
| 풀스택 개발자 (2명) | Lambda 함수, API 개발, React Native 앱 |
| AI/ML 엔지니어 (1명) | Bedrock 파이프라인, RAG 구축, 프롬프트 엔지니어링 |
| DevOps 엔지니어 (0.5명) | AWS CDK, CI/CD, 모니터링 구축 |
| UX 디자이너 (1명) | 다문화 사용자 리서치, UI 설계, 접근성 |
| 다국어 콘텐츠 매니저 (1명) | 교육 용어 용어집, 문화 가이드 콘텐츠 제작 |

### 14.2 AWS 예상 월 운영 비용 (MAU 5,000명 기준)

| AWS 서비스 | 예상 월 비용 |
|---|---|
| Amazon Bedrock (Claude Sonnet 4.5 API) | ~$800 (공지 처리 + Q&A 기준) |
| AWS Lambda | ~$50 (서버리스, 호출 기반) |
| Amazon DynamoDB | ~$70 (On-Demand, TranslationCache 테이블 포함) |
| Amazon OpenSearch Serverless | ~$200 (벡터 스토어) |
| Amazon S3 | ~$20 |
| API Gateway | ~$20 |
| Amazon Textract | ~$100 (문서 분석) |
| 기타 (SNS, SQS, CloudWatch 등) | ~$40 |
| **총 예상 비용** | **~$1,300/월 (약 175만원)** |

> 💡 **비용 최적화 팁**
>
> - 한양 프로젝트 AWS 환경 활용 (계정 크레딧 범위 내 운영)
> - DynamoDB TranslationCache TTL 24시간 설정으로 중복 Bedrock 호출 최대 40% 절감
> - Bedrock 답변 캐싱 적극 활용
> - Lambda Provisioned Concurrency는 성장 후 도입 (초기 불필요)

---

## 부록: 기술 스택 요약

| 영역 | 기술 스택 |
|---|---|
| 모바일 앱 | React Native + Expo SDK 51, TanStack Query, Zustand |
| API 레이어 | Amazon API Gateway (HTTP API), AWS Lambda (Python 3.12 / Node.js 20) |
| AI 엔진 | Amazon Bedrock — Claude Sonnet 4.5 (claude-sonnet-4-20250514), Titan Embeddings V2 |
| RAG 스토어 | Amazon Bedrock Knowledge Bases + OpenSearch Serverless |
| 크롤링 | Lambda + Playwright (Chromium Layer) + BeautifulSoup |
| OCR | Amazon Textract + Bedrock Vision |
| 데이터베이스 | Amazon DynamoDB (8개 테이블, TranslationCache 포함) |
| 번역 캐시 | DynamoDB TranslationCache 테이블 (TTL 24시간) — ElastiCache 대체 |
| 파일 저장 | Amazon S3 (SSE-S3 암호화, 버킷명: hanyang-pj-1- 접두사) |
| 인증 | Amazon Cognito + Social Login (Google, Apple) |
| 알림 | Firebase Cloud Messaging + Amazon SNS |
| 모니터링 | CloudWatch + X-Ray + CloudTrail |
| IaC | AWS CDK (TypeScript) — StorageStack / ApplicationStack / MonitoringStack |
| 배포 | AWS Cloud9 (SafeRole-hanyang-pj-1) + GitHub Actions (CI 전용) |
| 보안 | Secrets Manager + IAM (SafeRole-hanyang-pj-1) + HTTPS |
| 리전 | us-east-1 (버지니아 북부) — Bedrock 포함 전체 서비스 |

---

## 부록: 한양 프로젝트 AWS 제약사항 요약

| 항목 | 제약 내용 | 대응 방식 |
|---|---|---|
| 리전 | us-east-1만 허용 (Bedrock은 미국 전 리전) | 전체 CDK 리전 us-east-1로 통일 |
| IAM Role | 새 Role 생성 불가 | SafeRole-hanyang-pj-1 기존 역할 참조 |
| ElastiCache | 사용 불가 | DynamoDB TranslationCache 테이블로 대체 |
| VPC | Private Subnet / NAT Gateway 사용 불가 | Lambda VPC 외부 실행 |
| S3 버킷명 | 반드시 hanyang-pj-1- 으로 시작 | hanyang-pj-1-documents, hanyang-pj-1-kb-source |
| Access Key | 발급 불가 | IAM Role(SafeRole) 전용 사용 |
| CI/CD | GitHub Actions OIDC 사용 불가 | Cloud9에서 수동 CDK 배포 |
| 사용 가능 서비스 | EC2, Lambda, RDS, DynamoDB, S3, API GW, SQS, SNS, Bedrock | 해당 서비스 내에서만 설계 |

---
