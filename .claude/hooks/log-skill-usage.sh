#!/usr/bin/env bash
# Skill 호출을 기록한다. .claude/settings.json 의 PostToolUse(matcher: "Skill") 훅이 실행한다.
#
# stdin  : 훅 입력 JSON ({session_id, tool_name, tool_input:{skill, args}, tool_response})
# stdout : 아무것도 출력하지 않는다. 훅의 stdout은 대화 기록에 남으므로 조용해야 한다.
# 산출물 : .claude/skill-usage.jsonl (원본 로그, append-only)
#          .claude/skill-usage.json  (집계, 매번 로그에서 재생성)
set -uo pipefail

# 훅의 실행 디렉터리를 가정하지 않는다. CLAUDE_PROJECT_DIR이 없으면 git 루트로, 그것도 없으면 현재 위치로.
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
LOG="$ROOT/.claude/skill-usage.jsonl"
COUNT="$ROOT/.claude/skill-usage.json"

payload="$(cat)"
skill="$(printf '%s' "$payload" | jq -r '.tool_input.skill // empty' 2>/dev/null)"

# 스킬 이름이 없으면 기록할 것이 없다. 훅은 조용히 성공해야 한다(실패하면 사용자에게 에러가 보인다).
[ -n "$skill" ] || exit 0

mkdir -p "$(dirname "$LOG")" || exit 0

# 1) 원본 로그 — append-only.
#    한 줄을 덧붙이기만 하므로 스킬이 동시에 여러 개 호출돼도 서로의 기록을 덮어쓰지 않는다.
session="$(printf '%s' "$payload" | jq -r '.session_id // ""' 2>/dev/null)"
jq -cn --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
       --arg skill "$skill" \
       --arg session "$session" \
       '{ts: $ts, skill: $skill, session: $session}' >> "$LOG" || exit 0

# 2) 집계 — 로그에서 매번 다시 만든다.
#    누적 파일을 읽고-고쳐-쓰면 동시 호출에 카운트가 유실된다. 재생성은 그 위험이 없고,
#    파일이 깨져도 다음 호출에 스스로 복구된다.
tmp="$COUNT.tmp.$$"
if jq -s 'group_by(.skill)
          | map({key: .[0].skill, value: {count: length, last: (max_by(.ts) | .ts)}})
          | from_entries
          | {total: ([.[].count] | add), skills: .}' "$LOG" > "$tmp" 2>/dev/null; then
  mv "$tmp" "$COUNT"
else
  rm -f "$tmp"
fi

exit 0
