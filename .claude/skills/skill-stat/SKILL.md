---
name: skill-stat
description: >-
  PreToolUse 훅이 기록한 스킬 호출 데이터(.claude/skill-usage-stats.json,
  .claude/skill-usage.log)를 읽어 호출 횟수 통계를 보여준다.
  전체 호출 수, 스킬별 순위와 비중, 기록 기간, 오늘 호출 수, 최근 7일 일자별 추이를 낸다.
  사용자가 "스킬 통계", "skill-stat", "스킬 얼마나 썼는지", "호출 횟수 보여줘"를 요청할 때 사용한다.
allowed-tools: Bash, Read
---

# skill-stat — 스킬 호출 통계

`git-commit` 스킬처럼 **정해진 순서**를 따른다. 데이터가 없으면 억지로 만들어내지 말고
"기록 없음"을 그대로 보고한다.

---

## 데이터가 어디서 오는가 (배경)

`.claude/settings.json` 의 `PreToolUse` 훅이 `Skill` 툴 호출마다
`.claude/hooks/skill-usage-stats.sh` 를 실행해서 두 파일을 갱신한다:

| 파일 | 내용 | 무엇을 답하나 |
| --- | --- | --- |
| `.claude/skill-usage-stats.json` | `{ "스킬명": 누적횟수 }` | **누가 몇 번** — 합계·순위·비중 |
| `.claude/skill-usage.log` | `시각<TAB>스킬명` 한 줄 = 한 호출 | **언제** — 기록 기간·오늘·일자별 추이 |

두 파일 모두 `.gitignore` 처리된 **로컬 데이터**다. 새로 클론한 저장소에는 없을 수 있고,
`log` 없이 `stats.json` 만 있을 수도 있다. 스크립트가 두 경우를 모두 처리한다.

훅은 스킬이 실행되기 **직전**에 카운트를 올린다. 따라서 이 통계에는
**방금 실행한 `skill-stat` 호출 자신도 이미 포함**되어 있다 — 보고할 때 한 번 언급해 준다.

---

## 절차

### 1. 리포트 생성

```bash
bash "$CLAUDE_PROJECT_DIR/.claude/skills/skill-stat/report.sh"
```

이 스크립트가 하는 일:

1. `stats.json` 이 없거나 `{}` 이면 → "아직 기록된 호출이 없습니다" 출력 후 종료.
2. `jq` 로 전체 합계와 스킬 수를 구한다.
3. `log` 가 있으면 첫/마지막 기록 시각, 오늘 호출 수를 구한다.
4. `jq` 로 스킬을 횟수 내림차순 정렬하고, `awk` 로 비중(%)과 막대(`█`, 1칸=5%)를 그린다.
5. `log` 가 있으면 최근 7일 일자별 호출 수를 막대(`▪`)로 그린다.

### 2. 결과 정리해서 보고

스크립트 출력을 그대로 붙여도 되지만, 터미널에서 읽기 좋게 **마크다운 표**로 다시 정리해 준다:

```
📊 스킬 호출 통계 (기준: .claude/skill-usage-stats.json)

- 전체 호출: N회 · 사용한 스킬: M개
- 기록 기간: YYYY-MM-DD ~ YYYY-MM-DD · 오늘: K회

| 스킬 | 호출 | 비중 |
| --- | ---: | ---: |
| git-commit | 30 | 71.4% |
| skill-stat | 8 | 19.0% |

*이 수치에는 방금 실행한 skill-stat 호출도 포함됩니다.*
```

`log` 가 없으면 "기간/오늘/추이" 줄은 생략하고, 그 이유(로컬 로그 파일 없음)를 한 줄로 덧붙인다.

### 3. (선택) 사용자가 원하면 더 파고들기

- 특정 스킬만: `grep '<스킬명>$' .claude/skill-usage.log`
- 시간대별 분포: `cut -f1 .claude/skill-usage.log | cut -d' ' -f2 | cut -c1-2 | sort | uniq -c`
- 원본 확인: `cat .claude/skill-usage-stats.json | jq .`

---

## 하지 말 것

1. 데이터가 없는데 예시 숫자를 실제 통계인 것처럼 제시하지 않는다.
2. `stats.json` / `skill-usage.log` 를 이 스킬에서 수정하거나 삭제하지 않는다 (읽기 전용).
3. 훅이나 `settings.json` 을 바꾸지 않는다 — 통계를 "보여주는" 것이 이 스킬의 전부다.
