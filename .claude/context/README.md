# `.claude/context/` — 운영 지침 컨텍스트

OS가 **판단할 때 참조하는, 사람이 정한 지침**을 모아 둔 곳이다.

`skills/`(절차) · `agents/`(위임)와 달리 여기 있는 파일은 **실행되지 않는다.**
스킬과 서브에이전트가 *읽어서* 판단 근거로 삼는 자료다.

## 왜 스킬·에이전트 본문에 안 쓰고 밖으로 뺐나

판단 기준이 `agents/classifier.md` 안에 하드코딩돼 있으면,
팀에 사람이 한 명 들어올 때마다 **에이전트 정의를 고쳐야 한다.**
기준(자주 바뀜)과 절차(거의 안 바뀜)의 수명이 다르므로 파일을 분리한다.
— `OS.md` §5 원칙 2 "규칙과 데이터를 분리한다" 의 확장.

## 의존 표

| 파일 | 성격 | 변경 주기 | 읽는 쪽 | 주입 방식 |
| --- | --- | --- | --- | --- |
| [`style.md`](./style.md) | 판단 룰 (형식) | 반기 | 파일 쓰는 모든 스킬·에이전트 | **훅** — `Write`/`Edit` 직전 PreToolUse 가 세션당 1회 주입 (`.claude/hooks/inject-style-context.sh`) |
| [`team-capability.md`](./team-capability.md) | 사실 (팀 집계) | 분기 | `classifier`, `intake-interview` | **필요할 때** — 두 소비자가 각자 Read |
| [`classification-policy.md`](./classification-policy.md) | 판단 룰 | 분기~반기 | `classifier`(필수), `intake` | **필요할 때** — `classifier` 가 Read |
| [`sizing.md`](./sizing.md) | 판단 룰 (기준) | 반기 | `classifier`(필수), `/spec` | **필요할 때** — `classifier` 가 Read (판단 전 목록 5) |
| [`dod-patterns.md`](./dod-patterns.md) | 판단 룰 (작성·검토 기준) | 반기 | `/spec`, `spec-reviewer` | **필요할 때** — 두 소비자가 각자 Read |
| [`interview-method.md`](./interview-method.md) | 판단 룰 (방법론) | 분기~반기 | `/interview`(전부), `intake-interview`(§1·2·3·8) | **필요할 때** — 두 소비자가 각자 Read |
| [`../../maintenance/capacity.md`](../../maintenance/capacity.md) | 라이브 데이터 | 매달 | `classifier` | **필요할 때** — `classifier` 가 Read |
| [`../knowledge/systems/board.md`](../knowledge/systems/board.md) | 사실 (시스템별) | 시스템 변경 시 | `classifier` | **필요할 때** — `classifier` 가 §1② 에서 Read (있으면) |

> Day2 도전 2 최적화: `@import` 항상 로드를 없앴다. `style.md` 는 훅으로, `team-capability.md` 는 Lazy 로 내림.
> 세션 시작 시 컨텍스트 창을 먹는 운영 지침이 0.

> 데이터인 `capacity.md` 만 `maintenance/` 에 있다.
> `.claude/` = 규칙, `maintenance/` = 데이터 (`OS.md` §5 원칙 2).

## 주입 방식 3가지 — 왜 갈랐나

Claude Code에서 컨텍스트가 들어오는 통로는 성질이 다르다.

| | 항상 로드 (`@import`) | 필요할 때 (소비자가 Read) | 훅 (PreToolUse `additionalContext`) |
| --- | --- | --- | --- |
| 로드 시점 | 세션 시작, 무조건 | 그 스킬·에이전트가 돌 때만 | 특정 툴 실행 직전 |
| 확실히 들어가나 | ✅ | ❌ 소비자가 안 읽으면 무시 | ✅ 훅이 매번 발동 |
| 컨텍스트 창 비용 | ❌ 안 쓰는 턴에도 계속 | ✅ 필요할 때만 | ✅ 트리거될 때만 |
| 적합 | (지금 이 OS 는 안 씀 — 도전 2에서 제거) | 길고 특정 단계에서만 필요한 것 | 특정 행동(파일 쓰기 등) 직전에 꼭 필요한 짧은 것 |

- `style.md` → "어떻게 쓸까" 는 **파일을 쓸 때만** 필요. 안 쓰는 세션은 0 토큰이어야 한다 → **훅**(`Write`/`Edit`, 세션당 1회)
- `team-capability.md` → 소비자가 `classifier`·`intake-interview` 둘뿐이고 둘 다 Read 지시가 있다. 항상 로드는 낭비 → **필요할 때**
- `classification-policy.md` → 길고, `/intake` 분류 순간에만 필요하다 → **필요할 때**
- `sizing.md` → 짧지만 분류 순간에만 필요하다. `classification-policy.md` 와 짝이라 같이 Read → **필요할 때**
- `dod-patterns.md` → 스펙 단계에만 필요한 레퍼런스, 소비자 2개 공유 → **필요할 때**
- `capacity.md` → 매달 바뀌는 숫자. 세션 내내 들고 있을 이유가 없다 → **필요할 때**
- `interview-method.md` → 길고, 인터뷰하는 순간에만 필요하다 → **필요할 때**

> **훅의 한계**: `additionalContext` 는 훅을 발동시킨 **그 컨텍스트(메인 세션)** 에만 들어간다.
> `Task` 로 띄운 서브에이전트(`classifier`, `intake-interview`) 안으로는 안 들어가므로,
> 서브에이전트가 소비하는 `team-capability.md` 는 훅이 아니라 Lazy Read 로 보장한다.

> `interview-method.md` 는 **소비자가 둘**이다 (`/interview` 스킬, `intake-interview` 서브에이전트).
> 방법론을 양쪽에 복사하면 반드시 갈라지므로 파일 하나를 공유한다 —
> `OS.md` §5 원칙 6 "공유는 정의 재사용이지 기억 공유가 아니다" 와 같은 구조.

"필요할 때" 방식은 소비자가 안 읽으면 무시되므로,
`agents/classifier.md` · `agents/intake-interview.md` 에 **"판단 전에 반드시 읽어라"** 를 절차로 못박아 두었다.
이 배선이 실제로 유지되는지는 `.claude/scripts/check-context-wiring.sh` 가 검사한다 (Day2 도전 1).
`--self-test` 로 검사기 자체를 검증하고, `verify-wiring-on-edit.sh` PostToolUse 훅이 이 표·소비자 파일
편집 시마다 자동으로 재검사한다.

## 활용 검증 — 죽은 지침 잡기

`classification-policy.md` §5 가 판단마다 **적용한 기준의 출처 인용**을 강제한다.
인용은 케이스 파일(`maintenance/requests/REQ-XXX.md`)에 쌓이므로 감사할 수 있다:

```bash
# 어느 정책이 몇 번 인용됐나
grep -rho 'classification-policy\.md §[0-9]' maintenance/requests/ | sort | uniq -c
```

인용 횟수가 0인 항목 = **죽은 지침**. 지우거나, 조건이 안 맞는 것이니 고친다.

## 앞으로 들어올 것 (설계상 자리만 잡아 둠)

| 파일 | 담을 것 |
| --- | --- |
| `priority.md` | P1 / P2 / P3 산정 기준 (`OS.md` §7 열린 질문) |
| `escalation.md` | 사람 판단으로 넘기는 조건 (`OS.md` §7 human gate) — 훅 주입 후보 |
| `operator.md` | 운영자 개인 프로필 (판단 성향·선호) |

> 시스템별 사실(스택·관리주체·외주사·작업 이력)은 여기가 아니라
> `.claude/knowledge/systems/` 에 둔다. 벤더 계약 정보는 `.claude/knowledge/vendors/`.
