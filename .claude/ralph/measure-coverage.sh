#!/usr/bin/env bash
# 랄프 루프의 "지표(metric)" — 테스트 커버리지 %를 stdout으로 딱 하나 뱉는다.
#
# 계약(measurement contract):
#   - 성공: 커버리지 백분율 한 줄만 stdout에 출력하고 exit 0  (예: "96.09")
#   - 실패(테스트 깨짐/빌드 실패): stderr에 사유, exit 1        (루프가 "회귀"로 감지)
# 이 "명령 하나 → 숫자 하나 → 객관적 종료 판정" 이 green-gate의 핵심이다.
#
# 사용법:  measure-coverage.sh [line|instruction|branch]   (기본: line)
set -euo pipefail
cd "$(dirname "$0")/../.."   # 저장소 루트로 이동

METRIC="${1:-line}"
CSV="build/reports/jacoco/test/jacocoTestReport.csv"

# 1) 측정: 테스트 실행 + JaCoCo 리포트 생성. 테스트가 하나라도 깨지면 여기서 exit 1.
if ! ./gradlew test jacocoTestReport -q >/tmp/ralph-gradle.log 2>&1; then
  echo "measure-coverage: 테스트/빌드 실패 — 회귀로 간주한다. 로그: /tmp/ralph-gradle.log" >&2
  exit 1
fi

if [[ ! -f "$CSV" ]]; then
  echo "measure-coverage: CSV 리포트를 찾지 못했다 ($CSV)" >&2
  exit 1
fi

# 2) 파싱: 선택한 지표의 covered/(covered+missed) 백분율. (JaCoCo CSV 컬럼 4~9)
#    INSTRUCTION_MISSED=4 COVERED=5 / BRANCH_MISSED=6 COVERED=7 / LINE_MISSED=8 COVERED=9
awk -F, -v m="$METRIC" '
  NR>1 {
    if (m=="instruction") { miss+=$4; cov+=$5 }
    else if (m=="branch") { miss+=$6; cov+=$7 }
    else                  { miss+=$8; cov+=$9 }   # 기본 line
  }
  END {
    total = cov + miss
    if (total == 0) { print "0.00"; exit }
    printf "%.2f\n", 100*cov/total
  }
' "$CSV"
