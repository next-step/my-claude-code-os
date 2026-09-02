#!/usr/bin/env bash
# 미션 제출 전 사전 점검.
# 저장소 구조와 GitHub 계정 정합성을 검사해 push/PR 실패를 미리 잡는다.
# 종료코드: 0 = 제출 가능(경고는 있을 수 있음), 1 = 차단

set -uo pipefail

fail=0; warn=0
ok()   { printf '  [OK]   %s\n' "$*"; }
bad()  { printf '  [FAIL] %s\n' "$*"; fail=1; }
note() { printf '  [WARN] %s\n' "$*"; warn=1; }

command -v gh >/dev/null 2>&1 || { echo "gh CLI가 필요합니다."; exit 1; }

origin_url=$(git remote get-url origin 2>/dev/null) || { echo "origin 원격이 없습니다."; exit 1; }
slug=$(printf '%s' "$origin_url" | sed -E 's#^(https://github\.com/|git@github\.com:)##; s#\.git$##')
owner=${slug%%/*}
branch=$(git rev-parse --abbrev-ref HEAD)

echo "저장소   : $slug"
echo "현재 브랜치: $branch"
echo

echo "[1] fork 구조"
parent=$(gh api "repos/$slug" --jq '.parent.full_name // empty' 2>/dev/null)
if [ -n "$parent" ]; then
  ok "부모 레포: $parent"
else
  bad "origin이 fork가 아니거나 부모를 찾을 수 없습니다 ($slug)"
fi

echo "[2] GitHub 계정 정합성"
active=$(gh api user --jq '.login' 2>/dev/null)
if [ "$active" = "$owner" ]; then
  ok "gh 활성 계정 = $active (fork 소유자와 일치)"
else
  note "gh 활성 계정이 '${active:-불명}' 입니다. fork 소유자는 '$owner' 입니다."
  note "해결: scripts/with-account.sh $owner -- <명령>   (작업 후 원래 계정으로 자동 복귀)"
fi

cred=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill 2>/dev/null | sed -n 's/^username=//p')
if [ "$cred" = "$owner" ]; then
  ok "git 자격증명 = $cred"
else
  note "git 자격증명이 '${cred:-없음}' 입니다. push가 403으로 실패할 수 있습니다."
fi

echo "[3] 제출 대상 base 브랜치"
if [ -n "$parent" ]; then
  if gh api "repos/$parent/branches/$owner" --jq '.name' >/dev/null 2>&1; then
    ok "base 존재: $parent:$owner"
  else
    bad "$parent 에 '$owner' 브랜치가 없습니다. 강사에게 생성을 요청하세요."
  fi
fi

echo "[4] 제출할 변경"
if [ -n "$parent" ]; then
  if git fetch -q "https://github.com/$parent.git" "$owner" 2>/dev/null; then
    base_sha=$(git rev-parse FETCH_HEAD 2>/dev/null)
    n=$(git rev-list --count "$base_sha..$branch" 2>/dev/null || echo 0)
    if [ "${n:-0}" -gt 0 ]; then
      ok "base 대비 커밋 ${n}개"
      git log --oneline "$base_sha..$branch" | sed 's/^/         /'
    else
      bad "base 대비 새 커밋이 없습니다. 제출할 내용이 없습니다."
    fi
  else
    note "base 브랜치를 fetch하지 못해 차이를 계산하지 못했습니다."
  fi
fi

echo "[5] 작업 트리"
if [ -z "$(git status --porcelain)" ]; then
  ok "커밋되지 않은 변경 없음"
else
  note "커밋되지 않은 변경이 있습니다 (untracked 포함):"
  git status --short | sed 's/^/         /'
fi

echo "[6] 기존 PR"
if [ -n "$parent" ]; then
  existing=$(gh api "repos/$parent/pulls?head=$owner:$branch&state=open" --jq '.[0].number // empty' 2>/dev/null)
  if [ -n "$existing" ]; then
    note "이미 열린 PR #$existing 이 있습니다. 새로 만들지 말고 push로 갱신하세요."
  else
    ok "열린 PR 없음 (신규 생성)"
  fi
fi

echo
if [ "$fail" -ne 0 ]; then
  echo "=> 차단: [FAIL] 항목을 해결해야 제출할 수 있습니다."
  exit 1
fi
[ "$warn" -ne 0 ] && echo "=> 주의: [WARN] 항목을 확인하세요."
echo "=> 제출 가능"
exit 0
