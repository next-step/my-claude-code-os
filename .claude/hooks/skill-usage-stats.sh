#!/usr/bin/env bash
# 스킬(Skill 툴) 호출마다 호출 횟수를 로컬 파일에 기록하는 PreToolUse 훅.
#
# 동작 방식:
#   1. Claude Code 가 Skill 툴을 호출하기 직전에 이 스크립트를 실행하고,
#      stdin 으로 훅 이벤트 JSON 을 넘겨준다.
#   2. JSON 에서 스킬 이름(.tool_input.skill)을 뽑는다.
#   3. .claude/skill-usage.log        <- 사람이 읽는 호출 로그 (시각 + 스킬명)
#      .claude/skill-usage-stats.json <- 스킬별 누적 호출 횟수
#   두 파일에 기록한다.
set -euo pipefail

# 훅 실행 시 Claude Code 가 넣어주는 프로젝트 루트. 없으면 현재 디렉터리로 폴백.
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
STATS_FILE="$PROJECT_DIR/.claude/skill-usage-stats.json"
LOG_FILE="$PROJECT_DIR/.claude/skill-usage.log"

# stdin 전체(PreToolUse 이벤트 JSON)를 읽는다.
input="$(cat)"

# 스킬 이름 추출. Skill 툴이 아니거나 이름이 없으면 조용히 종료.
skill_name="$(printf '%s' "$input" | jq -r '.tool_input.skill // empty')"
[ -n "$skill_name" ] || exit 0

# 1) 사람이 읽기 쉬운 호출 로그 한 줄 추가.
printf '%s\t%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$skill_name" >> "$LOG_FILE"

# 2) 카운트 파일 갱신 (없으면 빈 객체에서 시작).
[ -f "$STATS_FILE" ] || printf '{}\n' > "$STATS_FILE"
tmp="$(mktemp)"
jq --arg s "$skill_name" '.[$s] = ((.[$s] // 0) + 1)' "$STATS_FILE" > "$tmp" && mv "$tmp" "$STATS_FILE"

exit 0
