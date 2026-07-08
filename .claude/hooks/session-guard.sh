#!/usr/bin/env bash
# session-guard (신규, 헌법 지원): 매 세션 시작 시 OS.md 준수를 유도한다.
# SessionStart 에서 OS.md 존재를 확인하고 현재 파이프라인 phase 를 컨텍스트로 주입.
#
# stdout 은 세션 컨텍스트로 Claude 에게 전달된다 (SessionStart 훅 규약).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PHASE_FILE="$ROOT/.claude/phase"

if [[ ! -f "$ROOT/OS.md" ]]; then
  echo "[session-guard] 경고: OS.md 를 찾을 수 없습니다. 이 프로젝트는 OS.md 청사진을 전제로 동작합니다." >&2
  exit 0
fi

phase=""
[[ -f "$PHASE_FILE" ]] && phase="$(tr -d '[:space:]' < "$PHASE_FILE")"
[[ -n "$phase" ]] || phase="(없음 — 파이프라인 비활성)"

cat <<EOF
[session-guard] 이 프로젝트는 OS.md 청사진(SDD+TDD 3단계 파이프라인)을 따릅니다.
- 세션 시작 시 OS.md 를 읽고 헌법 H1~H6 을 준수하세요.
- 현재 파이프라인 단계(.claude/phase): $phase
- 파이프라인 진입: /m-brainstorm → /m-spec → /m-plan → /m-build, 회고: /m-retrospect, 현황: /m-status
EOF
exit 0
