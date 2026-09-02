# 나의 Claude Code OS — 청사진

> 이 문서는 **먼저 정하고 시작하는 설계도**다.
> 구현(`.claude/`, `maintenance/`)이 이 문서를 따르며, 방향이 바뀌면 코드보다 이 문서를 먼저 고친다.

**목차**

1. [OS 생성 목적](#1-OS-생성-목적)
2. [어떤 흐름으로 진행되는지](#2-어떤-흐름으로-진행되는지)
3. [빌딩블록 구성](#3-빌딩블록-구성)
4. [성공 기준](#4-성공-기준)
5. [설계 원칙](#5-설계-원칙)
6. [로드맵](#6-로드맵)
7. [열린 질문 / 결정 대기](#7-열린-질문--결정-대기)

---

## 1. OS 생성 목적

### 배경

IT 담당자로서 여러 시스템의 유지보수 요청을 매일 처리한다.
요청이 들어오면 아래 흐름을 혼자서 반복한다.

1. 요청 내용 파악 및 담당자 면담
2. 내부 처리 가능 여부 판단
3. 기획 문서(스펙) 작성
4. 외주 개발사 요청 또는 직접 개발
5. 테스트 및 배포

### 문제

가장 반복적이고 소모적인 구간은 **"요청 접수 → 분류 → 기획 초안"** 이다.
이 구간에서 매번 세 가지가 샌다.

| 새는 곳 | 내용 |
| --- | --- |
| **분류가 들쭉날쭉** | 내부 처리 / 외주 판단 기준이 암묵지로만 있어 매번 처음부터 생각한다. |
| **완료 기준이 모호** | "됐다"의 정의가 요청마다 달라, 누락 항목이 배포 후에야 발견된다. |
| **맥락 재조사 낭비** | 관련 코드·패턴·과거 이력을 요청마다 다시 훑는다. |

### 목적

이 반복 흐름을 **AI 에이전트 구조**로 설계해 처리 속도와 정확도를 높인다.
핵심은 암묵지를 **정해진 단계 + 검증 가능한 완료 기준 + 공유 컨텍스트 수집**이라는
문서화된 절차로 바꾸는 것이다.

> **목표** — 유지보수 요청의 내부 처리 비율을 높이고, 외주 의뢰 건수를 줄인다.

### 무엇으로 만드나

Claude Code 위에서 도는 개인용 "운영체제". 반복 작업을 세 가지 빌딩블록으로 규격화한다.

| 빌딩블록 | 성격 | 예 |
| --- | --- | --- |
| **스킬** (`/명령어`) | 사람이 부르는 절차. 상태를 바꾼다 (파일·코드·커밋) | `/intake`, `/spec` |
| **서브에이전트** | 스킬이 위임하는 판단·조사. 읽기 전용 결과만 반환 | `classifier`, `context-loader` |
| **훅** | 특정 이벤트에 자동 실행되는 기록·검사 | 스킬 사용량 집계 |

> 부차 목적 — 이 구조를 직접 조립해 보며 AI 협업 방식을 익힌다 (`CLAUDE.md` 규칙 2).
> 그래서 각 산출물에는 "왜 이렇게 했는지"를 함께 남긴다.

---

## 2. 어떤 흐름으로 진행되는지

### 2-1. OS를 **쓰는** 흐름 — 유지보수 요청 처리

```
요청 접수
  │  /intake  "<요청 내용>"
  │    ├─ intake-interview  → 빠진 정보 있으면 담당자에게 질문
  │    └─ classifier        → internal / outsource + 규모 S·M·L
  ▼
분류 (classification)
  ├─ internal ─▶ /spec ─▶ /implement ─▶ /verify ─┬─ 통과 ─▶ done ─▶ /handoff ─▶ handed_off
  │              │  ▲                            └─ 실패 ─▶ blocked ─▶ /implement 재시도
  │        spec-reviewer   └── 범위가 커지면 스펙부터 수정
  │        (초안 검토)
  └─ outsource ─▶ /outsource ─▶ 외주 요청서 발행 ─▶ outsourced

/status  ── 어느 시점에서든 현황 조회 (읽기 전용)
```

- 요청 1건 = `maintenance/requests/REQ-XXX.md` 1개. 모든 단계가 이 한 파일에 누적된다.
- `/spec` · `/implement` · `/verify` 는 저장소 맥락을 **`context-loader`** 서브에이전트로
  똑같이 모은다 — 스킬마다 제각각 훑어 생기는 불일치를 없앤다.
- 세션을 시작하면 **`SessionStart` 훅**이 진행 중인 요청(끝나지 않은 것)을 자동 브리핑한다.

### 2-2. OS를 **만드는** 흐름 — 미션 진행 (`README.md`)

```
주차별 요구사항 파악 ─▶ 구현 ─▶ 자기 브랜치에 PR ─▶ 리뷰 피드백 반영 ─▶ merge ─▶ 다음 Step
```

- 작업 브랜치는 Step 단위(`step1`, `step2`, …), 리뷰는 PR로 받는다.
- 이 청사진의 [로드맵](#6-로드맵)이 Step과 대응한다.

---

## 3. 빌딩블록 구성

| 종류 | 이름 | 역할 | 위치 | 상태 변경 |
| --- | --- | --- | --- | :---: |
| 스킬 | `/intake` | 요청 접수 → `intake-interview`·`classifier` 호출 → 케이스 파일 생성·분류 | `.claude/skills/intake/` | O |
| 스킬 | `/spec` | 내부 처리 요청의 구현 스펙 작성 → `spec-reviewer` 로 검토 | `.claude/skills/spec/` | O |
| 스킬 | `/implement` | 스펙대로 코드 구현 + 구현 로그 | `.claude/skills/implement/` | O |
| 스킬 | `/verify` | 완료 기준을 하나씩 검증 → `done` / `blocked` | `.claude/skills/verify/` | O |
| 스킬 | `/handoff` | 완료(`done`) 요청의 배포 노트·담당자 통보문 작성 → `handed_off` | `.claude/skills/handoff/` | O |
| 스킬 | `/outsource` | 외주 요청서(브리프) 작성 | `.claude/skills/outsource/` | O |
| 스킬 | `/status` | 요청 현황 조회 (전체 표 / 단건 상세 / 상태 필터) | `.claude/skills/status/` | X |
| 스킬 | `/git-commit` | 안전장치 있는 커밋·푸시 (한글 Conventional Commits, 시크릿 스캔) | `.claude/skills/git-commit/` | O |
| 스킬 | `/skill-stat` | 훅이 쌓은 스킬 호출 데이터를 통계로 표시 | `.claude/skills/skill-stat/` | X |
| 서브에이전트 | `classifier` | 접수 내용으로 `internal` / `outsource` 판단 + **규모 S·M·L** + 근거·신뢰도 | `.claude/agents/classifier.md` | X |
| 서브에이전트 | `context-loader` | `REQ-ID` + phase 로 "컨텍스트 팩"(관련 파일·패턴·테스트·설정) 수집 | `.claude/agents/context-loader.md` | X |
| 서브에이전트 | `intake-interview` | 요청 원문에서 빠진 정보를 파악해 담당자 면담 질문 목록 생성 | `.claude/agents/intake-interview.md` | X |
| 서브에이전트 | `spec-reviewer` | 스펙 초안을 구현 착수 전에 검토 (완료 기준·범위·롤백 누락 점검) | `.claude/agents/spec-reviewer.md` | X |
| 훅 (PreToolUse) | 스킬 사용량 기록 | `Skill` 호출마다 횟수·시각을 로컬 파일에 적재 | `.claude/hooks/skill-usage-stats.sh` | O (로컬) |
| 훅 (SessionStart) | 요청 현황 브리핑 | 세션 시작 시 진행 중인 요청을 요약해 컨텍스트에 주입 | `.claude/hooks/session-open-requests.sh` | X |
| 템플릿 | `_TEMPLATE.md` | 케이스 파일 원본. `/intake` 가 복사 | `maintenance/requests/_TEMPLATE.md` | — |

> **`context-loader` 공유** — `/spec` · `/implement` · `/verify` 세 스킬이 같은 정의를 재사용한다.
> 서브에이전트 호출은 매번 새 세션이라 이전 호출을 기억하지 못하므로, 매 호출 케이스 파일을 처음부터 다시 읽는다.

---

## 4. 성공 기준

[§1의 목표](#목적)를 다음 지표로 측정한다.

| 지표 | 측정 방법 | 방향 |
| --- | --- | :---: |
| **처리 추적** | 모든 요청이 `maintenance/requests/` 에 케이스 파일로 남고 `/status` 로 집계됨 | 누락 0 |
| **내부 처리 비율** | 월별 `classification: internal` 비율 추이 | ↑ |
| **처리 시간** | 접수(`created`) → 완료(`done` / `handed_off` / `outsourced`) 소요일 | ↓ |
| **초안 품질** | `/verify` 에서 `blocked` 로 되돌아가는 비율 · `spec-reviewer` 반려 횟수 | ↓ |

---

## 5. 설계 원칙

1. **스킬 = 절차, 서브에이전트 = 위임.**
   스킬은 사람이 부르고 **상태를 바꾼다**(케이스 파일 갱신, 코드 수정, 커밋).
   서브에이전트는 스킬이 부르고 **읽기 전용 판단·조사 결과만 돌려준다**.
   예: 분류는 `classifier`, 저장소 맥락 수집은 `context-loader` 가 전담한다.

2. **규칙과 데이터를 분리한다.**
   - `.claude/` = OS의 **정의** (스킬 · 서브에이전트 · 훅 · 설정)
   - `maintenance/` = OS가 돌며 만든 **산출물** (요청 케이스 파일)

   섞지 않으면 "규칙 변경"과 "작업 진행"이 git diff에서 구분된다.

3. **상태는 파일 하나에 모은다.**
   요청 1건 = `REQ-XXX.md` 1개. frontmatter(`status` · `classification` · `size` · `priority` · `updated`)가
   인덱스, 본문 8개 섹션이 단계별 로그. 별도 DB 없음 — 이력은 git이 남긴다.

4. **완료 기준은 검증 가능하게 쓴다.**
   `/spec` 의 완료 기준은 `/verify` 가 하나씩 실행·확인할 수 있는 문장이어야 한다.
   "잘 동작함" 같은 표현 금지. 기준을 바꾸려면 검증 중이 아니라 `/spec` 으로 돌아가 고치고 그 사실을 남긴다.

5. **가드레일을 스킬 안에 박아 둔다.**
   각 스킬 끝의 `## 하지 말 것` 이 그 스킬의 안전장치다.
   예: 분류를 직접 판단하지 않기(classifier에 위임), 스펙 없이 구현하지 않기,
   실행 안 한 검증을 통과로 적지 않기, `main` / `master` 직접 커밋 금지, force push 금지.

6. **공유는 "정의 재사용"이지 "기억 공유"가 아니다.**
   `context-loader` 를 세 스킬이 공유한다 = 같은 조사 방식을 재사용한다.
   서브에이전트는 호출마다 새 세션이므로, 매번 케이스 파일을 처음부터 다시 읽는다.

7. **문체·형식을 기존 스킬과 맞춘다.**
   한글, 단계형(`## 0. 선행 조건` → `## 1.` …), `## 하지 말 것` 마무리 —
   `git-commit` · `skill-stat` 스킬과 동일한 골격.

8. **점진적으로 키운다.**
   한 번에 거대한 OS를 만들지 않는다. Step 단위로 기능 묶음을 추가하고 PR 리뷰를 거친 뒤 다음 Step으로.

---
## 6. 로드맵

- [x] **Step 0** — 튜토리얼
  - [x] `git-commit` 스킬 만들기
  - [x] 스킬 사용량 기록 훅
  - [x] `skill-stat` 스킬 만들기

- [ ] **Step 1** — 유지보수 요청 처리 OS 뼈대 (Day 1 과제)
  - **필수**
    - [x] 스킬 6개: `intake` · `spec` · `implement` · `verify` · `outsource` · `status`
    - [x] 서브에이전트 2개: `classifier` · `context-loader`
    - [x] 공유 서브에이전트 확인 (`context-loader` → `spec` · `implement` · `verify` 재활용)
    - [x] **전체 사이클 1회 동작 확인** — `REQ-001` 이 `intake → classified → spec →
      implementing → done → handed_off` 완주
  - **도전**
    - [x] 훅 적용 — `SessionStart` 훅이 세션 시작 시 진행 중인 요청을 브리핑 (`session-open-requests.sh`)
    - [x] `spec-reviewer` 서브에이전트 — 스펙 초안 검토
    - [x] `intake-interview` 서브에이전트 — 담당자 면담 질문 생성
    - [x] `/handoff` 스킬 — 완료 후 배포 노트·통보문
    - [x] `classifier` 에 규모(S/M/L) 판단 추가
    - [x] 스킬·서브에이전트 10개 이상 (현재 스킬 9 + 서브에이전트 4 = 13)
    - [x] **실제 요청 1건 OS로 처리** (도그푸딩) — `REQ-001`: `sandbox/board` 게시판의
      빈 제목 저장 버그. `maintenance/requests/REQ-001.md` 에 전 과정 기록
  - [ ] PR 제출 (접근 방식 · 설계 의도 · 궁금한 점 작성)

  > **왜 사내 소스가 아니라 목업(`sandbox/board`)으로 첫 완주를 했나**
  > 사내 유지보수 대상은 스택·접근 권한·규모가 제각각이고, 파이프라인이 아직
  > 검증 안 된 상태에서 실무 코드에 바로 태우면 OS 결함과 도메인 문제가 섞여 원인 분리가 어렵다.
  > 통제 가능한 최소 시스템으로 먼저 한 바퀴 돌려 OS 자체의 구멍을 뽑아냈다
  > (실제로 `SessionStart` 훅 파싱 버그, `/verify` 의 diff 전제 등을 이 과정에서 발견).
  > **사내 실제 코드 적용은 다음 단계 과제로 남긴다 (Step 2).**

- [ ] **Step 2** — 사내 유지보수 요청에 OS 적용 (실 코드)
  - [ ] 스킬·서브에이전트를 사내 저장소에서 쓸 수 있게 배치 (`~/.claude` 전역 vs 저장소별 복사 결정)
  - [ ] 실제 요청 1~2건을 OS로 처리하고 목업 대비 차이(권한·빌드·테스트 부재 등) 정리
  - [ ] 그 경험으로 `/verify`·`context-loader`·`priority` 기준 보정

- [ ] **Step 3** — *(미정)*
---

## 7. 열린 질문 / 결정 대기

- **`classifier` 에 "사람 판단 필요(human gate)" 3번째 결과를 둘까?**
  현재 구현은 `internal` / `outsource` 2분류. 애매한 건은 사람에게 에스컬레이션하는 경로가 없다.
- `context-loader` 결과를 케이스 파일(또는 사이드카 파일)에 **캐시**할까? 매 호출 재조사 비용 대비.
- 외주 요청서를 실제 외부 포맷(이메일 / 이슈 템플릿)으로 **내보내는 단계**가 필요한가?
- `priority`(P1 / P2 / P3) **산정 기준**을 더 구체화할 것 (규모 `size` 를 재료로).
- `/verify` 실패 → `/implement` 재시도 **루프를 자동화**할지, 수동 유지할지.
- 요청 여러 건을 동시에 진행할 때 **브랜치 전략** (요청별 브랜치? Step 브랜치에 몰기?).
- **`/verify` 가 `git diff` 검증을 은근히 전제**한다 — REQ-001 에서 "테스트 코드 미수정"
  기준을 sandbox 첫 커밋 전이라 diff 로 못 봐 육안 확인으로 대체했다. 커밋 전 요청에서
  "코드 변경 없음" 류 기준을 어떻게 검증할지.
- **`intake-interview` 질문이 많다** (REQ-001 에서 11개) — 서브에이전트가 "필수 / 선택" 을
  나눠 주면 `/intake` 가 사용자에게 되물을 것을 추리기 쉬워진다.
- **spec → implement 문구 표류** — 스펙 "항목 제거" 가 구현에서 "절 전체 삭제" 로 바뀌었다.
  구현 로그에 남아 추적은 됐고 완료 기준을 `grep` 로 못박아 판정엔 영향 없었으나,
  구현 단계의 스펙 이탈을 무엇이 잡을지(사후 리뷰? `/verify` 확장?).

### 보류한 아이디어 (필요해지면 착수)

- **`/digest` — 성과 리포트 스킬.** `maintenance/requests/` 전체를 훑어 §4 성공 기준
  (내부 처리 비율, 평균 사이클타임, `blocked` 율)을 집계. 요청 데이터가 쌓인 뒤 Step 2에서 판단.
- **`/reopen` — 재개 스킬.** `done` / `handed_off` / `outsourced` 요청이 재발했을 때
  이전 케이스와 링크해 다시 여는 경로. 실제 재발 케이스가 생기면 착수.
