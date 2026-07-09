#!/usr/bin/env bash
# 컨텍스트 자동 주입 배선 검증 (버그 방지)
#
# @import은 세션 시작 시 런타임에 일어나 조용히 깨지기 쉽다: 경로 오타, 파일 이동,
# import 줄이 코드펜스 안에 들어감, 레지스트리와 CLAUDE.md의 드리프트. 런타임 주입
# 자체는 여기서 못 잡지만, 주입을 일으키는 '배선'이 맞는지는 잡는다 — 실제 버그는
# 거기서 난다. 하나라도 어긋나면 비-0으로 끝나 커밋 전에 걸린다.
#
# 단일 기준은 레지스트리(INDEX.md). CLAUDE.md와 디스크가 레지스트리와 맞는지 본다.
#
# 실행: bash tools/verify-injection.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"   # tools
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"          # repo root
CLAUDE_DIR="$REPO/.claude"
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
INDEX="$CLAUDE_DIR/context/INDEX.md"

fail=0
note() { printf '  %s\n' "$1"; }
bad()  { printf 'FAIL %s\n' "$1"; fail=$((fail + 1)); }
ok()   { printf 'ok   %s\n' "$1"; }

# 전제 파일
for f in "$CLAUDE_MD" "$INDEX"; do
  [ -f "$f" ] || { bad "필수 파일 없음: $f"; }
done
[ "$fail" -eq 0 ] || { echo; echo "결과: 전제 파일 누락으로 중단"; exit 1; }

# 1) CLAUDE.md의 @import 추출 (코드펜스 안은 import로 안 쳐서 제외)
imports="$(awk '
  /^```/      { infence = !infence; next }
  !infence && /^@[^ ]/ { sub(/^@/, ""); print $1 }
' "$CLAUDE_MD")"

echo "[1] @import 경로가 실제 파일로 풀리는가"
if [ -z "$imports" ]; then
  bad "CLAUDE.md에서 @import를 하나도 못 찾음 (코드펜스 안에 들어갔거나 지워짐)"
else
  while IFS= read -r imp; do
    [ -z "$imp" ] && continue
    if [ -f "$CLAUDE_DIR/$imp" ]; then
      ok "@$imp"
    else
      bad "@$imp -> 파일 없음 ($CLAUDE_DIR/$imp)"
    fi
  done <<< "$imports"
fi

# 2) 레지스트리(INDEX)의 '컨텍스트 4분류' 표에 실린 파일 경로 추출
#    해당 섹션(## 컨텍스트 4분류)에서만 .claude/....md 경로를 긁는다.
reg_paths="$(awk '
  /^## / { insec = ($0 ~ /컨텍스트 4분류/) }
  insec  { print }
' "$INDEX" | grep -oE '\.claude/[^`]+\.md' | sort -u)"

echo
echo "[2] 레지스트리가 카탈로그한 컨텍스트가 디스크에 있는가"
if [ -z "$reg_paths" ]; then
  bad "INDEX의 '컨텍스트 4분류' 표에서 파일 경로를 못 찾음 (표 형식이 바뀌었나)"
else
  while IFS= read -r p; do
    [ -z "$p" ] && continue
    if [ -f "$REPO/$p" ]; then
      ok "$p"
    else
      bad "레지스트리에 있으나 파일 없음: $p"
    fi
  done <<< "$reg_paths"
fi

# 3) 레지스트리의 컨텍스트 == CLAUDE.md의 import (양방향 드리프트 검사)
#    레지스트리 경로 .claude/X 를 import 형식 X 로 바꿔 비교.
echo
echo "[3] 레지스트리와 CLAUDE.md 주입이 일치하는가"
while IFS= read -r p; do
  [ -z "$p" ] && continue
  want="${p#.claude/}"
  if grep -qxF "$want" <<< "$imports"; then
    ok "레지스트리 $want <-> CLAUDE.md @$want"
  else
    bad "레지스트리에 있으나 CLAUDE.md가 주입 안 함: $want"
  fi
done <<< "$reg_paths"

# import 쪽에만 있고 레지스트리엔 없는 것도 잡는다 (미등록 주입)
while IFS= read -r imp; do
  [ -z "$imp" ] && continue
  if ! grep -qxF ".claude/$imp" <<< "$reg_paths"; then
    bad "CLAUDE.md가 주입하나 레지스트리에 미등록: @$imp"
  fi
done <<< "$imports"

echo
if [ "$fail" -eq 0 ]; then
  echo "결과: 통과 — 컨텍스트 주입 배선 정상"
  exit 0
else
  echo "결과: 실패 $fail 건 — 위 FAIL 항목을 고칠 것"
  exit 1
fi
