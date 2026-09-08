#!/usr/bin/env bash
# 지정한 GitHub 계정으로 잠시 전환해 명령을 실행하고, 끝나면 반드시 원래 계정으로 되돌린다.
#
# 사용법: with-account.sh <계정> -- <명령...>
# 예:     with-account.sh mj950425 -- git push origin step0
#         with-account.sh mj950425 -- gh pr create --repo ... --base ... --head ...
#
# 설계 노트
# - 복귀는 trap EXIT로 건다. 명령이 실패하든 중간에 끊기든(INT/TERM) 회사 계정으로 돌아온다.
#   복귀를 마지막 줄에 두면 실패 경로에서 개인 계정이 남는다.
# - git 자격증명은 credential.https://github.com.helper = gh auth git-credential 이므로
#   gh 활성 계정을 따라간다. 전환 한 번으로 gh와 git push가 모두 커버된다.
# - 전환/복귀 후 실제로 반영됐는지 확인한다. gh auth switch는 성공을 출력하고도
#   반영되지 않는 경우가 관찰됐다.
# - 명령의 종료코드를 그대로 전파한다. 래퍼가 실패를 삼키면 안 된다.

set -uo pipefail

[ $# -ge 3 ] || { echo "사용법: $(basename "$0") <계정> -- <명령...>" >&2; exit 2; }
target=$1; shift
[ "$1" = "--" ] || { echo "'--' 구분자가 필요합니다." >&2; exit 2; }
shift

command -v gh >/dev/null 2>&1 || { echo "gh CLI가 필요합니다." >&2; exit 1; }

current() { gh api user --jq .login 2>/dev/null; }

original=$(current)
[ -n "$original" ] || { echo "현재 gh 계정을 확인하지 못했습니다. gh auth status 를 확인하세요." >&2; exit 1; }

if [ "$original" = "$target" ]; then
  echo "[유지] 이미 '$target' 계정입니다. 전환 없이 실행합니다."
  "$@"
  exit $?
fi

restore() {
  code=$?
  trap - EXIT INT TERM
  if gh auth switch --user "$original" >/dev/null 2>&1 && [ "$(current)" = "$original" ]; then
    echo "[복귀] gh 계정 → $original"
  else
    echo "[경고] '$original' 로 되돌리지 못했습니다. 현재: '$(current)'" >&2
    echo "        수동 복귀: gh auth switch --user $original" >&2
  fi
  exit $code
}

gh auth switch --user "$target" >/dev/null 2>&1 || {
  echo "'$target' 로 전환하지 못했습니다. 로그인돼 있는지 확인하세요: gh auth status" >&2
  exit 1
}
[ "$(current)" = "$target" ] || {
  echo "전환이 반영되지 않았습니다. 현재: '$(current)', 기대: '$target'" >&2
  gh auth switch --user "$original" >/dev/null 2>&1
  exit 1
}

trap restore EXIT INT TERM
echo "[전환] gh 계정 → $target (작업 후 $original 로 복귀)"

"$@"
