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
│  └─ test_skill_stats.py        # 산출물: 위 유틸의 unittest (16개)
└─ .claude/
   ├─ settings.json              # 훅 등록 등 프로젝트 설정
   ├─ agents/                    # ── 서브에이전트 정의 (each *.md) ──
   │  ├─ code-analyzer.md        #   ① 코드베이스 파악 (읽기 전용)
   │  ├─ code-writer.md          #   ② 분석·개발·테스트 (쓰기)
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

## 3. 서브에이전트 (4개)

각 에이전트는 `.md` 파일 하나이고, 상단 frontmatter에 `name`·`description`·`tools`(권한)를 둔다.

| 에이전트 | 단계 | 역할 | 권한(tools) | 코드 수정 |
|----------|:----:|------|-------------|:--------:|
| **code-analyzer** | ① | 관련 파일·관습·진입점을 지도로 정리 | Read, Grep, Glob, Bash | ✗ (읽기 전용) |
| **code-writer** | ② | 요구 분석 → 테스트 작성 → 구현(TDD) | Read, Grep, Glob, **Write, Edit**, Bash | ✓ |
| **review-correctness** | ③ | 리뷰 렌즈 **정확성·안정성** → 판정 (feature-dev, 병렬) | Read, Grep, Glob, Bash | ✗ (지적만) |
| **review-tests** | ③ | 리뷰 렌즈 **테스트 커버리지·green** → 판정 (feature-dev, 병렬) | Read, Grep, Glob, Bash | ✗ (지적만) |
| **code-reviewer** | ③ | 단일 리뷰 후 **통과/수정필요** 판정 (quick-review 전용) | Read, Grep, Glob, Bash | ✗ (지적만) |
| **doc-writer** | ④ | 변경 내용을 문서로 기록 | Read, Grep, Glob, **Write, Edit** | 문서만 |

> 💡 **최소 권한 원칙**: 필요한 도구만 준다. 읽기 전용 리뷰어들(analyzer·review-*·code-reviewer)은 Write/Edit이 없고, doc-writer는 코드 실행이 필요 없어 Bash도 없다.
>
> 💡 **③단계 리뷰의 두 갈래**: 무거운 `feature-dev`는 관점을 나눈 `review-correctness`·`review-tests`를 **병렬로** 돌려 깊게 검증하고, 가벼운 `quick-review`는 단일 `code-reviewer`로 빠르게 본다. 자세한 설계 근거는 [subagent-specialization.md](.claude/guidelines/subagent-specialization.md) 참고.

---

## 4. 스킬 (4개)

스킬은 두 종류로 나뉜다 — 에이전트를 지휘하는 **오케스트레이터**와, 직접 일을 처리하는 **실행형**.

| 스킬 | 유형 | 트리거(예) | 사용하는 에이전트 |
|------|------|-----------|-------------------|
| **feature-dev** | 오케스트레이터 | "~기능 만들어줘/구현해줘" | analyzer → writer → [review-correctness ∥ review-tests] ⇄ writer → doc-writer |
| **quick-review** | 오케스트레이터 | "리뷰해줘/봐줘" | analyzer → code-reviewer |
| **git-commit** | 실행형 | "커밋해줘/푸시해줘" | (없음 — 직접 git 수행) |
| **skill-stat** | 실행형 | "스킬 통계 보여줘" | (없음 — 로그 집계) |

---

## 5. 오케스트레이션 & 파이프라인

### 5-1. feature-dev — 기능 개발 풀 파이프라인 (4단계 + 검증 루프)

```
   사용자: "○○ 기능 만들어줘"
        │
        ▼                                  ┌─ review-correctness ─┐ (정확성·안정성)
 ① code-analyzer ──▶ ② code-writer ──▶ ③ ─┤  (병렬 리뷰)          ├─┐
   (어디를·어떻게)     (테스트+구현)         └─ review-tests ───────┘ │ (테스트)
                            ▲                                        │
                            │        판정=수정필요(🔴 하나라도)        │
                            └────────────────────────────────────────┘
                                     (최대 3회 반복)
                                          │ 둘 다 판정=통과
                                          ▼
                                    ④ doc-writer ──▶ 최종 보고
                                      (문서화)
```

- **③ 검증 루프**가 이 파이프라인의 심장이다. 두 리뷰어(`review-correctness`·`review-tests`)를 **병렬로** 돌려 각자의 렌즈로 검증한다. **둘 중 하나라도** 🔴(Blocking)을 찾으면 **수정필요** → 두 리뷰어의 지적을 합쳐 writer에게 되돌려 고치고 → 다시 리뷰. **둘 다 "통과"가 되거나 3회에 도달하면** 종료한다(무한 루프 방지).
- 두 판정의 취합(🔴 하나라도 → 수정필요)은 **스킬이 직접** 한다 — 관점이 2개라 별도 취합 에이전트는 두지 않았다.
- 리뷰어는 **직접 고치지 않는다.** 수정은 항상 writer가 한다.

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
 code-writer             ✓              ✗
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
python3 -m unittest discover tests        # 테스트 16개 실행
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
| `scripts/skill_stats.py` | 스킬 사용 로그 통계 유틸(`--top N` 옵션 포함) | **feature-dev 파이프라인**으로 개발 |
| `tests/test_skill_stats.py` | 위 유틸의 unittest 16개 (전부 green) | 같은 파이프라인의 code-writer가 작성 |

이 산출물 자체가 "OS 전체 사이클이 실제로 한 바퀴 돈다"는 증거다. feature-dev를 2회(초기 구현 + `--top N` 추가) 구동했고, 매번 4단계 + 검증 루프를 완주했다.

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
