#!/usr/bin/env bash
# commit-guard (H5, §3-3 게이트): git commit 을 두 조건으로 검문.
#   ① .claude/phase == build 이면 차단 — 커밋은 verifier 감사 + 사람 최종 승인 후에만.
#   ② 커밋 메시지가 conventional commits 형식이 아니면 차단.
#
# 입력: stdin 으로 PreToolUse(Bash) 훅 JSON (tool_input.command 포함).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PHASE_FILE="$ROOT/.claude/phase"

payload="$(cat)"
cmd=""
if command -v jq >/dev/null 2>&1; then
  cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')"
else
  cmd="$(printf '%s' "$payload" | grep -oE '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*:"([^"]*)"/\1/')"
fi

# git commit 이 아니면 통과
printf '%s' "$cmd" | grep -qE '\bgit[[:space:]]+commit\b' || exit 0

# ① phase 검문
phase=""
[[ -f "$PHASE_FILE" ]] && phase="$(tr -d '[:space:]' < "$PHASE_FILE")"
if [[ "$phase" == "build" ]]; then
  echo "H5 위반 차단: build 단계에서는 커밋할 수 없습니다. verifier 감사 통과 + 사람 최종 승인(§3-3) 후 phase 해제 상태에서만 커밋하세요." >&2
  exit 2
fi

# ② conventional commit 메시지 검문 (-m "<msg>" 에서 첫 -m 값 추출)
msg="$(printf '%s' "$cmd" | grep -oE "\-m[[:space:]]+(\"[^\"]*\"|'[^']*')" | head -1 | sed -E "s/^-m[[:space:]]+.//; s/.$//")"
if [[ -n "$msg" ]]; then
  if ! printf '%s' "$msg" | grep -qE '^(feat|fix|refactor|docs|test|chore|perf|ci)(\([^)]+\))?: .+'; then
    echo "커밋 메시지 형식 차단: '<type>: <description>' (type ∈ feat|fix|refactor|docs|test|chore|perf|ci) 을 따르세요. 받은 메시지: $msg" >&2
    exit 2
  fi
fi

exit 0
