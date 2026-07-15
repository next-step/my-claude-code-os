#!/usr/bin/env bash
#
# tests/context-budget.sh — L1(예산검증): Eager 컨텍스트가 예산 안에 있는가
#
# inject.sh 와의 역할 분담:
#   inject.sh        = "Eager @import 배선이 존재하고 문서와 현실이 일치하는가" — 배선 무결성
#   context-budget   = "그 Eager 페이로드가 비대해지지 않았는가" — 페이로드 크기 회귀
#
# 왜 필요한가:
#   Eager 정본(CLAUDE.md + @import 대상)은 스킬 실행과 무관하게 **매 세션 항상** 컨텍스트
#   창에 상주한다. 여기 한 줄이 늘면 그 비용을 모든 세션이 영구히 부담한다. "정말 모든
#   상황에서 필요한가?"를 통과하지 못한 내용이 슬그머니 Eager로 승격되는 것을 막는 게이트다.
#   (Lazy 로 내려야 할 것이 Eager 에 눌러앉는 회귀를 조기에 잡는다.)
#
# 무엇을 재나:
#   Eager 대상 = CLAUDE.md 본문 + CLAUDE.md 가 @import 하는 모든 정본 파일.
#   @import 목록을 하드코딩하지 않고 CLAUDE.md 에서 동적으로 읽으므로, Eager import 를
#   새로 추가하면 자동으로 예산 계산에 포함된다.
#
# 예산 (환경변수로 조정 가능):
#   EAGER_MAX_TOKENS (기본 1200) — 근사 토큰(바이트÷3.5, 한국어 혼합 기준). 주 게이트.
#   EAGER_MAX_LINES  (기본 80)   — 줄 수. 보조 게이트(한 줄이 비정상적으로 길어도 잡도록).
#
# 종료 코드: 예산 내 → 0, 초과 → 1
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PASS=0
FAIL=0
ok()   { PASS=$((PASS+1)); printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  \033[31m✗\033[0m %s\n' "$1"; }
skip() { printf '  \033[33m–\033[0m %s (SKIP)\n' "$1"; }

CLAUDE_MD="CLAUDE.md"
EAGER_MAX_TOKENS="${EAGER_MAX_TOKENS:-1200}"
EAGER_MAX_LINES="${EAGER_MAX_LINES:-80}"

echo "── L1: 예산검증 (Eager 컨텍스트 크기) ──────────"

if [[ ! -f "$CLAUDE_MD" ]]; then
  bad "$CLAUDE_MD 이 없음 — Eager 예산을 계산할 수 없음"
  echo "────────────────────────────────────────────────"
  echo "예산검증 결과: ${PASS} pass / ${FAIL} fail"
  exit 1
fi

# ── Eager 대상 파일 목록 구성 ────────────────────────────────
# CLAUDE.md 자신 + CLAUDE.md 가 @import 하는 정본 파일들.
# @import 형식: 줄 맨 앞의 `@<경로>` (inject.sh 와 같은 규칙).
EAGER_FILES=("$CLAUDE_MD")
missing=0
while IFS= read -r imp; do
  [[ -z "$imp" ]] && continue
  if [[ -f "$imp" ]]; then
    EAGER_FILES+=("$imp")
  else
    bad "@import 대상 '$imp' 이 실재하지 않음 (inject.sh 도 함께 볼 것)"
    missing=$((missing+1))
  fi
done < <(grep -oE '^@[^[:space:]]+' "$CLAUDE_MD" | sed 's/^@//')

# ── 파일별 크기 합산 + 내역 출력 ─────────────────────────────
echo "[1] Eager 파일별 크기"
TOTAL_BYTES=0
TOTAL_LINES=0
for f in "${EAGER_FILES[@]}"; do
  b=$(wc -c < "$f" | tr -d ' ')
  l=$(wc -l < "$f" | tr -d ' ')
  TOTAL_BYTES=$((TOTAL_BYTES + b))
  TOTAL_LINES=$((TOTAL_LINES + l))
  printf '      %-40s %5s줄  %6sB\n' "$f" "$l" "$b"
done
APPROX_TOKENS=$((TOTAL_BYTES * 10 / 35))
printf '      %-40s %5s줄  %6sB  (≈%s토큰)\n' "합계" "$TOTAL_LINES" "$TOTAL_BYTES" "$APPROX_TOKENS"

# ── 토큰 예산 (주 게이트) ────────────────────────────────────
echo "[2] 토큰 예산 (≈${APPROX_TOKENS} / 상한 ${EAGER_MAX_TOKENS})"
if [[ "$APPROX_TOKENS" -le "$EAGER_MAX_TOKENS" ]]; then
  ok "Eager 근사 토큰 ${APPROX_TOKENS} ≤ ${EAGER_MAX_TOKENS}"
else
  bad "Eager 근사 토큰 ${APPROX_TOKENS} > ${EAGER_MAX_TOKENS} — 매 세션 상주 비용 초과. Lazy 로 내릴 내용이 없는지, 'Eager 여야만 하는가'를 재심사하라 (EAGER_MAX_TOKENS 로 상한 조정 가능)"
fi

# ── 줄 수 예산 (보조 게이트) ─────────────────────────────────
echo "[3] 줄 수 예산 (${TOTAL_LINES} / 상한 ${EAGER_MAX_LINES})"
if [[ "$TOTAL_LINES" -le "$EAGER_MAX_LINES" ]]; then
  ok "Eager 총 ${TOTAL_LINES}줄 ≤ ${EAGER_MAX_LINES}"
else
  bad "Eager 총 ${TOTAL_LINES}줄 > ${EAGER_MAX_LINES} — 상주 정본이 비대해짐 (EAGER_MAX_LINES 로 상한 조정 가능)"
fi

echo "────────────────────────────────────────────────"
echo "예산검증 결과: ${PASS} pass / ${FAIL} fail"
[[ "$FAIL" -eq 0 ]]
