#!/usr/bin/env bash
#
# cache.sh — 할일 로컬 read-model 캐시 (list/done 응답을 네트워크에서 분리)
#
# 왜 이 스크립트가 있나:
#   /list·/done 의 크리티컬 패스에는 `notion.sh read`(curl 동기 POST, 실측 ~0.5s)가 매번
#   얹혀 있었다. 조회는 결정론적이라 LLM 은 이미 우회했지만, "네트워크 왕복"이라는 물리적
#   지연은 그대로 남아 있었다. capture 가 쓰기를 로컬 outbox + 백그라운드 동기로 뺀 것과
#   대칭으로, 이 스크립트는 읽기를 로컬 캐시로 뺀다.
#
#   stale-while-revalidate 전략:
#     - 캐시가 있으면 즉시 반환(~10ms)하고, 오래됐으면 백그라운드로 갱신을 던진다.
#       → 사용자 체감 응답에서 0.5s 네트워크 왕복이 사라진다.
#     - 캐시가 아예 없으면(콜드) 그때 한 번만 동기로 채운다.
#   이 트레이드오프는 "직전 순간의 원격 변경이 한 박자 늦게 보일 수 있음"이며, 개인 할일
#   OS 에서 capture 가 이미 택한 것과 같은 성격의 최종 일관성이다.
#
# read-model = 순수 스냅샷 + 오버레이 2장 (병합은 읽기 시점 _emit 한 곳에서만):
#   ┌ todos.json        = 순수 Notion 스냅샷. 지워도 되는 파생물. refresh 가 통째로 교체.
#   ├ outbox/*.json     = 아직 동기 안 된 "생성"(방금 /capture). 지우면 유실되는 원본.
#   └ pending-done.json = 아직 Notion 이 확인 안 한 "완료"(id 배열). done 의 낙관적 반영.
#   _emit 이 스냅샷 위에 두 오버레이를 얹어 내보낸다.
#     → refresh 가 스냅샷을 언제 덮어써도, 방금 캡처(outbox)·방금 완료(pending-done)한
#       항목이 사라지지 않는다. done 을 스냅샷에 직접 쓰지 않으므로 "순수 스냅샷" 불변식이
#       지켜지고, 백그라운드 refresh 와 done 이 서로를 덮어쓰는 레이스가 원천 차단된다.
#     (오버레이 읽기는 전부 로컬 파일이라 ~10ms, 네트워크 0)
#
# 사용법:
#   cache.sh read              # 스냅샷+오버레이를 flat json 배열로 반환(즉시) + 필요시 백그라운드 갱신
#   cache.sh refresh           # Notion 을 동기로 다시 읽어 스냅샷에 원자적 기록 후 오버레이 얹어 출력
#   cache.sh refresh-bg        # 위 refresh 를 detached 백그라운드로 던지고 즉시 종료
#   cache.sh mark-done <id>... # 완료 오버레이(pending-done.json)에 id 들을 원자적으로 추가
#
# 출력(read/refresh): notion.sh 와 동일한 flat json 배열, 캡처일 오래된 순 정렬
#   { id, title, category, status, captured_at, recurrence, due_date, time, detail, local? }
#   local:true 는 아직 Notion 에 없는(outbox) 항목. id 는 "local:<uid>" 형식.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SELF="$SCRIPT_DIR/cache.sh"
CACHE_DIR="$SCRIPT_DIR/../../data/cache"
CACHE_FILE="$CACHE_DIR/todos.json"
DONE_OVERLAY="$CACHE_DIR/pending-done.json"
OUTBOX_DIR="$SCRIPT_DIR/../../data/outbox"
NOTION="$SCRIPT_DIR/notion.sh"

# 캐시를 "신선"으로 볼 최대 나이(초). 이보다 오래되면 백그라운드 갱신을 건다.
STALE_SECONDS="${TODO_CACHE_STALE_SECONDS:-60}"

# ── outbox(아직 동기 안 된 캡처 항목) → flat json 배열 ─────────────
# 각 파일은 {title,category,status,captured_at} 형식. id/local 을 덧붙이고
# notion.sh 와 필드 스키마를 맞춘다(없는 필드는 null).
_read_outbox() {
  mkdir -p "$OUTBOX_DIR"
  local out='[]' f uid item
  shopt -s nullglob
  for f in "$OUTBOX_DIR"/*.json; do
    uid="$(basename "$f" .json)"
    item="$(jq -c --arg id "local:$uid" '
      {
        id:          $id,
        title:       (.title // null),
        category:    (.category // null),
        status:      (.status // "draft"),
        captured_at: (.captured_at // null),
        recurrence:  (.recurrence // null),
        due_date:    (.due_date // null),
        time:        (.time // null),
        detail:      (.detail // null),
        local:       true
      }' "$f" 2>/dev/null || true)"
    [[ -n "$item" ]] && out="$(jq -c --argjson x "$item" '. + [$x]' <<<"$out")"
  done
  printf '%s' "$out"
}

# ── 완료 오버레이(아직 Notion 이 확인 안 한 done id 배열) ──────────
_read_done_overlay() {
  if [[ -f "$DONE_OVERLAY" ]]; then
    jq -c 'if type=="array" then . else [] end' "$DONE_OVERLAY" 2>/dev/null || echo '[]'
  else
    echo '[]'
  fi
}

# ── Notion 스냅샷을 캐시에 원자적 기록 + 완료 오버레이 정리 ───────
# 캐시(todos.json)는 "순수 Notion 스냅샷"만 담는다. outbox·완료 오버레이 병합은 읽기 시점
# (_emit)에서 얹으므로 여기서는 신경 쓰지 않는다.
_refresh() {
  mkdir -p "$CACHE_DIR"

  local notion_items tmp
  notion_items="$("$NOTION" read 2>/dev/null || true)"
  # Notion 읽기 실패(네트워크/오프라인)면 기존 캐시를 보존하고 조용히 끝낸다.
  if ! jq -e 'type=="array"' >/dev/null 2>&1 <<<"$notion_items"; then
    [[ -f "$CACHE_FILE" ]] && return 0
    notion_items='[]'
  fi

  tmp="$CACHE_FILE.tmp.$$"
  printf '%s' "$notion_items" > "$tmp"
  mv -f "$tmp" "$CACHE_FILE"   # 원자적 교체(동시 갱신 시 마지막 승자)

  # 완료 오버레이 정리(누수 방지): Notion 이 이미 done 으로 확인했거나(백그라운드 update 착)
  # 아예 사라진 id 는 오버레이에서 제거한다. 아직 Notion 에서 not-done 으로 보이는 id
  # (= update 가 아직 안 착)만 남겨, 그 항목이 refresh 로 다시 "미완료"로 돌아가지 않게 한다.
  if [[ -f "$DONE_OVERLAY" ]]; then
    local otmp="$DONE_OVERLAY.tmp.$$"
    if jq --argjson notion "$notion_items" '
          ( $notion | map(select(.status != "done") | .id) ) as $pending
          | (if type=="array" then . else [] end)
          | map(select( . as $id | $pending | index($id) ))
        ' "$DONE_OVERLAY" > "$otmp" 2>/dev/null; then
      mv -f "$otmp" "$DONE_OVERLAY"
    else
      rm -f "$otmp"
    fi
  fi
}

# ── 스냅샷 위에 두 오버레이를 얹어 출력 (병합의 단일 출처) ─────────
#   - 스냅샷의 Notion 항목은 전부 보존한다(제목·초 단위 캡처시각이 우연히 같아도
#     서로 다른 항목을 합치지 않는다). outbox 항목은 스냅샷에 (title,captured_at)이
#     이미 있는 것만 빼고 얹는다 — 동기 직후 잠깐 겹쳐도 중복이 안 생긴다.
#   - 완료 오버레이(id 배열)에 든 항목은 status 를 done 으로 덮는다(낙관적 반영).
#   - captured_at 오름차순 정렬(ISO 문자열 = 시간순). notion.sh 계약과 동일.
_emit() {
  local done_overlay
  done_overlay="$(_read_done_overlay)"
  jq -s --argjson done "$done_overlay" '
    .[0] as $notion | .[1] as $outbox
    | ( $notion | map((.title // "") + "|" + (.captured_at // "")) ) as $nkeys
    | ( $notion
        + ( $outbox | map(select( ((.title // "") + "|" + (.captured_at // "")) as $k
                                   | ($nkeys | index($k)) | not )) ) )
    | map( if (.id as $i | $done | index($i)) then .status = "done" else . end )
    | sort_by(.captured_at // "")
  ' "$CACHE_FILE" <(_read_outbox)
}

# ── 완료 오버레이에 id 들을 원자적으로 합집합 추가 ────────────────
# done-fast.sh 가 "실제 Notion id" 를 넘겨 부른다. (local:id 는 outbox 로 처리되므로 제외)
_mark_done() {
  mkdir -p "$CACHE_DIR"
  local ids_json existing tmp
  ids_json="$(printf '%s\n' "$@" | jq -R . | jq -s .)"
  existing="$(_read_done_overlay)"
  tmp="$DONE_OVERLAY.tmp.$$"
  jq -n --argjson a "$existing" --argjson b "$ids_json" '($a + $b) | unique' > "$tmp"
  mv -f "$tmp" "$DONE_OVERLAY"
}

# ── refresh 를 부모와 분리된 백그라운드로 ────────────────────────
_refresh_bg() {
  ( nohup "$SELF" refresh >/dev/null 2>&1 & )
  disown 2>/dev/null || true
}

# ── 캐시가 STALE_SECONDS 보다 오래됐는가 (macOS stat) ────────────
_is_stale() {
  local mtime now
  mtime="$(stat -f %m "$CACHE_FILE" 2>/dev/null || echo 0)"
  now="$(date +%s)"
  (( now - mtime > STALE_SECONDS ))
}

cmd="${1:-read}"
shift || true

case "$cmd" in
  read)
    if [[ ! -f "$CACHE_FILE" ]]; then
      # 콜드 스타트: 캐시가 없을 때만 동기로 한 번 채운다.
      _refresh
    elif _is_stale; then
      # 신선하지 않으면 지금 것을 즉시 주고, 갱신은 백그라운드로.
      _refresh_bg
    fi
    _emit   # 스냅샷(신선도 무관) + outbox·완료 오버레이 → 방금 캡처/완료한 항목도 항상 즉시 반영
    ;;

  refresh)
    _refresh
    _emit
    ;;

  refresh-bg)
    _refresh_bg
    ;;

  mark-done)
    if [[ $# -eq 0 ]]; then
      echo '{"ok":false,"error":"usage: cache.sh mark-done <id> [<id> ...]"}' >&2
      exit 1
    fi
    _mark_done "$@"
    ;;

  *)
    echo "usage: cache.sh {read | refresh | refresh-bg | mark-done <id>...}" >&2
    exit 1
    ;;
esac
