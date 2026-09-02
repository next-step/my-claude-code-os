#!/usr/bin/env bash
# skill-stat: PreToolUse 훅이 남긴 스킬 호출 데이터를 읽어 통계 리포트를 출력한다.
#
# 입력 파일 (둘 다 훅이 생성/갱신, .gitignore 처리된 로컬 데이터):
#   .claude/skill-usage-stats.json  스킬별 누적 호출 횟수  { "스킬명": 횟수, ... }
#   .claude/skill-usage.log         호출 로그  "YYYY-MM-DD HH:MM:SS<TAB>스킬명" 한 줄에 한 호출
#
# 출력: 사람이 읽는 통계 리포트 (stdout)
#   - stats.json 은 "누가 몇 번" (합계/순위/비중)
#   - log 는 "언제"        (기간/오늘/일자별 추이)
#   log 파일이 없어도 stats.json 만으로 순위까지는 보여준다.

set -uo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
STATS_FILE="$PROJECT_DIR/.claude/skill-usage-stats.json"
LOG_FILE="$PROJECT_DIR/.claude/skill-usage.log"

# ── 0) 준비 확인 ────────────────────────────────────────────────
if ! command -v jq >/dev/null 2>&1; then
  echo "jq 가 필요합니다. (brew install jq)" >&2
  exit 1
fi

if [ ! -f "$STATS_FILE" ] || [ "$(jq -r 'length' "$STATS_FILE" 2>/dev/null || echo 0)" = "0" ]; then
  echo "아직 기록된 스킬 호출이 없습니다."
  echo "스킬을 한 번 사용하면 PreToolUse 훅이 다음 파일에 기록을 시작합니다:"
  echo "  ${STATS_FILE#"$PROJECT_DIR"/}"
  exit 0
fi

# ── 1) stats.json: 합계 / 스킬 수 ──────────────────────────────
total="$(jq -r '[.[]] | add' "$STATS_FILE")"
distinct="$(jq -r 'length' "$STATS_FILE")"

echo "📊 스킬 호출 통계"
echo "출처: ${STATS_FILE#"$PROJECT_DIR"/}"
echo
printf '전체 호출      : %s회\n' "$total"
printf '사용한 스킬 수 : %s개\n' "$distinct"

# ── 2) log: 기록 기간 / 오늘 호출 ─────────────────────────────
if [ -f "$LOG_FILE" ] && [ -s "$LOG_FILE" ]; then
  first="$(head -n1 "$LOG_FILE" | cut -f1)"
  last="$(tail -n1 "$LOG_FILE" | cut -f1)"
  today="$(date '+%Y-%m-%d')"
  today_count="$(grep -c "^${today}" "$LOG_FILE" 2>/dev/null || true)"
  printf '기록 기간      : %s ~ %s\n' "$first" "$last"
  printf '오늘(%s) : %s회\n' "$today" "${today_count:-0}"
fi

# ── 3) 스킬별 순위 + 비중 + 막대 ─────────────────────────────
echo
echo "스킬별 호출 횟수 (많은 순)"
jq -r 'to_entries | sort_by(-.value) | .[] | "\(.key)\t\(.value)"' "$STATS_FILE" \
| awk -F'\t' -v total="$total" '
{
  name = $1; count = $2 + 0;
  pct  = (total > 0) ? count * 100 / total : 0;
  n    = int(pct / 5 + 0.5);            # 막대 1칸 = 5%
  bar  = "";
  for (i = 0; i < n; i++) bar = bar "\xe2\x96\x88";
  printf "  %-18s %4d회  %5.1f%%  %s\n", name, count, pct, bar;
}'

# ── 4) log: 최근 7일 일자별 추이 ─────────────────────────────
if [ -f "$LOG_FILE" ] && [ -s "$LOG_FILE" ]; then
  echo
  echo "일자별 호출 (최근 7일)"
  cut -f1 "$LOG_FILE" | cut -d' ' -f1 | sort | uniq -c | tail -n 7 \
  | awk '{
      c = $1 + 0; d = $2; bar = "";
      for (i = 0; i < c; i++) bar = bar "\xe2\x96\xaa";
      printf "  %s  %3d  %s\n", d, c, bar;
    }'
fi
