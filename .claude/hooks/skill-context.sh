#!/usr/bin/env bash
# 스킬·서브에이전트 카탈로그를 컨텍스트로 자동 주입하는 hook.
#
# .claude/skills/*/SKILL.md 와 .claude/agents/*.md 의 frontmatter 를 실시간으로 읽어
# "지금 이 프로젝트에 무엇이 있는지"를 만들어 낸다. 손으로 관리하는 목록이 없으므로
# 스킬을 추가·삭제해도 이 카탈로그는 절대 어긋나지 않는다.
#
# 의존성 없음(jq 불필요). 어떤 경우에도 도구 실행을 막지 않도록 항상 exit 0 한다.
#
# 사용법: skill-context.sh <hookEventName>
#   예) skill-context.sh PreToolUse

set -uo pipefail

EVENT="${1:-PreToolUse}"
ROOT="${CLAUDE_PROJECT_DIR:-.}"

# frontmatter(--- ... ---) 안에서 `key: value` 한 줄을 뽑는다.
# 값에 콜론·따옴표가 들어 있어도 첫 콜론 뒤 전부를 값으로 취한다.
fm_field() {
  sed -n '/^---[[:space:]]*$/,/^---[[:space:]]*$/p' "$2" \
    | sed -n "s/^$1:[[:space:]]*//p" \
    | head -n 1
}

emit_catalog() {
  printf '# 이 프로젝트의 클로드 OS 구성 (자동 생성)\n\n'
  printf '> `.claude/hooks/skill-context.sh` 가 파일 시스템에서 실시간으로 읽어 주입한다.\n'
  printf '> 손으로 고치는 목록이 아니므로 항상 실제와 일치한다.\n\n'

  local n f name desc

  # ── 스킬 ─────────────────────────────────────────────
  n=0
  for f in "$ROOT"/.claude/skills/*/SKILL.md; do
    [ -f "$f" ] && n=$((n + 1))
  done
  printf '## 사용 가능한 스킬 (%d)\n\n' "$n"
  for f in "$ROOT"/.claude/skills/*/SKILL.md; do
    [ -f "$f" ] || continue
    name="$(fm_field name "$f")"
    desc="$(fm_field description "$f")"
    [ -n "$name" ] || continue
    printf -- '- **%s** — %s\n' "$name" "$desc"
  done
  printf '\n'

  # ── 서브에이전트 ─────────────────────────────────────
  n=0
  for f in "$ROOT"/.claude/agents/*.md; do
    [ -f "$f" ] && n=$((n + 1))
  done
  printf '## 공유 서브에이전트 (%d)\n\n' "$n"
  for f in "$ROOT"/.claude/agents/*.md; do
    [ -f "$f" ] || continue
    name="$(fm_field name "$f")"
    desc="$(fm_field description "$f")"
    [ -n "$name" ] || continue
    printf -- '- **%s** — %s\n' "$name" "$desc"
  done
  printf '\n'

  printf '## 어디를 읽을지\n\n'
  printf -- '- 계약·구현 규약 → `OS.md` 12장 (단일 진실 출처)\n'
  printf -- '- 지금 뭘 해야 하나 → `STATUS.md`\n'
  printf -- '- 청사진 변경 이력 → `DECISIONS.md`\n'
}

# 문자열을 JSON string 리터럴 본문으로 이스케이프한다.
#   1) 역슬래시 → \\      2) 따옴표 → \"      3) 탭 → \t
#   4) CR 제거            5) 개행 → \n (마지막 줄 개행은 남기지 않음)
json_escape() {
  sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/\t/\\t/g' -e 's/\r//g' \
    | sed -e ':a' -e 'N' -e '$!ba' -e 's/\n/\\n/g'
}

CONTEXT="$(emit_catalog | json_escape)" || exit 0
[ -n "$CONTEXT" ] || exit 0

printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"%s"}}\n' \
  "$EVENT" "$CONTEXT"

exit 0
