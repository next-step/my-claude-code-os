#!/bin/bash
# ─────────────────────────────────────────────────────────────
# watchdog-cron.sh — telegram-listener 데몬 감시 루프 (cron 이 주기 호출)
#
# 무엇을 하나:
#   폰에서 오는 명령을 받는 telegram-listener 는 launchd KeepAlive 로 크래시 시
#   자동 재시작된다. 하지만 (a) 서비스가 아예 언로드됐거나(재부팅·수동 bootout),
#   (b) 로드는 됐는데 running 이 아닌 경우는 KeepAlive 만으론 사용자가 모른 채
#   폰 명령이 죽는다. 이 워치독이 주기적으로 헬스를 확인해, 다운을 감지하면
#   ① 폰으로 알리고 ② 자동 재시작을 시도한다.
#
# 디바운스(스팸 방지):
#   상태 파일(watchdog-state.txt)에 직전 상태(healthy|down)를 기억한다. 알림은
#   상태가 "전이"할 때만 보낸다 — healthy→down 에 다운 경보를, down→healthy 에
#   복구 통지를 한 번씩. down 이 지속돼도 매 주기 경보를 쏘지 않는다(재시작은 계속 시도).
#
# 한계(정직하게):
#   "loaded && state=running" 까지 확인한다. long-poll 이 실제로 폴링 중인지(멈춤)
#   까지는 정적으로 확인하지 않는다 — 그 판정은 별도 하트비트가 필요하다(후속 과제).
# ─────────────────────────────────────────────────────────────
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.." || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

USER_NAME="$(id -un)"
UID_NUM="$(id -u)"
LABEL="com.${USER_NAME}.telegram-listener"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"

SEND="$SCRIPT_DIR/../skills/_shared/telegram-send.sh"
STATE_FILE="$SCRIPT_DIR/../data/watchdog-state.txt"
LOG="$SCRIPT_DIR/../data/watchdog.log"

notify() { [ -x "$SEND" ] && "$SEND" "$1" >/dev/null 2>&1 || true; }
logline() { echo "[watchdog] $(date '+%F %T') $1" >> "$LOG"; }

# 헬스: 서비스가 로드돼 있고 state=running 이면 정상.
is_healthy() {
  launchctl print "gui/${UID_NUM}/${LABEL}" 2>/dev/null | grep -q "state = running"
}

# 재시작 시도: 로드돼 있으면 kickstart, 아니면 plist 로 bootstrap.
attempt_restart() {
  if launchctl print "gui/${UID_NUM}/${LABEL}" >/dev/null 2>&1; then
    launchctl kickstart -k "gui/${UID_NUM}/${LABEL}" 2>/dev/null
  elif [ -f "$PLIST" ]; then
    launchctl bootstrap "gui/${UID_NUM}" "$PLIST" 2>/dev/null
  else
    return 1   # 설치 자체가 없음 → install.sh 필요
  fi
}

prev="unknown"
[ -s "$STATE_FILE" ] && prev="$(cat "$STATE_FILE")"

if is_healthy; then
  cur="healthy"
  if [ "$prev" = "down" ]; then
    logline "복구됨 (healthy 로 전이)"
    notify "✅ telegram-listener 복구됨 — 폰 명령이 다시 동작합니다."
  fi
else
  cur="down"
  if [ "$prev" != "down" ]; then
    logline "다운 감지 — 재시작 시도"
    notify "⚠️ telegram-listener 다운 감지 — 자동 재시작을 시도합니다."
  fi
  if attempt_restart; then
    sleep 2
    if is_healthy; then
      cur="healthy"
      logline "재시작 성공"
      [ "$prev" = "down" ] || notify "✅ telegram-listener 재시작 성공."
    else
      logline "재시작 시도했으나 아직 비정상"
    fi
  else
    logline "재시작 불가 — launchd 미설치(plist 없음)"
    [ "$prev" = "down" ] || notify "❌ telegram-listener 가 설치돼 있지 않아요. .claude/launchd/install.sh 를 실행하세요."
  fi
fi

echo "$cur" > "$STATE_FILE"
exit 0
