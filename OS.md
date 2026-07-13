# Claude OS 청사진

나만의 Claude Code 운영체제 — 반복 작업을 자동화하고 개발 흐름을 끊기지 않게 만드는 시스템.

---

## 핵심 철학

> "귀찮은 건 Claude가, 판단이 필요한 건 내가"

개발자가 직접 해야 하는 것(코드 작성, 기술 판단)에 집중하고,
반복·전달·확인 작업은 Claude OS가 대신한다.

---

## 전체 구조

```
my-claude-code-os/
├── CLAUDE.md              # Claude 행동 규칙 (OS의 커널)
├── OS.md                  # 이 파일 — 전체 청사진
└── .claude/
    ├── settings.json      # 훅 설정 (이벤트 기반 자동 실행)
    ├── docs/              # 공용 규칙 문서 (스킬이 필요할 때 참조)
    │   ├── commit-conventions.md        # 커밋 메시지 형식, scope 기준
    │   ├── code-conventions.md          # 코드 스타일, 네이밍, 패턴 규칙
    │   └── project-domain-detection.md  # 프로젝트 도메인 파악 절차
    ├── skills/            # 스킬 (재사용 가능한 작업 단위)
    │   ├── ticket-start/  # 티켓 시작 워크플로
    │   ├── task-impl/     # 개발 단위 분해 + 구현 + 커밋 루프
    │   ├── dev-test/      # 테스트 루프 + 자동 수정
    │   ├── dev-pr/      # 리뷰 루프 + 자동 수정 + PR 생성
    │   ├── dev-loop/      # dev-test → dev-pr 오케스트레이터
    │   ├── retrospect/    # 티켓 회고 — 가정 검증 + 규칙 승격 (리포트는 docs/retrospects/ 누적)
    │   ├── deploy-notify/ # 파이프라인 단계 관찰 알림
    │   ├── auto-commit/   # 커밋 자동화 (구현 완료)
    │   └── skill-stats/   # 스킬 사용 통계 (구현 완료)
    ├── skill_calls.log    # 스킬 호출 이력
    └── memory/            # 컨텍스트 영속화
        ├── MEMORY.md      # 메모리 인덱스
        ├── user_*.md      # 나에 대한 정보
        ├── project_*.md   # 프로젝트 맥락
        └── feedback_*.md  # Claude 행동 교정 기록
```

---

## 레이어 구조

```
┌──────────────────────────────────┐
│  CLAUDE.md (행동 규칙)             │  Claude가 어떻게 행동할지 정의
├──────────────────────────────────┤
│  Skills (작업 단위)                │  /ticket-start, /deploy-notify 등
├──────────────────────────────────┤
│  Hooks (이벤트 트리거)              │  특정 명령 실행 시 자동 동작
├──────────────────────────────────┤
│  Memory (컨텍스트 영속화)            │  대화 끊겨도 맥락 유지
├──────────────────────────────────┤
│  MCP 연동 (외부 시스템)              │  Notion, Slack, GitHub 등
└──────────────────────────────────┘
```

---

## 자동화 대상 워크플로

### 1. 티켓 시작 워크플로 — `/ticket-start`

**문제:** 티켓 받으면 기획서 읽고, 어디 고쳐야 하는지 파악하고, 사이드 이펙트 생각하고, Notion 상태 바꾸는 게 전부 수동

**목표:** 기획서 소스 하나 주면 아래를 자동으로

```
input:  Notion URL | Slack URL | 파일 첨부 | 일반 HTTP URL
          ↓
        프로젝트 도메인 파악 (project-domain-detection.md 절차)
          ↓
        소스 감지 → 적절한 방법으로 기획서 읽기
        (Notion MCP | Slack MCP | Read 도구 | WebFetch)
          ↓
        기획서 분석
          ↓
        충돌/미정의 정책 있으면 사용자에게 질문 (AskUserQuestion)
          ↓
        사용자 응답을 통해 수정 범위 및 미정의된 정책 정리
          ↓
        코드베이스 스캔 → 영향받는 파일/컴포넌트 목록
          ↓
        사이드 이펙트 체크리스트 생성
          ↓
output: 결과 md 파일 및 작업 브리핑 출력 (수정 범위, 사이드 이펙트 후보)
```

**구현 완료:**

- [x] SKILL.md 작성 (v3.0, spec-analyzer 에이전트 위임 구조)
- [x] 코드베이스 스캔 프롬프트 설계 (Explore 서브에이전트)
- [x] 사이드이펙트 + QA 체크리스트 포맷 정의 및 자동 저장
- [x] 0단계 프로젝트 도메인 파악 추가
- [x] 1.5단계 충돌/미정의 정책 사용자 질문 추가
- [ ] Notion MCP 연동 확인 (실제 프로젝트 적용 시 검증 필요)

---

### 1.5. 개발 단위 분해 + 구현 루프 — `/task-impl`

**문제:** ticket-start가 브리핑을 줘도, "그래서 무엇부터 어떻게 짤지"는 여전히 수동이고 중간 커밋도 제때 안 됨

**목표:** 브리핑 결과를 받아 개발 단위로 쪼개고, 단위별로 구현 → 커밋까지 자동으로

```
input:  ticket-start의 작업 브리핑
        (수정 범위, 영향 파일 목록, 사이드 이펙트 체크리스트)
          ↓
        태스크 분해
        - 영향 범위를 기능 / 레이어 / 파일 단위로 쪼개기
        - 각 태스크마다 "무엇을 어디서 어떻게" 명시
        - 의존성 기준으로 실행 순서 결정
          ↓
        태스크 목록 출력 + 사용자 확인
        (수정 / 추가 / 순서 변경 기회 제공)
          ↓
        태스크 목록을 docs/tasks.md에 저장 (진행 상태의 단일 원본)
          ↓
        [태스크 루프 — 규모에 따라 선택]
        직접 실행: 태스크 1 → 구현 → 검토 → auto-commit → 태스크 2 → ...
        위임 모드: 독립 태스크들을 병렬 에이전트로 실행
        랄프 모드: /loop /task-impl 랄프 반복 — 반복마다 새 컨텍스트에서
                   tasks.md 읽기 → 태스크 하나 구현·커밋·체크 → 종료,
                   전부 완료 시 DONE 출력으로 루프 정지
          ↓
output: 모든 태스크 커밋 완료
        + 커밋 이력 요약 (태스크 ↔ 커밋 SHA 매핑)
        + /dev-loop 진입 안내
```

**구현 완료:**

- [x] 태스크 분해 프롬프트 설계 (논리적 완결성/의존성/파일 응집도/크기 기준)
- [x] 태스크 목록 포맷 정의 (번호, 제목, 대상 파일, 의존 관계 테이블)
- [x] 사용자 확인 단계 설계 (수정/추가/순서 변경 허용)
- [x] 태스크별 구현 → auto-commit 루프 (직접 실행 + 에이전트 위임 모드)
- [x] 커밋 이력 요약 포맷 정의 (SHA 매핑 테이블)
- [x] `docs/tasks.md` 영속화 — 체크박스 + SHA + 메모(가정/이탈/보류만) 포맷
- [x] 랄프 모드 — 외부 루프(/loop) 기반 반복 실행, 질문 대신 가정 기록/보류 규칙, DONE/BLOCKED 정지 신호

---

### 2. 개발 루프 자동화 — `/dev-test` + `/dev-pr` + `/dev-loop`

**문제:** 개발 중 커밋, 셀프 리뷰, 테스트 실행, PR 생성까지 반복 작업이 많고 흐름이 자주 끊김

**목표:** 두 단계로 분리해 테스트와 리뷰를 독립 실행 가능하게

```
[Phase 1] /dev-test
input:  /dev-test (개발 완료 후 호출)
          ↓
        테스트 실행 (static-code-tester 에이전트)
        + Playwright QA (qa-checklist.md 기반 또는 diff 기반 스모크)
          ↓
        실패 시: 자동 수정 → 커밋 → 재실행 (최대 3회 루프,
        재실행은 실패 항목만 → 통과 시 전체 1회 최종 검증)
          ↓
output: 테스트 결과 출력
        "코드 리뷰와 PR 생성은 /dev-pr을 실행하세요" 안내

[Phase 2] /dev-pr
input:  /dev-pr (테스트 통과 후 호출)
          ↓
        code-reviewer 에이전트로 새 리뷰 (항상 fresh 실행)
          ↓
        CRITICAL 이슈 있으면: 자동 수정 → 커밋 → 재실행 (최대 3회 루프)
          ↓
        CRITICAL 이슈 없으면: PR 생성
        (프로젝트 PR 템플릿 감지 → 없으면 기본 템플릿)
          ↓
output: PR 생성 (브랜치 push + gh pr create)
        + 리뷰 결과 요약 출력

[오케스트레이터] /dev-loop
        /dev-test → 성공 시 → /dev-pr 순서 실행
        (리뷰는 어차피 dev-pr에서 반드시 거치므로 dev-test에서는 빼고 테스트에만 집중)
```

**구현 완료:**

- [x] `/dev-test` 스킬 — 테스트 루프 (코드 리뷰는 dev-pr로 이관)
- [x] `/dev-pr` 스킬 — code-reviewer 루프 + PR 생성
- [x] `/dev-loop` 오케스트레이터 — dev-test → dev-pr 순차 호출
- [x] 테스트 실행 명령어 감지 로직 (package.json / Makefile 등)
- [x] PR 템플릿 감지 및 적용 (프로젝트 템플릿 우선, 없으면 기본 템플릿 폴백)

---

### 2.5. 회고 — `/retrospect`

**문제:** 티켓이 끝나도 가정 검증·반복 실수 정리가 안 됨. 랄프 모드의 가정 메모는 DONE 후 아무도 확인하지 않고, 리뷰 지적은 저장되지 않아 티켓마다 같은 지적이 반복됨

**목표:** 티켓 산출물을 모아 가정을 검증하고, 반복 패턴을 규칙으로 승격

```
input:  /dev-pr 완료 시 자동 호출 | /retrospect 수동 실행
          ↓
        재료 수집 (있는 것만)
        - docs/tasks.md 메모 (가정/이탈/보류)
        - docs/ticket-briefing.md, docs/interview-spec.md
        - .claude/qa-report.md, .claude/review-report.md
        - docs/retrospects/ 이전 리포트 (반복 패턴 비교 대상)
          ↓
        분석
        - 가정 검증: 사용자에게 맞았는지 확인 (AskUserQuestion)
        - 보류/이탈 정리: 사람 판단 필요 목록
        - 반복 패턴 탐지: 이슈 유형 누적 2회 이상 → 규칙 승격 후보
          ↓
        규칙 승격 제안 (후보 있을 때만)
        - 코드 관련 → code-conventions.md / 행동 관련 → CLAUDE.md
        - 사용자 승인 후에만 append
          ↓
output: docs/retrospects/YYYY-MM-DD-<브랜치>.md 저장 (누적)
        + 다음 액션 목록 (틀린 가정 후속 조치 등)
```

**구현 완료:**

- [x] `retrospect` 스킬 구현 (재료 수집 → 가정 검증 → 리포트 누적 저장 → 규칙 승격 제안)
- [x] `dev-pr` v1.1 — 리뷰 결과 `.claude/review-report.md` 영속화 + PR 생성 후 retrospect 자동 호출

---

### 3. 배포 알림 워크플로 — `/deploy-notify`

**문제:** CodePipeline이 Build → Approval → Deploy로 넘어가는 동안 콘솔을 계속 들여다보고 있어야 함

**목표:** `/deploy-notify` 한 번 실행하면 알아서 루프를 돌며 N분마다 현재 파이프라인 단계를 알림 (Slack/Notion 업데이트는 범위 밖)

```
input:  /deploy-notify (파이프라인 이름 지정, 주기 N분 — 기본 3분)
          ↓
        스킬 내부에서 /loop Nm 자동 시작
          ↓
        aws codepipeline get-pipeline-state 주기 조회
          ↓
output: PushNotification으로 현재 단계 알림 (매 주기마다)
```

**구현 완료:**

- [x] AWS CLI 인증 확인 (`codepipeline:GetPipelineState` 권한) — 사전 검증 1단계에서 단일 호출로 확인
- [x] 파이프라인 이름 / 알림 주기(N분) 지정 방식 정의 — `/deploy-notify <이름> [N분]` 인자
- [x] 스킬 실행 시 `/loop` 자동 트리거 — Skill 도구로 `loop`를 직접 호출 (task-impl 랄프 모드의 "안내만 출력하고 종료" 방식과 다르게, 조회 전용이라 자동 시작이 안전하다고 판단)
- [x] 파이프라인 종료(성공/실패) 감지 시 루프 자동 종료 조건 — 관찰 반복마다 스테이지 상태 판정 후 종료 상태면 `DONE` 출력

**한계 (의도적으로 감수):**

- 세션(터미널)이 열려 있는 동안만 동작 — 상시 인프라 아님
- N분 간격 폴링이라 그만큼 지연 있음
- 실행한 사람에게만 알림

---

## 구현 순서 (로드맵)

| 단계     | 내용                                                                                                            | 상태    |
| -------- | --------------------------------------------------------------------------------------------------------------- | ------- |
| Step 0   | 기본 인프라 (settings.json, auto-commit, skill-stats)                                                           | ✅ 완료 |
| Step 1   | `/ticket-start` 스킬 구현                                                                                       | ✅ 완료 |
| Step 1.5 | `/task-impl` 스킬 구현 (태스크 분해 + 구현 루프 + 단위 커밋)                                                    | ✅ 완료 |
| Step 2   | `/dev-loop` 스킬 구현 (셀프 리뷰, 테스트, 커밋, PR 자동화)                                                      | ✅ 완료 |
| Step 2.5 | `spec-analyzer` 에이전트 분리 + `ticket-start` v3.0 리팩토링                                                    | ✅ 완료 |
| Step 2.6 | `/dev-loop` PR 템플릿 자동 감지 — 프로젝트 템플릿 우선 적용                                                     | ✅ 완료 |
| Step 2.7 | `ticket-start` QA 체크리스트 생성 — 기획서 시나리오 → Playwright 실행 가능 포맷으로 `docs/qa-checklist.md` 저장 | ✅ 완료 |
| Step 2.8 | `dev-loop` Playwright QA 실행 — `docs/qa-checklist.md` 기반 체크리스트 순회 + PR 본문 자동 반영                 | ✅ 완료 |
| Step 2.9 | `/dev-loop` 분리 — `/dev-test`(테스트+리뷰) + `/dev-pr`(리뷰루프+PR) + `/dev-loop`(오케스트레이터)            | ✅ 완료 |
| Step 2.10 | `task-impl` 랄프 모드 — `docs/tasks.md` 영속화 + 외부 루프(/loop) 반복 실행                                    | ✅ 완료 |
| Step 2.11 | `/dev-test` 코드 리뷰 단계 제거 — 어차피 `/dev-pr`에서 반드시 리뷰하므로 `dev-test`는 테스트 통과에만 집중       | ✅ 완료 |
| Step 3   | `/deploy-notify` 스킬 구현 (실행 시 자동 `/loop` 관찰 + N분마다 단계 알림)                                      | ✅ 완료 |
| Step 4   | 배포 명령 감지 훅 자동화                                                                                        | 🔲 예정 |
| Step 5   | Memory 시스템 구축                                                                                              | 🔲 예정 |
| Step 6   | CLAUDE.md 고도화 (페르소나, 금지사항 정교화)                                                                    | 🔲 예정 |

---

## 목표 지표 (프로젝트별 루브릭)

**원칙:** 루브릭 기준은 여기(OS.md)에 한 번만 정의한다. 채점은 각 프로젝트에 배포된 스킬(`retrospect`, `skill-stats`)이 **그 프로젝트의 로컬 파일**(`.claude/skill_calls.log`, `docs/tasks.md`, `.claude/review-report.md`, `docs/retrospects/`)만 읽어서 수행한다. 여러 프로젝트를 이 레포로 모아 보는 중앙 집계는 하지 않는다 — 필요해지면 그때 추가.

| 지표 | 측정 소스 (프로젝트 로컬) | 상 (3점) | 중 (2점) | 하 (1점) |
|---|---|---|---|---|
| 자동화 커버리지 | `.claude/skill_calls.log` 호출 빈도 | 로드맵 스킬의 80%+ 최근 30일 내 1회 이상 호출 | 50~79% | 50% 미만 |
| 개입 빈도 | `docs/tasks.md`의 가정/이탈/보류 메모 개수 | 티켓당 평균 2회 이하 | 3~5회 | 6회 이상 |
| 재작업률 | `.claude/review-report.md` CRITICAL 재시도 횟수 | 평균 1회 이하 | 2회 | 3회 이상 |
| 반복 실수 감소 | `docs/retrospects/*.md` 신규 반복 패턴 승격 건수 | 티켓당 0건 | 1건 | 2건 이상 |

**채점 시점:** `retrospect` 스킬 실행 시 함께 채점해 `docs/retrospects/scorecard.md`에 누적. 별도 주기(월간 등)를 두지 않는다 — 새 트리거를 만들면 그 자체가 유지보수 대상이 됨.

---

## 미결 질문 (구현 전 확인 필요)

- [ ] 티켓 관리: Notion이 source of truth인가, Slack인가?
- [ ] 배포 방식: 터미널 명령어인가, CI/CD인가, Vercel 등 플랫폼인가?
- [ ] Slack 배포 알림 채널 이름은?
- [ ] Notion 티켓의 상태 필드 이름은? ("진행중", "완료" 등 실제 값)
