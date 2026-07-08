# OS 청사진 — 취업 준비생을 위한 채용 리서치 웹 서비스

> 이 문서는 앞으로 만들 프로젝트의 전체 청사진이다. 작업 전 항상 이 문서를 참고하고,
> 방향이 바뀌면 이 문서를 먼저 갱신한 뒤 구현한다.

---

## 1. 한 줄 요약

취업 준비생이 **공고를 찾는 단계**와 **자소서를 쓰기 위해 회사를 조사하는 단계**에서
겪는 반복적·소모적인 병목을, 한곳에서 자동으로 모아주고 정리해주는 웹 서비스.

---

## 2. 문제 정의

취업 준비생의 전형적인 워크플로우는 다음과 같다.

```
[1] 공고 탐색        [2] 회사 조사            [3] 자소서 작성     [4] 제출
여러 사이트를     →  공시 자료 / 인재상 등  →  초안 작성/퇴고  →  접수
스크리닝해 공고      자소서용 근거 자료
를 발굴             수집
```

이 중 **[1] 공고 탐색**과 **[2] 회사 조사**에서 가장 큰 병목이 발생한다.

- **공고 탐색의 병목**
  - 잡코리아, 사람인, 원티드, 링크드인, 관심 회사 채용 페이지 등 **여러 사이트를 매번 따로** 돌아야 한다.
  - 같은 공고가 사이트마다 중복으로 뜨고, 마감일/직무 조건은 제각각 흩어져 있다.
  - "내 조건(직무·지역·경력·마감임박)"에 맞는 공고를 매번 수작업으로 거른다.

- **회사 조사의 병목**
  - 공고를 찾은 뒤, 자소서를 쓰려면 **회사의 공시 자료(재무·사업보고서)와 인재상·핵심가치**를 따로 찾아봐야 한다.
  - 정보 출처가 흩어져 있다(전자공시, 회사 홈페이지, 채용 페이지, 리뷰 사이트 등).
  - 찾아낸 정보를 자소서에 쓸 수 있게 **요약·정리하는 일이 매번 반복**된다.

> **이 서비스가 푸는 범위는 [1]과 [2]다.**
> [3] 자소서 작성과 [4] 제출은 1차 범위 밖이며, 향후 확장 후보로만 둔다(8장 참고).

---

## 3. 타겟 사용자

- **주 사용자**: 신입·경력 전환을 준비하는 취업 준비생.
- **상황**: 동시에 여러 회사·공고를 비교하며, 회사마다 자소서 근거 자료를 새로 찾아야 하는 사람.
- **핵심 니즈**: "내 조건에 맞는 공고를 한눈에" + "이 회사에 대해 자소서 쓸 재료를 빠르게".

---

## 4. 핵심 가치 제안

1. **모아보기**: 흩어진 채용 공고를 한 곳에서 본다(중복 제거 + 내 조건 필터).
2. **빠른 회사 이해**: 공고를 클릭하면 그 회사의 공시 요약과 인재상이 자소서 관점으로 정리되어 나온다.
3. **반복 제거**: 매번 수동으로 하던 검색·정리를 자동화해 시간을 아낀다.

---

## 5. 핵심 기능

### 5.1 공고 스크리닝 (Feature A)
- 여러 채용 소스에서 공고를 **수집·정규화**(직무/회사/지역/경력/마감일 등 공통 스키마로 통일).
- **중복 제거**: 같은 공고가 여러 사이트에 있어도 하나로 묶기.
- **개인 조건 필터/정렬**: 직무·지역·경력·키워드·마감임박순.
- **관심 공고 저장(북마크)** 및 상태 관리(지원 예정 / 지원함 / 마감).

### 5.2 회사 공시 · 인재상 리서치 (Feature B)
- 공고에 연결된 회사의 **공시 자료 요약**: 사업 개요, 주요 재무 지표, 최근 이슈(자소서에 인용 가능한 형태로).
- **인재상·핵심가치 수집·정리**: 회사 채용 페이지·홈페이지 등에서 인재상/비전/핵심가치 추출.
- **자소서 관점 요약**: "이 회사가 중시하는 가치 → 이런 경험을 강조하면 좋음" 식의 정리(근거 출처 링크 포함).
- 회사별 **리서치 노트 저장**(나중에 자소서 쓸 때 재활용).

---

## 6. 사용자 흐름 (1차)

```
1. 온보딩: 관심 직무 / 지역 / 경력 / 키워드 입력
2. 공고 피드: 내 조건에 맞춰 모인 공고 리스트 (중복 제거·필터·정렬)
3. 공고 상세: 직무 요건 + "이 회사 리서치 보기" 진입점
4. 회사 리서치: 공시 요약 + 인재상/핵심가치 + 자소서 관점 정리 (출처 링크)
5. 저장: 관심 공고 북마크 / 리서치 노트 보관
```

- **온보딩 조건과 피드 필터의 관계(전제)**: 온보딩 입력은 피드의 **초기 필터 프리셋**이다. 사용자는 **피드에서 조건을 언제든 자유롭게 변경**할 수 있고, preference도 언제든 수정 가능(고정 필터 아님). frontend 화면 설계의 전제.
- **"필터 전체 해제"(초기화)의 의미**: 피드의 초기화 동작은 **모든 필터 조건을 풀고 전체 보기**로 돌아가는 것이다(온보딩 프리셋으로 되돌리는 것이 **아님**). 오해 방지를 위해 버튼 라벨은 "**필터 전체 해제**"로 표기한다.
- **온보딩 프리셋의 위치**: 온보딩 프리셋은 **최초 진입 시 기본값**일 뿐, 초기화가 되돌아갈 목표점이 아니다. 프리셋으로 되돌리는 "프리셋 복원" 버튼은 **M2+ 후보**(M1 범위 밖).

---

## 7. 시스템 구성 (개략)

> 아래는 **개념 수준의 계층 구분**이다. 실제 개발 컴포넌트 경계(프론트↔API↔수집↔DB)와 M1 계약은 **12장 참조**.

```
[수집 계층]  채용 소스 크롤링/API  ─┐
            공시 데이터(예: DART)   ├─► [정규화·중복제거]
            회사/인재상 정보        ─┘
                                        │
[가공 계층]  요약·정리 (LLM 활용: 공시/인재상 → 자소서 관점 요약)
                                        │
[저장 계층]  공고 DB · 회사 DB · 사용자(조건/북마크/노트)
                                        │
[제공 계층]  웹 프론트엔드 (피드 / 상세 / 리서치 / 저장)
```

- **데이터 소스 후보**
  - 공고: 잡코리아·사람인·원티드·링크드인·관심 회사 채용 페이지.
  - 공시: 전자공시시스템(DART) 등 공개 공시.
  - 인재상/핵심가치: 회사 홈페이지·채용 페이지 등 공개 정보.
- **수집 방식 (결정됨)**: 3단계 폴백 전략
  1. **API 우선** — 공식 API가 있으면 무조건 API로 수집.
  2. **크롤링** — API로 가져올 수 없는 데이터는 크롤링으로 보완.
  3. **URL 전달(폴백)** — 자동 수집이 불가능하면, 최소한 사용자에게 해당 출처 URL이라도 전달.
- **법적/정책 유의**: 각 소스의 크롤링 약관·robots·이용약관 확인 필요(소스별 수집 방식 확정 시 점검).
  - **사람인 공개 API**: 재판매·대가 수취 금지. M1(단일 로컬·비상업 실습)은 무방하나, 향후 공개 서비스화 시 약관 재점검 필요.

---

## 8. 범위 (Scope)

**1차 범위 (In)**
- 공고 스크리닝(수집·중복제거·필터)
- 회사 공시/인재상 리서치 및 자소서 관점 요약
- 사용자 조건·북마크·리서치 노트 저장

**범위 밖 (Out, 향후 확장 후보)**
- 자소서 초안 작성/퇴고 보조
- 자소서 제출/지원 관리 자동화
- 합격 데이터·면접 정보 등 후속 단계

---

## 9. 단계별 로드맵

- **M1 — MVP: 공고 모아보기**
  - 1~2개 소스에서 공고 수집 → 정규화 → 조건 필터 피드 + 북마크.
  - **M1의 "모아보기" 체감** = 내 조건 필터·마감임박 정렬로 여러 사이트 순회를 대체하는 것. 실제 **중복 병합 체감은 M3 다중소스부터**(M1은 소스 1개라 중복이 발생하지 않음; 계약의 `sources[]`/`duplicateCount`는 자리만 확보).
  - **직무 범위: 개발직군 한정**(11장 결정). 온보딩 직무 선택지·사람인 job_cd 매핑을 개발직군으로 좁혀 시작.
- **M2 — 회사 리서치**
  - 공고에 회사 연결 → 공시 요약 + 인재상 정리(자소서 관점) + 리서치 노트.
  - 무거운 마일스톤이므로 **필요 시 M2a(회사-공고 연결 + 원문 URL 노출)와 M2b(LLM 요약)로 분할** 가능.
- **M3 — 다중 소스·중복 제거 고도화**
  - 소스 확장, 중복 병합 품질 개선, 마감임박 알림 등.
- **M4 — 개인화·확장**
  - 추천(내 이력 기반), 자소서 단계와의 연결 등 확장 후보 검토.

---

## 10. 성공 지표 (초안)

- 사용자가 **공고 탐색에 쓰는 시간 감소**(여러 사이트 → 한 곳).
- 공고 클릭 후 **회사 리서치까지 도달하는 비율**.
- 저장된 **북마크·리서치 노트 수**(재방문/재활용 지표).

---

## 11. 결정 사항 / 열린 질문

### 결정됨
- **수집 방식**: API 우선 → 불가 시 크롤링 → 그래도 안 되면 사용자에게 출처 URL 전달(7장 폴백 전략 참고).
- **대상 시장 범위**: 국내 한정. **국내에 있는 외국계 회사도 대상에 포함**(국내 채용 공고 기준).
- **개발 실행 구조**: 12장 참조(스택·아키텍처·M1 계약 확정).
- **M1 인증**: 실제 로그인 없이 **단일 로컬 사용자(고정 userId)** 로 진행. 정식 인증·개인화는 M2~M3에서 도입.
- **직무 영역 범위**: **M1은 개발직군 한정**으로 좁게 시작, 이후 일반 직군으로 확장(실습 규모·라벨 매핑 최소화·확장 용이).

### 열린 질문 (구현하면서 결정 — 보류)
- 공시 요약·인재상 정리에 사용할 LLM/요약 파이프라인 구체화.
- 데이터 신선도: 공고/공시 갱신 주기와 캐싱 전략.
- 인증·개인화 범위(M2+): M1 이후 로그인 도입 시점과 저장 데이터 범위.

---

## 12. 개발 실행 구조 (확정)

> "무엇을·왜"(1~11장)에 이어 "어떻게 만들 것인가"를 정의한다. backend-developer·frontend-developer는
> 이 장을 **공통 틀**로 삼는다. 계약(타입·API)이 바뀌면 이 장을 먼저 갱신한 뒤 구현한다.

### 12.1 기술 스택 (승인됨)
- **언어**: TypeScript (프론트·백·수집 통일). 타입을 그대로 contract로 공유.
- **프레임워크**: Next.js (App Router). 프론트 페이지 + 백엔드 Route Handlers를 한 앱에서.
- **DB**: SQLite (M1) + Prisma ORM. M2/M3에서 PostgreSQL로 교체(Prisma가 추상화).
- **수집**: TS 모듈(`fetch` + 필요 시 `cheerio`). 본격 크롤링용 Playwright는 M3.
- **배포**: M1은 로컬(`next dev`). 필요 시 Vercel + Neon/Supabase.

선택 기준: ① M1 가장 빨리 검증 ② 취준생 1인 실습 규모 ③ 확장 가능.

### 12.2 아키텍처 (컴포넌트 경계)
```
[제공] Next.js 단일 앱
   웹 프론트엔드(온보딩·피드·상세·저장)  ──HTTP/JSON──  백엔드 API(Route Handlers)
                                                          │  (타입 contract 공유)
[저장] Prisma ── SQLite(M1→Postgres) : Job · UserPreference · Bookmark  (Company/Note=M2)
                                                          │  upsert (정규화·dedup 후)
[가공] Collector 모듈 : Normalizer(RawJob→Job, 코드→라벨 매핑) + dedupKey 계산(병합은 M3)
                                                          │  fetchRaw(): RawJob[]
[수집] Source Adapter (공통 인터페이스) : ① SaraminAdapter(공개 API, M1) → ②크롤링(M3) → ③DART(M2)
                                          폴백: 수집 실패 시 url 만 채워 전달
   실행: M1 = 수동 `npm run collect` (배치/스케줄러는 M3)
```
- 수집은 API 서버와 **분리**된 모듈. 사용자 요청은 항상 DB만 읽음(빠르고 안정적).
- 새 소스 추가 = 어댑터 1개 추가. 폴백 전략(API→크롤링→URL)을 어댑터 내부에서 흡수.
- 수집 파이프라인 세부 계약(어댑터 시그니처·Normalizer·dedupKey·수집 스위치)은 **12.8 참조**.

### 12.3 데이터 스키마 (저장 — Prisma 개념)

**Job** (정규화 공통 스키마)
| 필드 | 타입 | 비고 |
|---|---|---|
| id | string | 내부 안정 ID |
| source | string | 수집 소스("saramin" 등) |
| sourceJobId | string | 소스 원본 ID |
| url | string | 원문 출처 URL(폴백 시에도 항상 채움) |
| title | string | 공고/직무명 |
| companyName | string | 회사명 |
| companyId | string \| null | M2 회사 리서치 연결용(M1은 null) |
| jobRole | string \| null | 직무 분류(코드→라벨 매핑됨) |
| location | string \| null | 지역(코드→라벨 매핑됨) |
| experienceLevel | "NEW"\|"EXPERIENCED"\|"ANY" | 신입/경력/무관 |
| employmentType | string \| null | 정규직 등 |
| deadline | string \| null | ISO date. null=상시채용/미정 |
| postedAt | string \| null | ISO date |
| description | string \| null | 직무 요건. **사람인 API는 본문 미제공 → 보통 null**(본문 수집은 M2/M3) |
| dataQuality | "FULL"\|"PARTIAL" | 자동수집 완성도. PARTIAL=핵심 필드 누락 |
| dedupKey | string | `회사+직무+지역`(마감일 null은 키에서 제외). **unique 아님**, 계산·저장만 |
| collectedAt | string | 수집 시각 ISO |

- **UNIQUE 제약은 `(source, sourceJobId)` 단 하나** (재수집 idempotent upsert 키 겸용).
  dedupKey에 unique를 걸지 않는다(상시채용·다지역 동일직무를 한 건으로 뭉개 정상 공고가 사라지는 것 방지). 실제 중복 병합은 M3.
- `isBookmarked`는 Job 테이블 컬럼이 **아님** → API 응답 DTO에서 Bookmark join으로 계산.

**Bookmark**
| 필드 | 타입 | 비고 |
|---|---|---|
| id | string | bookmarkId |
| jobId | string | FK → Job |
| status | "PLANNED"\|"APPLIED"\|"CLOSED" | 지원예정/지원함/마감 |
| memo | string \| null | 가벼운 메모(정식 리서치 노트는 M2) |
| createdAt | string | ISO |

**UserPreference** (M1은 단일 로컬 사용자 1행)
`{ roles: string[]; locations: string[]; experience: "NEW"|"EXPERIENCED"|"ANY"; keywords: string[] }`

### 12.4 응답 DTO (프론트가 받는 형태)
```ts
type JobDTO = Job & {
  sources: string[];        // M1은 [source] 1개. M3 중복 병합 시 복수(계약 변경 불필요)
  duplicateCount: number;   // 묶인 중복 수(M1=1). "여러 사이트를 한 곳에서" 체감용
  bookmark: { bookmarkId: string; status: BookmarkStatus } | null; // null=미저장
};
```

### 12.5 API 엔드포인트 (M1)
| 메서드·경로 | 요청 | 응답 |
|---|---|---|
| GET /api/jobs | query: `role(다중 가능, 콤마), location(다중 가능, 콤마), experience(다중 가능), keyword, sort(deadline\|recent), deadlineWithin(days), includeExpired(기본 false), cursor` | `{ items: JobDTO[], nextCursor: string\|null, totalCount: number, partialHiddenCount: number }` |
| GET /api/jobs/:id | — | `JobDTO` (description null이면 프론트는 원문 URL 폴백을 1급 요소로) |
| GET /api/me/preferences | — | `UserPreference` |
| PUT /api/me/preferences | `{ roles, locations, experience, keywords }` | `UserPreference` |
| GET /api/bookmarks | query: `status?` (includeExpired 무시, 마감도 표시) | `{ items: JobDTO[] }` |
| POST /api/bookmarks | `{ jobId }` | `{ bookmarkId, status:"PLANNED" }` |
| PATCH /api/bookmarks/:id | `{ status }` | `{ bookmarkId, status }` |
| DELETE /api/bookmarks/:id | — | 204 |

규약: 날짜=ISO 8601 문자열, 페이지네이션=커서 방식, 에러=`{ error: { code, message } }`+HTTP status, 빈 결과는 에러 아님(`items: []`).

### 12.6 정렬·필터 규약 (양쪽 합의)
- **마감 지난 공고는 기본 제외**(`includeExpired=false`). 단 GET /api/bookmarks는 includeExpired 무시(마감도 표시).
- **마감임박순(sort=deadline)**: 커서는 `(deadline, id)` 복합. `deadline=null`(상시채용)은 **항상 맨 뒤**, 프론트는 "상시" 뱃지.
- **최신순(sort=recent)**: `postedAt` **내림차순**. `postedAt=null`은 **항상 맨 뒤**(deadline 규약과 대칭), 커서는 `(postedAt, id)` 복합.
- **PARTIAL 공고**: 조건 필터 시 null 필드 때문에 전부 사라지지 않도록, 필터로 가려지는 PARTIAL 공고 수를 `partialHiddenCount`로 반환 → 프론트는 "조건 확인 어려운 공고 N건"을 접이식으로 노출(모아보기 가치 보호).
  - **두 경우를 구분한다**: ① **결과에 포함된 PARTIAL**(필터엔 걸렸으나 일부 필드 null) = **전용 카드**(원문 직접 확인 CTA). ② **필터로 가려진 PARTIAL**(필터 축 값이 null이라 확인 불가로 빠진 것) = `partialHiddenCount` **카운트 넛지만 노출**(항목 데이터 미포함·카드 확장 없음). 가려진 항목을 카드로 펼치면 필터에 맞지 않는 공고를 피드에 섞어 필터 신뢰를 깨므로, 계약(`JobsListResponse`) 확장 없이 카운트+필터 완화 안내에 그친다.
- **집계 기준**: `totalCount` = 필터·`includeExpired` 적용 후 매칭된 전체 수(**PARTIAL 숨김 반영 전**). `partialHiddenCount`는 그중 필터로 가려진 PARTIAL 수(`totalCount`의 부분집합). 프론트의 "결과 N건"은 `totalCount`를 쓴다.
- 필터 다중값 허용(콤마, 값 간 **OR/합집합**): `role=backend,fullstack`, `location=서울,경기`, `experience` 복수. 온보딩에서 직무를 복수 선택하면 피드 프리셋의 `role`에 합집합으로 반영된다(12.4 흐름과 일관).
- **미지의 필터값은 무시**(에러 아님): 카탈로그에 없는 `role`/`location`/`experience` 값이나 빈 값은 조용히 무시한다(HTTP 500 금지). 모든 값이 무시되어도 정상 응답(`items: []`)으로 반환한다.

### 12.7 M1 작업 분배·순서
- **backend**: 스캐폴딩 → Prisma 스키마 → **타입 export + Mock seed 공개(프론트 unblock)** → SaraminAdapter(API 우선, 약관/robots 점검) → Normalizer(코드→라벨, **개발직군 job_cd 한정**)+dedupKey → API. 사람인 API는 이용신청→승인 + 하루 500콜·요청당 count≈110 상한 → day-1은 mock, 승인 후 실수집 교체.
  - **B-1 어댑터 소스 비종속**: SaraminAdapter를 특별 취급하지 말고 공통 `SourceAdapter` 인터페이스만 준수한다. 사람인 API 승인 지연/실패 시 다른 소스 어댑터로 즉시 교체 가능하게(구조적 보험).
  - **A-3 회사 식별 힌트 보존**: M1 수집 시 회사 식별 가능한 원본 필드(사업자번호·법인명 원문 등이 사람인 응답에 있으면)를 버리지 말고 raw로라도 보존한다(M2 DART 공시 연결 대비).
- **frontend**: 온보딩 → 피드(카드·필터·마감임박순·북마크 토글·상태 뱃지) → 상세(요건+리서치 진입점 placeholder+원문 폴백) → 저장(상태 관리) → 빈/로딩/에러+폴백 UX.
- **순서**: ①기획 계약 확정(본 장) → ②backend 타입+Mock 공개 → ③frontend·backend 병렬 → ④Mock→실 API 교체로 통합. **M1 완료 기준 = "온보딩→피드→북마크"가 끝까지 도는 것.**

### 12.8 수집 파이프라인 계약 (M1 실수집 선작업 — 승인 대기 중 fixture 기반)

> 사람인 API 승인 대기(⛔)와 무관하게 진행 가능한 선작업의 계약. **백엔드 전담**(프론트 영향 없음 —
> `src/types/contract.ts` 변경 불필요, `JobDTO`/API 8종 그대로). 승인 후에는 환경변수 하나로 실수집 전환.

**(1) SourceAdapter 인터페이스 — 기존 확정(코드가 원본)**
- 단일 출처: `src/lib/collect/source-adapter.ts` 의 `SourceAdapter`(`source: string` + `fetchRaw(params?): Promise<RawJob[]>`)와 `RawJob`. 이 파일이 수집 계층 타입의 원본이며 12.2 B-1(소스 비종속)을 따른다.
- `SaraminAdapter`는 **fetch 함수를 주입받는다**: `new SaraminAdapter({ accessKey, fetchFn = globalThis.fetch })`. fixture 테스트는 가짜 fetchFn 주입으로 **실 파싱 코드를 그대로** 태운다.
- 사람인 job-search 응답 → RawJob 매핑: `id→sourceJobId`, `url→url`, `position.title→title`, `company.detail.name→companyName`, `position."job-code".code→jobRoleCode`, `position.location.code→locationCode`, `position."experience-level".code→experienceRaw`, `position."job-type".name→employmentType`, `expiration-date→deadline`, `posting-date→postedAt`, **원본 job 객체 전체→raw**(A-3). 필드명·구조는 승인 후 실응답으로 최종 검증.
- **[유보 — 다음 소스 추가 시 개정 검토]** 현재 Normalizer 의 name 기반 라벨 매핑은 `raw.position.*.name` 을 직접 참조한다(사람인 단일 소스라 허용). 소스가 늘어나면 raw 구조가 소스마다 달라지므로, **두 번째 소스 어댑터 추가 시점**에 RawJob 에 `jobRoleName`/`locationName` 정규 필드 승격을 검토한다(M3 소스 확장의 선행 과제).
- 요청 규약: `job_mid_cd=2`(IT개발·데이터) 고정, `count=110`, `start` 페이지 순회. 쿼터(하루 500콜) 보호를 위해 M1 수집은 **1회 실행당 최대 5콜** 상한.

**(2) Normalizer 입출력 (신규 확정)**
- 파일: `src/lib/collect/normalizer.ts` (신규).
- 시그니처: `normalizeRawJob(raw: RawJob): JobUpsertInput`
  - `JobUpsertInput` = 계약 `Job`에서 `id`·`collectedAt`·`companyId` 제외 + `rawData: string | null`(raw 를 JSON.stringify). 날짜는 ISO 문자열이며 upsert 직전에 Date 변환(수집 진입점 책임).
- **라벨 매핑은 코드표가 아니라 응답의 name 필드 기반**(M1 결정): 사람인 응답의 `job-code.name`·`location.name` 문자열을 키워드 테이블로 `DEV_ROLE_OPTIONS.value`(7종)·`LOCATION_OPTIONS.value` 라벨에 매핑. 매핑 실패 시 null(전체 코드표 유지 부담 제거, code 원문은 raw에 보존). `contract.ts`의 `DevRoleOption.code`는 계속 placeholder 유지.
- experienceRaw 매핑: 사람인 experience-level code `0(무관)→ANY`, `1(신입)→NEW`, `2(경력)→EXPERIENCED`, `3(신입/경력)→ANY`. 해석 실패 → `ANY` + PARTIAL.
- **dataQuality 판정**: 다음 중 하나라도 해당하면 `PARTIAL` — title 누락(→ `"(제목 미확인 공고)"` 대체 저장), companyName 누락(→ `"(회사 미확인)"`), jobRole null, location null, experienceRaw 해석 실패. **deadline null(상시채용)과 description null(사람인 API 특성)은 PARTIAL 사유가 아님.**

**(3) dedupKey 계산 규칙 (신규 확정 — 12.3 "회사+직무+지역" 구체화)**
- `dedupKey = normCompany + "|" + (jobRole ?? "") + "|" + (location ?? "")`
- `normCompany` = companyName 에서 `"(주)"`, `"㈜"`, `"주식회사"` 제거 → 모든 공백 제거 → 소문자화.
- unique 아님(12.3). 헬퍼 `computeDedupKey(companyName, jobRole, location)` 를 normalizer 에서 export.

**(4) 수집 소스 스위치 — 환경변수 (신규 확정)**
- `COLLECT_SOURCE` = `mock`(기본) | `saramin-fixture` | `saramin`. `scripts/collect.ts` 가 이 값으로 어댑터를 선택.
  - `saramin-fixture`: SaraminAdapter 에 로컬 fixture 를 반환하는 가짜 fetchFn 주입 → **실 파싱·정규화·upsert 경로 전체를 승인 전에 검증**.
  - `saramin`: 실 API 호출. `SARAMIN_ACCESS_KEY` 필수(없으면 즉시 명확한 에러로 종료, 조용한 폴백 금지).
- fixture 위치: `src/lib/collect/fixtures/saramin-job-search.json` — 사람인 job-search 응답 형태(`{ jobs: { count, start, total, job: [...] } }`), 개발직군 5~10건 + **필드 누락 PARTIAL 케이스 최소 2건** 포함.
- 수집 진입점 파이프라인(고정): `adapter.fetchRaw()` → `normalizeRawJob()` → `prisma.job.upsert({ where: { source_sourceJobId } })`(idempotent) → 수집 요약 로그(총·FULL·PARTIAL 건수). **고정 규약은 mock 에도 동일 적용**(mock 만 upsert 생략 금지 — 경로 분기는 실전환 시 검증 공백을 만든다).
- **mock 데이터 정합 규약**: MockAdapter 데이터는 seed 행과 upsert 키(`source, sourceJobId`)가 겹칠 수 있으므로, normalize 시 **FULL 판정이 가능한 힌트(name·description 등)를 포함**해야 한다 — 기본 `npm run collect` 가 seed 된 FULL 행을 PARTIAL 로 강등시키지 않기 위함.
