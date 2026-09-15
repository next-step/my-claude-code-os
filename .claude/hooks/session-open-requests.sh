#!/usr/bin/env bash
# SessionStart 훅 — 세션이 열릴 때 "진행 중인 유지보수 요청"을 브리핑한다.
#   - maintenance/requests/REQ-*.md 의 frontmatter를 읽어
#     status 가 done / outsourced / handed_off 가 아닌 것만 요약해 출력한다.
#   - SessionEnd 훅(os-health-snapshot.sh)이 쌓은 OS 건강도 이력이 있으면
#     최근 스냅샷과 직전 스냅샷을 비교한 추이도 한 줄 덧붙인다.
#   - 이 스크립트의 stdout 은 Claude 세션 컨텍스트 맨 앞에 주입되므로 짧게 유지한다.
#   - 실패해도 세션을 막지 않는다 (요청 폴더가 없으면 조용히 종료).
set -eo pipefail

root="${CLAUDE_PROJECT_DIR:-$PWD}"
dir="$root/maintenance/requests"
[ -d "$dir" ] || exit 0

fm=""
# frontmatter 값 한 줄을 뽑고, YAML 인라인 주석( " #..." )과 양끝 공백을 제거한다.
# (제목에 " #" 두 칸+해시가 들어가는 경우는 드물어 허용 가능한 한계로 둔다.)
get() {
  printf '%s\n' "$fm" | sed -n "s/^$1:[[:space:]]*//p" | head -1 \
    | sed -e 's/[[:space:]][[:space:]]*#.*$//' -e 's/[[:space:]]*$//'
}

rows=""
count=0
for f in "$dir"/REQ-*.md; do
  [ -e "$f" ] || continue
  fm=$(awk 'NR==1 && $0=="---"{inside=1; next} inside && $0=="---"{exit} inside{print}' "$f")
  status=$(get status)
  case "$status" in done|outsourced|handed_off|"") continue ;; esac
  id=$(get id); title=$(get title); cls=$(get classification); prio=$(get priority)
  case "$status" in
    intake)       nxt="/intake 마무리 (분류)" ;;
    classified)   if [ "$cls" = "outsource" ]; then nxt="/outsource $id"; else nxt="/spec $id"; fi ;;
    spec)         nxt="/implement $id" ;;
    implementing) nxt="/verify $id" ;;
    blocked)      nxt="원인 확인 후 /implement $id" ;;
    *)            nxt="/status $id" ;;
  esac
  rows+="${prio:-P?}|${id:-?}|${status}|${title:-(제목 없음)}|${nxt}"$'\n'
  count=$((count + 1))
done

if [ "$count" -eq 0 ]; then
  echo "[유지보수 OS] 진행 중인 요청 없음. 새 요청은 /intake 로 접수하세요."
else
  echo "[유지보수 OS] 진행 중인 요청 ${count}건 — 세션 브리핑"
  printf '%s' "$rows" | sort -t'|' -k1,1 | while IFS='|' read -r prio id status title nxt; do
    [ -n "$id" ] && printf -- '- %-8s %-3s %-12s %s  → %s\n' "$id" "$prio" "$status" "$title" "$nxt"
  done
  blocked=$(printf '%s' "$rows" | awk -F'|' '$3=="blocked"{n++} END{print n+0}')
  [ "$blocked" -gt 0 ] && echo "⚠ blocked ${blocked}건 — 먼저 확인 권장. (/status blocked)"
fi

# --- OS 건강도 추이 (SessionEnd 훅이 쌓은 이력에서 최근·직전 스냅샷을 비교) ---
health="$root/maintenance/os-health/history.tsv"
delta() {
  # "-" (계산 불가) 가 섞이면 델타도 "-"로. 아니면 부호 붙인 정수 차이.
  if [ "$1" = "-" ] || [ "$2" = "-" ]; then
    echo "-"
  else
    awk -v c="$1" -v p="$2" 'BEGIN{d=c-p; if(d>0) printf "+%d", d; else printf "%d", d}'
  fi
}
if [ -f "$health" ]; then
  hrows=$(grep -v '^#' "$health" 2>/dev/null || true)
  hn=$(printf '%s\n' "$hrows" | grep -c . || true)
  if [ "$hn" -ge 1 ]; then
    last=$(printf '%s\n' "$hrows" | tail -1)
    IFS=$'\t' read -r _ l_total _ l_internal l_avgdays l_blocked <<< "$last"
    if [ "$hn" -ge 2 ]; then
      prev=$(printf '%s\n' "$hrows" | tail -2 | head -1)
      IFS=$'\t' read -r _ _ _ p_internal _ p_blocked <<< "$prev"
      d_internal=$(delta "$l_internal" "$p_internal")
      d_blocked=$(delta "$l_blocked" "$p_blocked")
      echo "[OS 건강도] 요청 ${l_total}건 · 내부처리 ${l_internal}%(전 세션 대비 ${d_internal}%p) · 평균처리 ${l_avgdays}일 · blocked ${l_blocked}%(${d_blocked}%p)"
    else
      echo "[OS 건강도] 요청 ${l_total}건 · 내부처리 ${l_internal}% · 평균처리 ${l_avgdays}일 · blocked ${l_blocked}% (첫 스냅샷 — 추이는 다음 세션부터 보임)"
    fi
  fi
fi
exit 0
