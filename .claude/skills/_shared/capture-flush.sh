#!/usr/bin/env bash
#
# capture-flush.sh — outbox 에 남은(= 백그라운드 write 가 실패한) 캡처 항목을 재동기한다.
#
# 왜 필요한가:
#   capture-fast.sh 는 Notion 반영을 백그라운드로 던진다. 네트워크 실패/오프라인이면 항목이
#   data/outbox/ 에 남는다. 이 스크립트가 남은 항목을 다시 밀어넣어 유실을 방지한다.
#   (수동 호출하거나, 필요하면 cron/훅에서 주기 호출할 수 있다.)
#
# 사용법:
#   capture-flush.sh          # outbox 전체 재시도, 결과 요약 출력
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTBOX_DIR="$SCRIPT_DIR/../../data/outbox"
NOTION_SH="$SCRIPT_DIR/notion.sh"

if [[ ! -d "$OUTBOX_DIR" ]]; then
  echo '{"flushed":0,"remaining":0}'
  exit 0
fi

flushed=0
remaining=0
shopt -s nullglob
for item in "$OUTBOX_DIR"/*.json; do
  res="$(cat "$item" | "$NOTION_SH" write 2>/dev/null || true)"
  if printf "%s" "$res" | jq -e '.id and (.id|length>0)' >/dev/null 2>&1; then
    rm -f "$item"
    flushed=$((flushed+1))
  else
    remaining=$((remaining+1))
  fi
done

jq -n --argjson f "$flushed" --argjson r "$remaining" '{flushed:$f, remaining:$r}'
