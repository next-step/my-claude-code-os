#!/usr/bin/env bash
#
# list-view.sh — 할일 목록 조회 + 표시 (단일 소스)
#
# 왜 이 스크립트가 있나:
#   /list는 입력이 정해지면 출력도 정해지는 "결정론적" 조회다. LLM 판단이 필요 없다.
#   표시 규칙(상태별 그룹핑·번호·일정 요약·경과일)을 여기 한 곳에 두고,
#   /list 스킬과 텔레그램 리스너가 똑같이 이 스크립트를 호출한다.
#   덕분에 (1) 폰 응답이 claude -p(~15초) 대신 ~0.7초로 빨라지고
#         (2) 표시 규칙이 두 곳에 중복되지 않는다.
#
#   항목 조회는 notion.sh(curl 동기 POST, 실측 ~0.5s)를 직접 부르지 않고
#   cache.sh read(로컬 read-model, stale-while-revalidate)를 거친다.
#   캐시가 신선하면 ~0.01s로 즉시 반환하고, 갱신은 백그라운드로 던지므로
#   네트워크 왕복이 이 스크립트의 크리티컬 패스에서 완전히 빠진다.
#
# 사용법:
#   list-view.sh             # 전체 (상태별 그룹)
#   list-view.sh draft       # 특정 상태만 (planned/done 동일)
#   list-view.sh 장보기       # 제목 키워드 부분 일치 검색 (상태 무관)
#
# 출력: 사람이 읽는 텍스트 (claude/텔레그램 양쪽에 그대로 전달 가능)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE="$SCRIPT_DIR/cache.sh"
TODAY="$(date +%F)"

arg="${1:-}"

# ── 인자 파싱: 상태 필터 vs 키워드 vs 전체 ──────────────────
status_filter=""
keyword=""
case "$arg" in
  "")                 ;;                       # 전체
  draft|planned|done) status_filter="$arg" ;;  # 상태 필터 → jq 단에서 거름
  *)                  keyword="$arg" ;;        # 그 외 → 키워드 검색
esac

# ── 항목 조회 ──────────────────────────────────────────────
# cache.sh는 상태 인자를 받지 않고 항상 전체를 반환하므로,
# 상태 필터는 (키워드 필터와 마찬가지로) jq 단에서 거른다.
items="$("$CACHE" read)"
if [[ -n "$status_filter" ]]; then
  items="$(jq --arg s "$status_filter" '[.[] | select(.status==$s)]' <<<"$items")"
elif [[ -n "$keyword" ]]; then
  items="$(jq --arg k "$keyword" '[.[] | select(.title // "" | contains($k))]' <<<"$items")"
fi

count="$(jq 'length' <<<"$items")"

# ── 비어 있으면 상황별 안내 후 종료 ─────────────────────────
if [[ "$count" -eq 0 ]]; then
  if [[ -n "$keyword" ]]; then
    echo "'$keyword'에 해당하는 할일이 없어요."
  elif [[ -n "$status_filter" ]]; then
    echo "'$status_filter'에 해당하는 할일이 없어요."
  else
    echo "아직 등록된 할일이 없어요. /capture로 첫 할일을 추가해보세요."
  fi
  exit 0
fi

# ── 헤더 ───────────────────────────────────────────────────
if [[ -n "$keyword" ]]; then
  header="🔍 '$keyword' 검색 결과 (${count}개)"
else
  header="📋 할일 전체 (${count}개)"
fi

# ── 상태별 그룹핑 + 포맷 (표시 규칙의 단일 출처) ────────────
#   - 흐름 순서 draft → planned → done 으로 묶는다
#   - 각 그룹 내부는 cache.sh가 캡처일 오래된 순으로 정렬해 반환
#   - 번호는 그룹을 가로질러 연속(1,2,3,…)
#   - 비어 있는 그룹은 출력하지 않는다
jq -r --arg today "$TODAY" --arg header "$header" '
  def epoch(d): (d[0:10] + " 00:00:00" | strptime("%Y-%m-%d %H:%M:%S") | mktime);

  # draft 경과일 라벨: 0일이면 "오늘 캡처", 그 외 "N일 전 캡처"
  def capLabel:
    (((epoch($today) - epoch(.captured_at)) / 86400) | floor) as $d
    | if $d <= 0 then "오늘 캡처" else "\($d)일 전 캡처" end;

  # planned 일정 요약: daily → "매일[ time]", 그 외 → "due_date[ time]" (날짜 미정이면 "미정")
  def schedLabel:
    if .recurrence == "daily" then
      "매일" + (if .time then " " + .time else "" end)
    else
      (.due_date // "미정") + (if .time then " " + .time else "" end)
    end;

  ([.[] | select(.status=="draft")])   as $draft   |
  ([.[] | select(.status=="planned")]) as $planned |
  ([.[] | select(.status=="done")])    as $done    |
  ($draft + $planned + $done) as $ordered |
  ($ordered | to_entries | map({key:.value.id, value:(.key+1)}) | from_entries) as $idx |

  [ $header,
    ( if ($draft|length)   > 0 then
        "", "📝 구체화 대기 (draft) · \($draft|length)개",
        ($draft[]   | "  \($idx[.id]). \(.title) (\(.category // "-")) — \(capLabel)")
      else empty end ),
    ( if ($planned|length) > 0 then
        "", "📅 예정 (planned) · \($planned|length)개",
        ($planned[] | "  \($idx[.id]). \(.title) (\(.category // "-")) — \(schedLabel)")
      else empty end ),
    ( if ($done|length)    > 0 then
        "", "✅ 완료 (done) · \($done|length)개",
        ($done[]    | "  \($idx[.id]). \(.title) (\(.category // "-"))")
      else empty end )
  ] | flatten | .[]
' <<<"$items"
