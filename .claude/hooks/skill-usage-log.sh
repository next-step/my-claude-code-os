#!/usr/bin/env bash
# Skill 호출 기록용 PreToolUse(matcher: Skill) hook.
#
# 스킬이 호출될 때마다 .claude/skill-usage.log 에 한 줄을 덧붙인다.
#   2026-07-09T06:31:02Z<TAB>commit
#
# ── 왜 이렇게 만들었나 ────────────────────────────────────────
# 1) jq 를 쓰지 않는다. 이 환경엔 jq 가 없다. 이전 버전은 jq 로 payload 를 읽고
#    jq 로 JSON 통계 파일을 갱신했는데, 애초에 settings.json 에 등록조차 안 돼 있었다.
#    payload 에 "skill" 은 정확히 한 번만 등장하므로 sed 로 안전하게 뽑는다.
#      {"tool_name":"Skill","tool_input":{"skill":"skill-stat"}, …}
#
# 2) JSON 을 갱신하지 않고 "덧붙이기 전용 로그"로 바꿨다. jq 없이 JSON 을 읽고
#    고쳐 쓰는 건 취약하다. 한 줄 append 는 실패할 구석이 거의 없고, 집계는
#    읽는 쪽(skill-stat)이 awk 로 하면 된다. 덤으로 호출 이력이 그대로 남는다.
#
# 3) 기록 위치가 프로젝트 안이다(`.claude/`). 이전엔 `~/.claude/` 였는데,
#    CLAUDE.md 1번 규칙("클로드 OS 관련 모든 파일은 프로젝트 안에")에 어긋났다.
#
# 4) 조용히 실패하지 않는다. payload 는 왔는데 스킬 이름을 못 읽으면
#    .claude/skill-usage.err 에 흔적을 남긴다.
#
# 어떤 경우에도 Skill 도구 실행을 막지 않도록 항상 exit 0 한다.

set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-.}"
LOG="$ROOT/.claude/skill-usage.log"
ERR="$ROOT/.claude/skill-usage.err"

payload="$(cat 2>/dev/null)" || exit 0
[ -n "$payload" ] || exit 0

skill="$(printf '%s' "$payload" | tr -d '\n\r' \
  | sed -n 's/.*"skill"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"

# 스킬 이름에 쓰일 수 있는 글자만 남긴다(로그 오염 방지).
skill="$(printf '%s' "$skill" | tr -cd 'A-Za-z0-9_:-')"

if [ -z "$skill" ]; then
  printf '%s · skill 이름 파싱 실패 (payload %d bytes)\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${#payload}" >> "$ERR" 2>/dev/null
  exit 0
fi

printf '%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$skill" >> "$LOG" 2>/dev/null

exit 0
