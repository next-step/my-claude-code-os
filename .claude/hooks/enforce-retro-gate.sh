#!/usr/bin/env bash
# PreToolUse(Bash) 훅: `git push` 전에 "마지막 푸시 이후 /retro 회고를 했나"를 강제한다.
# 안 했으면 차단(exit 2). 스킬(/retro)은 그대로 두고, 훅이 "사람이 기억해서 불러야만 작동"을 없앤다.
#
# 왜 push 인가: 커밋은 수시로 하니(노이즈) 게이트로 부적절. push = "외부 공개 = 마무리" 경계라 여기서 강제.
# 감지 신호: .claude/skill-usage.log 에 /retro 호출이 자동 기록됨(사용통계 훅). 그걸 마커 시각과 비교한다.
# 마커(.retro-gate-marker): "마지막으로 게이트를 통과시킨 시각". 설치 시점부터만 강제(과거 커밋 날짜 꼬임 회피),
#   새 작업이 없으면 통과(푸시 재시도 안전).
# 탈출구: 명령에 SKIP_RETRO_GATE=1 을 붙이면 통과(정말 회고가 불필요한 푸시용).

set -euo pipefail

cmd=$(jq -r '.tool_input.command // empty' 2>/dev/null || true)

# `git push` 를 "명령으로 실행"할 때만 관여(문자열 안 언급은 무시).
printf '%s' "$cmd" | grep -qE '(^|[;&|])[[:space:]]*git[[:space:]]+push' || exit 0

# 탈출구: 명시적 우회
printf '%s' "$cmd" | grep -q 'SKIP_RETRO_GATE' && exit 0

root="${CLAUDE_PROJECT_DIR:-.}"
log="$root/.claude/skill-usage.log"
marker="$root/.claude/.retro-gate-marker"
now=$(date '+%Y-%m-%d %H:%M:%S')

# 로그 없으면 판단 불가 → 통과(오탐 방지)
[ -f "$log" ] || exit 0

# 마커 없으면(첫 실행) 지금 시각으로 만들고 통과 — 설치 이후 작업부터만 강제한다.
if [ ! -f "$marker" ]; then
  printf '%s\n' "$now" > "$marker" 2>/dev/null || true
  exit 0
fi
mark=$(cat "$marker" 2>/dev/null || echo "")
[ -n "$mark" ] || exit 0

# 마커 이후 새 작업(커밋)이 없으면 통과 — 푸시 재시도·회고 불필요 푸시 안전.
newest=$(git log -1 --date=format:'%Y-%m-%d %H:%M:%S' --format='%cd' HEAD 2>/dev/null || echo "")
if [ -n "$newest" ] && [[ "$newest" < "$mark" ]]; then
  exit 0
fi

# 마커 이후 /retro 실행 기록이 있나(문자열 사전순 = 시간순 비교).
if awk -F'\t' -v b="$mark" '$2=="retro" && $1>=b {f=1} END{exit f?0:1}' "$log"; then
  # 회고 흔적 있음 → 통과하고, 다음 주기를 위해 마커를 지금으로 갱신.
  printf '%s\n' "$now" > "$marker" 2>/dev/null || true
  exit 0
fi

# 여기 도달 = 마커 이후 새 작업이 있는데 /retro 흔적이 없음 → 차단.
echo "이번에 푸시할 작업에 /retro 회고 흔적이 없습니다(마지막 게이트 통과 이후)." >&2
echo "먼저 /retro 로 이번 세션을 회고하세요(스킬 개선 · 도메인 변경점). 그 뒤 다시 push 하세요." >&2
echo "정말 회고가 불필요한 푸시라면 'SKIP_RETRO_GATE=1 git push ...' 로 우회할 수 있습니다." >&2
exit 2
