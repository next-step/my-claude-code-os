#!/usr/bin/env bash
#
# PreToolUse:Skill 훅 — 스킬 호출 1건을 JSONL 한 줄로 기록한다.
#
# stdin 으로 훅 입력 JSON 을 받는다:
#   { "session_id": "...", "cwd": "...", "tool_name": "Skill",
#     "tool_input": { "skill": "superpowers:brainstorming", "args": "..." } }
#
# 설계 원칙: 이 훅은 절대 스킬 실행을 막지 않는다. 무슨 일이 있어도 exit 0.
# (PreToolUse 훅이 0 이 아닌 코드로 끝나면 툴 호출 자체가 차단될 수 있다.
#  로그를 남기지 못하는 것보다 작업이 멈추는 쪽이 훨씬 나쁘다.)

set -uo pipefail

# 스크립트 자신의 위치에서 프로젝트 루트를 역산한다.
# .claude/hooks/ 의 두 단계 위 = 프로젝트 루트.
# cwd 나 환경변수에 의존하지 않으므로 훅이 어디서 실행되든 같은 파일에 쌓인다.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$PROJECT_DIR/.claude/data/skill-usage.jsonl"

command -v jq >/dev/null 2>&1 || exit 0
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || exit 0

# 로컬 시간 + UTC 오프셋으로 기록한다 (예: 2026-08-26T20:41:11+0900).
# UTC 로 저장하면 KST 기준 '일별 집계'가 9시간 어긋나므로 로컬 시각을 원본으로 삼는다.
NOW="$(date +%Y-%m-%dT%H:%M:%S%z)"

# append(>>) 로 한 줄씩만 쓴다. 훅이 동시에 여러 번 떠도 줄이 섞이지 않는다.
jq -c --arg ts "$NOW" '{
  ts:         $ts,
  skill:      (.tool_input.skill // "unknown"),
  args:       (.tool_input.args  // ""),
  session_id: (.session_id // ""),
  cwd:        (.cwd // "")
}' >> "$LOG_FILE" 2>/dev/null

exit 0
