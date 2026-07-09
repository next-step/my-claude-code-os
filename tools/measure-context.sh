#!/usr/bin/env bash
# 컨텍스트 체계 비용 측정 (정량 비교용)
#
# 비용 단위는 문자 수(wc -m)다. 토큰은 세션·모델마다 달라 정확값을 스크립트로 못
# 내지만, 문자 수는 결정적·재현 가능하고 전략 간 상대 비교(%)엔 충분하다. 한국어+
# 마크다운은 대략 문자 2~3개당 토큰 1개꼴이라, 토큰은 아래 문자 수를 그 비율로 나눈
# 근사로 읽으면 된다.
#
# 실행: bash tools/measure-context.sh

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1   # repo root (from tools/)

chars() { wc -m < "$1" | tr -d ' '; }
sum=0
row() { local c; c=$(chars "$1"); sum=$((sum + c)); printf '  %-40s %6s자\n' "$1" "$c"; }

echo "[A] 항상 주입되는 번들 (세션 시작마다 메인 컨텍스트로)"
sum=0
for f in .claude/CLAUDE.md .claude/context/user.md .claude/context/project.md \
         .claude/guides/writing-style.md .claude/guides/work-principles.md; do row "$f"; done
ALWAYS=$sum
printf '  %-40s %6s자  <= 항상 켜진 비용\n' "합계" "$ALWAYS"

echo
echo "[B] 주입 안 되는 것 (레지스트리·도식, 이름으로만 참조)"
sum=0
for f in .claude/context/INDEX.md .claude/context/context-map.md; do row "$f"; done
LAZY=$sum
printf '  %-40s %6s자  <= 필요할 때만\n' "합계" "$LAZY"

echo
echo "[C] 전략 비교 — 무엇을 항상 켜 두나"
NAIVE=$((ALWAYS + LAZY))
printf '  %-32s %6s자\n' "순진(전부 인라인 always-on)" "$NAIVE"
printf '  %-32s %6s자\n' "현재(4개 import + 나머지 lazy)" "$ALWAYS"
printf '  절감: %s자 (%d%%) — 점진적 공개로 항상 켠 비용을 줄임\n' \
  "$((NAIVE - ALWAYS))" "$(( (NAIVE - ALWAYS) * 100 / NAIVE ))"

echo
echo "[D] 단일 출처 이름 참조의 실익 (writing-style 기준)"
WS=$(chars .claude/guides/writing-style.md)
REFS=$(grep -rl "writing-style" .claude/skills .claude/agents | wc -l | tr -d ' ')
printf '  writing-style 원본: %s자, 이를 참조하는 컴포넌트: %s개\n' "$WS" "$REFS"
printf '  복붙 방식이면 중복 사본: %s개 × %s자 = %s자를 별도 유지·동기화\n' \
  "$REFS" "$WS" "$((REFS * WS))"
printf '  현재(이름 참조): 원본 1벌만 유지. 사본 %s벌·드리프트 위험 0\n' "$REFS"
