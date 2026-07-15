#!/bin/bash
# ─────────────────────────────────────────────────────────────
# flush-cron.sh — outbox 재동기 조정 루프 (cron 이 주기 호출)
#
# 무엇을 하나:
#   capture 는 Notion 반영을 백그라운드로 던진다. 네트워크 실패/오프라인이면 항목이
#   data/outbox/ 에 남는다. capture-flush.sh 가 이를 재전송하는 "몸통"이지만 지금까지
#   자동 구동이 없어 수동 호출만 가능했다. 이 스크립트가 그 몸통을 주기적으로 돌려
#   "원하는 상태(모두 동기됨) ↔ 실제 상태(outbox 잔여)"를 수렴시키는 조정 루프를 닫는다.
#
# 설계:
#   - outbox 가 비어 있으면 capture-flush 는 즉시 {flushed:0,remaining:0} 로 끝난다(저비용).
#   - flushed>0 일 때만 로그를 남긴다(평상시 무소음). 값(제목 등)은 남기지 않는다.
# ─────────────────────────────────────────────────────────────
set -uo pipefail

# 스크립트 위치 기준 프로젝트 루트(.claude/hooks → ../..). 절대경로 미사용.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.." || exit 1

# cron 의 제한된 PATH 보완 — jq·curl 을 찾기 위함.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

FLUSH="$SCRIPT_DIR/../skills/_shared/capture-flush.sh"
LOG="$SCRIPT_DIR/../data/flush-cron.log"

[ -x "$FLUSH" ] || exit 0   # 몸통이 없으면 조용히 통과

res="$("$FLUSH" 2>/dev/null || echo '{"flushed":0,"remaining":0}')"
flushed="$(printf '%s' "$res" | jq -r '.flushed // 0' 2>/dev/null || echo 0)"
remaining="$(printf '%s' "$res" | jq -r '.remaining // 0' 2>/dev/null || echo 0)"

# 실제로 뭔가 재전송했을 때만 기록 (평상시엔 무소음).
if [ "${flushed:-0}" -gt 0 ] 2>/dev/null; then
  echo "[flush-cron] $(date '+%F %T') 재동기 ${flushed}건 성공, 잔여 ${remaining}건" >> "$LOG"
fi

exit 0
