---
name: skill-stat
description: Use when the user asks to see skill usage statistics, how many times skills have been called, or wants a report of skill invocation counts (e.g. "스킬 통계 보여줘", "스킬 호출 몇 번 됐어?", "어떤 스킬을 제일 많이 썼어?"). Reads .claude/skill-stats.json (written by the record_skill_usage.py PostToolUse hook) and displays counts sorted by frequency.
---

# skill-stat

## 개요

`.claude/hooks/record_skill_usage.py` PostToolUse 훅이 스킬 호출마다 누적한
`.claude/skill-stats.json`을 읽어, 호출 빈도 내림차순 표로 보여주는 스킬이다.

## 동작 순서

1. `.claude/skill-stats.json`을 Read 도구로 읽는다.
   - 파일이 없거나, 내용이 비어 있거나, JSON 파싱이 안 되면: "아직 기록된
     스킬 호출이 없습니다."라고 안내하고 종료한다.
2. JSON을 `{스킬 이름: 호출 수}` 형태의 객체로 파싱한다.
3. 호출 수 기준 내림차순으로 정렬한다. 호출 수가 같으면 스킬 이름 가나다순으로
   정렬한다.
4. 다음 형식의 마크다운 표로 출력한다:

   | 순위 | 스킬 | 호출 수 |
   |---|---|---|
   | 1 | claude-api | 12 |
   | 2 | skill-stat | 3 |

5. 표 아래에 총 호출 수와 서로 다른 스킬 개수를 한 줄로 덧붙인다. 예:
   "총 15회 호출, 2개의 서로 다른 스킬 사용."

## 주의

- 이 스킬은 파일을 수정하지 않는다 — 읽기만 한다.
- 통계 파일 경로는 항상 프로젝트 루트 기준 `.claude/skill-stats.json`이다.
