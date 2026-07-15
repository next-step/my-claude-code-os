#!/bin/bash
# ─────────────────────────────────────────────────────────────
# digest-cron.sh — 집계(digest) 루프 (cron 이 주 1회 호출)
#
# 무엇을 하나:
#   digest-report.sh 로 현재 할일 현황(상태 분포·카테고리·오래 방치된 draft)을
#   요약해 폰으로 보낸다. remind 가 매일 draft 를 재촉한다면, 이건 주 1회 전체를
#   돌아보는 회고용 집계다. (기본 스케줄: 매주 일요일 20:00 — install.sh 참고)
#
# 설계:
#   - 집계(결정론)와 발송(부작용)을 분리: digest-report.sh 가 텍스트를 만들고
#     telegram-send.sh 가 보낸다. 각자 단일 책임.
#   - 자격증명이 없으면 telegram-send 가 값 노출 없이 실패하고, 이 스크립트는
#     조용히 로그만 남긴다(세션·크론을 막지 않음).
# ─────────────────────────────────────────────────────────────
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.." || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

REPORT="$SCRIPT_DIR/../skills/_shared/digest-report.sh"
SEND="$SCRIPT_DIR/../skills/_shared/telegram-send.sh"
LOG="$SCRIPT_DIR/../data/digest-cron.log"

[ -x "$REPORT" ] || exit 0

text="$("$REPORT" 2>/dev/null || true)"
[ -n "$text" ] || exit 0

if [ -x "$SEND" ] && printf '%s' "$text" | "$SEND"; then
  echo "[digest-cron] $(date '+%F %T') 주간 요약 발송 성공" >> "$LOG"
else
  echo "[digest-cron] $(date '+%F %T') 발송 실패(자격증명/네트워크) — 스킵" >> "$LOG"
fi

exit 0
