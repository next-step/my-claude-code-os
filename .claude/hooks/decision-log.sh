#!/usr/bin/env bash
# 기획 결정 변경 로그용 PostToolUse(Edit|Write) hook.
#
# OS.md(서비스 단일 진실 출처)가 수정될 때마다 DECISIONS.md 에
#   - <시각> · OS.md 「12.6 정렬·필터 규약」 Edit (+3/-1)
# 형태로 한 줄을 append 한다.
#
# ── 왜 이렇게 만들었나 ────────────────────────────────────────
# 1) jq 를 쓰지 않는다. 이 환경엔 jq 가 없다(이전 버전은 jq 로 payload 를 파싱하다
#    조용히 exit 0 하며 아무것도 기록하지 않았다). payload 에서 "file_path" 는 정확히
#    한 번만 등장하므로(tool_response 는 camelCase "filePath") sed 로 안전하게 뽑는다.
#
# 2) 어느 절이 바뀌었는지를 payload 가 아니라 "스냅샷 비교"로 알아낸다.
#    .claude/.os-snapshot.md 에 직전 OS.md 를 보관해 두고, 편집 직후의 OS.md 와 diff 해
#    바뀐 줄 번호를 얻은 뒤, 그 줄 위쪽의 가장 가까운 제목(#~####)을 절 이름으로 삼는다.
#    tool_response.structuredPatch 를 파싱하는 것보다 형식 변화에 강하고,
#    Edit·Write 어느 도구로 바뀌든 똑같이 동작한다.
#
# 3) 조용히 실패하지 않는다. 경로를 못 읽는 등 비정상 종료는 .claude/decision-log.err 에
#    흔적을 남긴다. (이전 버전이 몇 달간 죽은 줄 몰랐던 이유가 바로 조용한 실패였다)
#
# 한계: "왜" 바꿨는지는 payload 에 없다. 그 의도는 OS.md 본문과 커밋 메시지가 보관한다.
#       이 로그는 "언제 · 어디가" 바뀌었나까지만 책임진다.
#       사람이 에디터로 직접 OS.md 를 고치면 스냅샷이 갱신되지 않으므로,
#       그 변경분은 다음 훅 실행 때 함께 묶여 보고된다.
#
# 어떤 경우에도 도구 실행 결과에 영향을 주지 않도록 항상 exit 0 한다.

set -uo pipefail

payload="$(cat 2>/dev/null)" || exit 0

# ── payload → OS.md 경로 ─────────────────────────────────────
# "file_path":"C:\\Users\\...\\OS.md"  →  C:/Users/.../OS.md
fpath="$(printf '%s' "$payload" | tr -d '\n\r' \
  | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
  | sed -e 's/\\\\/\\/g' | tr '\\' '/')"

# 편집 도구 이름(로그용). 못 읽어도 치명적이지 않다.
tool="$(printf '%s' "$payload" | tr -d '\n\r' \
  | sed -n 's/.*"tool_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"

# 경로가 없으면: payload 자체가 없었으면 그냥 종료, 있었는데 못 읽었으면 흔적을 남긴다.
if [ -z "$fpath" ]; then
  if [ -n "$payload" ]; then
    err="${CLAUDE_PROJECT_DIR:-.}/.claude/decision-log.err"
    printf '%s · file_path 파싱 실패 (payload %d bytes)\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${#payload}" >> "$err" 2>/dev/null
  fi
  exit 0
fi

# OS.md 수정일 때만 기록 (다른 파일 편집은 무시)
case "${fpath##*/}" in
  OS.md) ;;
  *) exit 0 ;;
esac

[ -f "$fpath" ] || exit 0

root="$(dirname "$fpath")"
log="$root/DECISIONS.md"
snap="$root/.claude/.os-snapshot.md"

# ── 헤더가 없으면 한 번 생성 ─────────────────────────────────
if [ ! -f "$log" ]; then
  {
    printf '# 결정 변경 로그 (DECISIONS.md)\n\n'
    printf '> OS.md(청사진)가 수정될 때마다 decision-log hook 이 자동으로 한 줄씩 남긴다.\n'
    printf '> "왜" 바꿨는지는 OS.md 본문과 커밋 메시지를 참조한다.\n\n'
  } > "$log"
fi

now="$(date -u +%Y-%m-%dT%H:%MZ)"

# ── 스냅샷이 없으면(최초 1회) 기준점만 만들고 끝낸다 ─────────
if [ ! -f "$snap" ]; then
  cp "$fpath" "$snap" 2>/dev/null
  printf -- '- %s · OS.md 기준 스냅샷 생성 (다음 변경부터 절 단위로 기록)\n' "$now" >> "$log"
  exit 0
fi

# ── 바뀐 줄 번호 뽑기 ────────────────────────────────────────
# [주의] 이 저장소의 .md 는 CRLF 다. 어떤 도구가 LF 로 저장하면 --strip-trailing-cr 없이는
#        "전 줄이 바뀌었다"고 오탐한다(실측: +315/-315). 그래서 항상 붙인다.
DIFF_OPTS="--strip-trailing-cr"

# 새 파일 기준으로 추가·수정된 줄 번호. (순수 삭제만 있으면 비어 있다)
new_lines="$(diff $DIFF_OPTS --unchanged-line-format='' --old-line-format='' \
  --new-line-format='%dn ' "$snap" "$fpath" 2>/dev/null)" || true

added="$(printf '%s' "$new_lines" | wc -w | tr -d ' ')"
removed="$(diff $DIFF_OPTS --unchanged-line-format='' --old-line-format='x' \
  --new-line-format='' "$snap" "$fpath" 2>/dev/null | wc -c | tr -d ' ')" || true

# 내용이 실제로 안 바뀌었으면 기록하지 않는다 (같은 내용 재저장 등)
if [ "$added" -eq 0 ] && [ "${removed:-0}" -eq 0 ]; then
  exit 0
fi

# 순수 삭제뿐이면 옛 파일(스냅샷) 기준 줄 번호로 절을 찾는다.
target="$fpath"
if [ "$added" -eq 0 ]; then
  new_lines="$(diff $DIFF_OPTS --unchanged-line-format='' --new-line-format='' \
    --old-line-format='%dn ' "$snap" "$fpath" 2>/dev/null)" || true
  target="$snap"
fi

# ── 줄 번호 → 그 위의 가장 가까운 제목 ───────────────────────
section_of() {
  # $1 = 줄 번호, $2 = 파일
  head -n "$1" "$2" 2>/dev/null \
    | grep '^#\{1,4\}[[:space:]]' \
    | tail -n 1 \
    | sed -e 's/^#\{1,4\}[[:space:]]*//' -e 's/[[:space:]]*$//'
}

sections=""
for ln in $new_lines; do
  s="$(section_of "$ln" "$target")"
  [ -n "$s" ] || s="(문서 앞머리)"
  sections="$sections$s
"
done

# 중복 제거(등장 순서 유지), 최대 3개까지만 적고 나머지는 "외 N개"
uniq_sections="$(printf '%s' "$sections" | grep -v '^$' | awk '!seen[$0]++')"
total="$(printf '%s\n' "$uniq_sections" | grep -c . )"

label="$(printf '%s\n' "$uniq_sections" | head -n 3 \
  | sed 's/^/「/; s/$/」/' | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
if [ "$total" -gt 3 ]; then
  label="$label 외 $((total - 3))개"
fi
[ -n "$label" ] || label="(절 미상)"

printf -- '- %s · OS.md %s %s (+%s/-%s)\n' \
  "$now" "$label" "${tool:-Edit}" "$added" "${removed:-0}" >> "$log"

# 다음 비교를 위해 스냅샷 갱신
cp "$fpath" "$snap" 2>/dev/null

exit 0
