---
name: skill-stat
description: 스킬 호출 기록(.claude/skill-usage.log)을 집계해 통계로 보여준다. 사용자가 "스킬 통계", "어떤 스킬 많이 썼어", "호출 횟수 보여줘", "skill-stat" 이라고 할 때 사용한다.
user-invocable: true
allowed-tools:
  - Bash(cat:*)
  - Bash(wc:*)
  - Bash(cut:*)
  - Bash(sort:*)
  - Bash(uniq:*)
  - Bash(grep:*)
  - Bash(awk:*)
  - Bash(test:*)
  - Bash(head:*)
  - Bash(tail:*)
---

# /skill-stat — 스킬 호출 통계

PreToolUse 훅이 `.claude/skill-usage.log` 에 기록한 스킬 호출 내역을 집계해
보기 좋게 보여줍니다. (로그 한 줄 = 호출 1회, 형식: `시각<TAB>스킬명`)

전달된 인자: `$ARGUMENTS`
- 인자가 없으면 → 전체 통계
- 특정 스킬명이 주어지면 → 그 스킬만 필터링해서 통계

---

## 진행 순서

### 1단계: 로그 존재 확인

```bash
test -f ".claude/skill-usage.log"
```

파일이 없으면 "아직 기록된 스킬 호출이 없습니다. 스킬을 한 번 호출하면 기록이 시작됩니다."
라고 안내하고 종료한다. (훅이 `/hooks` 또는 재시작으로 활성화되어야 기록됨을 함께 알린다.)

### 2단계: 집계 (한 번에 실행)

아래 명령들로 핵심 수치를 모은다.

```bash
LOG=".claude/skill-usage.log"

# 총 호출 횟수
wc -l < "$LOG"

# 스킬별 호출 횟수 (많은 순)
cut -f2 "$LOG" | sort | uniq -c | sort -rn

# 최근 호출 5건
tail -n 5 "$LOG"

# 오늘 호출 횟수 (선택) — 오늘 날짜로 시작하는 줄 수
#   날짜는 사용자에게 주어진 currentDate 를 사용하거나 무시 가능
```

### 3단계: 표로 정리해 보고

다음 형태로 사람이 읽기 좋게 출력한다:

```
📊 스킬 호출 통계

총 호출: N건   (서로 다른 스킬 M종)

순위  스킬            호출 수   비율
 1    commit            12     50%
 2    skill-stat         7     29%
 3    deep-research      5     21%

최근 호출:
  2026-06-25 14:03  commit
  2026-06-25 13:50  skill-stat
  ...
```

- 비율은 (해당 스킬 횟수 / 총 호출) 로 계산한다.
- 막대(▇)를 곁들여 시각적으로 표현하면 더 좋다.

### 4단계: 가벼운 인사이트 (선택)

가장 많이 쓴 스킬, 거의 안 쓰는 스킬 등 눈에 띄는 점이 있으면 한두 줄로 짚어준다.
과한 분석은 피하고 데이터에 근거한 것만 말한다.

---

## 참고
- 로그 파일은 `.gitignore` 에 포함되어 커밋되지 않는 개인 사용 기록이다.
- 기록은 `PreToolUse`(matcher: `Skill`) 훅과 `UserPromptSubmit` 훅이 담당한다. 통계가 비어 있으면 훅이 활성화됐는지(`/hooks`) 먼저 확인한다.
- 로그 경로는 **상대경로**(`.claude/skill-usage.log`)로 읽는다 — Bash 도구의 cwd가 프로젝트 루트다. `$CLAUDE_PROJECT_DIR`는 **훅 실행 시에만** 채워지고 Bash 도구 셸에선 비어 있으니 쓰지 말 것(빈 경로로 오판함).
