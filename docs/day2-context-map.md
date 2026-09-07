# Day2 필수 3 — 내 OS 컨텍스트 체계 도식 (1P)

> `.claude/context/` 운영 지침이 **어느 파일 → 어떤 트리거 → 어떤 소비자**로 흘러가는지 한 장으로.
> 이 지도는 [`day2-ab-injection-test.md`](./day2-ab-injection-test.md) 의 A/B 3라운드로 실제 동작이 검증됨.
> 작성일: 2026-09-07

---

## 흐름도

```mermaid
flowchart LR
    subgraph SRC["컨텍스트 파일"]
        direction TB
        TC["team-capability.md<br/><i>팀 스택·여력 (사실)</i>"]
        ST["style.md<br/><i>코드·TDD·문서 규칙</i>"]
        CP["classification-policy.md<br/><i>internal/outsource 룰</i>"]
        SZ["sizing.md<br/><i>S/M/L 루브릭</i>"]
        DOD["dod-patterns.md<br/><i>완료 기준 패턴</i>"]
        IM["interview-method.md<br/><i>모호함 진단 방법론</i>"]
        CAP["maintenance/capacity.md<br/><i>이번 달 잔여 M/M (라이브)</i>"]
        KS["knowledge/systems/&lt;sys&gt;.md<br/><i>⚠ 미생성 — 갭</i>"]
    end

    subgraph CON["소비자 (스킬 · 서브에이전트)"]
        direction TB
        CLF(["classifier"])
        II(["intake-interview"])
        INT(["/interview"])
        SP(["/spec"])
        SR(["spec-reviewer"])
        TXT(["텍스트·코드 내는<br/>모든 스킬"])
    end

    TC ==>|"① @import 항상"| CLF
    TC ==>|"① @import 항상"| II
    ST ==>|"① @import 항상"| TXT

    CP -->|"② Lazy Read"| CLF
    CP -->|"② Lazy Read"| II
    SZ -->|"② Lazy Read"| CLF
    SZ -->|"② Lazy Read"| SP
    DOD -->|"② Lazy Read"| SP
    DOD -->|"② Lazy Read"| SR
    IM -->|"② Lazy Read"| INT
    IM -->|"② Lazy Read"| II
    CAP -->|"② Lazy Read"| CLF
    KS -.->|"② 있으면 Read<br/>(지금은 추측 대체)"| CLF

    linkStyle 0,1,2 stroke:#2563eb,stroke-width:3px
    linkStyle 12 stroke:#dc2626,stroke-dasharray:4
```

**엣지 범례** — `══>` ① 항상 로드(굵은 파랑) · `──>` ② Lazy Read · `┈┈>` 미구현/갭(빨강 점선)

---

## 파일 → 트리거 → 소비자 표

| 파일 | 성격 | 주입 방식 | 트리거(언제 들어오나) | 소비자 |
| --- | --- | --- | --- | --- |
| `team-capability.md` | 사실 | ① `CLAUDE.md` `@import` | 세션 시작, 무조건 | `classifier`, `intake-interview` |
| `style.md` | 형식 룰 | ① `CLAUDE.md` `@import` | 세션 시작, 무조건 | 텍스트·코드 내는 모든 스킬 |
| `classification-policy.md` | 판단 룰 | ② 소비자가 Read | `classifier` 가 분류 판단 직전 | `classifier`(필수), `intake` |
| `sizing.md` | 판단 룰 | ② 소비자가 Read | `classifier` 판단 시 (Read 목록 5번) | `classifier`, `/spec` |
| `dod-patterns.md` | 작성·검토 룰 | ② 소비자가 Read | `/spec` 완료 기준 작성 시 / `spec-reviewer` 체크 #1 | `/spec`, `spec-reviewer` |
| `interview-method.md` | 방법론 | ② 소비자가 Read | 인터뷰·면담 진행 시 | `/interview`, `intake-interview` |
| `maintenance/capacity.md` | 라이브 데이터 | ② 소비자가 Read | `classifier` 가 정책 §2 캐파 룰 평가 시 | `classifier` |
| `knowledge/systems/<sys>.md` | 시스템별 사실 | ② 있으면 Read | `classifier` §1② 수행주체 확인 시 | `classifier` |

> 세 번째 방식 **③ 훅(PreToolUse `additionalContext`)** 은 아직 없음.
> 소비자가 많은 `escalation.md`(사람 판단 넘김 조건)를 도입할 때 정석.

---

## 왜 방식을 갈랐나

| | ① 항상 로드 | ② Lazy Read |
| --- | --- | --- |
| 장점 | 확실히 들어감 | 컨텍스트 창 안 먹음 |
| 단점 | 안 쓰는 턴에도 자리 차지 (@team-capability ≈ 940토큰/세션) | 소비자가 안 읽으면 무시됨 |
| 배정 기준 | 짧고 두루 필요 (`team-capability`, `style`) | 길고 특정 단계에서만 (`classification-policy`, `sizing`, `dod-patterns`, `interview-method`) |

② 방식의 "안 읽으면 무시" 를 막으려고 `classifier.md` 에 **"판단 전 반드시 Read 할 것"** 표를 절차로 못박음.

---

## 활용 검증 루프 (죽은 지침 잡기)

```mermaid
flowchart LR
    P["classification-policy.md §5<br/>판단마다 출처 인용 강제"] --> C["케이스 파일<br/>maintenance/requests/REQ-*.md<br/>에 인용 축적"]
    C --> G["grep 감사<br/>정책별 인용 횟수 집계"]
    G --> D{"인용 0회?"}
    D -->|"예"| X["죽은 지침 → 삭제 또는 수정"]
    D -->|"아니오"| K["살아있는 지침 → 유지"]
```

```bash
grep -rho 'classification-policy\.md §[0-9]' maintenance/requests/ | sort | uniq -c
```

---

## 이 지도의 검증 상태 (필수 2 결과)

| 확인 항목 | 결과 |
| --- | --- |
| ② Lazy Read 가 실제로 발동하나 | ✅ A/A2/A3 실행이 `classification-policy`·`team-capability`·`sizing`·`capacity` 를 도구 호출로 Read |
| 새로 배선한 `sizing.md` 가 소비되나 | ✅ A·A2·A3 세 라운드 `적용한 기준` 에 모두 인용 |
| ① 항상 로드 `team-capability.md` 가 판단을 바꾸나 | ✅ 라운드 3에서 이 파일 때문에 판단이 outsource↔internal 로 갈림 |
| `knowledge/systems/` 갭 | ⚠ 파일 부재로 `classifier` §1② 가 "board = 내부 관리" 를 추측으로 대체 중 |
