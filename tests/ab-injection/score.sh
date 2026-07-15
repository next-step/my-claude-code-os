#!/usr/bin/env bash
#
# score.sh — 컨텍스트 주입 A/B 채점기 (정본 categories.md 주입 有無 대조)
#
# 무엇을 재나 (arm 별):
#   1) 어휘 준수율  — 출력이 정본 6종 {스터디,업무,일상,건강,금융,기타} 안인가
#                     (정본이 없으면 모델이 라벨을 지어냄 → 스키마 위반)
#   2) 정확도(strict) — 출력 == 정답(GT). 지어낸 라벨은 자동 오답.
#   3) 정확도(lenient)— 사람이 사후에 동의어 사전을 만들어 매핑한 뒤 비교.
#                       "정본 없이도 사람이 손보면 맞출 수 있다"의 비용을 드러내는 지표.
#   4) 일관성       — 같은 입력 3회 반복이 모두 같은 답이었나 (12항목 중 만장일치 수).
#   5) 함정 항목    — probe=1(정본만이 해소하는 케이스)의 정확도.
#
# 입력: ground-truth.tsv, raw-runs.tsv (같은 폴더)
# 종료코드: 항상 0 (측정 리포트지 게이트가 아님). 데이터 손상 시 1.
#
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GT="$DIR/ground-truth.tsv"
RAW="$DIR/raw-runs.tsv"
VOCAB="스터디 업무 일상 건강 금융 기타"

[[ -f "$GT" && -f "$RAW" ]] || { echo "데이터 파일 없음"; exit 1; }

# 정본 어휘인가
in_vocab() { case " $VOCAB " in *" $1 "*) return 0;; *) return 1;; esac }

# arm A가 지어낸 라벨 → 정본 카테고리 동의어 매핑(사후 수작업 사전).
# 이 사전이 "필요하다"는 사실 자체가 정본 미주입의 숨은 비용이다.
synonym() {
  case "$1" in
    자격증|공부|학습) echo "스터디" ;;
    생활|취미|사교|여가|약속) echo "일상" ;;
    재정) echo "금융" ;;
    운동) echo "건강" ;;
    반려동물) echo "기타" ;;
    *) echo "$1" ;;   # 이미 정본 어휘거나 매핑 없음
  esac
}

gt_of() { awk -F'\t' -v i="$1" '$1==i{print $3}' "$GT"; }
is_probe() { [ "$(awk -F'\t' -v i="$1" '$1==i{print $4}' "$GT")" = "1" ]; }

score_arm() {
  local arm="$1"
  local total=0 vocab_ok=0 exact=0 lenient=0
  local probe_total=0 probe_ok=0
  # 만장일치 계산용: 항목별 답 수집
  local unanimous=0 items=0

  # 항목 순회 (1..12)
  local i
  for i in $(awk -F'\t' '/^[0-9]/{print $1}' "$GT"); do
    items=$((items+1))
    local gt; gt="$(gt_of "$i")"
    local probe=0; is_probe "$i" && probe=1
    # 이 arm·이 항목의 3회 답
    local answers; answers="$(awk -F'\t' -v a="$arm" -v it="$i" '$1==a && $3==it{print $4}' "$RAW")"
    local first="" same=1 n=0
    local ans
    while IFS= read -r ans; do
      [ -z "$ans" ] && continue
      n=$((n+1)); total=$((total+1))
      in_vocab "$ans" && vocab_ok=$((vocab_ok+1))
      [ "$ans" = "$gt" ] && exact=$((exact+1))
      [ "$(synonym "$ans")" = "$gt" ] && lenient=$((lenient+1))
      if [ "$probe" = "1" ]; then
        probe_total=$((probe_total+1))
        [ "$ans" = "$gt" ] && probe_ok=$((probe_ok+1))
      fi
      if [ -z "$first" ]; then first="$ans"; elif [ "$ans" != "$first" ]; then same=0; fi
    done <<EOF
$answers
EOF
    [ "$same" = "1" ] && [ "$n" -gt 0 ] && unanimous=$((unanimous+1))
  done

  pct() { awk -v n="$1" -v d="$2" 'BEGIN{ if(d==0){print "  n/a"} else printf "%5.1f%%", 100*n/d }'; }
  printf 'Arm %s (%s)\n' "$arm" "$([ "$arm" = A ] && echo '정본 미주입 · 대조' || echo '정본 주입 · 처치')"
  printf '  어휘 준수율     %s  (%d/%d)\n' "$(pct $vocab_ok $total)" "$vocab_ok" "$total"
  printf '  정확도(strict)  %s  (%d/%d)\n' "$(pct $exact $total)"   "$exact"   "$total"
  printf '  정확도(lenient) %s  (%d/%d)  ← 사후 동의어 사전 적용 후\n' "$(pct $lenient $total)" "$lenient" "$total"
  printf '  일관성(만장일치)%s  (%d/%d 항목)\n' "$(pct $unanimous $items)" "$unanimous" "$items"
  printf '  함정 항목 정확도%s  (%d/%d)  ← #6·#11·#12\n' "$(pct $probe_ok $probe_total)" "$probe_ok" "$probe_total"
  echo
}

echo "══════════ 컨텍스트 주입 A/B 채점 (categories.md) ══════════"
echo "입력 12종 × 2 arm × 3회 = 72 관측.  GT=정본 기준 정답."
echo
score_arm A
score_arm B
echo "─────────────────────────────────────────────────────────────"
echo "해석: strict 정확도 격차 = 주입의 순효과. lenient와 strict의 차이(Arm A) ="
echo "      '정본 없이도 사람이 사전을 만들어 손보면 회복되는 양' = 주입이 없애주는 수작업 비용."
