#!/usr/bin/env bash
#
# done-fast.sh — /done 조회·완료 처리를 크리티컬 패스에서 네트워크를 빼는 헬퍼
#
# 왜 이 스크립트가 있나:
#   /done 은 두 군데서 네트워크를 탔다. ① 미완료 목록 조회가 매번 `notion.sh read`
#   (curl 동기 POST, 실측 ~0.5s)를 부르고 오케스트레이터가 status 로 걸러냈다.
#   ② 완료 처리가 선택된 항목 수만큼 `notion.sh update` 를 반복 호출했다(항목당 ~0.5s).
#   cache.sh 가 이미 read 를 로컬 캐시로 옮겨놨으니(①), 이 스크립트는 그 캐시 위에서
#   pending 만 걸러 돌려주고(read), capture-fast.sh 가 쓰기에서 했던 것과 같은 패턴을
#   완료 처리에도 적용한다(complete): 캐시를 즉시 동기로 고치고, Notion 반영은
#   detached 백그라운드로 던진다.
#
# 완료를 어떻게 즉시·안전하게 반영하나 (오버레이 방식):
#   complete 는 순수 스냅샷(todos.json)을 직접 고치지 않는다. 대신 완료를 오버레이로 남긴다.
#     - 실제 Notion 항목 → `cache.sh mark-done <id>` 로 완료 오버레이(pending-done.json)에 기록.
#       이 오버레이는 스냅샷과 별개 파일이라, 백그라운드 refresh 가 스냅샷을 통째로 덮어써도
#       완료 표시가 살아남는다(= refresh 가 방금 완료한 항목을 "미완료"로 되돌리는 레이스가
#       원천 차단된다). Notion 반영은 detached 백그라운드 update 로 던지고, 그 update 가
#       Notion 에 착하면 다음 refresh 가 오버레이에서 그 id 를 자동으로 걷어낸다(누수 없음).
#     - 아직 Notion 에 없는 항목(local:id) → outbox 파일의 status 를 done 으로 고친다.
#       읽기 시점 _emit 이 outbox 를 그대로 얹으므로 즉시 done 으로 보이고, 나중에 동기될 때도
#       done 상태로 들어간다.
#   두 경로 모두 네트워크 왕복을 크리티컬 패스에서 뺀다(캐시/오버레이는 로컬 파일, ~10ms).
#
# 정직한 한계:
#   백그라운드 Notion update 는 best-effort 다(capture-fast 의 백그라운드 write 와 동일 성격).
#   그 update 가 실패하면 항목은 오버레이에 남아 로컬로는 계속 done 으로 보이지만 Notion 엔
#   반영이 안 된 채로 있을 수 있다 — 개인 할일 OS 에서 capture 가 이미 받아들인 것과 같은
#   최종 일관성 트레이드오프다. (capture 의 outbox 재시도(capture-flush)에 대응하는 완료
#   재시도는 아직 없다.)
#
# 사용법:
#   done-fast.sh read                    # 캐시에서 status != done 인 항목만 flat json 배열로 반환
#   done-fast.sh complete <id> [<id> ...] # 각 id 를 즉시 done 처리(오버레이) + Notion 은 백그라운드 반영
#     → 요약 flat json 반환: { completed:[{id,title}...], count:N }
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE_SH="$SCRIPT_DIR/cache.sh"
CACHE_FILE="$SCRIPT_DIR/../../data/cache/todos.json"
OUTBOX_DIR="$SCRIPT_DIR/../../data/outbox"
NOTION_SH="$SCRIPT_DIR/notion.sh"

cmd="${1:-}"
shift || true

case "$cmd" in
  read)
    "$CACHE_SH" read | jq -c '[.[] | select(.status != "done")]'
    ;;

  complete)
    if [[ $# -eq 0 ]]; then
      echo '{"ok":false,"error":"usage: done-fast.sh complete <id> [<id> ...]"}' >&2
      exit 1
    fi

    # 캐시가 없으면(콜드) 우선 채운다 — cache.sh read 와 동일한 정책.
    if [[ ! -f "$CACHE_FILE" ]]; then
      "$CACHE_SH" read >/dev/null
    fi

    # 완료 요약(title 조회)과 "실제로 존재했는지" 판단은 순수 스냅샷이 아니라 cache.sh read
    # (outbox·완료 오버레이가 얹힌 병합 뷰)에서 한다. 스냅샷만 보면 아직 Notion 에 없는
    # local:id 항목은 존재하지 않는 것으로 오판되어 스킵되어 버린다.
    snapshot="$("$CACHE_SH" read)"

    completed='[]'
    real_ids=()   # 실제 Notion id 만 모아 마지막에 완료 오버레이에 한 번에 기록
    for id in "$@"; do
      found="$(jq -r --arg id "$id" 'any(.[]; .id==$id)' <<<"$snapshot")"
      if [[ "$found" != "true" ]]; then
        continue
      fi
      title="$(jq -r --arg id "$id" '.[] | select(.id==$id) | .title // empty' <<<"$snapshot")"
      completed="$(jq -c --arg id "$id" --arg t "$title" '. + [{id:$id, title:$t}]' <<<"$completed")"

      if [[ "$id" == local:* ]]; then
        # 아직 Notion 에 없는 항목 — outbox 파일의 status 를 done 으로 고친다. 읽기 시점
        # _emit 이 outbox 를 그대로 얹으므로 즉시 done 으로 보이고, 나중에 동기될 때도 done
        # 으로 들어간다. 파일이 이미 없으면(동기 완료 후 삭제됨)엔 아래 real 경로가 못 타므로
        # 드문 경계지만, 그 경우 다음 refresh 가 Notion 의 실제 상태로 수렴시킨다.
        uid="${id#local:}"
        outbox_file="$OUTBOX_DIR/$uid.json"
        if [[ -f "$outbox_file" ]]; then
          otmp="$outbox_file.tmp.$$"
          jq '.status = "done"' "$outbox_file" > "$otmp" 2>/dev/null && mv -f "$otmp" "$outbox_file" || rm -f "$otmp"
        fi
      else
        real_ids+=("$id")
        # Notion 반영은 detached 백그라운드로 — capture-fast.sh 와 동일한 nohup+&+disown 패턴.
        nohup bash -c '
          id="$1"; notion="$2"
          printf "%s" "{\"status\":\"done\"}" | "$notion" update "$id" >/dev/null 2>&1 || true
        ' _ "$id" "$NOTION_SH" >/dev/null 2>&1 &
        disown 2>/dev/null || true
      fi
    done

    # 실제 Notion id 들을 완료 오버레이에 durable 하게 기록한다(즉시·원자적). 스냅샷과 별개
    # 파일이라 백그라운드 refresh 가 스냅샷을 덮어써도 완료 표시가 살아남는다. Notion update
    # 가 착하면 다음 refresh 가 이 id 들을 오버레이에서 자동으로 걷어낸다.
    if (( ${#real_ids[@]} > 0 )); then
      "$CACHE_SH" mark-done "${real_ids[@]}"
    fi

    count="$(jq 'length' <<<"$completed")"
    jq -n --argjson completed "$completed" --argjson count "$count" \
      '{completed:$completed, count:$count}'
    ;;

  *)
    echo "usage: done-fast.sh {read | complete <id> [<id> ...]}" >&2
    exit 1
    ;;
esac
