#!/bin/bash
# 텔레그램 인바운드 브리지 (long polling 데몬)
# ─────────────────────────────────────────────────────────────
# 폰에서 봇에게 보낸 "/capture ..." 같은 명령을 받아 로컬 claude로 실행한다.
# launchd가 상시 띄워두는 데몬이며, getUpdates를 long poll로 호출해
# 메시지가 오는 즉시 처리한다. (cron 1분 폴링 대비 거의 실시간 응답)
#
# 보안 3종 (반드시 유지):
#   1) chat_id 화이트리스트 — telegram.json의 내 chat_id가 보낸 것만 처리
#   2) 명령 화이트리스트   — ALLOWED_COMMANDS에 등록된 슬래시 명령만 실행
#   3) eval 미사용         — 사용자 텍스트를 셸로 재평가하지 않고 인자로만 전달

set -u

# 스크립트 위치 기준 프로젝트 루트(.claude/hooks → ../..)로 이동.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.." || exit 1

# launchd의 제한된 PATH 보완 — claude 바이너리/jq를 찾기 위함.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# launchd 환경엔 USER가 없다. claude는 키체인에서 로그인 토큰(claudeAiOauth)을
# 꺼낼 때 계정명으로 $USER를 쓰기 때문에, 이게 비면 "Not logged in"이 된다.
export USER="$(id -un)"

DATA_DIR=".claude/data"
CRED="$DATA_DIR/telegram.json"
OFFSET_FILE="$DATA_DIR/telegram-offset.txt"

# long poll 대기 시간(초). 이 시간 동안 메시지가 없으면 빈 응답으로 끊고 재요청.
# 메시지가 도착하면 그 즉시 반환되므로 체감 응답은 거의 실시간이다.
POLL_TIMEOUT=25

# ── 허용 명령 화이트리스트 ──────────────────────────────────
# 새 명령을 열려면 여기에 슬래시 명령만 추가하면 된다 (예: "/done" "/plan").
ALLOWED_COMMANDS=("/capture" "/list" "/plan")

# 인자 없이도 실행되는 명령. (예: "/list"는 인자 없이 전체 조회)
# 여기에 없는 명령은 인자가 비면 거절 안내를 보낸다.
NO_ARG_OK_COMMANDS=("/list" "/plan")

# ── 자격증명 로드 ───────────────────────────────────────────
if [ ! -s "$CRED" ]; then
  echo "[telegram-listener] $CRED 없음 — 중단"
  exit 1
fi
BOT_TOKEN=$(jq -r '.bot_token' "$CRED")
MY_CHAT_ID=$(jq -r '.chat_id' "$CRED")
API="https://api.telegram.org/bot${BOT_TOKEN}"

# ── 텔레그램 발송 헬퍼 (text는 4000자로 자름: API 한도 4096) ──
send_tg() {
  local text="$1"
  text="${text:0:4000}"
  curl -s "${API}/sendMessage" \
    --data-urlencode "chat_id=${MY_CHAT_ID}" \
    --data-urlencode "text=${text}" \
    -o /dev/null
}

# ── 명령 허용 여부 검사 ─────────────────────────────────────
is_allowed() {
  local cmd="$1"
  for a in "${ALLOWED_COMMANDS[@]}"; do
    [ "$cmd" = "$a" ] && return 0
  done
  return 1
}

# ── 인자 없이 실행 가능한 명령인지 검사 ─────────────────────
no_arg_ok() {
  local cmd="$1"
  for a in "${NO_ARG_OK_COMMANDS[@]}"; do
    [ "$cmd" = "$a" ] && return 0
  done
  return 1
}

# ── 업데이트 한 건 처리 ─────────────────────────────────────
handle_update() {
  local row="$1"
  field() { echo "$row" | base64 --decode | jq -r "$1"; }

  local cid text cmd args
  cid=$(field '.message.chat.id // empty')
  text=$(field '.message.text // empty')

  # 보안 1: 내 chat_id가 아니면 무시 (응답도 하지 않음 — 정보 노출 방지).
  [ -n "$cid" ] && [ "$cid" = "$MY_CHAT_ID" ] || return
  [ -n "$text" ] || return

  # 슬래시(/)로 시작하지 않으면 → 직전 대화의 "답변"으로 보고 이어간다.
  # 배경: /plan 같은 멀티턴 인터뷰 스킬은 "매일/일회성?"처럼 되묻는데,
  #       텔레그램은 매 메시지를 독립 처리하므로 "일회성" 답이 새 명령으로 취급돼
  #       화이트리스트에서 거절됐다. claude --continue로 직전 세션을 이어받아 해결.
  # 보안: chat_id(#1)로 이미 소유자만 통과했고, eval 없이 인자로만 전달(#3)한다.
  # --disallowedTools AskUserQuestion: -p(비대화) 모드에서 AskUserQuestion은 입력을
  #   영원히 기다려 데몬 전체를 멈춘다. 막으면 모델이 질문을 "텍스트로 출력하고 종료"해
  #   다음 메시지로 이어받을 수 있다.
  # 프롬프트는 stdin(printf)으로 전달 — --disallowedTools가 가변 인자라 위치 인자
  #   프롬프트를 삼키는 문제를 피한다.
  if [ "${text:0:1}" != "/" ]; then
    echo "[telegram-listener] 대화 이어가기: ${text}"
    local cout crc
    cout=$(printf '%s' "$text" | claude -p --continue --strict-mcp-config --disallowedTools AskUserQuestion 2>&1)
    crc=$?
    if [ "$crc" -eq 0 ]; then
      send_tg "$cout"
    else
      send_tg "❌ 이어가기 실패 (code ${crc})
${cout}"
    fi
    return
  fi

  # 첫 토큰을 명령으로 파싱. 그룹용 "/capture@botname" 형태의 @봇이름은 제거.
  cmd="${text%% *}"
  cmd="${cmd%%@*}"
  args="${text#"$cmd"}"
  args="${args# }"   # 앞 공백 한 칸 제거

  # 보안 2: 화이트리스트에 없는 명령은 거절 안내만.
  if ! is_allowed "$cmd"; then
    send_tg "⚠️ 허용되지 않은 명령이에요: ${cmd}
사용 가능: ${ALLOWED_COMMANDS[*]}"
    return
  fi

  if [ -z "$args" ] && ! no_arg_ok "$cmd"; then
    send_tg "⚠️ ${cmd} 뒤에 내용을 적어주세요. 예: ${cmd} 장보기"
    return
  fi

  # 보안 3: eval 없이 인자로만 전달. (변수 확장은 명령 치환을 재실행하지 않음)
  echo "[telegram-listener] 실행: ${cmd} ${args}"
  local out rc
  case "$cmd" in
    /list)
      # 결정론적 조회 — claude -p(~15초)를 우회하고 공유 포매터를 직접 호출(~1초).
      # /list 스킬과 동일한 표시 규칙을 같은 스크립트에서 쓴다(단일 소스).
      out=$(.claude/skills/_shared/list-view.sh ${args:+"$args"} 2>&1)
      rc=$?
      ;;
    /capture)
      # 결정론적 캡처 — claude -p(콜드 스타트 ~10초)를 우회하고 분류→저장→노티스를
      # 순수 bash 로 처리(~0.03초). /list 와 같은 패턴. capture.sh 가 사전 분류 후
      # 로컬 outbox 에 즉시 저장하고 Notion 동기는 백그라운드로 던지므로, 노티스까지
      # 네트워크 왕복이 없다. (인자는 위 no_arg 검사에서 이미 비어있지 않음을 보장)
      out=$(.claude/skills/_shared/capture.sh "$args" 2>&1)
      rc=$?
      ;;
    *)
      # AskUserQuestion 차단 + stdin 프롬프트: 위 "이어가기"와 같은 이유.
      # /plan 등 인터뷰형 스킬이 블로킹 없이 질문을 텍스트로 돌려주게 한다.
      # --strict-mcp-config: MCP 서버를 0개로 로드해 콜드 스타트 ~7초를 줄인다.
      #   텔레그램 스킬(capture/plan/list)은 MCP를 쓰지 않으므로(Notion도 notion.sh
      #   셸 스크립트) 부작용 없이 인증·스킬만 살린 채 부팅만 가볍게 한다.
      out=$(printf '%s' "${cmd}${args:+ $args}" | claude -p --strict-mcp-config --disallowedTools AskUserQuestion 2>&1)
      rc=$?
      ;;
  esac

  if [ $rc -eq 0 ]; then
    send_tg "$out"
  else
    send_tg "❌ 실행 실패 (code ${rc})
${out}"
  fi
}

# ── long poll 루프 (launchd가 KeepAlive로 데몬을 상시 유지) ──
echo "[telegram-listener] 데몬 시작 (long poll ${POLL_TIMEOUT}s)"

# offset(마지막으로 확정 처리한 update_id+1) 로드 — 재시작 시 재처리 방지.
OFFSET=0
[ -s "$OFFSET_FILE" ] && OFFSET=$(cat "$OFFSET_FILE")

while true; do
  # timeout만큼 연결을 열어두고, 메시지가 오면 즉시 반환.
  # --max-time은 long poll 타임아웃보다 넉넉히 줘서 정상 대기를 끊지 않게 한다.
  RESP=$(curl -s --max-time $((POLL_TIMEOUT + 10)) \
    "${API}/getUpdates?offset=${OFFSET}&timeout=${POLL_TIMEOUT}")

  # 네트워크 블립 등으로 실패하면 잠깐 쉬고 재시도 (데몬은 죽지 않는다).
  if [ "$(echo "$RESP" | jq -r '.ok' 2>/dev/null)" != "true" ]; then
    sleep 3
    continue
  fi

  COUNT=$(echo "$RESP" | jq '.result | length')
  [ "$COUNT" -eq 0 ] && continue   # 새 메시지 없음 → 곧장 다음 long poll

  # 각 업데이트를 base64로 통째 인코딩해 텍스트 내 개행/탭 안전 처리.
  for row in $(echo "$RESP" | jq -r '.result[] | @base64'); do
    uid=$(echo "$row" | base64 --decode | jq -r '.update_id')
    # offset은 처리/스킵 여부와 무관하게 항상 전진시켜 재처리를 막는다.
    [ "$uid" -ge "$OFFSET" ] && OFFSET=$((uid + 1))
    handle_update "$row"
  done

  # offset 확정 저장 (재시작 후에도 이어서 처리).
  echo "$OFFSET" > "$OFFSET_FILE"
done
