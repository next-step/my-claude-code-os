# 2주차 — 컨텍스트 설계

> 이 문서는 **"Claude 가 무엇을, 언제 보게 되는가"** 를 다룬다.
> 코드가 아니라 **컨텍스트**가 주제다. 실제 훅 구현은 [`README.md`](../README.md)의 OS 구성 절을,
> 서비스 청사진은 [`OS.md`](../OS.md)를 본다.

## 한눈에

컨텍스트와 관련된 파일은 23개다. 하지만 **전부가 컨텍스트로 들어가지는 않는다.**
중요한 건 개수가 아니라 **"언제 들어오느냐"** 다.

| 분류 | 개수 | 언제 들어오나 |
|---|---|---|
| 항상 | 1 | 모든 세션·모든 서브에이전트 |
| 조건부 자동 | 11 | 세션 시작 / 스킬 호출 / 서브에이전트 시작 |
| 수동 (읽어야 들어옴) | 5 | 필요할 때 직접 읽음 |
| 기계 (주입 안 됨) | 6 | 컨텍스트를 *넣는* 쪽 |

---

## 1. 항상 들어오는 것 — 1개

**`CLAUDE.md`** — Claude Code 가 **자동으로 로드하는 유일한 슬롯**이다. 그래서 여기에는
*항상 참인 사실*과 *어디를 더 볼지 이정표*만 담는다. 세부는 `OS.md` 로 넘긴다.

> **여기 거짓이 있으면 가장 비싸다.** 매 세션, 모든 서브에이전트가 그 거짓을 믿고 출발한다.
> 실제로 이번 주차에 `CLAUDE.md` 의 실행 명령이 하나도 동작하지 않는 상태였다
> (`node_modules`·`dev.db`·`.env` 부재). 그걸 고치는 것이 컨텍스트를 더 넣는 것보다 급했다.

## 2. 조건이 맞으면 자동으로 들어오는 것 — 11개

| 무엇 | 언제 | 넣는 훅 |
|---|---|---|
| `STATUS.md` | 세션 시작 | `status-context` |
| `src/types/contract.ts` | 개발자 에이전트 시작 | `contract-context` |
| 스킬 6 + 에이전트 3 의 목록 | 스킬 호출 직전 · 서브에이전트 시작 | `skill-context` |

마지막 9개는 파일 맨 위 두 줄(`name`, `description`)만 뽑아 **목록**으로 만든다.
본문 전체가 들어가는 건 그 스킬을 실제로 호출할 때다.

## 3. 읽어야만 들어오는 것 — 5개

| 파일 | 왜 자동이 아닌가 |
|---|---|
| `OS.md` (315줄) | 너무 크다. `CLAUDE.md` 가 이정표로만 가리킨다 |
| `README.md` | OS 구성 상세. 필요할 때만 |
| `DECISIONS.md` | 기획 결정 전에만 |
| `docs/context.md` (이 문서) | 컨텍스트 설계를 되짚을 때만 |
| `.claude/skills/interview/PHILOSOPHY.md` | 그 스킬을 쓸 때만 |

**모든 걸 넣는 게 좋은 게 아니다.** 컨텍스트에는 예산이 있고, `OS.md` 315줄을 매번 넣으면
정작 중요한 것이 묻힌다. 그래서 "작고 자주 변하는 것"(`STATUS.md`)은 넣고,
"크고 잘 안 변하는 것"(`OS.md`)은 가리키기만 한다.

## 4. 컨텍스트가 아니라 기계 — 6개

훅 5개(`.claude/hooks/*.sh`)와 `.claude/settings.json`.
컨텍스트에 들어가지 않고, **컨텍스트를 넣는 쪽**이다.

## 5. 부산물 — git 제외

`.claude/.os-snapshot.md` · `.claude/skill-usage.log` · `.claude/*.err`

---

## 훅 5개 — 무엇을 하나

훅은 두 가지 일을 한다. **(A) 필요한 것을 알아서 넣어주기**, **(B) 벌어진 일을 알아서 남기기.**

| 훅 | 언제 | 종류 | 하는 일 | 왜 필요했나 |
|---|---|---|---|---|
| `status-context` | 세션 시작 | A | `STATUS.md` 전문 주입 | CLAUDE.md 가 "먼저 읽어라"고 *부탁*만 했다. 이제 *보장*이다 |
| `skill-context` | 스킬 호출 직전 · 서브에이전트 시작 | A | 스킬·에이전트 카탈로그를 파일에서 실시간 생성 | 손으로 적은 목록은 반드시 실제와 어긋난다 |
| `contract-context` | 서브에이전트 시작 | A | 공유 계약 전문 주입. **개발자 둘에게만** | "단일 진실 출처"라 선언해놓고 정작 개발 에이전트는 못 보고 시작했다 |
| `skill-usage-log` | 스킬 호출 직전 | B | `시각<TAB>스킬이름` 한 줄 append | `skill-stat` 이 볼 데이터가 아예 없었다 |
| `decision-log` | `OS.md` 편집 직후 | B | 바뀐 **절 이름**을 `DECISIONS.md` 에 기록 | 기존 기록은 절을 몰라 정보가 없었다 |

### 부탁 vs 보장

이 주차의 핵심 교훈이다.

`CLAUDE.md` 에 "작업 시작 시 `STATUS.md` 를 먼저 확인하라"고 적어두는 것은 **부탁**이다.
모델이 읽기로 선택해야만 읽힌다. 반면 SessionStart 훅으로 넣으면 **보장**이다.

문서에 규칙을 적는 것과, 그 규칙이 지켜지도록 장치를 만드는 것은 다르다.

### 왜 `product-planner` 에겐 계약을 안 주나

`contract-context` 는 `agent_type` 을 보고 `backend-developer` / `frontend-developer` 에만 계약을 넣는다.
기획자는 상위 의사결정만 하므로 타입 207줄이 필요 없다. **컨텍스트는 필요한 사람에게만 준다.**

---

## 설계 원칙 3가지

이번 주차에 반복해서 부딪힌 것들이다. 새 훅을 만들 때 지킨다.

### 1. `jq` 를 쓰지 않는다

이 환경에 `jq` 가 없다. 죽어 있던 훅 두 개(`decision-log`, `skill-usage-log`)가 **둘 다 이것 때문**이었다.
payload 는 `sed` 로 뽑는다. `"file_path"` 와 `"skill"` 은 payload 에 각각 정확히 한 번만 등장하므로 안전하다
(`tool_response` 는 `filePath` 처럼 camelCase 라 겹치지 않는다).

### 2. 조용히 실패하지 않는다

`decision-log` 는 `jq` 가 없어 경로를 못 읽고 **조용히 `exit 0`** 했다. 실패 신호가 어디에도 안 남아
2026-07-05 이후 몇 달간 죽은 줄 아무도 몰랐다.

이제 파싱에 실패하면 `.claude/*.err` 에 흔적을 남긴다.
훅은 작업을 막으면 안 되므로 여전히 `exit 0` 하지만, **말없이 사라지지는 않는다.**

### 3. payload 를 추측하지 않는다

훅이 무엇을 받는지 문서로 짐작하지 말고 **실측**한다.
이미 등록된 훅에 임시로 `cat > dump.json` 한 줄을 넣고 한 번 실행한 뒤 되돌리면 된다.

실측 결과:

```jsonc
// SubagentStart
{"session_id":"…","transcript_path":"…","cwd":"…","prompt_id":"…",
 "agent_id":"a72176…","agent_type":"backend-developer","hook_event_name":"SubagentStart"}

// PreToolUse (matcher: Skill)
{"…","tool_name":"Skill","tool_input":{"skill":"skill-stat"},"tool_use_id":"…"}

// PostToolUse (matcher: Edit|Write)
{"…","tool_name":"Edit",
 "tool_input":{"file_path":"C:\\…\\OS.md","old_string":"…","new_string":"…","replace_all":false},
 "tool_response":{"filePath":"…","structuredPatch":[{"oldStart":1,"newStart":1,"lines":["…"]}],…}}
```

`agent_type` 이 있다는 걸 확인했기에 "개발자에게만 계약 주입"이 가능해졌다.

---

## 알아두면 덜 헤매는 것

### `settings.json` 은 세션 시작 때 한 번만 읽힌다

- 훅을 **새로 등록**하면 → 다음 세션부터 적용된다.
- 훅 **스크립트 내용**만 고치면 → 실행할 때마다 새로 읽히므로 즉시 적용된다.

`decision-log` 는 명령어가 그대로였기에 고치자마자 같은 세션에서 동작했다.

### 이 저장소의 `.md` 는 CRLF 다

`OS.md` 315줄이 전부 CRLF(Windows 줄바꿈)다. 어떤 도구가 LF 로 저장하면
`diff` 가 **모든 줄이 바뀌었다**고 오탐한다(실측: `+315/-315`).
`decision-log` 는 `diff --strip-trailing-cr` 로 이를 막는다.

### 한 이벤트에 훅이 여러 개일 때

`PreToolUse(Skill)` 에 2개, `SubagentStart` 에 2개가 붙어 있다.
각 훅이 올바른 JSON 을 낸다는 것까지는 검증했으나,
**Claude Code 가 둘의 `additionalContext` 를 모두 합쳐 넣는지는 아직 확인하지 못했다.**
다음 세션에서 개발 에이전트를 한 번 띄워 확인할 것. 하나만 들어간다면 두 스크립트를 합치면 된다.

---

## 다음 세션 확인 목록

새로 등록한 훅은 다음 세션부터 붙는다. 그때 이것들을 확인한다.

- [ ] `STATUS.md` 가 자동으로 들어오는가
- [ ] 개발 에이전트를 띄우면 계약 전문이 들어오는가 (위의 "훅이 여러 개일 때" 참고)
- [ ] 아무 스킬이나 부른 뒤 `/skill-stat` 이 처음으로 숫자를 보여주는가

---

## 함께 보기

- [`CLAUDE.md`](../CLAUDE.md) — 항상 로드되는 슬롯. 실행 명령·계약·제약
- [`README.md`](../README.md) — 훅·스킬·서브에이전트 구현 상세
- [`OS.md`](../OS.md) — 서비스 청사진 (12장이 개발 계약)
- [`STATUS.md`](../STATUS.md) — 지금 어디까지 왔나
- [`DECISIONS.md`](../DECISIONS.md) — 청사진이 언제·어디가 바뀌었나
