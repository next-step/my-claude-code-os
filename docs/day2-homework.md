# Day2 과제 워크시트 — 내 OS에 컨텍스트 체계 심기

> 이 파일은 `/clear` 로 대화가 날아가도 작업을 이어갈 수 있게 **계획과 측정값을 박제**해 둔 것이다.

---

## 1. before 지표 측정

### 절차

1. 이 파일 저장 확인 → `/clear`
2. `/context` 실행 → **측정 1** 표에 숫자 기입
3. `CLAUDE.md` 마지막 줄 `@.claude/context/team-capability.md` 삭제(또는 `#` 주석)
4. `/clear` → `/context` → **측정 2** 표에 기입
5. `CLAUDE.md` 그 줄 **복구**

(측정 3 은 도전 2 최적화의 전·후 측정 — 아래 별도 절차)

> `/context` 출력은 항목별 토큰 수로 나온다. 아래 표의 항목명은 버전에 따라 조금 다를 수 있으니 비슷한 줄을 적으면 된다.

### 측정 1 — 클린 베이스라인 (`@team-capability.md` 포함)

| 항목 | 토큰 |
| --- | --- |
| System prompt | 4.5k tokens |
| System tools | 20.4k tokens |
| MCP tools | 30 tools · 0 tokens |
| Memory files (CLAUDE.md + @import) | 1.2k tokens |
| Custom agents |  agents · 645 tokens |
| **합계** | 30.7k/1m tokens |
| 남은 여유 | 936.3k |

측정일: 2026-09-07

### 측정 2 — `@team-capability.md` import 제거 후

| 항목 | 토큰 |
| --- | --- |
| Memory files | 259 tokens |
| **합계** | 29.8k/1m tokens |

측정일: 2026-09-07

**→ `@team-capability.md` import 비용 = 측정1 Memory files − 측정2 Memory files ≈ 1.2k − 259 ≈ 약 940 토큰**

> `team-capability.md` 원문은 1,115자(한글 위주). 세션 시작마다 무조건 이 ~940 토큰을 낸다.
> 이 파일을 자주 안 읽는 스킬까지 전부 부담하므로, Day2 도전 2(최적화)에서 "항상 로드" 대신
> Lazy Read 로 내릴지 판단할 후보 1순위.

### 측정 3 — 도전 2 최적화 전·후 (`@import` 제거)

**최적화 내용**: `CLAUDE.md` 의 `@import` 2줄 제거.
- `style.md` → PreToolUse 훅(`Write`/`Edit`, 세션당 1회) 주입
- `team-capability.md` → Lazy Read (소비자 classifier·intake-interview 가 직접 Read)

**측정 절차**: 새 `claude` 세션에서 `git switch --detach 4ae2cfd` → `/context` (= before),
`git switch step2` → `/context` (= after). `/context` 의 `Memory files` 줄 + 맨 위 합계.

측정일: 2026-09-08 (각각 새 세션, `/clear` 아님)

| 시점 | Memory files | 합계 |
| --- | --- | --- |
| before (`@team-capability` + `@style` 항상 로드) | **2,600** (2.6k) | **32.0k** |
| after (`@import` 0개) | **543** | **29.9k** |
| **절감** | **−2,057 (−79%)** | **−2,100 (−6.6%)** |

- Memory files 만 놓고 보면 **79% 감소** (2.6k → 543). `after` 의 543 = `CLAUDE.md` 본문 하나
  (설명 섹션 추가로 이전 ~250 → 543 으로 늘어난 상태 포함).
- 전체 세션 시작 컨텍스트 대비 **6.6% 감소**. 나머지(System prompt 4.5k, System tools 20.3k,
  Skills 3.9k, Custom agents 645)는 우리가 못 건드리는 고정분 → **제어 가능한 부분에서 79% 절감**한 셈.
- 예상(−1,900)보다 실측이 −2,057 로 조금 더 큼 (`style.md` 가 추정 1,190 보다 무거웠음).

**트레이드오프**: `style.md`(~1,190 tok)는 파일 쓰는 세션의 첫 `Write`/`Edit` 때 한 번 들어옴(그 뒤 재주입 없음).
파일 안 쓰는 세션(질문·조사·계획)은 0. `team-capability.md` 는 `classifier`/`intake-interview` 가 돌 때만 Read.
`CLAUDE.md` 설명 섹션을 뺐으면 after 가 ~250 으로 더 내려가지만, 가독성 위해 유지.

---

## 2. 과제 할 일 (순서)

Day2 과제 완료 조건 = 필수 3 + 도전 2.

| # | 구분 | 할 일 | 완료 조건 | 상태 |
| - | --- | --- | --- | --- |
| 0 | 준비 | `team-capability.md` 의 `(채울 것)` 를 `sandbox/board` 소유팀 값으로 교체 (첨삭 제출용이라 실회사 정보는 뺌 — 회사 전환 시 이 파일만 교체) | 플레이스홀더 0개 | ✅ |
| 1 | 필수 1 | 컨텍스트 md **5개 이상** + 스킬·서브에이전트 자동 주입 연결 | `.claude/context/` 실질 컨텍스트 5개, 각각 소비자에 연결(=@import / Read 지침 / 훅 트리거) | ✅ (6개, A/B 실증은 필수 2에서) |
| 2 | 필수 2 | 주입 O/X **A/B 동작 비교** (`skill-creator` 포함) | 같은 입력에 대해 컨텍스트 있을 때 vs 없을 때 스킬 출력 차이를 기록 | ✅ → [`day2-ab-injection-test.md`](./day2-ab-injection-test.md) |
| 3 | 필수 3 | 컨텍스트 체계 **도식화** 1P 파일 | `docs/` 에 다이어그램 파일 1개 (파일→트리거→소비자 관계) | ✅ → [`day2-context-map.md`](./day2-context-map.md) |
| 4 | 도전 1 | 주입 검증 **테스트** 제작 | 컨텍스트가 실제로 주입됐는지 확인하는 자동 검사 | ✅ `check-context-wiring.sh` (검사) + `--self-test` (검사기 검증) + PostToolUse 훅 (자동 실행) |
| 5 | 도전 2 | 컨텍스트 체계 **최적화 + 정량 비교** | before 표 대비 after 표, 절감 토큰/% 기록 | ✅ → 위 §1 측정 3 (Memory files 2.6k → 543, −79%) |

### 필수 1 — 컨텍스트 6개 + 주입 연결 (완료 2026-09-07, 도전 2에서 주입 방식 재배정)

| 파일 | 소비자 | 주입 방식 (도전 2 이후) |
| --- | --- | --- |
| `style.md` (신규) | 파일 쓰는 모든 스킬·에이전트 | **훅** — `Write`/`Edit` PreToolUse, 세션당 1회 |
| `team-capability.md` | `classifier`, `intake-interview` | **Lazy Read** (도전 2 전엔 `@import`) |
| `classification-policy.md` | `classifier`, `intake` | Lazy Read |
| `sizing.md` (신규) | `classifier`, `/spec` | Lazy Read — `classifier.md` "판단 전 Read 목록 5" |
| `dod-patterns.md` (신규) | `/spec`, `spec-reviewer` | Lazy Read — 두 소비자 공유 |
| `interview-method.md` | `/interview`, `intake-interview` | Lazy Read |

남은 후보(안 만듦): `priority.md`, `escalation.md`, `operator.md`.

### 자동 주입 방식 3가지 — 최종 (도전 2)

| 방식 | 트리거 | 현재 적용 |
| --- | --- | --- |
| `CLAUDE.md` `@import` | 세션 시작 무조건 | **없음** (도전 2에서 제거 — baseline 토큰 절감) |
| 소비자가 `Read` (Lazy) | 그 스킬·에이전트가 돌 때 | `team-capability`, `classification-policy`, `sizing`, `dod-patterns`, `interview-method`, `capacity` |
| **훅 (PreToolUse additionalContext)** | `Write`/`Edit` 툴 실행 직전 (세션당 1회) | `style.md` (`.claude/hooks/inject-style-context.sh`) |

---

> 변경 이력은 커밋 로그 참고 (`git log main..step2`). 이 파일은 측정값과 완료 현황만 남긴다.
