#!/usr/bin/env bash
# sim-chain.sh — 장중 시뮬 디스패처 (헤르메스 무인 루프)
#
# 아침 체인이 위원회를 끝낸 뒤 직접 호출하고, 09:00 cron이 백스톱으로 같은 스크립트를 부른다
# (Q20). 두 기동 경로가 겹칠 수 있으므로 flock 락이 필수다(Q21) — 이중 poll = 이중 체결.
#
# 하는 일:
#   1. flock 락 획득(이미 돌고 있으면 조용히 종료).
#   2. `/sim-engine watchlist 조립`을 claude -p로 1회 호출(실패 시 푸시+중단).
#   3. `fill_engine.py poll`을 파이프로 읽어 emit되는 이벤트마다 claude -p를 **동기 호출**.
#      셸은 이벤트 종류를 해석하지 않고 그대로 전달한다(fill·emergency·fetch_fail).
#   4. session_end를 받으면 루프를 끝내고 체결 요약을 stdout으로 낸다
#      (헤르메스 `--no-agent --deliver discord:<#일간>`이 stdout을 전송 — Q15·Q17).
#
# 권한(Q6 재결정 — A안): claude -p에 --dangerously-skip-permissions를 붙이지 않는다.
#   무인 세션은 프롬프트에 답할 수 없으므로 `.claude/settings.json`의 permissions.allow에
#   이 루프가 실제로 쓰는 툴만 열거하고, 목록 밖의 행동은 거부되게 둔다.
#
# 설계 근거: docs/interviews/2026-07-10-hermes-wiring.md (Q3·Q4·Q6·Q16·Q19·Q20·Q21·Q22)
set -uo pipefail

# ── 환경(cron은 최소 PATH만 가지므로 homebrew·로컬 경로를 보정) ──────────────────
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin:$PATH"

# ── 경로 ────────────────────────────────────────────────────────────────────────
# 복사본 경로 보정: ~/.hermes/scripts/ 에 복사된 실행 환경에서 저장소 루트를 가리키도록 고정.
PROJECT_DIR="/Users/parkchu/Workspace/my-claude-code-os"
SCRIPT_DIR="$PROJECT_DIR/scripts/hermes"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
LOG_DIR="$HERMES_HOME/logs"                       # 운영 로그는 저장소 밖(Q22)
LOCK_FILE="$HERMES_HOME/sim-chain.lock"
WATCHLIST="$PROJECT_DIR/.runtime/sim-watchlist.json"   # 작업 파일(박제 아님) — 저장소 밖 취급, gitignore
FILL_ENGINE="$PROJECT_DIR/.claude/skills/sim-engine/scripts/fill_engine.py"

ONCE=""
[ "${1:-}" = "--once" ] && ONCE="--once"           # 장외 코드경로 확인용(디스패치 루프 한 바퀴)

mkdir -p "$LOG_DIR" "$(dirname "$WATCHLIST")"
LOG_FILE="$LOG_DIR/sim-chain-$(date +%F).log"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*" >>"$LOG_FILE"; }

# ── 락(Q21): 이미 돌고 있으면 조용히 종료 ─────────────────────────────────────────
# flock이 없으면 이중 poll = 이중 체결을 막을 수 없다 → 조용히 넘기지 않고 크게 실패시킨다
# (매일 락 없이 도는 것보다 설정 문제를 드러내는 편이 안전 — 무결성).
if ! command -v flock >/dev/null 2>&1; then
  log "flock 미설치 — 락을 걸 수 없어 중단(이중 체결 방지 불가). flock을 설치해야 한다."
  printf '시뮬 중단: flock 미설치로 중복 실행 방지 락을 걸 수 없습니다. flock 설치 후 재실행하세요. 로그: %s\n' "$LOG_FILE"
  exit 1
fi
exec 9>"$LOCK_FILE" || { log "락 파일 열기 실패: $LOCK_FILE"; exit 1; }
if ! flock -n 9; then
  log "이미 실행 중 — 락 획득 실패, 조용히 종료(백스톱이 무해하게 빠짐)"
  exit 0
fi
log "락 획득 — sim-chain 시작 (once=${ONCE:-no})"

# ── claude -p 헬퍼: 화이트리스트 권한으로만 실행(A안, 플래그 없음) ────────────────
# permissions.allow 밖의 툴을 요구하면 무인 세션이라 프롬프트 없이 거부된다(그게 요점).
run_claude() { ( cd "$PROJECT_DIR" && claude -p "$1" ); }

# ── 1단계: watchlist 조립(Q16·Q19) ──────────────────────────────────────────────
# 회의록 유무로 진입 대기 주문 포함 여부를 가르는 판단은 스킬(클로드)이 한다 — 셸은 판단하지 않는다.
TODAY="$(date +%F)"
ASSEMBLE_PROMPT="/sim-engine watchlist 조립 — data/investment-plan.md·data/portfolio.md를 읽어 poll이 읽을 watchlist JSON을 '$WATCHLIST' 경로에 쓴다. 오늘자 회의록(data/minutes/$TODAY.md) 유무로 진입 대기 주문 포함 여부는 스킬이 판단한다(셸은 판단하지 않음)."
log "watchlist 조립 호출"
if ! run_claude "$ASSEMBLE_PROMPT" >>"$LOG_FILE" 2>&1; then
  log "watchlist 조립 실패 — 시뮬 중단"
  printf '시뮬 중단: watchlist 조립(/sim-engine) 호출이 실패했습니다. 오늘 장중 시뮬을 띄우지 못했습니다. 로그: %s\n' "$LOG_FILE"
  exit 1
fi
if [ ! -f "$WATCHLIST" ]; then
  log "watchlist 파일이 생성되지 않음: $WATCHLIST — 시뮬 중단"
  printf '시뮬 중단: watchlist 파일이 생성되지 않았습니다(%s). 로그: %s\n' "$WATCHLIST" "$LOG_FILE"
  exit 1
fi
log "watchlist 준비됨: $WATCHLIST"

# ── 2단계: poll 기동 + 이벤트 동기 디스패치(Q3·Q4) ──────────────────────────────
# poll의 stdout(JSON 한 줄/이벤트)을 파이프로 읽어 이벤트마다 claude -p를 동기 호출(완료까지 대기).
# 조용한 장은 이벤트가 없어 claude 호출 0(토큰 0). poll은 session_end 후 스스로 종료한다.
log "poll 기동 — 이벤트 디스패치 루프 시작"
python3 "$FILL_ENGINE" poll --watchlist "$WATCHLIST" $ONCE 2>>"$LOG_FILE" | \
while IFS= read -r event; do
  [ -z "$event" ] && continue
  log "event: $event"
  case "$event" in
    *'"event": "session_end"'*|*'"event":"session_end"'*)
      # 장 마감: 루프 종료 + 체결 요약을 stdout으로(헤르메스 --deliver가 #일간 전송 — Q15·Q17)
      log "session_end — 체결 요약 생성 후 루프 종료"
      summary="$(run_claude "/sim-engine 장 마감 반영 및 오늘 체결 요약 — session_end 이벤트: $event" 2>>"$LOG_FILE")"
      if [ -n "$summary" ]; then
        printf '%s\n' "$summary"
      else
        printf '오늘 장중 시뮬 종료. 체결 요약을 생성하지 못했습니다(로그: %s).\n' "$LOG_FILE"
      fi
      break
      ;;
    *)
      # 종류 해석 없이 그대로 전달(fill·emergency·fetch_fail) — 동기 호출, 완료까지 대기
      if ! run_claude "/sim-engine 이벤트 반영: $event" >>"$LOG_FILE" 2>&1; then
        log "이벤트 반영 실패(루프는 계속): $event"
      fi
      ;;
  esac
done

log "sim-chain 종료"
exit 0
