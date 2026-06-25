#!/usr/bin/env bash
# Skill 호출 카운터 hook.
# - PostToolUse(matcher: Skill)로 등록되어 있다고 가정.
# - stdin으로 들어온 JSON에서 skill 이름을 뽑아 .claude/data/skill-stats.json에 누적.
# - 실패해도 사용자 흐름을 끊지 않도록 항상 exit 0.

set -u

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
STATS_FILE="$PROJECT_DIR/.claude/data/skill-stats.json"

mkdir -p "$(dirname "$STATS_FILE")" 2>/dev/null || exit 0

if [ ! -f "$STATS_FILE" ]; then
  printf '{"version":1,"total_invocations":0,"skills":{}}' > "$STATS_FILE" || exit 0
fi

INPUT="$(cat)"
SKILL="$(printf '%s' "$INPUT" | jq -r '.tool_input.skill // empty' 2>/dev/null)"
[ -z "$SKILL" ] && exit 0

NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TMP="$(mktemp "${TMPDIR:-/tmp}/skill-stats.XXXXXX")" || exit 0

jq --arg s "$SKILL" --arg now "$NOW" '
  .total_invocations = ((.total_invocations // 0) + 1)
  | .updated_at = $now
  | .skills[$s] = (
      (.skills[$s] // {count: 0, first_invoked_at: $now})
      | .count = ((.count // 0) + 1)
      | .last_invoked_at = $now
    )
' "$STATS_FILE" > "$TMP" 2>/dev/null && mv "$TMP" "$STATS_FILE"

rm -f "$TMP" 2>/dev/null
exit 0
