#!/usr/bin/env bash
#
# digest-report.sh — 할일 현황 요약(집계) 텍스트 생성 (결정론적)
#
# 왜 이 스크립트가 있나:
#   집계(digest) 루프의 "몸통". 매주 한 번 현재 할일 스냅샷을 요약해 폰으로 보낸다.
#   remind 가 매일 "구체화 안 한 draft"를 재촉하는 알림이라면, 이건 주 1회 전체
#   현황(상태 분포·카테고리·오래 방치된 draft)을 돌아보는 회고용 집계다.
#
#   /list·usage-report 와 같은 철학: 입력이 정해지면 출력도 정해지는 결정론적
#   집계라 LLM 판단이 필요 없다. 항목은 cache.sh(로컬 read-model)에서 읽어
#   네트워크 왕복을 크리티컬 패스에서 뺀다.
#
# 사용법:
#   digest-report.sh          # cache.sh read 로 현재 항목을 집계해 요약 텍스트 출력
# 환경변수:
#   ITEMS_JSON_FILE  이 파일(flat json 배열)을 항목 소스로 사용 — 테스트가 픽스처를
#                    주입해 cache/네트워크 없이 집계 로직만 검증할 때 쓴다.
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE="$SCRIPT_DIR/cache.sh"
TODAY="$(date +%F)"

# 항목 소스: 기본은 cache.sh read, 테스트는 ITEMS_JSON_FILE 로 픽스처 주입.
if [ -n "${ITEMS_JSON_FILE:-}" ]; then
  items="$(cat "$ITEMS_JSON_FILE" 2>/dev/null || echo '[]')"
else
  items="$("$CACHE" read 2>/dev/null || echo '[]')"
fi
# 유효성 방어: 배열이 아니면 빈 배열로.
jq -e 'type=="array"' >/dev/null 2>&1 <<<"$items" || items='[]'

count="$(jq 'length' <<<"$items")"
if [ "$count" -eq 0 ]; then
  printf '📊 할일 현황 요약 (%s)\n\n  아직 등록된 할일이 없어요.\n' "$TODAY"
  exit 0
fi

# ── 집계 + 포맷 (표시 규칙의 단일 출처) ─────────────────────
#   - 상태 분포(draft/planned/done), 카테고리 분포(내림차순), 2일+ 방치 draft
#   - epoch 정의는 list-view.sh 와 동일(ISO 문자열 = 시간순) — 검증된 패턴 재사용
jq -r --arg today "$TODAY" '
  def epoch(d): (d[0:10] + " 00:00:00" | strptime("%Y-%m-%d %H:%M:%S") | mktime);
  def emj($c): {"스터디":"📚","업무":"💼","일상":"🏠","건강":"🏥","금융":"💰","기타":"🔧"}[$c] // "🔖";

  (map(select(.status=="draft")))   as $d  |
  (map(select(.status=="planned"))) as $p  |
  (map(select(.status=="done")))    as $dn |
  length as $tot |

  ( group_by(.category // "기타")
    | map({cat: (.[0].category // "기타"), n: length})
    | sort_by(-.n) ) as $cats |

  ( $d | map(select(.captured_at != null))
       | map(. + {age: (((epoch($today) - epoch(.captured_at)) / 86400) | floor)})
       | map(select(.age >= 2))
       | sort_by(-.age) ) as $stale |

  [ "📊 할일 현황 요약 (\($today))",
    "",
    "전체 \($tot)개",
    "  📝 draft \($d|length) · 📅 planned \($p|length) · ✅ done \($dn|length)",
    "",
    "카테고리 분포",
    ( $cats[] | "  \(emj(.cat)) \(.cat) \(.n)개" ),
    ( if ($stale|length) > 0 then
        "", "⏳ 오래 방치된 draft (2일+)",
        ( $stale[] | "  • \(.title) (\(.age)일 전 캡처)" )
      else empty end )
  ] | flatten | .[]
' <<<"$items"
