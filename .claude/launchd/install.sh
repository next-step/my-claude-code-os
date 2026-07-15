#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# install.sh — 세션 밖 자동화(launchd 데몬 + crontab)를 이 PC에 설치한다.
#
# 왜 필요한가:
#   launchd plist와 crontab은 "절대경로"를 요구한다(둘 다 상대경로 미지원).
#   그래서 경로를 레포에 박아두면 clone 받은 다른 PC에서 깨진다.
#   이 스크립트는 "설치 시점"에 현재 clone 경로($PROJECT_ROOT)와 로그인
#   사용자명(id -un)을 채워 넣어, 누구의 PC에서든 그대로 동작하게 만든다.
#
# 설치 대상:
#   1) ~/Library/LaunchAgents/com.<user>.telegram-listener.plist  (launchd 데몬)
#   2) crontab 항목: 매일 17:00 remind-cron.sh 실행
#
# 멱등(idempotent): 여러 번 실행해도 안전하다. 기존 것을 걷어내고 다시 깐다.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

# 스크립트 자기 위치(.claude/launchd) 기준으로 프로젝트 루트(../..)를 절대경로로 확정.
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
USER_NAME="$(id -un)"
UID_NUM="$(id -u)"

LABEL="com.${USER_NAME}.telegram-listener"
LA_DIR="$HOME/Library/LaunchAgents"
PLIST="$LA_DIR/${LABEL}.plist"

LISTENER="$PROJECT_ROOT/.claude/hooks/telegram-listener.sh"
LOG="$PROJECT_ROOT/.claude/data/telegram-listener.log"
CRON_SCRIPT="$PROJECT_ROOT/.claude/hooks/remind-cron.sh"
FLUSH_CRON="$PROJECT_ROOT/.claude/hooks/flush-cron.sh"
WATCHDOG_CRON="$PROJECT_ROOT/.claude/hooks/watchdog-cron.sh"
DIGEST_CRON="$PROJECT_ROOT/.claude/hooks/digest-cron.sh"

echo "▶ 프로젝트 루트: $PROJECT_ROOT"
echo "▶ launchd Label: $LABEL"

# ── 사전 점검 ───────────────────────────────────────────────
[ -f "$LISTENER" ]     || { echo "✗ 리스너 스크립트 없음: $LISTENER"; exit 1; }
[ -f "$CRON_SCRIPT" ]  || { echo "✗ remind-cron 스크립트 없음: $CRON_SCRIPT"; exit 1; }
[ -f "$FLUSH_CRON" ]   || { echo "✗ flush-cron 스크립트 없음: $FLUSH_CRON"; exit 1; }
[ -f "$WATCHDOG_CRON" ]|| { echo "✗ watchdog-cron 스크립트 없음: $WATCHDOG_CRON"; exit 1; }
[ -f "$DIGEST_CRON" ]  || { echo "✗ digest-cron 스크립트 없음: $DIGEST_CRON"; exit 1; }
chmod +x "$LISTENER" "$CRON_SCRIPT" "$FLUSH_CRON" "$WATCHDOG_CRON" "$DIGEST_CRON" \
  "$PROJECT_ROOT/.claude/hooks/restart-listener-on-change.sh" 2>/dev/null || true

# 로그/데이터 디렉토리 보장 (launchd가 로그 파일을 열 수 있어야 함).
mkdir -p "$PROJECT_ROOT/.claude/data" "$LA_DIR"

# 자격증명 안내 (없어도 설치는 진행 — 데몬은 실행 시점에 필요).
if [ ! -s "$PROJECT_ROOT/.claude/data/telegram.json" ]; then
  echo "⚠ .claude/data/telegram.json 이 없어요. 봇 토큰/내 chat_id를 넣어야 데몬이 동작합니다."
  echo "  예: {\"bot_token\":\"...\",\"chat_id\":\"...\"}"
fi

# ── 1) launchd plist 생성 ───────────────────────────────────
# 기존 파일/심링크를 먼저 제거한다. 과거 수동 셋업이 LaunchAgents에 "레포 plist를
# 가리키는 심링크"를 걸어둔 경우, cat > 가 심링크를 따라가 레포 파일을 되살려버린다
# (=이식성 붕괴). rm -f로 링크 자체를 끊고 실제 파일을 새로 쓴다.
rm -f "$PLIST"
# heredoc(따옴표 없는 EOF)이라 $PROJECT_ROOT, $LABEL, $LISTENER, $LOG 가 확장된다.
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${LISTENER}</string>
    </array>

    <!-- 로그인 시 자동 시작 + 죽으면 자동 재시작 (long poll 데몬 상시 유지) -->
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>

    <!-- 크래시 루프 시 과도한 재시작 방지: 최소 10초 간격 -->
    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>WorkingDirectory</key>
    <string>${PROJECT_ROOT}</string>

    <key>StandardOutPath</key>
    <string>${LOG}</string>
    <key>StandardErrorPath</key>
    <string>${LOG}</string>
</dict>
</plist>
EOF
echo "✓ plist 생성: $PLIST"

# ── 2) launchd 로드 (재실행 대비 먼저 언로드) ───────────────
# 최신 macOS는 bootstrap/bootout(gui 도메인)을 쓴다. 이미 로드돼 있으면 bootout
# 실패는 무시하고, bootstrap 으로 새로 띄운다.
launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/${UID_NUM}" "$PLIST"
launchctl enable "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
echo "✓ launchd 데몬 로드 완료 (com.${USER_NAME}.telegram-listener)"

# ── 3) crontab 등록 (멱등) ──────────────────────────────────
# 우리 크론 4종의 기존 라인을 모두 제거한 뒤 현재 경로로 새로 추가한다.
#   remind  (매일 17:00)      — 미처리 draft 알럿
#   flush   (15분마다)         — outbox 재동기 조정 루프
#   watchdog(10분마다)         — telegram-listener 데몬 감시·자동 재시작
#   digest  (매주 일요일 20:00) — 할일 현황 주간 집계 발송
REMIND_LINE="0 17 * * * ${CRON_SCRIPT} 2>&1 | logger -t claude-remind"
FLUSH_LINE="*/15 * * * * ${FLUSH_CRON} 2>&1 | logger -t claude-flush"
WATCHDOG_LINE="*/10 * * * * ${WATCHDOG_CRON} 2>&1 | logger -t claude-watchdog"
DIGEST_LINE="0 20 * * 0 ${DIGEST_CRON} 2>&1 | logger -t claude-digest"
( crontab -l 2>/dev/null \
    | grep -v -e 'remind-cron.sh' -e 'flush-cron.sh' -e 'watchdog-cron.sh' -e 'digest-cron.sh' || true
  echo "$REMIND_LINE"; echo "$FLUSH_LINE"; echo "$WATCHDOG_LINE"; echo "$DIGEST_LINE"
) | crontab -
echo "✓ crontab 등록: remind(매일 17:00) · flush(15분) · watchdog(10분) · digest(일 20:00)"

echo ""
echo "설치 완료. 상태 확인:"
echo "  launchctl print gui/${UID_NUM}/${LABEL} | head"
echo "  crontab -l | grep -E 'remind|flush|watchdog|digest'-cron"
echo "제거하려면: .claude/launchd/uninstall.sh"
