#!/usr/bin/env bash
# STATUS.md(현황 문서)를 세션 시작 시 컨텍스트로 자동 주입하는 hook.
#
# CLAUDE.md 는 "작업 시작 시 STATUS.md 를 먼저 확인하라"고 적어두지만, 그건 부탁일 뿐
# 강제가 아니다. 모델이 읽기로 선택해야만 읽힌다. 이 훅은 그 부탁을 보장으로 바꾼다.
#
# STATUS.md 는 46줄 남짓이라 매 세션 통째로 넣어도 컨텍스트 부담이 거의 없다.
# (반면 OS.md 는 315줄이라 주입하지 않고 CLAUDE.md 의 이정표로만 가리킨다.)
#
# 의존성 없음(jq 불필요). 어떤 경우에도 세션 시작을 막지 않도록 항상 exit 0 한다.
#
# 사용법: status-context.sh <hookEventName>
#   예) status-context.sh SessionStart

set -uo pipefail

EVENT="${1:-SessionStart}"
ROOT="${CLAUDE_PROJECT_DIR:-.}"
STATUS="$ROOT/STATUS.md"

[ -f "$STATUS" ] || exit 0

emit_status() {
  printf '# 현재 진행 상태 (STATUS.md · 자동 주입)\n\n'
  printf '> `.claude/hooks/status-context.sh` 가 세션 시작 시 파일을 그대로 읽어 넣는다.\n'
  printf '> **작업이 끝나거나 막히면 `STATUS.md` 를 갱신할 것.** 아래는 스냅샷이 아니라 원본 전문이다.\n\n'
  printf -- '---\n\n'
  cat "$STATUS"
}

# 문자열을 JSON string 리터럴 본문으로 이스케이프한다.
#   1) 역슬래시 → \\      2) 따옴표 → \"      3) 탭 → \t
#   4) CR 제거            5) 개행 → \n (마지막 줄 개행은 남기지 않음)
json_escape() {
  sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/\t/\\t/g' -e 's/\r//g' \
    | sed -e ':a' -e 'N' -e '$!ba' -e 's/\n/\\n/g'
}

CONTEXT="$(emit_status | json_escape)" || exit 0
[ -n "$CONTEXT" ] || exit 0

printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"%s"}}\n' \
  "$EVENT" "$CONTEXT"

exit 0
