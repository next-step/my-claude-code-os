#!/usr/bin/env bash
#
# capture.sh — /capture 결정론 엔트리 (분류 → 저장 → 완료 노티스). 모델 0.
#
# 왜 이 스크립트가 있나:
#   텔레그램 /capture 는 telegram-listener 의 기본 케이스에서 claude -p(콜드 스타트 ~10s)를
#   탔다. /list 가 list-view.sh 로 claude -p 를 우회하듯, capture 도 이 스크립트로 우회해
#   "입력 → 노티스"를 2초 안에 끝낸다. 세 단계 모두 순수 bash·로컬이라 네트워크 왕복이
#   크리티컬 패스에 없다(저장은 capture-fast.sh 가 백그라운드 동기).
#     1) classify.sh   : 사전 기반 카테고리 분류 (모델 없이)
#     2) capture-fast.sh: 로컬 outbox 즉시 저장 + Notion 백그라운드 동기
#     3) 사람이 읽는 완료 노티스 텍스트 출력 (telegram send_tg / 대화형 양쪽에 그대로 전달)
#
# 사용법:
#   capture.sh "<키워드/문장>"     # 완료 노티스 텍스트를 stdout 으로 출력
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLASSIFY="$SCRIPT_DIR/classify.sh"
CAPTURE_FAST="$SCRIPT_DIR/capture-fast.sh"

input="${1:-}"
# 앞뒤 공백 정리
input="$(printf '%s' "$input" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

if [[ -z "$input" ]]; then
  printf '%s\n' "캡처할 내용을 입력해주세요. 예: /capture 장보기"
  exit 0
fi

# 1) 분류 (결정론)
category="$("$CLASSIFY" "$input")"

# 2) 저장 (즉시 로컬 + 백그라운드 동기). 확인 json 은 참고용으로만 받는다.
"$CAPTURE_FAST" "$input" "$category" >/dev/null

# 3) 완료 노티스 (SKILL.md Step 4 와 동일 포맷)
printf '%s\n' "✅ 캡처 완료!

📝 ${input}
🏷️  카테고리: ${category}
📌 상태: draft (구체화 필요)

/plan 을 실행하면 언제·어떻게 할지 구체화할 수 있어요."
