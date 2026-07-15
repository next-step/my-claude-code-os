# Claude OS 동작 테스트

이 OS는 **결정적 부품**(훅 JS·셸 스크립트·스킬 구조)과 **LLM 의존 부품**(스킬 오케스트레이션)이
섞여 있다. 자동화 난이도가 완전히 다르므로 테스트를 3계층으로 나눈다.

| 계층 | 파일 | 검사 대상 | 성격 | 비용 |
|------|------|-----------|------|------|
| **L1** | `tests/lint.sh` | frontmatter·참조 링크 무결성·문법·JSON 스키마 | 결정적·정적 | 즉시 |
| **L1** | `tests/inject.sh` | 정본 컨텍스트 **주입 배선** 무결성 (Eager @import·고아 정본·지도 드리프트) | 결정적·정적 | 즉시 |
| **L1** | `tests/context-budget.sh` | Eager 컨텍스트 **크기 회귀** (매 세션 상주 정본의 토큰·줄 예산) | 결정적·정적 | 즉시 |
| **L2** | `tests/unit.test.js` | `detect-todo.js` 훅의 stdin→stdout 계약 | 결정적·단위 | 즉시 |
| **L2** | `tests/unit-scripts.sh` | 순수 셸 스크립트(`log-skill-invocation.sh`·`usage-report.sh`) 동작 계약 | 결정적·단위 | 즉시 |
| **L3** | `tests/smoke.sh` | `claude -p "/capture"` → Notion 저장 end-to-end | 비결정적·통합 | 수십 초·자격증명 필요 |

> **왜 이렇게 나눴나:** LLM 흐름까지 매번 돌리면 느리고 비결정적이라 CI 가 불안정해진다.
> 가장 자주 깨지는 건 사실 "파일명 바꿨더니 참조가 끊긴" 같은 구조 문제(L1)다.
> 그래서 **결정적 L1·L2 를 게이트로** 두고, 진짜 동작 확인(L3)은 필요할 때만 돌린다.

## 실행 방법

```bash
./run-tests.sh          # 전체 (L1 → L2 → L3)
./run-tests.sh l1 l2    # 결정적 계층만 (CI 가 쓰는 조합, 빠름)
./run-tests.sh l3       # 통합 스모크만
```

## 각 계층이 잡는 것

### L1 — 정적 검증 (`lint.sh`)
- 모든 `SKILL.md` 에 `name`/`description` frontmatter 가 있는가
- 스킬·에이전트 md 가 참조하는 `.claude/...(md|sh|js)` 경로가 **실재**하는가
  → 파일명을 바꾸면 런타임에야 깨지는 끊어진 링크를 커밋 전에 잡는다
- 훅 JS 문법(`node --check`), 셸 문법(`bash -n`)
- `data/*.json` 이 valid JSON 이고 필수 키를 갖는가 (비밀값이라 없으면 SKIP)

### L1 — 주입검증 (`inject.sh`)
`lint.sh` 가 "참조 경로가 실재하는가"(파일 무결성)를 본다면, `inject.sh` 는 **"정본이 주입
배선에 실제로 걸려 있고, 문서와 현실이 일치하는가"**(배선 무결성)를 본다. 이 검사만이 잡는
조용한 사고:
- **Eager 회귀** — `CLAUDE.md` 의 `@.claude/context/security.md` 한 줄이 사라지면 보안 정본이
  매 세션 주입되던 게 에러 없이 멈춘다 (검사 1·2)
- **고아 정본** — `context/*.md` 는 있는데 아무 주입 경로(@import·스킬 참조)에도 안 걸린 정본은
  조용히 썩는다 (검사 3)
- **지도 드리프트** — `context-map.md §2` 표가 주장하는 `소비자→정본` 참조가 실제 md 와 어긋나면
  지도가 거짓말이 된다. 양방향(표↔현실)으로 대조한다 (검사 4)
- **문서 정합성** — `context/README.md` 정본 목록의 `security.md = Eager` 표기가 실제 배선(§1의
  @import)과 일치하는가 (검사 5)

**알려진 한계 (설계상 커버하지 않음 — 독립 검증 결과 명시)**
- **Lazy 참조는 "텍스트 존재"만 확인한다.** `grep` 은 실제 `참조 정본` 지시문과, 같은 경로를
  스치듯 언급하거나 부정하는 문장을 구별하지 못한다. 나아가 "모델이 그 참조를 실제로 Read
  하는가"는 정적으로 검증 불가하다(레포 README 가 Lazy 로딩 일반에 대해 이미 인정한 한계와 동일).
- **고아 검사는 `context/` 최상위(`-maxdepth 1`)만 스캔한다.** 하위 폴더에 정본 `.md` 를 두면
  검사에서 빠진다. 현재 구조는 평탄해 무해하나, 하위 폴더를 도입하면 `inject.sh` 를 갱신해야 한다.
- **글로벌 `~/.claude/CLAUDE.md`·`.claude/settings*.json` 의 주입 상호작용은 검사하지 않는다.**
  이 레포가 통제할 수 없는 사용자 환경이라 범위 밖으로 둔다.
- **§4 파서는 §2 표의 헤더 텍스트와 열 헤더=정본 파일명 규약에 결합돼 있다.** 표를 번역·재배치하면
  "파서가 표를 못 찾음" / "열 헤더가 정본 파일과 불일치"로 **명확히** 실패한다(무더기 오탐 대신).
  즉 파싱 취약성 자체는 남되, 깨질 때 혼란스럽지 않게 알린다.

### L1 — 예산검증 (`context-budget.sh`)
`inject.sh` 가 "Eager 배선이 **존재하는가**"(배선 무결성)를 본다면, `context-budget.sh` 는
그 Eager 페이로드가 **비대해지지 않았는가**(크기 회귀)를 본다. 상보적이라 겹치지 않는다.
- **왜 필요한가** — Eager 정본(`CLAUDE.md` + `@import` 대상)은 스킬 실행과 무관하게 **매 세션
  항상** 컨텍스트 창에 상주한다. 여기 한 줄이 늘면 그 비용을 모든 세션이 영구히 부담한다.
  "정말 모든 상황에서 필요한가?"를 통과 못 한 내용이 슬그머니 Eager 로 승격되는 것을 막는다.
- **무엇을 재나** — `@import` 목록을 하드코딩하지 않고 `CLAUDE.md` 에서 동적으로 읽어, Eager
  대상 전체의 근사 토큰(바이트÷3.5)과 줄 수를 합산한다. Eager import 를 새로 추가하면 자동 포함.
- **예산** — `EAGER_MAX_TOKENS`(기본 1200, 주 게이트)·`EAGER_MAX_LINES`(기본 80, 보조) 환경변수로
  조정. 초과하면 실패하며 "Lazy 로 내릴 내용이 없는지 재심사하라"고 안내한다.

### L2 — 훅 단위 테스트 (`unit.test.js`)
`detect-todo.js` 는 stdin(JSON)→stdout(JSON|빈출력)인 순수 함수에 가깝다.
의존성 없이 실제 훅을 실행해 두 계약을 검증한다:
- 할일 뉘앙스 + 명령/질문/슬래시 아님 → **capture 힌트 출력**
- 그 외(명령·질문·슬래시·무관·빈입력) → **침묵**

### L2 — 순수 셸 스크립트 단위 테스트 (`unit-scripts.sh`)
외부 의존(네트워크·데몬·`claude`)이 없는 결정적 셸 스크립트들은 `detect-todo.js` 처럼
검증할 수 있다. 실데이터·네트워크를 건드리지 않으려고 각 스크립트가 지원하는 주입용
환경변수(`SKILL_LOG`·`ITEMS_JSON_FILE`)로 임시 픽스처를 넣어 계약을 확인한다:
- `log-skill-invocation.sh`(write) — Skill 호출 → `#N 스킬명` append·카운터 증가,
  비-Skill 호출 → 무기록·exit0, 네임스페이스 스킬명 보존
- `usage-report.sh`(read) — 빈도·연쇄(`capture → plan`)·유휴 스킬 집계, 빈 로그 안내
- `digest-report.sh`(집계) — 상태 분포·카테고리 분포·2일+ 방치 draft 강조, 빈 항목 안내
- `telegram-send.sh`(발송 가드) — 빈 메시지는 값 노출 없이 exit1 (네트워크 미접촉)

> cron 훅(`flush-cron`·`watchdog-cron`·`digest-cron`)과 `telegram-send` 의 실제 발송
> 경로는 launchd·네트워크·자격증명 의존이라 단위 대상이 아니다 — L1 문법 검사로만
> 커버하고, 동작은 설치 후 통합에서 확인한다.

### L3 — headless 통합 스모크 (`smoke.sh`)
1. 고유 마커 제목으로 `claude -p "/capture <marker>"` 를 실제 실행
2. `notion.sh read draft` 로 그 항목이 생성·분류됐는지 확인
3. 만든 테스트 항목을 **아카이브**해서 DB 오염 방지

`claude` CLI·`notion.json`·`jq` 중 하나라도 없으면 **SKIP**(실패 아님) → CI 에서 안전.

## 별도: 주입 효과 A/B 실험 (`ab-injection/`)

위 L1~L3 이 정본 주입의 **배선·크기**를 정적으로 게이트한다면, [`ab-injection/`](./ab-injection/)
는 그 배선이 **스킬 동작에 미치는 효과**를 통제 실험으로 잰다 (게이트가 아닌 1회성 측정 기록).

- **무엇을** — 분류 정본(`categories.md`) 주입 有無(Arm A/B)에서 같은 모델·입력의 분류 동작 대조.
- **결과** — 정확도 50.0%→**97.2%**, 6종 어휘 준수 50.0%→**100%**, 3회 일관성 58.3%→**91.7%**.
- **재현** — `bash tests/ab-injection/score.sh` (원자료 `raw-runs.tsv` → 지표 재계산). 상세는
  [`ab-injection/README.md`](./ab-injection/README.md).
- **inject.sh 와의 관계** — inject 는 "정본이 배선에 걸렸나"(존재), ab-injection 은 "그래서
  동작이 달라지나"(효과). 상보적이다.

## CI

`.github/workflows/ci.yml` 가 push·PR 마다 **L1+L2** 를 돌린다.
L3 는 자격증명과 `claude` CLI 가 필요해 CI 에선 생략하고, 로컬에서 수동 실행한다.

## 테스트 추가하기

- **새 훅**을 만들면 → JS 훅은 `unit.test.js` 케이스 테이블에, 외부 의존 없는 순수 셸
  스크립트는 `unit-scripts.sh` 에 계약 테스트를 추가 (외부 의존이 큰 `.sh` 는 통합/보고 대상)
- **새 스킬**을 만들면 → L1 이 자동으로 frontmatter·링크를 검사 (별도 작업 불필요)
- **새 데이터 파일**을 쓰면 → `lint.sh` 의 `check_json` 한 줄 추가
- **새 정본**을 `context/` 에 추가하면 → `inject.sh` 가 자동으로 고아 여부를 검사.
  스킬이 그 정본을 참조하기 시작하면 `context-map §2` 표도 함께 갱신해야 드리프트 검사를 통과한다
- **정본을 Eager 로 승격**하면 → `inject.sh` 의 검사 1·2·5 대상(현재 `security.md` 하드코딩)을 함께 갱신.
  또한 `context-budget.sh` 가 Eager 총량을 자동 재계산하니, 예산을 넘기면 상한(`EAGER_MAX_*`) 조정이
  아니라 **"정말 Eager 여야 하는가"를 먼저 재심사**한다
