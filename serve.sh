#!/usr/bin/env bash
# 산출물 서버를 상시 프로세스로 띄운다.
#
# 왜 스크립트인가 — 포그라운드로 띄우면 터미널 하나를 점유하고 세션을 닫으면 죽는다.
# 보고서는 며칠에 걸쳐 몇 번씩 다시 열어 보는 것이라 주소가 계속 살아 있어야 한다.
# PID 파일 하나로 «지금 떠 있는가»를 판별하고, 두 번 start해도 하나만 남게 한다.
#
# 속성을 모른다. 어떤 속성이 있는지는 파이썬 쪽이 프로필을 훑어서 정한다.
set -euo pipefail

# 레포 맨 위에서 부른다. 어디서 실행하든 자기 위치에서 OS 폴더를 찾는다 —
# 현재 디렉터리에 기대면 다른 폴더에서 부를 때 조용히 엉뚱한 곳을 가리킨다.
OS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.claude/os" && pwd)"
RUN_DIR="$OS_ROOT/runs/.serve"
PORT="${CATALOG_OS_PORT:-7391}"
# PID 파일 이름에 포트를 넣는다 — 이름이 하나면 다른 포트로 띄운 두 번째가
# 첫 번째의 PID를 덮어써서, 멈추라고 한 적 없는 서버가 조용히 고아가 된다.
PID_FILE="$RUN_DIR/serve.$PORT.pid"
LOG_FILE="$RUN_DIR/serve.$PORT.log"
HOST="${CATALOG_OS_HOST:-127.0.0.1}"
URL="http://$HOST:$PORT"

alive() {
  [ -f "$PID_FILE" ] || return 1
  local pid; pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [ -n "$pid" ] || return 1
  # 명령줄까지 확인한다 — PID는 재사용되므로 번호만으로는 남의 프로세스를 죽일 수 있다.
  ps -p "$pid" -o command= 2>/dev/null | grep -q serve_reports.py || return 1
  printf '%s' "$pid"
}

start() {
  if pid="$(alive)"; then
    echo "이미 떠 있습니다 — pid $pid · $URL"
    return 0
  fi
  mkdir -p "$RUN_DIR"
  rm -f "$PID_FILE"
  CATALOG_OS_PORT="$PORT" CATALOG_OS_HOST="$HOST" \
    nohup python3 "$OS_ROOT/engine/scripts/serve_reports.py" >>"$LOG_FILE" 2>&1 &
  local pid=$!
  echo "$pid" > "$PID_FILE"

  # 포트를 못 열면 즉시 죽는다. 살아 있는 척하지 않도록 여기서 확인한다.
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS --max-time 1 "$URL/healthz" >/dev/null 2>&1; then
      echo "기동 — pid $pid · $URL"
      echo "로그 $LOG_FILE"
      return 0
    fi
    ps -p "$pid" >/dev/null 2>&1 || break
    sleep 0.3
  done
  rm -f "$PID_FILE"
  echo "기동하지 못했습니다. 마지막 로그:" >&2
  tail -n 15 "$LOG_FILE" >&2 || true
  return 1
}

stop() {
  if ! pid="$(alive)"; then
    rm -f "$PID_FILE"
    echo "떠 있지 않습니다."
    return 0
  fi
  kill "$pid" 2>/dev/null || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    ps -p "$pid" >/dev/null 2>&1 || break
    sleep 0.2
  done
  ps -p "$pid" >/dev/null 2>&1 && kill -9 "$pid" 2>/dev/null || true
  rm -f "$PID_FILE"
  echo "종료 — pid $pid"
}

status() {
  if pid="$(alive)"; then
    echo "떠 있음 — pid $pid · $URL"
    echo "로그 $LOG_FILE"
    curl -fsS --max-time 2 "$URL/healthz" >/dev/null 2>&1 \
      && echo "응답 정상" || echo "프로세스는 살아 있으나 응답이 없습니다." >&2
  else
    echo "떠 있지 않음. '$0 start'로 띄웁니다."
    return 1
  fi
}

case "${1:-status}" in
  start)   start ;;
  stop)    stop ;;
  restart) stop; start ;;
  status)  status ;;
  logs)    tail -n "${2:-40}" "$LOG_FILE" ;;
  open)    status >/dev/null && open "$URL" ;;
  *)
    echo "사용법: $0 {start|stop|restart|status|logs [줄수]|open}" >&2
    exit 2 ;;
esac
