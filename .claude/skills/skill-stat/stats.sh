#!/usr/bin/env bash
#
# skill-stat 집계 스크립트 — PreToolUse:Skill 훅이 쌓은 JSONL 을 읽어 통계를 출력한다.
#
# 사용법: stats.sh [--days N] [--top N]
#   --days N   최근 N일만 집계 (기본: 전체)
#   --top  N   랭킹 상위 N개만 표시 (기본: 15)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# .claude/skills/skill-stat/ 의 세 단계 위 = 프로젝트 루트
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
LOG_FILE="$PROJECT_DIR/.claude/data/skill-usage.jsonl"

DAYS=0
TOP=15
while [[ $# -gt 0 ]]; do
  case "$1" in
    --days) DAYS="${2:-0}"; shift 2 ;;
    --top)  TOP="${2:-15}"; shift 2 ;;
    -h|--help) sed -n '3,9p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) shift ;;
  esac
done

if [[ ! -s "$LOG_FILE" ]]; then
  echo "아직 기록된 스킬 호출이 없습니다."
  echo "로그 위치: $LOG_FILE"
  echo "훅이 등록되어 있는지 /hooks 로 확인해 보세요."
  exit 0
fi

# cutoff 계산 — BSD(macOS) date 를 먼저 시도하고 실패하면 GNU date 로 폴백
if [[ "$DAYS" -gt 0 ]]; then
  CUTOFF="$(date -v-"${DAYS}"d +%F 2>/dev/null || date -d "${DAYS} days ago" +%F)"
  RANGE="최근 ${DAYS}일"
else
  CUTOFF="0000-00-00"
  RANGE="전체 기간"
fi

# -Rs 로 raw slurp 한 뒤 줄 단위로 try/catch 파싱한다.
# 깨진 줄이 한 줄 섞여도 나머지 통계가 통째로 날아가지 않게 하기 위함.
jq -Rr --arg cutoff "$CUTOFF" --argjson top "$TOP" --arg range "$RANGE" -s '
  def rpad($n): tostring | . + ((" " * ($n - length)) // "");
  def lpad($n): tostring | ((" " * ($n - length)) // "") + .;
  def bar($n; $max; $w): ("█" * (((($n * $w) / $max) | floor) | if . < 1 then 1 else . end));

  split("\n")
  | map(select(length > 0) | (try fromjson catch empty))
  | map(select(.ts[0:10] >= $cutoff))
  | if length == 0 then
      "해당 기간(\($range))에 기록된 스킬 호출이 없습니다."
    else
      . as $ev
      | ($ev | length)                                   as $total
      | ($ev | map(.skill)      | unique | length)       as $uniq
      | ($ev | map(.session_id) | unique | length)       as $sessions
      | ($ev | map(.ts[0:10])   | sort)                  as $days
      | ($ev | group_by(.skill)
             | map({skill: .[0].skill, n: length})
             | sort_by(-.n, .skill))                     as $rank
      | ($rank[0].n)                                     as $maxn
      | ($ev | group_by(.ts[0:10])
             | map({d: .[0].ts[0:10], n: length})
             | sort_by(.d) | .[-7:])                     as $trend
      | ($trend | map(.n) | max)                         as $maxd
      | ($rank | map(select(.skill == "skill-stat")) | length > 0) as $selfcounted
      | (($rank[:$top] | map(.skill | length) | max) + 1)          as $w
      | ([
          "📊 스킬 호출 통계  —  \($range)  (\($days[0]) ~ \($days[-1]))",
          "",
          "  총 호출      \($total)회",
          "  고유 스킬    \($uniq)개",
          "  세션 수      \($sessions)개   (세션당 평균 \((($total * 10 / $sessions) | round / 10))회)",
          "",
          "── 스킬별 랭킹 " + ("─" * 46)
        ]
        + ($rank[:$top] | to_entries | map(
            "  \((.key + 1) | lpad(2)). \(.value.skill | rpad($w)) \(.value.n | lpad(4))회  "
            + bar(.value.n; $maxn; 24)
            + "  \(((.value.n * 1000 / $total) | round / 10))%"
          ))
        + (if ($rank | length) > $top
           then ["  … 외 \(($rank | length) - $top)개 스킬"] else [] end)
        + [
          "",
          "── 일별 추이 (최근 \($trend | length)일) " + ("─" * 38)
        ]
        + ($trend | map("  \(.d)  \(.n | lpad(4))회  " + bar(.n; $maxd; 24)))
        + (if $selfcounted
           then ["", "  ※ skill-stat 자신의 호출도 훅에 잡히므로 통계에 포함되어 있습니다."]
           else [] end)
        ) | join("\n")
    end
' "$LOG_FILE"
