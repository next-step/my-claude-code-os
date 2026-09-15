#!/usr/bin/env bash
# SessionEnd 훅 — 세션이 끝날 때 OS 건강도 지표 스냅샷을 이력에 남긴다.
#   - maintenance/requests/REQ-*.md 프론트매터를 스캔해 OS.md §4 성공 기준 지표를 계산한다.
#     · 내부 처리 비율(%) = internal / (internal + outsource)  (classification:undecided 는 제외)
#     · 평균 처리 일수    = 종결 상태(done/handed_off/outsourced) 요청의 (updated - created) 평균
#     · blocked 비율(%)  = status:blocked 요청 수 / 전체 요청 수
#   - 한 줄을 maintenance/os-health/history.tsv 에 append 만 한다 (덮어쓰지 않음 — 이력이 자산이다).
#   - 실패해도 세션 종료를 막지 않는다 (요청 폴더가 없으면 조용히 종료).
set -euo pipefail

root="${CLAUDE_PROJECT_DIR:-$PWD}"
dir="$root/maintenance/requests"
out_dir="$root/maintenance/os-health"
out="$out_dir/history.tsv"

[ -d "$dir" ] || exit 0
mkdir -p "$out_dir"
[ -f "$out" ] || printf '# date\ttotal\tclassified\tinternal_rate_pct\tavg_days\tblocked_rate_pct\n' > "$out"

fm=""
# frontmatter 값 한 줄을 뽑는다 (session-open-requests.sh 와 동일한 방식).
get() {
  printf '%s\n' "$fm" | sed -n "s/^$1:[[:space:]]*//p" | head -1 \
    | sed -e 's/[[:space:]][[:space:]]*#.*$//' -e 's/[[:space:]]*$//'
}

# "%Y-%m-%d" → epoch. GNU date 우선, 실패하면 BSD date(macOS). 둘 다 실패하면 빈 문자열.
to_epoch() {
  date -d "$1" +%s 2>/dev/null || date -j -f "%Y-%m-%d" "$1" +%s 2>/dev/null || echo ""
}

total=0; classified=0; internal=0; blocked=0
day_sum=0; day_n=0

for f in "$dir"/REQ-*.md; do
  [ -e "$f" ] || continue
  fm=$(awk 'NR==1 && $0=="---"{inside=1; next} inside && $0=="---"{exit} inside{print}' "$f")
  status=$(get status); cls=$(get classification)
  created=$(get created); updated=$(get updated)
  total=$((total + 1))

  if [ "$cls" = "internal" ]; then
    classified=$((classified + 1)); internal=$((internal + 1))
  elif [ "$cls" = "outsource" ]; then
    classified=$((classified + 1))
  fi

  if [ "$status" = "blocked" ]; then
    blocked=$((blocked + 1))
  fi

  case "$status" in
    done|handed_off|outsourced)
      c_ep=$(to_epoch "$created"); u_ep=$(to_epoch "$updated")
      if [ -n "$c_ep" ] && [ -n "$u_ep" ] && [ "$u_ep" -ge "$c_ep" ]; then
        d=$(( (u_ep - c_ep) / 86400 ))
        day_sum=$((day_sum + d)); day_n=$((day_n + 1))
      fi
      ;;
  esac
done

pct() {
  if [ "$2" -gt 0 ]; then
    awk -v a="$1" -v b="$2" 'BEGIN{printf "%.0f", (a/b)*100}'
  else
    echo "-"
  fi
}

internal_rate=$(pct "$internal" "$classified")
blocked_rate=$(pct "$blocked" "$total")

avg_days="-"
if [ "$day_n" -gt 0 ]; then
  avg_days=$(awk -v s="$day_sum" -v n="$day_n" 'BEGIN{printf "%.1f", s/n}')
fi

stamp=$(date +"%Y-%m-%dT%H:%M")
printf '%s\t%d\t%d\t%s\t%s\t%s\n' "$stamp" "$total" "$classified" "$internal_rate" "$avg_days" "$blocked_rate" >> "$out"
exit 0
