#!/usr/bin/env bash
# PreToolUse(Edit|Write|MultiEdit) 훅: 편집 대상 경로에 맞는 컨텍스트 카드를 "자동 주입"한다.
#   - app/ · tests/  → backend-conventions.md (코드 컨벤션)
#   - docs/          → doc-conventions.md     (문서 작성 규칙)
# 경로 매칭 = 결정적 주입.
#
# 왜 훅인가: 스킬을 안 돌리고 맨손으로 코드를 고칠 때는 SKILL.md 규칙이 안 뜬다.
#            훅은 "무슨 파일을 만지는가"를 보고 규칙을 확실히 끼워 넣는다.
# 최적화(Day2): 같은 카드를 편집마다 다시 넣으면 컨텍스트 낭비 → 세션당 1회만 주입(dedup).
#
# 입력(stdin, JSON): { tool_input.file_path, session_id, ... }
# 출력(stdout, JSON): { hookSpecificOutput: { hookEventName, additionalContext } }

set -euo pipefail

input=$(cat)
proj="${CLAUDE_PROJECT_DIR:-$(pwd)}"

fp=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
[ -n "$fp" ] || exit 0

# 절대경로면 프로젝트 기준 상대경로로 환산해 매칭.
rel="${fp#"$proj"/}"

case "$rel" in
  app/*|tests/*) card="$proj/.claude/context/backend-conventions.md"; slug="backend" ;;
  docs/*)        card="$proj/.claude/context/doc-conventions.md";     slug="docs" ;;
  *) exit 0 ;;
esac

[ -f "$card" ] || exit 0

# 세션당 카드별 1회만 주입(중복 주입 방지 = 컨텍스트 최적화).
sid=$(printf '%s' "$input" | jq -r '.session_id // "nosession"' 2>/dev/null || echo nosession)
mark="${TMPDIR:-/tmp}/claude-ctx-inject-${sid}-${slug}"
[ -e "$mark" ] && exit 0
: > "$mark" 2>/dev/null || true

ctx=$(cat "$card")
jq -n --arg c "$ctx" \
  '{hookSpecificOutput: {hookEventName: "PreToolUse", additionalContext: $c}}'
exit 0
