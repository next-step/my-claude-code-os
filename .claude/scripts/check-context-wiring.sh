#!/usr/bin/env bash
# 도전 1 — 컨텍스트 주입 배선 검증 테스트
#
# SSOT = .claude/context/README.md 의 "의존 표".
# 표에 "이 파일은 이런 방식으로 이 소비자에 주입된다" 고 선언돼 있으면,
# 실제 저장소가 그렇게 배선돼 있는지 검사한다.
#
#   - 항상 로드  → CLAUDE.md 에 @import 줄이 있는가
#   - 필요할 때  → 소비자 파일(스킬·에이전트)이 그 파일명을 실제로 언급하는가
#   - 훅        → settings.json 의 PreToolUse 훅이 그 파일을 주입하는 스크립트를 부르는가
#
# 하나라도 깨지면 FAIL 을 세고 exit 1. 죽은 지침(인용 0회)은 WARN.
#
# 사용:
#   bash .claude/scripts/check-context-wiring.sh              # 저장소 배선 검사
#   bash .claude/scripts/check-context-wiring.sh --self-test  # 검사기 자체를 검증
#                                                             # (일부러 배선을 깨서 FAIL 이 나는지 확인)

set -u

# WIRING_ROOT 로 검사 대상 루트를 바꿀 수 있다 (--self-test 가 깨진 임시 복사본을 가리킬 때 사용).
ROOT="${WIRING_ROOT:-}"
[ -n "$ROOT" ] || ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

CTX_DIR="$ROOT/.claude/context"
README="$CTX_DIR/README.md"
CLAUDEMD="$ROOT/CLAUDE.md"
SETTINGS="$ROOT/.claude/settings.json"
REQ_DIR="$ROOT/maintenance/requests"

fail=0
warn=0
checks=0

pass() { checks=$((checks+1)); printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
err()  { checks=$((checks+1)); fail=$((fail+1)); printf '  \033[31mFAIL\033[0m  %s\n' "$1"; }
wrn()  { warn=$((warn+1)); printf '  \033[33mWARN\033[0m  %s\n' "$1"; }

# 소비자 키워드 → 그 소비자를 정의한 파일
consumer_file() {
  case "$1" in
    classifier)           echo "$ROOT/.claude/agents/classifier.md" ;;
    intake-interview)     echo "$ROOT/.claude/agents/intake-interview.md" ;;
    spec-reviewer)        echo "$ROOT/.claude/agents/spec-reviewer.md" ;;
    context-loader)       echo "$ROOT/.claude/agents/context-loader.md" ;;
    intake)               echo "$ROOT/.claude/skills/intake/SKILL.md" ;;
    /spec|spec)           echo "$ROOT/.claude/skills/spec/SKILL.md" ;;
    /interview|interview) echo "$ROOT/.claude/skills/interview/SKILL.md" ;;
    /verify|verify)       echo "$ROOT/.claude/skills/verify/SKILL.md" ;;
    /implement|implement) echo "$ROOT/.claude/skills/implement/SKILL.md" ;;
    *) echo "" ;;
  esac
}

# ─────────────────────────────────────────────────────────────
# 자가 테스트: 검사기가 "진짜로" 배선 고장을 잡는지 확인한다.
# 화재경보기 테스트 버튼 — 일부러 신호를 주고 울리는지 본다.
# 실제 파일은 절대 안 건드린다. 임시 복사본을 만들어 거기서 부수고 검사한 뒤 버린다.
# ─────────────────────────────────────────────────────────────
run_self_test() {
  echo "═══ 자가 테스트 — 검사기가 배선 고장을 실제로 탐지하는가 ═══"
  echo
  local real_root st_fail=0
  real_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

  # 0) 기준선: 진짜 저장소는 통과해야 한다.
  if bash "$SELF" >/dev/null 2>&1; then
    echo "  [기준] 실제 저장소 검사: PASS"
  else
    echo "  [기준] 실제 저장소가 이미 FAIL — 자가 테스트 전에 배선부터 고쳐야 한다."
    return 1
  fi

  _scenario() {
    local desc="$1" breakcmd="$2"
    local tmp; tmp="$(mktemp -d)"
    mkdir -p "$tmp/.claude" "$tmp/maintenance"
    cp "$real_root/CLAUDE.md" "$tmp/" 2>/dev/null || true
    cp "$real_root/.claude/settings.json" "$tmp/.claude/" 2>/dev/null || true
    cp -R "$real_root/.claude/context" "$tmp/.claude/"
    cp -R "$real_root/.claude/agents"  "$tmp/.claude/"
    cp -R "$real_root/.claude/skills"  "$tmp/.claude/"
    cp -R "$real_root/.claude/hooks"   "$tmp/.claude/"
    cp -R "$real_root/maintenance/requests" "$tmp/maintenance/" 2>/dev/null || true

    ( cd "$tmp" && eval "$breakcmd" )   # 임시 복사본에 고장 주입

    local out rc
    out="$(WIRING_ROOT="$tmp" bash "$SELF" 2>&1)"; rc=$?
    if [ "$rc" -ne 0 ] && printf '%s' "$out" | grep -q 'FAIL'; then
      echo "  [OK ] $desc"
      echo "         └ 검사기가 FAIL 로 탐지함"
    else
      echo "  [!! ] $desc"
      echo "         └ 검사기가 못 잡음 — 검사기 결함"
      st_fail=$((st_fail+1))
    fi
    rm -rf "$tmp"
  }

  _scenario "Lazy 배선 끊김: classifier 가 sizing.md 를 더 이상 참조하지 않음" \
    "sed -i.bak '/sizing\\.md/d' .claude/agents/classifier.md && rm -f .claude/agents/classifier.md.bak"

  _scenario "훅 미등록: settings.json 에서 스타일 주입 훅 항목이 사라짐" \
    "grep -v 'inject-style-context' .claude/settings.json > .claude/settings.json.new && mv .claude/settings.json.new .claude/settings.json"

  _scenario "고아 컨텍스트: 의존 표에 없는 .md 가 context/ 에 생김" \
    "printf '# orphan\\n' > .claude/context/__orphan_selftest.md"

  echo
  if [ "$st_fail" -eq 0 ]; then
    echo "자가 테스트 통과: 검사기가 3종 배선 고장을 모두 FAIL 로 잡았다."
    return 0
  else
    echo "자가 테스트 실패: 검사기가 못 잡는 고장 ${st_fail}종. 검사기를 고쳐야 한다."
    return 1
  fi
}

if [ "${1:-}" = "--self-test" ]; then
  run_self_test
  exit $?
fi

# ─────────────────────────────────────────────────────────────
# 본 검사
# ─────────────────────────────────────────────────────────────
[ -f "$README" ] || { echo "의존 표를 찾을 수 없음: $README"; exit 2; }

echo "컨텍스트 배선 검증 — SSOT: .claude/context/README.md 의존 표"
[ -n "${WIRING_ROOT:-}" ] && echo "(대상: $ROOT)"
echo

seen_files=""

# 의존 표: "| [`name`](target) | 성격 | 주기 | 읽는쪽 | 주입방식 |" 형태의 줄만
while IFS= read -r row; do
  case "$row" in
    "| ["*) : ;;
    *) continue ;;
  esac

  name=$(printf '%s\n' "$row"   | sed -n 's/^| \[`\([^`]*\)`.*/\1/p')
  target=$(printf '%s\n' "$row" | sed -n 's/^| \[`[^`]*`\](\([^)]*\)).*/\1/p')
  method_col=$(printf '%s\n' "$row" | awk -F'|' '{print $6}')
  reader_col=$(printf '%s\n' "$row" | awk -F'|' '{print $5}')

  [ -n "$name" ] || continue
  seen_files="$seen_files $name"

  # 1) 표에 적힌 파일이 실제로 존재하는가
  abs="$CTX_DIR/$target"
  if [ -f "$abs" ]; then
    pass "$name — 파일 존재"
  else
    err "$name — 표에 있으나 파일 없음 ($target)"
    continue
  fi

  # 2) 주입 방식별 배선 확인
  case "$method_col" in
    *"항상 로드"*)
      relpath=".claude/context/${target#./}"
      case "$target" in ../../*) relpath="${target#../../}" ;; esac
      if grep -qF "@$relpath" "$CLAUDEMD"; then
        pass "$name — @import 존재 (CLAUDE.md)"
      else
        err "$name — '항상 로드' 인데 CLAUDE.md 에 '@$relpath' 없음"
      fi
      ;;
    *"필요할 때"*)
      hit=0
      needle=$(basename "$name")
      for c in $(printf '%s\n' "$reader_col" | grep -o '`[^`]*`' | tr -d '`' | sed 's/(.*//'); do
        cf=$(consumer_file "$c")
        [ -n "$cf" ] && [ -f "$cf" ] || continue
        if grep -qF "$needle" "$cf"; then
          hit=1
          pass "$name — '$c' 가 참조함 ($(basename "$(dirname "$cf")")/$(basename "$cf"))"
        fi
      done
      [ "$hit" -eq 1 ] || err "$name — '필요할 때' 인데 어떤 소비자도 '$needle' 를 언급하지 않음 (Lazy 주입 끊김)"
      ;;
    *"훅"*)
      if grep -q '"PreToolUse"' "$SETTINGS" && grep -rlF "$name" "$ROOT/.claude/hooks/" >/dev/null 2>&1; then
        hookscript=$(grep -rlF "$name" "$ROOT/.claude/hooks/" | head -1)
        if grep -qF "$(basename "$hookscript")" "$SETTINGS"; then
          [ -x "$hookscript" ] && pass "$name — 훅 스크립트 등록·실행가능 ($(basename "$hookscript"))" \
                               || err "$name — 훅 스크립트가 실행 권한 없음 ($hookscript)"
        else
          err "$name — 훅 스크립트는 있으나 settings.json 에 등록 안 됨 ($(basename "$hookscript"))"
        fi
      else
        err "$name — '훅' 인데 .claude/hooks/ 에 이 파일을 주입하는 스크립트가 없거나 PreToolUse 미설정"
      fi
      ;;
    *)
      wrn "$name — 주입 방식 칸을 해석할 수 없음: '$method_col'"
      ;;
  esac
done < "$README"

echo

# 3) 표에 없는 고아 컨텍스트 파일
for f in "$CTX_DIR"/*.md; do
  b=$(basename "$f")
  [ "$b" = "README.md" ] && continue
  case " $seen_files " in
    *" $b "*) : ;;
    *) err "$b — .claude/context/ 에 있으나 의존 표에 행이 없음 (배선 미선언)" ;;
  esac
done

# 4) 죽은 지침 — classification-policy §N 이 케이스 파일에서 한 번도 인용 안 됨 (WARN)
if [ -d "$REQ_DIR" ] && ls "$REQ_DIR"/REQ-*.md >/dev/null 2>&1; then
  any=$(grep -rho 'classification-policy\.md §[0-9]' "$REQ_DIR" 2>/dev/null | head -1)
  if [ -z "$any" ]; then
    wrn "classification-policy.md §0~§5 — 케이스 파일에 §N 인용이 하나도 없음 (REQ-001 은 인용 규칙 도입 전 케이스)"
  else
    cited=$(grep -rho 'classification-policy\.md §[0-9]' "$REQ_DIR" 2>/dev/null | grep -o '§[0-9]' | sort -u)
    for s in "§0" "§1" "§2" "§3" "§4" "§5"; do
      case "$cited" in
        *"$s"*) : ;;
        *) wrn "classification-policy.md $s — 인용 0회 (죽은 지침 가능성)" ;;
      esac
    done
  fi
fi

echo
echo "검사 ${checks}건 · FAIL ${fail} · WARN ${warn}"
[ "$fail" -eq 0 ] && { echo "배선 정상."; exit 0; } || { echo "배선 문제 발견."; exit 1; }
