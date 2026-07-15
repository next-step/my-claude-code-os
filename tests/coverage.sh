#!/usr/bin/env bash
#
# tests/coverage.sh — L3 스모크 커버리지 카운터 (랄프 루프의 "측정법")
#
# 우선순위 스킬(plan·done·list)이 tests/smoke*.sh 에서 검증되고 있는지 센다.
# 검증 충실도를 태그로 구분해 지표를 정직하게 표시한다:
#   @covers: <skill>          → 스킬 실제 실행 e2e
#   @covers-contract: <skill> → 스킬의 결정적 계약만 격리 검증(오케스트레이터 미실행)
# (태그는 기계가 읽는 인덱스일 뿐, 실제 검증은 각 케이스의 assert 로직이 한다.)
#
# 출력:  커버 X/3  (e2e: ... · 계약검증: ...)
# 종료 코드: 목표(3/3) 달성 → 0, 미달 → 1  (게이트로도 쓸 수 있게)
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PRIORITY=(plan done list)

# 태그 종류별 수집 (e2e vs 계약검증)
collect() { # $1 = 태그 접두어
  grep -hoE "$1:[[:space:]]*[a-z]+" tests/smoke*.sh 2>/dev/null \
    | sed -E "s/$1:[[:space:]]*//" | sort -u
}
E2E="$(collect '@covers')"          # 주의: @covers-contract 도 함께 잡히므로 아래서 계약분을 뺀다
CONTRACT="$(collect '@covers-contract')"
# @covers 접두 grep 은 @covers-contract 도 매칭하니, e2e 순수분 = E2E - CONTRACT
E2E_ONLY="$(comm -23 <(echo "$E2E") <(echo "$CONTRACT"))"

covered=0; e2e_hits=(); contract_hits=(); missing=()
for s in "${PRIORITY[@]}"; do
  if grep -qx "$s" <<<"$E2E_ONLY"; then
    covered=$((covered+1)); e2e_hits+=("$s")
  elif grep -qx "$s" <<<"$CONTRACT"; then
    covered=$((covered+1)); contract_hits+=("$s")
  else
    missing+=("$s")
  fi
done

total="${#PRIORITY[@]}"
printf '커버 %d/%d  (e2e: %s · 계약검증: %s)\n' \
  "$covered" "$total" \
  "${e2e_hits[*]:-없음}" "${contract_hits[*]:-없음}"
if [[ "${#missing[@]}" -gt 0 ]]; then
  printf '  미커버: %s\n' "${missing[*]}"
fi

[[ "$covered" -eq "$total" ]]
