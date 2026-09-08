#!/usr/bin/env bash
# style.md 를 파일 작성/수정 직전에 주입하는 PreToolUse 훅 (matcher: Write|Edit).
#
# 왜 훅인가:
#   - style.md(코드·테스트·문서 스타일 규칙)는 "파일을 쓸 때만" 필요하다.
#   - CLAUDE.md @import 로 항상 로드하면 파일을 한 줄도 안 쓰는 세션(질문·조사·계획)에서도
#     매 세션 ~1k 토큰을 낸다.
#   - 이 훅은 그 세션에서 처음 Write/Edit 를 시도할 때 한 번만 style.md 를
#     additionalContext 로 끼워 넣는다. 파일을 안 쓰는 세션은 0 토큰.
#
# 동작:
#   1. Claude Code 가 Write/Edit 툴 실행 직전 이 스크립트를 부르고 stdin 으로 이벤트 JSON 전달.
#   2. session_id 로 마커 파일을 확인 — 이미 이번 세션에 주입했으면 아무것도 출력하지 않고 종료.
#   3. 처음이면 마커를 만들고 style.md 내용을 hookSpecificOutput.additionalContext 로 출력.
set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
STYLE_FILE="$PROJECT_DIR/.claude/context/style.md"

input="$(cat)"
session_id="$(printf '%s' "$input" | jq -r '.session_id // "nosid"')"
marker="${TMPDIR:-/tmp}/claude-style-injected-${session_id}"

# 이미 이번 세션에 주입함 → 조용히 종료 (추가 컨텍스트 없음)
[ -f "$marker" ] && exit 0
[ -f "$STYLE_FILE" ] || exit 0

touch "$marker"

jq -Rs --arg pre "다음은 이 프로젝트의 코드·테스트·문서 스타일 규칙이다 (.claude/context/style.md). 파일을 쓰거나 고칠 때 이를 따른다:

" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: ($pre + .)
  }
}' "$STYLE_FILE"

exit 0
