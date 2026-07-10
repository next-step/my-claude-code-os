#!/usr/bin/env bash
# weekly-chain.sh — 주간 회고 체인 (헤르메스 무인 루프, 토요일 09:00)
#
# 헤르메스 cron(`0 9 * * 6`, `--no-agent --deliver discord:<#주간>`)이 부른다.
# 하는 일:
#   1. flock 락 획득(Q21). 이미 회고가 돌고 있으면 조용히 종료.
#   2. `/weekly-retrospect`(F)를 1회 재시도 후 중단(Q13). 2회 실패면 실패 사실을 #주간에 푸시.
#   3. 회고 리포트 요약(스킬의 마지막 응답)을 stdout으로 내보내 #주간에 전달(Q15·Q17).
#
# 휴장일 게이트는 없다 — 회고는 '지난 한 주의 기록'을 되짚는 일이라 그날의 개장 여부와 무관하다.
#
# 권한(Q6 재결정 — A안): claude -p에 --dangerously-skip-permissions를 붙이지 않는다.
#   무인 세션이라 permissions.allow 밖의 툴은 프롬프트 없이 거부된다(그게 요점).
#
# 설계 근거: docs/interviews/2026-07-10-hermes-wiring.md (Q1·Q2·Q11·Q13·Q15·Q17·Q21·Q22)
set -uo pipefail

# ── 환경(cron은 최소 PATH만 가지므로 homebrew·로컬 경로를 보정) ──────────────────
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin:$PATH"

# ── 경로 ────────────────────────────────────────────────────────────────────────
# 복사본 경로 보정: ~/.hermes/scripts/ 에 복사된 실행 환경에서 저장소 루트를 가리키도록 고정.
PROJECT_DIR="/Users/parkchu/Workspace/my-claude-code-os"
SCRIPT_DIR="$PROJECT_DIR/scripts/hermes"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
LOG_DIR="$HERMES_HOME/logs"                       # 운영 로그는 저장소 밖(Q22)
LOCK_FILE="$HERMES_HOME/weekly-chain.lock"        # 스크립트별 락(Q21)

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/weekly-chain-$(date +%F).log"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*" >>"$LOG_FILE"; }
notify() { printf '%s\n' "$*"; }   # 헤르메스 --deliver가 stdout을 #주간으로 전송

# ── 락(Q21): 이미 돌고 있으면 조용히 종료 ─────────────────────────────────────────
if ! command -v flock >/dev/null 2>&1; then
  log "flock 미설치 — 락을 걸 수 없어 중단(중복 실행 방지 불가)"
  notify "[주간 회고 중단] flock 미설치로 중복 실행 방지 락을 걸 수 없습니다. flock 설치 후 재실행하세요. 로그: $LOG_FILE"
  exit 1
fi
exec 9>"$LOCK_FILE" || { log "락 파일 열기 실패: $LOCK_FILE"; exit 1; }
if ! flock -n 9; then
  log "이미 실행 중 — 락 획득 실패, 조용히 종료"
  exit 0
fi
log "락 획득 — 주간 회고 시작"

# ── claude -p 헬퍼: 화이트리스트 권한으로만 실행(A안, 플래그 없음) ────────────────
run_claude() { ( cd "$PROJECT_DIR" && claude -p "$1" ); }

# 1회 재시도 후 중단(Q13). 성공 시 스킬의 마지막 응답(stdout)을 그대로 흘린다.
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

# ── 주간 회고(F) — 마지막 응답을 리포트 요약으로 캡처 ────────────────────────────
REPORT_SUMMARY="$(run_step "주간 회고(/weekly-retrospect)" "/weekly-retrospect")"
if [ "$?" -ne 0 ]; then
  log "주간 회고 2회 실패 — 체인 중단"
  notify "[주간 회고 중단] /weekly-retrospect 가 2회 연속 실패했습니다. 이번 주 회고 리포트를 남기지 못했습니다. 로그: $LOG_FILE"
  exit 1
fi
log "주간 회고 완료 — 리포트 요약 캡처"

# ── 리포트 요약을 #주간으로 ──────────────────────────────────────────────────────
if [ -n "$REPORT_SUMMARY" ]; then
  notify "$REPORT_SUMMARY"
else
  notify "이번 주 회고는 끝났으나 리포트 요약 텍스트가 비어 있습니다(로그: $LOG_FILE)."
fi
log "주간 회고 종료"
exit 0
