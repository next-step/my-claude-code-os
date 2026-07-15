#!/usr/bin/env bash
#
# telegram-send.sh — 텔레그램 메시지 발송 (알림 루프 공용 sender)
#
# 왜 이 스크립트가 있나:
#   감시(watchdog)·집계(digest) 등 여러 루프가 "폰으로 한 줄 보내기"를 필요로 한다.
#   telegram-listener.sh 안에도 send_tg 가 있지만 그건 데몬 내부용이라, 외부 cron
#   루프들이 공통으로 쓸 발송기를 한 곳에 둔다(단일 소스). 자격증명 취급은
#   비밀값 규칙 정본(security.md)을 그대로 따른다.
#   (정본 경로를 코드에 박지 않는다 — .sh 는 정본을 컨텍스트에 Read 하는 소비자가
#    아니라 규칙을 코드로 따를 뿐이므로, context-map §2 주입 지도의 엣지가 아니다.
#    telegram-listener.sh 가 보안 규칙을 인라인으로만 두는 것과 같은 관례.)
#
# 보안 (security.md 불변 규칙):
#   - 토큰·chat_id 전문을 로그·응답·에러 어디에도 출력하지 않는다.
#   - 자격증명 파일이 없거나 비어 있으면 발송하지 않고 실패를 응답한다(값은 안 싣는다).
#   - 자격증명 파일은 읽기 전용으로만 접근한다.
#
# 사용법:
#   telegram-send.sh "보낼 메시지"      # 인자로 전달
#   echo "여러 줄..." | telegram-send.sh  # stdin 으로 전달(인자 없을 때)
#
# 반환: 성공 시 exit 0, 실패 시 exit 1 (stderr 에 값 없는 사유만)
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRED="$SCRIPT_DIR/../../data/telegram.json"

# cron/launchd 의 제한된 PATH 보완 — jq·curl 을 찾기 위함.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# 메시지: 인자 우선, 없으면 stdin.
if [ "$#" -gt 0 ]; then
  text="$1"
else
  text="$(cat)"
fi

# 빈 메시지는 보내지 않는다.
if [ -z "${text//[$'\t\r\n ']/}" ]; then
  echo "[telegram-send] 빈 메시지 — 발송 안 함" >&2
  exit 1
fi

# 자격증명 없으면 값 노출 없이 실패 응답 (security.md #3).
if [ ! -s "$CRED" ]; then
  echo "[telegram-send] 자격증명 없음 — 발송 안 함" >&2
  exit 1
fi

BOT_TOKEN="$(jq -r '.bot_token // empty' "$CRED")"
CHAT_ID="$(jq -r '.chat_id // empty' "$CRED")"
if [ -z "$BOT_TOKEN" ] || [ -z "$CHAT_ID" ]; then
  echo "[telegram-send] 자격증명 필드 누락 — 발송 안 함" >&2   # 값은 싣지 않는다
  exit 1
fi

# 텔레그램 sendMessage (text 4000자 컷: API 한도 4096). http_code 만 확인.
code="$(curl -s -o /dev/null -w '%{http_code}' \
  "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${CHAT_ID}" \
  --data-urlencode "text=${text:0:4000}")"

if [ "$code" = "200" ]; then
  exit 0
else
  echo "[telegram-send] 발송 실패 (http ${code})" >&2   # 토큰·chat_id 는 로그에 없음
  exit 1
fi
