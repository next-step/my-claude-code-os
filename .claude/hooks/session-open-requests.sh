#!/usr/bin/env bash
# SessionStart 훅 — 세션이 열릴 때 "진행 중인 유지보수 요청"을 브리핑한다.
#   - maintenance/requests/REQ-*.md 의 frontmatter를 읽어
#     status 가 done / outsourced / handed_off 가 아닌 것만 요약해 출력한다.
#   - 이 스크립트의 stdout 은 Claude 세션 컨텍스트 맨 앞에 주입되므로 짧게 유지한다.
#   - 실패해도 세션을 막지 않는다 (요청 폴더가 없으면 조용히 종료).
set -eo pipefail

dir="${CLAUDE_PROJECT_DIR:-$PWD}/maintenance/requests"
[ -d "$dir" ] || exit 0

fm=""
get() { printf '%s\n' "$fm" | sed -n "s/^$1:[[:space:]]*//p" | head -1; }

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
  exit 0
fi

echo "[유지보수 OS] 진행 중인 요청 ${count}건 — 세션 브리핑"
printf '%s' "$rows" | sort -t'|' -k1,1 | while IFS='|' read -r prio id status title nxt; do
  [ -n "$id" ] && printf -- '- %-8s %-3s %-12s %s  → %s\n' "$id" "$prio" "$status" "$title" "$nxt"
done
blocked=$(printf '%s' "$rows" | awk -F'|' '$3=="blocked"{n++} END{print n+0}')
[ "$blocked" -gt 0 ] && echo "⚠ blocked ${blocked}건 — 먼저 확인 권장. (/status blocked)"
exit 0
