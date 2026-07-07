#!/usr/bin/env bash
# SessionEnd 훅: 세션이 끝날 때 /retro(회고) 실행을 "안내"한다. (자동 실행이 아니라 리마인더)
#
# 왜 실행이 아니라 안내인가: /retro 는 맥락이 살아있는 세션 안에서 사람이 직접 돌려야 제값을 한다
#   — 스킬 개선(렌즈 A)·도메인 변경점(렌즈 B)을 사용자에게 직접 보고하고, 애매하면 되묻는 대화형이다.
#   SessionEnd 시점엔 그 맥락도, 대화할 사람도 없다. 그래서 여기선 "잊지 마세요"만 알린다.
# side-effect only(재귀 없음: claude 를 부르지 않는다). SessionEnd 는 종료를 막지 못하므로 알림만.
#
# 입력(stdin, JSON): { transcript_path, session_id, ... }

set -euo pipefail

input=$(cat)

# 실질 작업이 있던 세션만 안내한다(트리비얼한 1~2턴 세션엔 노이즈 방지).
tp=$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2>/dev/null || true)
lines=0
[ -n "$tp" ] && [ -f "$tp" ] && lines=$(wc -l < "$tp" 2>/dev/null | tr -d ' ')
[ "${lines:-0}" -ge 20 ] || exit 0

# 여기 도달 = 리마인드 결정. macOS 알림(테스트에선 RETRO_REMINDER_SILENT=1 로 억제).
title="🔁 세션 종료 · 회고 리마인더"
msg="이번 세션 회고 잊지 마세요 — /retro (스킬 개선 + 도메인 변경점)"
if [ "${RETRO_REMINDER_SILENT:-}" != "1" ] && command -v osascript >/dev/null 2>&1; then
  osascript -e "display notification \"$msg\" with title \"$title\"" >/dev/null 2>&1 || true
fi

# 관측·테스트용 표식(세션 종료 후라 화면엔 안 보일 수 있음).
echo "retro-reminder: 세션 종료 — /retro 회고 권장"
exit 0
