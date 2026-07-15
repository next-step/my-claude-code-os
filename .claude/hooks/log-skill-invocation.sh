#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# log-skill-invocation.sh
#
# PostToolUse 훅 (matcher: "Skill"). Claude가 Skill 툴로 스킬을 실행할 때마다
# 호출 사실을 .claude/skill-invocations.log 에 한 줄 append 한다.
#
# 왜 필요한가:
#   이 로그는 security.md 정본에 "스킬 호출 로그"로 등록돼 있지만, 지금까지
#   실제로 기록하는 코드가 없어 6/25 이후 갱신이 멈춘 고아 로그였다. 이 훅이
#   write 쪽을 살려, 나중에 이 로그를 읽어 사용 패턴/실패를 분석하는
#   "자기 관찰 → 개선" 루프의 read 쪽이 의미를 갖게 한다.
#
# 동작 원리:
#   - 훅은 stdin으로 tool 호출 정보(JSON)를 받는다. Skill 툴의 입력은
#     {skill, args} 이므로 tool_input.skill 에서 스킬명을 뽑는다.
#   - 기존 로그 포맷을 그대로 잇는다:  "YYYY-MM-DD HH:MM:SS | #N | 스킬명"
#     #N 은 파일 마지막 줄의 카운터를 읽어 +1 (없으면 1부터).
#   - 훅은 사용자 응답에 개입하지 않는다: stdout으로 아무것도 내지 않고
#     조용히 exit 0. (실패해도 세션을 막지 않게 전 구간 방어)
# ─────────────────────────────────────────────────────────────
set -uo pipefail

# cron/훅의 제한된 PATH 보완 — jq 를 찾기 위함 (다른 훅과 동일 관례).
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# 스크립트 자기 위치 기준 프로젝트 루트(.claude/hooks → ../..). 절대경로 미사용.
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# 로그 경로. 기본은 정본 위치이나, 테스트가 SKILL_LOG 로 임시 파일을 주입해
# 실데이터를 건드리지 않고 동작을 검증할 수 있게 오버라이드를 허용한다.
LOG="${SKILL_LOG:-$PROJECT_ROOT/.claude/skill-invocations.log}"

# stdin(JSON)에서 스킬명 추출. jq 실패해도 훅이 죽지 않게 방어.
payload="$(cat)"
skill="$(printf '%s' "$payload" | jq -r '.tool_input.skill // empty' 2>/dev/null || true)"

# 스킬명을 못 얻으면(다른 툴이거나 파싱 실패) 조용히 통과.
[ -n "$skill" ] || exit 0

# 다음 카운터 계산 — 파일 전체에서 마지막 "#N" 을 읽어 +1. 없으면 0 → 1.
last_n="$(grep -oE '#[0-9]+' "$LOG" 2>/dev/null | tail -1 | tr -d '#')"
next=$(( ${last_n:-0} + 1 ))

# 한 줄 append. (동시 실행이 드물어 잠금 없이 append 로 충분)
printf '%s | #%d | %s\n' "$(date '+%F %T')" "$next" "$skill" >> "$LOG"

exit 0
