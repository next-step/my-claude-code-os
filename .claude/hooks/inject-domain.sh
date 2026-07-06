#!/usr/bin/env bash
# PreToolUse(Edit|Write|MultiEdit) 훅: 편집 대상 경로가 속한 "서비스 도메인" 문서를 자동 주입한다.
# 경로→도메인 매핑은 docs/domain/_territory.tsv (<glob>  <slug>) 에서 읽는다(데이터 주도 = 스크립트 하드코딩 아님).
#   → 도메인을 하나 늘려도 스크립트를 안 고치고 표에 한 줄만 추가하면 된다. /domain 스킬이 이 표를 유지한다.
# 컨벤션 카드 주입(inject-context.sh)과 형제다: 하나는 "어떻게 짜라", 이건 "여긴 무슨 도메인".
# 세션당 도메인별 1회만 주입(dedup = 컨텍스트 절약, inject-context.sh 와 동일 기법).
#
# 입력(stdin, JSON): { tool_input.file_path, session_id, ... }
# 출력(stdout, JSON): { hookSpecificOutput: { hookEventName, additionalContext } }

set -euo pipefail

input=$(cat)
proj="${CLAUDE_PROJECT_DIR:-$(pwd)}"
map="$proj/docs/domain/_territory.tsv"
[ -f "$map" ] || exit 0

fp=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
[ -n "$fp" ] || exit 0

# 절대경로면 프로젝트 기준 상대경로로 환산해 매칭.
rel="${fp#"$proj"/}"

# 편집 경로가 속한 첫 도메인을 찾는다. 글롭은 case 패턴이라 *가 / 를 넘어 매칭한다(중첩 경로 OK).
# 구분자는 공백/탭 모두 허용(기본 IFS). '#' 주석·빈 줄은 건너뛴다.
slug=""
while read -r glob s || [ -n "${glob:-}" ]; do
  case "$glob" in ''|'#'*) continue ;; esac
  # shellcheck disable=SC2254
  case "$rel" in
    $glob) slug="$s"; break ;;
  esac
done < "$map"

[ -n "$slug" ] || exit 0

doc="$proj/docs/domain/$slug.md"
[ -f "$doc" ] || exit 0

# 세션당 도메인별 1회만 주입(중복 주입 방지).
sid=$(printf '%s' "$input" | jq -r '.session_id // "nosession"' 2>/dev/null || echo nosession)
mark="${TMPDIR:-/tmp}/claude-domain-inject-${sid}-${slug}"
[ -e "$mark" ] && exit 0
: > "$mark" 2>/dev/null || true

ctx=$(printf '📎 이 파일이 속한 서비스 도메인 문서 (docs/domain/%s.md) — 코드를 만지기 전 이 도메인의 정체·경계·관계를 참고하라:\n\n%s' "$slug" "$(cat "$doc")")
jq -n --arg c "$ctx" \
  '{hookSpecificOutput: {hookEventName: "PreToolUse", additionalContext: $c}}'
exit 0
