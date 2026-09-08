#!/usr/bin/env bash
# PostToolUse(Write|Edit) — 배선 관련 파일이 수정되면 check-context-wiring.sh 를 돌려
# 배선이 깨졌는지 즉시 알린다.
#
# 비차단: 편집을 막지 않는다. 깨졌으면 additionalContext 로 경고만 띄운다.
# 대상: CLAUDE.md / .claude/context/ / settings.json / agents·skills 정의 / hooks/
set -u

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
CHECK="$PROJECT_DIR/.claude/scripts/check-context-wiring.sh"
[ -x "$CHECK" ] || exit 0

input="$(cat)"
fp="$(printf '%s' "$input" | jq -r '.tool_input.file_path // .tool_input.path // empty')"
[ -n "$fp" ] || exit 0

case "$fp" in
  */CLAUDE.md|*/.claude/context/*|*/.claude/settings.json|*/.claude/agents/*.md|*/.claude/skills/*/SKILL.md|*/.claude/hooks/*) : ;;
  *) exit 0 ;;
esac

out="$(bash "$CHECK" 2>&1)"; rc=$?
[ "$rc" -eq 0 ] && exit 0

fails="$(printf '%s\n' "$out" | grep 'FAIL' | sed 's/^[[:space:]]*//;s/'$'\033''\[[0-9;]*m//g')"
jq -n --arg f "$fails" '{
  hookSpecificOutput: {
    hookEventName: "PostToolUse",
    additionalContext: ("⚠️ 방금 편집으로 컨텍스트 배선이 깨졌다. check-context-wiring.sh FAIL:\n" + $f + "\n.claude/context/README.md 의존 표와 소비자 배선을 다시 맞춰라.")
  }
}'
exit 0
