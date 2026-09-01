#!/usr/bin/env bash
# 이 세션이 "루프 세션"인지를 정하는 한 곳.
# .claude/settings.json 의 PostToolUse(matcher: "Skill") · UserPromptSubmit 훅이 실행한다.
#
# 왜 따로 있나 — agent-handoff / human-intervention 두 로그는 feature-loop 안에서만 의미가 있다.
#   OS.md 3절의 네 구간을 도는 동안의 왕복과 개입이 관측 대상이지, 그냥 잡담하는 세션이 아니다.
#   범위를 두 로거에 각각 적어 넣으면 판정이 두 벌이 되어 갈라진다. 여기서만 정한다.
#
# 끄는 시점을 두지 않은 이유 — 스킬이 끝났다는 이벤트가 없다.
#   루프를 시작한 세션은 그 세션 전체가 루프라고 본다. 표식은 24시간 뒤 스스로 지워진다.
#
# stdout : 아무것도 출력하지 않는다(UserPromptSubmit 의 stdout 은 대화 컨텍스트에 주입된다).
# 산출물 : .claude/.hook-state/loop.<session_id>
set -uo pipefail

# 로그를 남길 오케스트레이터. 늘리려면 여기에만 추가한다(예: 'feature-loop|skill-forge').
LOOP_SKILLS='feature-loop'

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
STATE="$ROOT/.claude/.hook-state"

payload="$(cat)"
session="$(printf '%s' "$payload" | jq -r '.session_id // ""' 2>/dev/null)"
[ -n "$session" ] || exit 0

skill="$(printf '%s' "$payload" | jq -r '.tool_input.skill // ""' 2>/dev/null)"
prompt="$(printf '%s' "$payload" | jq -r '.prompt // ""' 2>/dev/null)"

armed=""
# 1) 스킬 툴로 부른 경우
printf '%s' "$skill" | grep -qE "^($LOOP_SKILLS)$" && armed="$skill"
# 2) 슬래시 명령으로 부른 경우 — 이때는 Skill 툴 호출이 없을 수 있다.
[ -n "$armed" ] || armed="$(printf '%s' "$prompt" | grep -oE "^/($LOOP_SKILLS)" | sed 's|^/||')"
[ -n "$armed" ] || exit 0

mkdir -p "$STATE" 2>/dev/null || exit 0
printf '%s\t%s' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$armed" > "$STATE/loop.$session" 2>/dev/null
exit 0
