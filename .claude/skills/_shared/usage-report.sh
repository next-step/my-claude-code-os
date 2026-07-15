#!/usr/bin/env bash
#
# usage-report.sh — 스킬 사용 로그 분석 (자기 관찰 루프의 read 절반)
#
# 왜 이 스크립트가 있나:
#   PostToolUse(Skill) 훅(log-skill-invocation.sh)이 스킬 호출을
#   .claude/skill-invocations.log 에 "시각 | #N | 스킬명" 으로 쌓는다(=write 절반).
#   이 스크립트는 그 로그를 읽어 사용 패턴을 뽑는다(=read 절반). 둘이 합쳐져야
#   "관찰 → 개선" 루프가 닫힌다.
#
#   /skills·/remind-when 과 같은 철학: 문서가 아니라 정본(로그·파일시스템)을 직접
#   읽고, 입력이 정해지면 출력도 정해지는 결정론적 조회라 LLM 판단이 필요 없다.
#   출력은 완성된 최종 메시지이므로 호출자는 그대로 relay 한다.
#
# 무엇을 뽑나:
#   1) 빈도    — 어떤 스킬을 얼마나 자주 부르나 (많이 쓰는 걸 더 빠르게/별칭)
#   2) 연쇄    — 바로 이어서 부른 쌍 (capture → plan 처럼) — 콤보 스킬 후보
#   3) 유휴    — 등록됐지만 한 번도 안 불린 스킬 — 폐기/점검 후보
#
# 알려진 한계(정직하게 명시):
#   - 로그에 성공/실패 필드가 없어 "실패 반복" 감지는 불가하다. 이걸 하려면 write
#     훅이 tool_response 상태까지 남기도록 스키마를 넓혀야 한다(후속 과제).
#   - 텔레그램 리스너의 claude -p 경로는 별도 세션이라 이 로그에 안 잡힐 수 있다.
#
# 사용법:
#   usage-report.sh
# 환경변수:
#   PAIR_SUGGEST_MIN  이 횟수 이상 반복된 연쇄를 콤보 후보로 제안 (기본 3)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"   # _shared → skills → .claude
# 로그 경로. 기본은 정본이나, 테스트가 SKILL_LOG 로 픽스처 로그를 주입할 수 있게 허용.
LOG="${SKILL_LOG:-$CLAUDE_DIR/skill-invocations.log}"
PAIR_SUGGEST_MIN="${PAIR_SUGGEST_MIN:-3}"

# ── 로그가 없거나 비어 있으면 안내 후 종료 ──────────────────
if [[ ! -s "$LOG" ]]; then
  echo "📊 스킬 사용 리포트"
  echo ""
  echo "  아직 기록된 스킬 호출이 없어요."
  echo "  PostToolUse(Skill) 훅이 켜져 있으면, 스킬을 부를 때마다 자동으로 쌓입니다."
  echo "  (훅 설치 확인: .claude/settings.json 의 PostToolUse matcher \"Skill\")"
  exit 0
fi

# 유효 로그 줄에서 스킬명만 뽑는 공통 필터(3번째 필드, 앞뒤 공백 제거).
skills_stream() {
  awk -F' \\| ' 'NF>=3 { s=$3; gsub(/^[ \t]+|[ \t]+$/,"",s); if (s!="") print s }' "$LOG"
}

total="$(skills_stream | wc -l | tr -d ' ')"
distinct="$(skills_stream | sort -u | wc -l | tr -d ' ')"
first_ts="$(awk -F' \\| ' 'NF>=3{print $1; exit}' "$LOG")"
last_ts="$(awk -F' \\| ' 'NF>=3{ts=$1} END{print ts}' "$LOG")"

echo "📊 스킬 사용 리포트"
echo ""
echo "  집계: 총 ${total}회 호출 · 고유 스킬 ${distinct}종"
echo "  기간: ${first_ts}  →  ${last_ts}"

# 표본이 얕으면 해석 주의를 먼저 알린다(과잉 해석 방지).
if [[ "$total" -lt 10 ]]; then
  echo ""
  echo "  ⚠️ 표본이 적어(${total}회) 아래 패턴은 아직 얕습니다 — 참고용으로만 보세요."
fi

# ── 1) 빈도 순위 ───────────────────────────────────────────
echo ""
echo "① 자주 쓰는 스킬"
skills_stream | sort | uniq -c | sort -rn \
  | awk '{ name=$2; for(i=3;i<=NF;i++) name=name" "$i; printf "  %2d회  /%s\n", $1, name }'

# ── 2) 연쇄(직전 스킬 → 다음 스킬) ─────────────────────────
# 로그 순서상 바로 이어 호출된 서로 다른 쌍을 센다. 같은 스킬 반복은 제외.
pairs="$(skills_stream | awk '
  NF>0 { if (prev!="" && prev!=$0) print prev" → "$0; prev=$0 }
' | sort | uniq -c | sort -rn)"

echo ""
echo "② 이어서 부른 연쇄 (직전 → 다음)"
if [[ -z "$pairs" ]]; then
  echo "  아직 이어진 호출이 없어요."
else
  echo "$pairs" | awk '{ c=$1; $1=""; sub(/^ /,""); printf "  %2d회  %s\n", c, $0 }'
  # 임계 이상 반복된 연쇄 → 콤보 스킬 제안
  echo "$pairs" | awk -v m="$PAIR_SUGGEST_MIN" '
    { c=$1; $1=""; sub(/^ /,""); if (c+0 >= m) print "  💡 "$0" 가 "c"회 반복 — 두 단계를 묶은 콤보 스킬을 고려해보세요." }
  '
fi

# ── 3) 유휴 스킬(등록됐지만 한 번도 안 불림) ────────────────
# 정본 = 파일시스템. user-invocable 스킬 중 로그에 한 번도 안 나온 것을 찾는다.
seen="$(skills_stream | sort -u)"
echo ""
echo "③ 유휴 스킬 (등록됐지만 호출 이력 없음)"
idle_found=0
for f in "$CLAUDE_DIR"/skills/*/SKILL.md; do
  [[ -e "$f" ]] || continue
  name="$(awk -F': *' '/^name:/{print $2; exit}' "$f" | tr -d ' \t\r')"
  inv="$(awk -F': *' '/^user-invocable:/{print $2; exit}' "$f" | tr -d ' \t\r')"
  [[ -n "$name" ]] || continue
  [[ "$inv" == "false" ]] && continue          # 내부 전용 스킬은 제외
  if ! grep -qxF "$name" <<<"$seen"; then
    echo "  • /$name"
    idle_found=1
  fi
done
[[ "$idle_found" -eq 0 ]] && echo "  (없음 — 등록된 스킬이 모두 최소 1회 호출됨)"

echo ""
echo "  ─ 이 리포트는 .claude/skill-invocations.log 를 읽어 생성됩니다(정본 직독)."
