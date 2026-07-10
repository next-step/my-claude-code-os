#!/usr/bin/env bash
# morning-chain.sh — 아침 체인 (헤르메스 무인 루프, 월~금 08:00)
#
# 헤르메스 cron(`0 8 * * 1-5`, `--no-agent --deliver discord:<#일간>`)이 부른다.
# 하는 일(완료 이벤트 체이닝 — 시각이 아니라 '끝나면 다음' Q20):
#   1. 휴장일 게이트(market_calendar.py). 종료 코드 1(휴장)이면 클로드를 한 번도 안 부르고 종료.
#      2(판정 불가)면 '개장'으로 가정해 진행하고, 판정 실패 사실을 #일간에 이상 푸시한다(Q18).
#   2. flock 락 획득(Q21). 이미 아침 체인이 돌고 있으면 조용히 종료.
#   3. `/morning-briefing`(A) → `/investment-committee`(B·D)를 각각 1회 재시도 후 중단(Q13).
#      한 단계라도 2회 실패하면 체인을 멈추고 실패 사실을 #일간에 푸시한다.
#   4. 위원회가 끝나면 `sim-chain.sh`를 직접 이어서 띄운다(Q20 — '끝나면 다음').
#      09:00 cron은 백스톱이라, 여기서 이미 sim이 떠 있으면 그쪽이 sim 락에 걸려 빠진다.
#   5. 오늘 계획 요약(위원회의 마지막 응답)을 stdout으로 내보내 #일간에 전달(Q15·Q17).
#
# 권한(Q6 재결정 — A안): claude -p에 --dangerously-skip-permissions를 붙이지 않는다.
#   무인 세션은 프롬프트에 답할 수 없으므로 `.claude/settings.json`의 permissions.allow에
#   이 체인이 실제로 쓰는 툴만 열거하고, 목록 밖의 행동은 거부되게 둔다.
#
# 설계 근거: docs/interviews/2026-07-10-hermes-wiring.md (Q1·Q2·Q13·Q15·Q17·Q18·Q20·Q21·Q22)
set -uo pipefail

# ── 환경(cron은 최소 PATH만 가지므로 homebrew·로컬 경로를 보정) ──────────────────
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin:$PATH"

# ── 경로 ────────────────────────────────────────────────────────────────────────
# 복사본 경로 보정: ~/.hermes/scripts/ 에 복사된 실행 환경에서 저장소 루트를 가리키도록 고정.
PROJECT_DIR="/Users/parkchu/Workspace/my-claude-code-os"
SCRIPT_DIR="$PROJECT_DIR/scripts/hermes"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
LOG_DIR="$HERMES_HOME/logs"                       # 운영 로그는 저장소 밖(Q22)
LOCK_FILE="$HERMES_HOME/morning-chain.lock"       # 스크립트별 락(Q21)
CALENDAR="$PROJECT_DIR/scripts/market_calendar.py"
SIM_CHAIN="$SCRIPT_DIR/sim-chain.sh"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/morning-chain-$(date +%F).log"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*" >>"$LOG_FILE"; }

# 이상/실패를 #일간으로: 헤르메스 --deliver가 stdout을 전송하므로 stdout에 쌓아 둔다.
notify() { printf '%s\n' "$*"; }

# ── 1단계: 휴장일 게이트(Q5·Q12·Q18) ─────────────────────────────────────────────
CAL_OUT="$(python3 "$CALENDAR" 2>&1)"
CAL_RC=$?
log "market_calendar: rc=$CAL_RC ${CAL_OUT}"
case "$CAL_RC" in
  1)
    # 휴장 — 클로드를 한 번도 부르지 않고 종료(빈 기록 방지). 정상 흐름이라 푸시하지 않는다.
    log "휴장일 — 아침 체인 종료(클로드 미호출)"
    exit 0
    ;;
  0)
    log "개장 확인 — 체인 진행"
    ;;
  *)
    # 판정 불가(코드 2 등): '개장'으로 가정하고 진행하되, 판정 실패를 #일간에 이상 푸시(Q18)
    log "달력 판정 불가(rc=$CAL_RC) — 개장으로 가정하고 진행 + 이상 푸시"
    notify "[아침 체인 이상] 휴장일 판정 실패(rc=$CAL_RC): ${CAL_OUT}. '개장'으로 가정하고 체인을 진행합니다(판단 부재에도 방어는 계속 — Q18)."
    ;;
esac

# ── 2단계: 락(Q21) — 이미 아침 체인이 돌고 있으면 조용히 종료 ──────────────────────
if ! command -v flock >/dev/null 2>&1; then
  log "flock 미설치 — 락을 걸 수 없어 중단(중복 실행 방지 불가)"
  notify "[아침 체인 중단] flock 미설치로 중복 실행 방지 락을 걸 수 없습니다. flock 설치 후 재실행하세요. 로그: $LOG_FILE"
  exit 1
fi
exec 9>"$LOCK_FILE" || { log "락 파일 열기 실패: $LOCK_FILE"; exit 1; }
if ! flock -n 9; then
  log "이미 실행 중 — 락 획득 실패, 조용히 종료"
  exit 0
fi
log "락 획득 — 아침 체인 시작"

# ── claude -p 헬퍼: 화이트리스트 권한으로만 실행(A안, 플래그 없음) ────────────────
run_claude() { ( cd "$PROJECT_DIR" && claude -p "$1" ); }

# 단계 실행: 1회 재시도 후 실패면 rc!=0. 성공 시 claude의 마지막 응답(stdout)을 그대로 흘린다(Q13).
run_step() {
  local label="$1" prompt="$2" attempt out rc
  for attempt in 1 2; do
    log "$label 호출 (시도 $attempt/2)"
    out="$(run_claude "$prompt" 2>>"$LOG_FILE")"
    rc=$?
    if [ "$rc" -eq 0 ]; then
      printf '%s' "$out"
      return 0
    fi
    log "$label 실패 (시도 $attempt/2, rc=$rc)"
  done
  return 1
}

# ── 3단계: 브리핑(A) ─────────────────────────────────────────────────────────────
if ! run_step "브리핑(/morning-briefing)" "/morning-briefing" >>"$LOG_FILE" 2>&1; then
  log "브리핑 2회 실패 — 체인 중단"
  notify "[아침 체인 중단] /morning-briefing 이 2회 연속 실패했습니다. 오늘 아침 브리핑·위원회를 진행하지 못했습니다. 로그: $LOG_FILE"
  exit 1
fi
log "브리핑 완료"

# ── 4단계: 위원회(B·D) — 마지막 응답을 오늘 계획 요약으로 캡처 ────────────────────
PLAN_SUMMARY="$(run_step "위원회(/investment-committee)" "/investment-committee")"
if [ "$?" -ne 0 ]; then
  log "위원회 2회 실패 — 체인 중단"
  notify "[아침 체인 중단] /investment-committee 가 2회 연속 실패했습니다. 오늘 위원회를 열지 못했습니다(시뮬 미기동). 로그: $LOG_FILE"
  exit 1
fi
log "위원회 완료 — 오늘 계획 요약 캡처"

# ── 5단계: 시뮬 직접 기동(Q20) ──────────────────────────────────────────────────
# 위원회가 끝났으니 sim-chain을 이어서 띄운다. sim은 장 마감까지 백그라운드로 돌며 자기 락을
# 잡으므로, 09:00 백스톱 cron은 그 락에 걸려 조용히 빠진다. 아침 체인은 여기서 sim을 기다리지
# 않고 오늘 계획 요약을 곧바로 #일간에 내보낸 뒤 종료한다(Q15 — 아침 push는 아침에).
# sim의 stdout(장 마감 체결 요약)·delivery는 sim-chain.sh / 09:00 cron이 소유한다(범위 밖).
if [ -x "$SIM_CHAIN" ]; then
  log "sim-chain 백그라운드 기동: $SIM_CHAIN"
  nohup "$SIM_CHAIN" >>"$LOG_DIR/sim-chain-launch-$(date +%F).log" 2>&1 9>&- &
  disown 2>/dev/null || true
else
  log "sim-chain 실행 불가(파일 없음/실행권한 없음): $SIM_CHAIN"
  notify "[아침 체인 이상] sim-chain.sh 를 기동하지 못했습니다($SIM_CHAIN). 09:00 백스톱 cron이 대신 시뮬을 띄웁니다. 로그: $LOG_FILE"
fi

# ── 오늘 계획 요약을 #일간으로 ───────────────────────────────────────────────────
if [ -n "$PLAN_SUMMARY" ]; then
  notify "$PLAN_SUMMARY"
else
  notify "오늘 아침 위원회는 끝났으나 계획 요약 텍스트가 비어 있습니다(로그: $LOG_FILE)."
fi
log "아침 체인 종료"
exit 0
