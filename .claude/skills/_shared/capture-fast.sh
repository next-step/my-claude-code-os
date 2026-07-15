#!/usr/bin/env bash
#
# capture-fast.sh — /capture 저장을 크리티컬 패스에서 제거하는 즉시-응답 헬퍼
#
# 왜 이 스크립트가 있나:
#   notion.sh write 는 curl 동기 POST 로 네트워크 왕복(실측 ~0.48s)을 하는 동안 사용자를
#   기다리게 한다. 할일 캡처는 "빨리 받아 적고 잊는" 행위이므로, 저장 완료를 기다릴 이유가
#   없다. 이 스크립트는 (1) 로컬 outbox 에 항목을 동기로 durable 하게 남기고(즉시),
#   (2) Notion 반영은 detached 백그라운드로 던진 뒤 즉시 종료한다. 그래서 저장 단계의
#   crit-path bash 시간이 100ms 미만으로 떨어진다. 유실은 없다 — 백그라운드 write 가
#   실패하면 항목이 outbox 에 남아 capture-flush.sh 로 재시도된다.
#
# 사용법:
#   capture-fast.sh "<키워드>" "<카테고리>"
#     → 확인용 flat json({id_local,title,category,status,captured_at,synced})을 stdout 으로 즉시 반환
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTBOX_DIR="$SCRIPT_DIR/../../data/outbox"
NOTION_SH="$SCRIPT_DIR/notion.sh"

title="${1:-}"
category="${2:-기타}"

if [[ -z "$title" ]]; then
  echo '{"ok":false,"error":"usage: capture-fast.sh <keyword> <category>"}' >&2
  exit 1
fi

mkdir -p "$OUTBOX_DIR"

# 로컬 uid (Notion 실제 id 와 별개, 즉시 응답/추적용). date +%s + PID + RANDOM 으로 충돌 회피.
uid="$(date +%s)-$$-${RANDOM}"
captured_at="$(date +%Y-%m-%dT%H:%M:%S%z)"
# %z 는 +0900 형식 → ISO 8601 의 +09:00 으로 보정
captured_at="${captured_at:0:22}:${captured_at:22:2}"

item_file="$OUTBOX_DIR/$uid.json"

# (1) 동기 durable append — jq 로 안전하게 escape (키워드에 따옴표가 있어도 깨지지 않음)
jq -n --arg t "$title" --arg c "$category" --arg ts "$captured_at" \
  '{title:$t, category:$c, status:"draft", captured_at:$ts}' > "$item_file"

# (2) Notion 반영을 detached 백그라운드로. 성공 시 outbox 파일 제거, 실패 시 남겨 재시도.
#     nohup + '&' + disown 으로 부모 종료와 무관하게 계속 실행되도록 분리한다.
nohup bash -c '
  item="$1"; notion="$2"
  res="$(cat "$item" | "$notion" write 2>/dev/null || true)"
  # 정상 write 는 Notion page id 를 담은 flat json 을 반환한다. id 가 있으면 성공으로 보고 제거.
  if printf "%s" "$res" | jq -e ".id and (.id|length>0)" >/dev/null 2>&1; then
    rm -f "$item"
  fi
' _ "$item_file" "$NOTION_SH" >/dev/null 2>&1 &
disown 2>/dev/null || true

# (3) 확인 정보를 네트워크 대기 없이 즉시 반환
jq -n --arg u "$uid" --arg t "$title" --arg c "$category" --arg ts "$captured_at" \
  '{id_local:$u, title:$t, category:$c, status:"draft", captured_at:$ts, synced:"background"}'
