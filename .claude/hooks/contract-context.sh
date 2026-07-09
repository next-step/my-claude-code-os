#!/usr/bin/env bash
# 공유 계약(src/types/contract.ts)을 개발 서브에이전트에게만 주입하는 hook.
#
# CLAUDE.md 는 이 파일을 "공유 타입 단일 출처"로 선언하지만, 정작 backend-developer /
# frontend-developer 는 이 파일을 못 본 채로 시작한다. OS.md 12장은 산문이고, 실제로
# 프론트·백엔드가 딛는 땅은 이 타입 파일이다. 그래서 시작 시점에 통째로 넣어준다.
#
# product-planner 는 타입이 필요 없다(상위 의사결정만 함) → 주입하지 않는다.
# 그 판단 근거는 SubagentStart payload 의 `agent_type` 필드다. (실측 확인:
#   {"session_id":…,"agent_id":…,"agent_type":"backend-developer","hook_event_name":"SubagentStart"})
#
# 의존성 없음(jq 불필요 — 이 환경엔 jq 가 없다). 어떤 경우에도 서브에이전트 시작을
# 막지 않도록 항상 exit 0 한다.
#
# 사용법: contract-context.sh <hookEventName>
#   예) contract-context.sh SubagentStart

set -uo pipefail

EVENT="${1:-SubagentStart}"
ROOT="${CLAUDE_PROJECT_DIR:-.}"
CONTRACT="$ROOT/src/types/contract.ts"

# stdin 의 hook payload 를 한 번만 읽는다. 개행을 지워 한 줄로 만든 뒤 sed 로 뽑는다.
# (payload 가 pretty-print 로 와도 동작하도록)
payload="$(cat 2>/dev/null | tr -d '\n\r')" || exit 0

agent_type="$(printf '%s' "$payload" \
  | sed -n 's/.*"agent_type"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"

# 계약이 필요한 에이전트에게만 준다.
case "$agent_type" in
  backend-developer | frontend-developer) ;;
  *) exit 0 ;;
esac

[ -f "$CONTRACT" ] || exit 0

emit_contract() {
  printf '# 공유 계약 전문 — `src/types/contract.ts` (자동 주입)\n\n'
  printf '> `.claude/hooks/contract-context.sh` 가 개발 서브에이전트 시작 시 주입한다.\n'
  printf '> **이 파일이 프론트·백엔드가 주고받는 데이터 모양의 단일 진실 출처다.**\n'
  printf '> 따로 열어 읽지 말 것. 계약을 바꿔야 하면 OS.md 12장 갱신이 선행이다(기획자 권한).\n'
  printf '> 주석에 타입만 봐서는 알 수 없는 규약이 들어 있으니 그대로 지킬 것.\n\n'
  printf -- '```ts\n'
  cat "$CONTRACT"
  printf -- '```\n'
}

# 문자열을 JSON string 리터럴 본문으로 이스케이프한다.
#   1) 역슬래시 → \\      2) 따옴표 → \"      3) 탭 → \t
#   4) CR 제거            5) 개행 → \n (마지막 줄 개행은 남기지 않음)
json_escape() {
  sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/\t/\\t/g' -e 's/\r//g' \
    | sed -e ':a' -e 'N' -e '$!ba' -e 's/\n/\\n/g'
}

CONTEXT="$(emit_contract | json_escape)" || exit 0
[ -n "$CONTEXT" ] || exit 0

printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"%s"}}\n' \
  "$EVENT" "$CONTEXT"

exit 0
