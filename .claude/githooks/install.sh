#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# install.sh — git 훅 배선 설치
#
# .git/hooks 는 버전 관리가 안 돼 클론 시 훅이 재현되지 않는다. 그래서 훅을
# 추적되는 .claude/githooks 에 두고, git 의 core.hooksPath 를 이 디렉터리로
# 돌린다. 클론한 사람은 이 스크립트 한 번만 실행하면 pre-commit 게이트가 산다.
#
# 되돌리기: bash .claude/githooks/uninstall.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

HOOKS_DIR=".claude/githooks"

# 추적 디렉터리 안의 훅들에 실행 권한 보장 (클론 직후엔 빠질 수 있음).
chmod +x "$HOOKS_DIR"/pre-commit 2>/dev/null || true

git config core.hooksPath "$HOOKS_DIR"

echo "✓ core.hooksPath → $HOOKS_DIR 설정 완료"
echo "  이제 매 커밋에 드리프트 게이트(L1+L2)가 돕니다."
echo "  해제하려면: bash $HOOKS_DIR/uninstall.sh"
