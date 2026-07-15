#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# restart-listener-on-change.sh
#
# PostToolUse 훅. Claude가 Edit/Write로 telegram-listener.sh(화이트리스트가
# 들어있는 파일)를 수정하면, launchd 데몬을 재시작해 변경을 즉시 반영한다.
#
# 동작 원리:
#   - 훅은 stdin으로 tool 호출 정보(JSON)를 받는다. tool_input.file_path를 읽어
#     수정 대상이 telegram-listener.sh일 때만 재시작한다(다른 파일엔 무반응).
#   - launchctl kickstart -k 는 실행 중 서비스를 죽이고 곧바로 다시 띄운다.
#     (plist의 KeepAlive 와 무관하게 즉시 재기동을 보장)
# ─────────────────────────────────────────────────────────────
set -euo pipefail

# Label은 install.sh가 만드는 것과 동일하게 로그인 사용자명 기준으로 계산한다.
# (com.<user>.telegram-listener) — 하드코딩하면 다른 PC에서 kickstart 대상이 어긋난다.
LABEL="com.$(id -un).telegram-listener"
TARGET_FILE="telegram-listener.sh"

# 스크립트 자기 위치 기준으로 프로젝트 루트(.claude/hooks → ../..)를 잡는다.
# 절대경로를 박지 않아 다른 환경/경로에서도 그대로 동작한다.
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG="$PROJECT_ROOT/.claude/data/telegram-listener.log"

# stdin(JSON)에서 편집된 파일 경로를 추출. jq 실패해도 훅이 죽지 않게 방어.
payload="$(cat)"
file_path="$(printf '%s' "$payload" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)"

# 수정 대상이 리스너 스크립트가 아니면 조용히 통과.
case "$file_path" in
  *"$TARGET_FILE") ;;
  *) exit 0 ;;
esac

# 데몬 재시작. gui 도메인(로그인 사용자) 기준.
if launchctl kickstart -k "gui/$(id -u)/${LABEL}" 2>>"$LOG"; then
  echo "[restart-listener] $(date '+%F %T') ${TARGET_FILE} 변경 감지 → ${LABEL} 재시작 완료" >>"$LOG"
  echo "🔄 화이트리스트 변경 감지 — telegram-listener 데몬을 재시작했어요."
else
  echo "[restart-listener] $(date '+%F %T') ${LABEL} 재시작 실패 (데몬 미로드 가능성)" >>"$LOG"
  echo "⚠️ telegram-listener 재시작 실패 — 데몬이 로드돼 있는지 확인하세요 (launchctl list | grep telegram)."
fi
exit 0
