#!/usr/bin/env bash
#
# run-tests.sh — Claude OS 동작 테스트 러너
#
# 사용법:
#   ./run-tests.sh            # 전체 (L1 → L2 → L3)
#   ./run-tests.sh l1 l2      # 결정적 계층만 (CI 가 쓰는 조합)
#   ./run-tests.sh l3         # 통합 스모크만
#
# 계층:
#   L1 (lint)  정적 검증     — frontmatter·링크 무결성·문법·JSON  (빠름, 외부 의존 없음)
#              + 주입검증    — 정본 컨텍스트 주입 배선 무결성(inject.sh) (빠름, 결정적)
#              + 예산검증    — Eager 컨텍스트 크기 회귀(context-budget.sh) (빠름, 결정적)
#   L2 (unit)  훅 단위       — detect-todo.js stdin/stdout        (빠름, 결정적)
#   L3 (smoke) headless 통합 — claude -p "/capture" → Notion 확인 (느림, 자격증명 필요)
#
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# 인자 없으면 전체
LAYERS=("$@")
[[ ${#LAYERS[@]} -eq 0 ]] && LAYERS=(l1 l2 l3)

declare -a RESULTS
RC=0

run_layer() {
  case "$1" in
    l1) bash tests/lint.sh; local r=$?
        bash tests/inject.sh; local ri=$?
        bash tests/context-budget.sh; local rb=$?
        [[ $r -eq 0 && $ri -ne 0 ]] && r=$ri
        [[ $r -eq 0 && $rb -ne 0 ]] && r=$rb ;;
    l2) node tests/unit.test.js;   local r=$?
        bash tests/unit-scripts.sh; local r2=$?
        [[ $r -eq 0 && $r2 -ne 0 ]] && r=$r2 ;;
    l3) bash tests/smoke.sh;       local r=$? ;;
    *)  echo "알 수 없는 계층: $1 (l1|l2|l3)"; return 0 ;;
  esac
  if [[ $r -eq 0 ]]; then RESULTS+=("$1: PASS"); else RESULTS+=("$1: FAIL"); RC=1; fi
  echo
}

echo "╔══════════════════════════════════════════════╗"
echo "║   Claude OS 테스트 러너                        ║"
echo "╚══════════════════════════════════════════════╝"
echo

for L in "${LAYERS[@]}"; do run_layer "$L"; done

echo "════════════════ 요약 ════════════════"
for r in "${RESULTS[@]}"; do
  if [[ "$r" == *PASS* ]]; then printf '  \033[32m%s\033[0m\n' "$r"
  else                          printf '  \033[31m%s\033[0m\n' "$r"; fi
done
echo "══════════════════════════════════════"
exit "$RC"
