# 컨텍스트 주입 도식 (Context Injection Map)

> 이 프로젝트의 **정본(Single Source of Truth)** 이 실행 중 **언제 컨텍스트 창에 주입되는지**를
> 그림으로 보여주는 문서. 정본 목록·폴더 성격 등 나머지 설명은 [`README.md`](./README.md)에 있고,
> 이 파일은 그중 **"주입"** 한 가지에 집중한다. 정본이나 참조 관계가 바뀌면 이 도식도 함께 갱신한다.

---

## 1. 컨텍스트 주입 — "언제 무엇이 컨텍스트 창에 들어오나"

정본은 `.claude/context/`에 **한 번만 정의**되고, 실행 중 **컨텍스트 창(=모델이 실제로 보는
창)** 에 주입된다. 핵심은 **"어떻게 연결되나"가 아니라 "언제 들어오나"** 다. 주입은 서로 다른
두 시점에 일어난다 — 세션이 켜지는 순간(Eager), 그리고 스킬이 실행되는 순간(Lazy).

### 1-1. 시간축으로 본 주입 (누가 · 언제 · 무엇을)

```mermaid
sequenceDiagram
    autonumber
    participant CM as CLAUDE.md
    participant CTX as .claude/context/
    participant SK as 스킬 (예: /capture)
    participant CW as 🪟 컨텍스트 창

    rect rgb(255, 233, 233)
    Note over CM,CW: ① 세션이 켜지는 순간 — 항상 (Eager)
    CM->>CTX: @import 로 security.md 끌어옴
    CTX-->>CW: 🔴 security.md 상주 (세션 내내 안 빠짐)
    end

    rect rgb(255, 248, 224)
    Note over SK,CW: ② 스킬이 실행되는 순간 — 그때만 (Lazy)
    SK->>CTX: Read data-model.md
    SK->>CTX: Read status-lifecycle.md
    SK->>CTX: Read categories.md
    CTX-->>CW: 🟡 3종 일시 로드 (스킬 끝나면 빠짐)
    end
```

읽는 법: **위 빨강 블록은 세션 시작 때 자동으로, 아래 노랑 블록은 스킬을 부를 때만** 일어난다.
즉 주입 = "정본을 컨텍스트 창에 넣는 사건"이고, 그 사건이 두 시점으로 갈린다.

### 1-2. 그래서 컨텍스트 창 안에는 실제로 뭐가 있나 (순간별 스냅샷)

같은 세션이라도 **어느 순간이냐에 따라 창 안의 정본이 달라진다.** 이게 Eager와 Lazy의 실제 차이.

```mermaid
flowchart LR
    subgraph T0["🕐 세션 시작 직후<br/>(아무 스킬도 안 씀)"]
        A["🔴 security.md"]
    end
    subgraph T1["🕑 /capture 실행 중"]
        B["🔴 security.md"]
        C["🟡 data-model"]
        D["🟡 categories"]
        E["🟡 status-lifecycle"]
    end
    subgraph T2["🕒 capture 끝난 뒤"]
        F["🔴 security.md"]
    end
    T0 -->|capture 호출| T1 -->|스킬 종료| T2
```

🔴는 세 순간 내내 그대로, 🟡는 스킬이 도는 동안만 나타났다 사라진다. **"Lazy = 일시적"** 이
이 그림의 핵심 — 평상시엔 창에 없으니 토큰을 안 먹고, 필요할 때만 잠깐 올라온다.

### 1-3. 두 방식 한눈 대비

| | 🔴 **Eager** | 🟡 **Lazy** |
|--|--------------|-------------|
| **대상** | `security.md` 1종 | 나머지 4종 |
| **언제 들어오나** | 세션 시작 시 자동 | 스킬 실행 시 |
| **넣는 주체** | `CLAUDE.md`의 `@import` | 스킬 안의 `Read` 호출 |
| **얼마나 머무나** | 세션 내내 상주 | 스킬 도는 동안만 |
| **보장성** | **100% 보장** | 모델이 Read해야 함(비보장) |
| **토큰 비용** | 매 세션 (그래서 짧아야) | 평상시 0, 쓸 때만 |

> **승격 기준**: "빈도 높음"이 아니라 **"안 읽으면 사고 + 파일이 짧음"**일 때만 Eager로 올린다.
> `security.md`가 유일하게 Eager인 이유 — 자격증명을 잘못 다루면 곧 사고이기 때문.

---

## 2. 누가 무엇을 주입받나 — 스킬·에이전트별 참조 정본

§1이 "언제 주입되나"라면, 이 표는 **"어느 소비자가 어떤 정본을 Read하나"** 를 보여준다.
§1-2 스냅샷에서 `/capture`가 왜 하필 저 3종을 로드했는지의 근거가 이 표다.
✅ = 그 소비자가 해당 정본을 Read한다.

| 소비자 | categories | data-model | status-lifecycle | design-principles | security |
|--------|:--:|:--:|:--:|:--:|:--:|
| capture | ✅ | ✅ | ✅ | | |
| list | | ✅ | ✅ | | |
| plan | ✅ | ✅ | ✅ | | |
| remind | | ✅ | ✅ | | ✅ |
| done | | | | | (🔴 상시) |
| classifier-agent | ✅ | | | | |
| telegram-agent | | | | | ✅ |
| state-sync-writer | | | | ✅ | |
| state-scanner | | | | ✅ | |

> `security.md`는 🔴 Eager라 표의 ✅가 없어도 모든 소비자 컨텍스트에 이미 존재한다. `remind`·
> `telegram-agent`가 명시적으로도 거는 건, 자격증명을 직접 만지는 경로라 강조하기 위함.
>
> `state-scanner`는 `sync-readme` 스킬이 위임해 스캔·비교를 수행하는 공유 에이전트다. `sync-readme`
> 자체는 정본을 직접 Read하지 않고 `state-scanner`에 위임하므로, 직접 참조 주체인 `state-scanner`만
> 표에 오른다(정본 참조는 `design-principles.md` 1종).
>
> 이 표는 실물에서 재확인할 수 있다:
> `grep -roE "\.claude/context/[a-z-]+\.md" .claude/skills/`
