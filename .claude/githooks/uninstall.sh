#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# uninstall.sh — git 훅 배선 해제
#
# install.sh 가 설정한 core.hooksPath 를 되돌려 기본(.git/hooks)으로 복귀한다.
# 훅 스크립트 자체(.claude/githooks/*)는 지우지 않는다 — 재설치가 쉽도록.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

git config --unset core.hooksPath 2>/dev/null || true

echo "✓ core.hooksPath 해제 — git 훅이 기본(.git/hooks)으로 복귀했습니다."
echo "  다시 켜려면: bash .claude/githooks/install.sh"
