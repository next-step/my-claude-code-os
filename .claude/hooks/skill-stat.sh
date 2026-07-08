#!/usr/bin/env bash
# skill-stat (§6 선택): 스킬 호출을 로컬 로그에 적립. 과제용 통계.
# PostToolUse(Skill) 에서 호출된 스킬 이름을 .claude/skill-stats.log 에 한 줄씩 기록.
#
# 시간 소스: Claude Code 훅 payload 에 timestamp 가 없을 수 있으므로,
# 결정성을 위해 커밋/조회 시점의 파일 순서로만 카운트한다 (라인 = 1회 호출).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG="$ROOT/.claude/skill-stats.log"

payload="$(cat)"
skill=""
if command -v jq >/dev/null 2>&1; then
  skill="$(printf '%s' "$payload" | jq -r '.tool_input.skill // .tool_input.name // empty')"
else
  skill="$(printf '%s' "$payload" | grep -oE '"skill"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*:"([^"]*)"/\1/')"
fi

[[ -n "$skill" ]] || exit 0
printf '%s\n' "$skill" >> "$LOG"
exit 0
