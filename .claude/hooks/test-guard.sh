#!/usr/bin/env bash
# test-guard (H3): build 단계 동안 src/test/** 는 read-only.
# PreToolUse(Write|Edit) 에서 대상 파일이 테스트 경로이고 phase가 build면 차단.
#
# 입력: stdin 으로 Claude Code 훅 JSON (tool_input.file_path 포함).
# 출력: 차단 시 exit 2 + stderr 메시지 (Claude 에게 사유 전달), 허용 시 exit 0.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PHASE_FILE="$ROOT/.claude/phase"

# 현재 phase 읽기 (없으면 빈 값 → 비차단)
phase=""
[[ -f "$PHASE_FILE" ]] && phase="$(tr -d '[:space:]' < "$PHASE_FILE")"

# build 단계가 아니면 통과
[[ "$phase" == "build" ]] || exit 0

# stdin JSON 에서 대상 파일 경로 추출 (jq 있으면 사용, 없으면 grep 폴백)
payload="$(cat)"
file_path=""
if command -v jq >/dev/null 2>&1; then
  file_path="$(printf '%s' "$payload" | jq -r '.tool_input.file_path // .tool_input.path // empty')"
else
  file_path="$(printf '%s' "$payload" | grep -oE '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*:"([^"]*)"/\1/')"
fi

[[ -n "$file_path" ]] || exit 0

# src/test/ 하위면 차단
case "$file_path" in
  *src/test/*)
    echo "H3 위반 차단: build 단계에서 src/test/** 는 read-only 입니다. 테스트가 틀렸다면 수정하지 말고 '테스트 이의 제기'를 산출물로 남기고 사람에게 올리세요. (대상: $file_path)" >&2
    exit 2
    ;;
esac

exit 0
