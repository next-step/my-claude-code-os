# My Claude Code OS

Claude Code 위에 쌓아 올린 **작은 자동 개발 운영체제(OS)**다.
사람이 "무엇을" 원하는지 말하면, 여러 전문 **서브에이전트**가 릴레이로 **분석 → 개발 → 검증 → 문서화**를 수행하고, 그 흐름을 **스킬**이 지휘한다.

> 이 문서는 처음 보는 사람이 이 OS의 구조와 사용법을 한 번에 이해하도록 쓴 개요다.

---

## 1. 큰 그림 — 두 가지 부품

이 OS는 딱 두 종류의 부품으로 이루어진다.

| 부품 | 무엇인가 | 비유 |
|------|----------|------|
| **서브에이전트 (agent)** | 한 가지 일만 잘하는 전문가. 각자 고유한 권한(도구)과 지침을 가짐 | 팀의 개별 구성원 |
| **스킬 (skill)** | 에이전트들을 **어떤 순서로 부를지** 지휘하는 워크플로우 | 팀을 이끄는 매니저(오케스트레이터) |

핵심 아이디어: **스킬은 "흐름"을 담고, 에이전트는 "실행"을 담는다.** 이 둘을 분리했기 때문에 하나의 에이전트를 여러 스킬이 재활용할 수 있다.

---

## 2. 디렉터리 구조

```
my-claude-code-os/
├─ CLAUDE.md                     # 프로젝트 전역 지침(모든 세션에 로드됨)
├─ OS.md                         # ← 이 문서
├─ scripts/
│  └─ skill_stats.py             # 산출물: 스킬 사용 로그 통계 유틸
├─ tests/
│  └─ test_skill_stats.py        # 산출물: 위 유틸의 unittest (24개)
└─ .claude/
   ├─ settings.json              # 훅 등록 등 프로젝트 설정
   ├─ agents/                    # ── 서브에이전트 정의 (each *.md) ──
   │  ├─ code-analyzer.md        #   ① 코드베이스 파악 (읽기 전용)
   │  ├─ test-writer.md          #   ②a 요구 분석 + red 테스트 작성 (쓰기)
   │  ├─ impl-writer.md          #   ②b red 테스트를 green으로 구현 (쓰기)
   │  ├─ review-correctness.md   #   ③ 리뷰 렌즈: 정확성·안정성 (읽기 전용, 병렬)
   │  ├─ review-tests.md         #   ③ 리뷰 렌즈: 테스트 (읽기 전용, 병렬)
   │  ├─ code-reviewer.md        #   ③ 단일 리뷰·판정 (quick-review 전용, 읽기 전용)
   │  └─ doc-writer.md           #   ④ 문서화 (문서만 쓰기)
   ├─ skills/                    # ── 스킬 정의 (each <이름>/SKILL.md) ──
   │  ├─ feature-dev/            #   기능 개발 풀 파이프라인
   │  ├─ quick-review/           #   가벼운 코드 리뷰
   │  ├─ git-commit/             #   커밋·푸시
   │  └─ skill-stat/             #   스킬 사용 통계(bash)
   ├─ hooks/
   │  └─ skill-counter.sh        # 스킬 실행 때마다 로그를 남기는 훅
   └─ logs/
      └─ skill-usage.log         # "시각<TAB>스킬이름" 한 줄씩 누적
```

**규칙**: 에이전트는 `.claude/agents/<이름>.md`, 스킬은 `.claude/skills/<이름>/SKILL.md`. 파일을 두면 Claude Code가 자동으로 인식한다(재시작·빌드 불필요).

---

## 3. 서브에이전트 (7개)

각 에이전트는 `.md` 파일 하나이고, 상단 frontmatter에 `name`·`description`·`tools`(권한)를 둔다.

| 에이전트 | 단계 | 역할 | 권한(tools) | 코드 수정 |
|----------|:----:|------|-------------|:--------:|
| **code-analyzer** | ① | 관련 파일·관습·진입점을 지도로 정리 | Read, Grep, Glob, Bash | ✗ (읽기 전용) |
| **test-writer** | ②a | 요구 분석 → 수용 기준 → **실패하는(red) 테스트** 작성 | Read, Grep, Glob, **Write, Edit**, Bash | 테스트만 |
| **impl-writer** | ②b | red 테스트를 **green**으로 만드는 최소 구현 (테스트는 못 고침) | Read, Grep, Glob, **Write, Edit**, Bash | 구현만 |
| **review-correctness** | ③ | 리뷰 렌즈 **정확성·안정성** → 판정 (feature-dev, 병렬) | Read, Grep, Glob, Bash | ✗ (지적만) |
| **review-tests** | ③ | 리뷰 렌즈 **테스트 커버리지·green** → 판정 (feature-dev, 병렬) | Read, Grep, Glob, Bash | ✗ (지적만) |
| **code-reviewer** | ③ | 단일 리뷰 후 **통과/수정필요** 판정 (quick-review 전용) | Read, Grep, Glob, Bash | ✗ (지적만) |
| **doc-writer** | ④ | 변경 내용을 문서로 기록 | Read, Grep, Glob, **Write, Edit** | 문서만 |

> 💡 **최소 권한 원칙**: 필요한 도구만 준다. 읽기 전용(analyzer·review-*·code-reviewer)은 Write/Edit이 없고, doc-writer는 코드 실행이 필요 없어 Bash도 없다.
>
> 💡 **②단계 TDD 분리**: `test-writer`가 "무엇이 맞는가"(red 테스트=명세)를, `impl-writer`가 "어떻게 충족하는가"(green 구현)를 소유한다. impl-writer는 **남이 쓴 테스트를 통과시켜야** 하므로 자기 테스트를 무력화할 수 없다. 단, 도구 권한으로 경로를 막지는 못하므로 스킬이 `git diff`로 테스트 미변경을 사후 검증한다.
>
> 💡 **③단계 리뷰의 두 갈래**: 무거운 `feature-dev`는 관점을 나눈 `review-correctness`·`review-tests`를 **병렬로** 돌려 깊게 검증하고, 가벼운 `quick-review`는 단일 `code-reviewer`로 빠르게 본다. 자세한 설계 근거는 [subagent-specialization.md](.claude/guidelines/subagent-specialization.md) 참고.

---

## 4. 스킬 (4개)

스킬은 두 종류로 나뉜다 — 에이전트를 지휘하는 **오케스트레이터**와, 직접 일을 처리하는 **실행형**.

| 스킬 | 유형 | 트리거(예) | 사용하는 에이전트 |
|------|------|-----------|-------------------|
| **feature-dev** | 오케스트레이터 | "~기능 만들어줘/구현해줘" | analyzer → test-writer → impl-writer → [review-correctness ∥ review-tests] ⇄ (라우팅) → doc-writer |
| **quick-review** | 오케스트레이터 | "리뷰해줘/봐줘" | analyzer → code-reviewer |
| **git-commit** | 실행형 | "커밋해줘/푸시해줘" | (없음 — 직접 git 수행) |
| **skill-stat** | 실행형 | "스킬 통계 보여줘" | (없음 — 로그 집계) |

---

## 5. 오케스트레이션 & 파이프라인

### 5-1. feature-dev — 기능 개발 풀 파이프라인 (4단계 + 검증 루프)

```
   사용자: "○○ 기능 만들어줘"
        │
        ▼                                                   ┌─ review-correctness ─┐ (정확성·안정성)
 ① analyzer ─▶ ②a test-writer ─▶ ②b impl-writer ─▶ ③ ─────┤  (병렬 리뷰)          ├─┐
   (어디를)      (red 테스트=스펙)   (green 구현)             └─ review-tests ───────┘ │ (테스트)
                     ▲                  ▲                                             │
   테스트 🔴 ────────┘   정확성 🔴 ──────┘         판정=수정필요(🔴 하나라도)            │
   (test-writer 보강      (impl-writer 수정)  ◀───────────────────────────────────────┘
    →impl이 green)                                (최대 3회 반복)
                                          │ 둘 다 판정=통과
                                          ▼
                                    ④ doc-writer ──▶ 최종 보고
                                      (문서화)
```

- **② 개발이 TDD 분리**다. `test-writer`가 red 테스트(=명세)를 쓰고, `impl-writer`가 그걸 green으로 만든다. impl-writer는 **테스트를 못 고친다**(남이 쓴 명세를 통과시켜야 함) — 스킬이 `git diff`로 사후 검증한다.
- **③ 검증 루프**가 심장이다. 두 리뷰어를 **병렬로** 돌리고, 지적을 **작성자별로 라우팅**한다 — 정확성 🔴 → impl-writer, 테스트 🔴 → test-writer(보강)→impl-writer(green). **둘 다 "통과"거나 3회 도달 시** 종료한다.
- 리뷰어는 **직접 고치지 않는다.** 수정은 항상 test-writer/impl-writer가 한다.

### 5-2. quick-review — 가벼운 리뷰 (2단계, 읽기 전용)

```
   사용자: "이 코드 리뷰해줘"
        │
        ▼
 ① code-analyzer ──▶ ② code-reviewer ──▶ 판정·지적 보고
   (맥락 파악)         (통과/수정필요)
```

- 새로 만들지 않고 **읽고 판정만** 한다. 코드를 수정하지 않아 빠르고 안전하다.
- 가벼운 흐름이라 **단일 `code-reviewer`**를 쓴다(feature-dev의 관점 병렬 팬아웃은 이 스킬엔 과하다).

### 5-3. 공유 에이전트 (재활용)

```
                    feature-dev     quick-review
 code-analyzer           ✓              ✓        ◀── 공유
 test-writer             ✓              ✗        ◀── TDD 분리(feature-dev 전용)
 impl-writer             ✓              ✗        ◀── TDD 분리(feature-dev 전용)
 review-correctness      ✓              ✗        ◀── 관점 병렬(feature-dev 전용)
 review-tests            ✓              ✗        ◀── 관점 병렬(feature-dev 전용)
 code-reviewer           ✗              ✓        ◀── 단일 리뷰(quick-review 전용)
 doc-writer              ✓              ✗
```

`code-analyzer`는 **두 스킬이 함께 재활용**한다("코드를 파악하는 전문가"를 한 번 정의해 여러 워크플로우에서 돌려 씀). 리뷰는 무게에 따라 갈라진다 — 무거운 개발은 관점을 나눈 `review-*` 병렬, 가벼운 리뷰는 단일 `code-reviewer`. 같은 "판정" 역할이라도 상황에 맞는 깊이를 고르는 것이 세분화의 이점이다.

---

## 6. 실행 방법 — 어떻게 명령하나

명령하는 방법은 3가지이고, 대부분은 **①번(자연어)**이면 충분하다.

| 방식 | 방법 | 예시 |
|------|------|------|
| ① 자연어(기본) | 하고 싶은 걸 그냥 말함 → 알맞은 스킬이 자동 선택 | `"로그 파싱 기능 만들어줘"` |
| ② 슬래시(명시) | `/스킬이름`으로 특정 스킬 콕 집기 | `/feature-dev`, `/quick-review` |
| ③ 에이전트 지정 | 특정 에이전트 하나만 직접 호출 | `"code-analyzer로 구조 파악해줘"` |

**대표 3가지만 기억하면 된다:**
- 만들 때 → **feature-dev** (`"~만들어줘"`)
- 볼 때 → **quick-review** (`"리뷰해줘"`)
- 올릴 때 → **git-commit** (`"커밋해줘"`)

### 산출물 유틸 직접 실행
```bash
python3 scripts/skill_stats.py            # 스킬 사용 통계 (전체)
python3 scripts/skill_stats.py --top 2    # 상위 2개만
python3 -m unittest discover tests        # 테스트 24개 실행
```

---

## 7. 훅 & 로깅 — OS가 자기 사용을 기록한다

```
 스킬 실행(Skill 툴 호출)
        │  settings.json 의 PreToolUse 훅(matcher: "Skill")
        ▼
 skill-counter.sh  ──기록──▶  .claude/logs/skill-usage.log   ("시각<TAB>스킬이름")
                                          │
                          ┌───────────────┴───────────────┐
                          ▼                                ▼
                  skill-stat (스킬)                 scripts/skill_stats.py (유틸)
                  로그를 bash로 집계                로그를 파이썬으로 집계 + --top N
```

- 어떤 스킬이든 실행되면 훅이 자동으로 로그 한 줄을 남긴다.
- 그 로그를 `skill-stat` 스킬(bash)이나 `skill_stats.py`(파이썬)로 통계 낼 수 있다 — **OS가 자신의 사용 패턴을 관찰하는 피드백 루프**다.

---

## 8. 산출물 (이 OS로 만든 결과물)

| 파일 | 무엇 | 만든 방법 |
|------|------|-----------|
| `scripts/skill_stats.py` | 스킬 사용 로그 통계 유틸(`--top N` CLI 옵션 + 순수 함수 `count_skills`·`count_by_weekday`·`top_skills`) | **feature-dev 파이프라인**으로 개발 |
| `tests/test_skill_stats.py` | 위 유틸의 unittest 24개 (전부 green) | 같은 파이프라인의 개발 단계(현재는 test-writer→impl-writer)가 작성 |
| `scripts/injection_check.py` + `tests/test_injection_check.py` | 지침 주입(배선)이 깨지면 빨갛게 되는 검증 안전망(순수 함수 3 + 통합 테스트 5 + CLI). `python3 scripts/injection_check.py`로 배선 상태 확인 | 직접 작성 (testing.md·coding-style.md 준수) |
| [`context-system.html`](context-system.html) | 컨텍스트 체계(SSOT→3중 주입→파이프라인 소비)와 주입 A/B를 담은 1페이지 도식 | 직접 작성 (아티팩트) |

이 산출물 자체가 "OS 전체 사이클이 실제로 한 바퀴 돈다"는 증거다. feature-dev를 여러 번(초기 구현 → `--top N` → 요일별 집계) 구동했고, 매번 4단계 + 검증 루프를 완주했다. 전체 테스트는 49개(skill_stats 24 + injection_check 25) 전부 green이다.

> 💡 **컨텍스트 지침 체계**는 별도 문서 없이 [`context-system.html`](context-system.html)에 시각화돼 있다. 각 에이전트의 역할·권한 요약은 위 **3장 표**가, 지침 자체의 정의는 `.claude/guidelines/`의 각 파일이 단일 출처(SSOT)다.

### 8-1. `count_by_weekday` — 요일별 호출 집계 (순수 함수)

로그의 시각에서 **요일을 파생**해 요일별 호출 횟수를 세는 순수 함수다. 반환은 `{요일한글: 횟수}` dict이며, 키 순서는 등장/횟수 순이 아니라 **월→화→수→목→금→토→일 고정 순서**(등장한 요일만 포함)다. 무시 규칙은 `count_skills`와 같고(빈 줄·탭 없는 줄·스킬이름 빈 줄), 여기에 **날짜 파싱 불가 줄**도 추가로 건너뛴다.

```python
from skill_stats import count_by_weekday

lines = [
    "2026-06-25 20:34:11\tgit-commit",   # 목
    "2026-06-25 09:00:00\tfeature-dev",  # 목
    "2026-07-02 08:43:54\tquick-review", # 목
]
count_by_weekday(lines)   # {"목": 3}
```

> 💡 **왜 CLI에 노출하지 않았나?** 이번엔 순수 함수와 모듈 상수(`WEEKDAYS_KO`)만 추가하고 `--by-weekday` 같은 CLI 옵션은 넣지 않았다(YAGNI). 실제 요구가 생기기 전에 인터페이스부터 늘리면 유지할 표면적만 커진다. 지금은 다른 코드가 `import`해 쓰거나 테스트로 검증하는 형태로만 존재한다.
>
> 💡 **왜 키 순서를 고정하나?** 요약 리포트에서 요일 축은 항상 같은 순서로 읽혀야 사람이 비교하기 쉽다. 그래서 등장 순서(dict 삽입 순)에 맡기지 않고 `WEEKDAYS_KO` 기준으로 재조립한다.

---

## 9. 설계 원칙 (왜 이렇게 만들었나)

1. **역할 분리** — 만드는 사람(writer)과 검증하는 사람(reviewer)을 나눈다. 자기 코드를 자기가 리뷰하면 생기는 확증 편향을 막는다.
2. **최소 권한** — 각 에이전트에 딱 필요한 도구만 준다. 읽기 전용은 읽기만, 문서 담당은 문서만.
3. **종료 조건 있는 루프** — 검증 루프는 "판정=통과" 또는 "3회"에서 반드시 멈춘다. 자동화가 무한 반복에 빠지지 않게.
4. **명시적 인계** — 서브에이전트끼리는 대화 맥락을 공유하지 않으므로, 스킬이 앞 단계 결과를 다음 단계 입력으로 직접 넘긴다.
5. **자동 발견** — 파일을 규칙대로 두기만 하면 인식된다. 별도 등록/빌드가 없다.

---

## 10. 확장하는 법

- **새 에이전트 추가** → `.claude/agents/<이름>.md` 생성. frontmatter에 `name`·`description`·`tools`를 적고, 본문에 역할·절차·출력형식·원칙을 쓴다. 어떤 스킬이 부를지도 함께 정한다(에이전트는 스킬이 불러야 동작).
- **새 스킬 추가** → `.claude/skills/<이름>/SKILL.md` 생성. `description`에 트리거 문구("~할 때 사용한다")를 자연어로 적을수록 자동 선택이 잘 된다. 훅 카운팅은 자동 포함된다.
- **팁** — `description`은 곧 "리모컨 버튼의 라벨"이다. 자동 선택이 잘 안 되면 트리거 문구를 보강하라.
