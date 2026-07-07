#!/usr/bin/env bash
# PreToolUse(Edit|Write|MultiEdit) 훅: 편집 경로가 속한 서비스 도메인의 컨텍스트를 "계층형"으로 주입한다.
#   - 도메인 목차(docs/domain/README.md)는 항상 얹는다(작으니 — 라우팅용).
#   - 손댄 도메인 상세(docs/domain/<slug>.md)는: 작으면 전체, 크면 머리(요약)+"전체는 Read" 포인터.
#     → 기본 도메인 감은 늘 보장하고, 큰 문서만 잘라 컨텍스트를 아낀다.
# 경로→도메인 매핑은 docs/domain/_territory.tsv (<glob>  <slug>)에서 읽는다(데이터 주도). /domain 이 유지.
# 컨벤션 카드 주입(inject-context.sh)의 형제. 세션당 도메인별 1회만 주입(dedup).
#
# 입력(stdin JSON): { tool_input.file_path, session_id, ... }
# 출력(stdout JSON): { hookSpecificOutput: { hookEventName, additionalContext } }

set -euo pipefail

TIER_MAX_LINES=60     # 상세 문서가 이 줄 수 이하면 전체 주입, 넘으면 머리(요약)+포인터.
TIER_HEAD_LINES=16    # 큰 문서일 때 얹을 머리(요약) 줄 수 — 제목·한 줄 정의·정체 머리 정도.

input=$(cat)
proj="${CLAUDE_PROJECT_DIR:-$(pwd)}"
map="$proj/docs/domain/_territory.tsv"
[ -f "$map" ] || exit 0

fp=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
[ -n "$fp" ] || exit 0
rel="${fp#"$proj"/}"

# 편집 경로가 속한 첫 도메인. 글롭은 case 패턴(*가 / 를 넘어 매칭). 공백/탭 구분·'#' 주석 허용.
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

# 세션당 도메인별 1회만 주입.
sid=$(printf '%s' "$input" | jq -r '.session_id // "nosession"' 2>/dev/null || echo nosession)
mark="${TMPDIR:-/tmp}/claude-domain-inject-${sid}-${slug}"
[ -e "$mark" ] && exit 0
: > "$mark" 2>/dev/null || true

# 목차(항상, 있으면). 라우팅용이라 작다.
toc="(목차 파일 없음)"
readme="$proj/docs/domain/README.md"
[ -f "$readme" ] && toc="$(cat "$readme")"

# 상세: 작으면 전체, 크면 머리+포인터(계층형).
lines=$(wc -l < "$doc" | tr -d ' ')
if [ "${lines:-0}" -le "$TIER_MAX_LINES" ]; then
  detail="$(cat "$doc")"
  note="전체"
else
  detail="$(head -n "$TIER_HEAD_LINES" "$doc")
…(이하 생략) — 더 깊은 맥락이 필요하면 docs/domain/$slug.md 를 직접 Read 하라."
  note="요약 · 큰 문서라 머리만"
fi

ctx=$(printf '📎 이 파일은 서비스 도메인 **%s** 영역이다. 아래 도메인 목차와 요약을 참고하고, 더 깊은 맥락이 필요하면 목차에서 골라 Read 하라.\n\n== 도메인 목차(라우팅) ==\n%s\n\n== %s 상세 (%s) ==\n%s' "$slug" "$toc" "$slug" "$note" "$detail")
jq -n --arg c "$ctx" \
  '{hookSpecificOutput: {hookEventName: "PreToolUse", additionalContext: $c}}'
exit 0
