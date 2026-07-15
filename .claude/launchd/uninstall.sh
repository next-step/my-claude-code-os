#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# uninstall.sh — install.sh가 설치한 것을 이 PC에서 되돌린다.
#   1) launchd 데몬 언로드 + plist 삭제
#   2) crontab의 remind-cron 항목 제거
# install.sh와 동일하게 현재 사용자/경로 기준으로 대상을 계산한다.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

USER_NAME="$(id -un)"
UID_NUM="$(id -u)"
LABEL="com.${USER_NAME}.telegram-listener"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"

# 데몬 언로드 (로드돼 있지 않아도 에러 무시).
launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
if [ -f "$PLIST" ]; then
  rm -f "$PLIST"
  echo "✓ plist 삭제: $PLIST"
else
  echo "· plist 없음 (이미 제거됨): $PLIST"
fi

# crontab에서 우리 크론 4종(remind·flush·watchdog·digest) 라인 제거 (남은 항목은 유지).
if crontab -l 2>/dev/null | grep -qE 'remind-cron.sh|flush-cron.sh|watchdog-cron.sh|digest-cron.sh'; then
  ( crontab -l 2>/dev/null \
      | grep -v -e 'remind-cron.sh' -e 'flush-cron.sh' -e 'watchdog-cron.sh' -e 'digest-cron.sh' || true ) | crontab -
  echo "✓ crontab에서 remind·flush·watchdog·digest 크론 제거"
else
  echo "· crontab에 우리 크론 항목 없음"
fi

echo "제거 완료."
