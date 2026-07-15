#!/usr/bin/env bash
#
# tests/inject.sh — L1(주입검증): 정본 컨텍스트가 "주입 배선"에 실제로 걸려 있는가
#
# lint.sh 와의 역할 분담:
#   lint.sh   = "참조 경로가 실재하는가"(끊어진 링크·문법·JSON) — 파일 무결성
#   inject.sh = "정본이 주입 배선에 걸려 있고, 문서와 현실이 일치하는가" — 배선 무결성
#
# 왜 필요한가 (이 검사만이 잡는 조용한 사고):
#   - Eager: CLAUDE.md 의 @import 한 줄이 사라지면 security 정본이 "매 세션 주입"되던 게
#            에러 없이 멈춘다. 이 레포에서 가장 위험한 회귀.
#   - Lazy:  context-map.md §2 표는 "remind→security"라 적혀 있는데 실제 SKILL.md 에서
#            참조가 빠지면, 지도는 거짓말이 되고 lazy 로드는 안 걸린다.
#   - 정본:  context/*.md 파일은 있는데 아무 주입 경로도 안 걸린 "고아 정본"은 조용히 썩는다.
#
# 검사 항목:
#   1) CLAUDE.md 에 Eager @import 라인이 존재하는가
#   2) 그 @import 가 가리키는 정본 파일이 실재하고 비어있지 않은가 (0바이트=빈 주입도 사고)
#   3) 모든 정본(context/*.md, 메타 문서 제외)이 최소 1개 주입 경로에 도달 가능한가 (고아 없음)
#   4) context-map §2 표의 "소비자→정본" ✅ 엣지 ↔ 실제 md 참조가 양방향 일치하는가 (드리프트).
#      소비자 이름은 하드코딩 대신 실제 파일 존재로 해석하고, 해석 불가한 이름은 건너뛰지 않고
#      실패시킨다(표에 가짜 행을 넣어 검증을 우회하는 것을 막는다). 표 형식이 바뀌어 파서가
#      깨지면 무더기 오탐 대신 "파서가 표를 못 찾음/열 불일치"로 한 번 명확히 실패한다.
#   5) README 정본 목록에서 security.md 가 Eager 로 표기돼 있는가 (문서 정합성)
#
# 알려진 한계(설계상 커버 안 함): Lazy 참조는 텍스트 존재만 확인(모델 Read 여부는 정적 검증 불가),
#   고아 검사는 context/ 최상위만 스캔, 글로벌 CLAUDE.md·settings 상호작용은 범위 밖. (tests/README.md 참고)
#
# 종료 코드: 실패 0건 → 0, 1건 이상 → 1
#
set -uo pipefail

# 레포 루트로 이동 (어디서 호출되든 동일 동작)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PASS=0
FAIL=0
ok()   { PASS=$((PASS+1)); printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  \033[31m✗\033[0m %s\n' "$1"; }
skip() { printf '  \033[33m–\033[0m %s (SKIP)\n' "$1"; }

CLAUDE_MD="CLAUDE.md"
CTX_DIR=".claude/context"
# context-map.md 는 정본이 아니라 정본을 설명하는 도식 문서라 docs/ 로 분리돼 있다
# (정본 *.md 는 CTX_DIR 에 남는다). §4 표의 소비자·정본 경로는 표 안에서 레포 루트
# 기준으로 해석하므로, 맵 파일 위치만 여기서 가리키면 된다.
CONTEXT_MAP="docs/context-map.md"
CONTEXT_README="$CTX_DIR/README.md"

echo "── L1: 주입검증 (정본 배선 무결성) ─────────────"

# ── 1) Eager @import 라인 존재 ─────────────────────────────────
# CLAUDE.md 에 `@.claude/context/security.md` 가 그대로 있어야 매 세션 주입된다.
echo "[1] Eager @import 라인 (CLAUDE.md → security.md)"
EAGER_TARGET="$CTX_DIR/security.md"
EAGER_LINE="@$EAGER_TARGET"
if [[ ! -f "$CLAUDE_MD" ]]; then
  bad "$CLAUDE_MD 이 없음 — Eager 주입 배선을 확인할 수 없음"
elif grep -qF "$EAGER_LINE" "$CLAUDE_MD"; then
  ok "$CLAUDE_MD 에 '$EAGER_LINE' 존재"
else
  bad "$CLAUDE_MD 에 Eager @import('$EAGER_LINE') 없음 — security 정본이 매 세션 주입되지 않음"
fi

# ── 2) Eager @import 타깃 실재 + 비어있지 않음 ────────────────
# @import 는 파일이 없어도 조용히 무시된다 → 존재를 명시적으로 확인.
# 또한 파일이 0바이트면 @import 는 성공해도 실질적으로 "빈 주입"이라 사고다 → 내용도 확인.
echo "[2] Eager 타깃 파일 실재 + 비어있지 않음"
if [[ ! -f "$EAGER_TARGET" ]]; then
  bad "$EAGER_TARGET 없음 — @import 가 조용히 무시됨(빈 주입)"
elif [[ ! -s "$EAGER_TARGET" ]]; then
  bad "$EAGER_TARGET 가 비어 있음 — @import 는 되지만 실질적으로 빈 주입(내용 0바이트)"
else
  ok "$EAGER_TARGET 존재 + 비어있지 않음"
fi

# ── 3) 고아 정본 없음 ──────────────────────────────────────────
# 정본 = context/*.md 에서 메타 문서(README, context-map)를 뺀 것.
# 각 정본은 (a) CLAUDE.md @import 대상이거나, (b) 스킬/에이전트 md 가 참조해야 도달 가능.
echo "[3] 고아 정본 없음 (모든 정본이 주입 경로에 도달 가능)"
orphan=0
canon=0
while IFS= read -r cf; do
  base="$(basename "$cf")"
  # 메타 문서는 정본이 아니라 정본을 설명하는 문서 → 제외
  [[ "$base" == "README.md" || "$base" == "context-map.md" ]] && continue
  canon=$((canon+1))
  rel="$CTX_DIR/$base"
  reachable=0
  # (a) Eager @import 대상?
  grep -qF "@$rel" "$CLAUDE_MD" 2>/dev/null && reachable=1
  # (b) 스킬/에이전트 md 중 하나라도 이 정본을 참조?
  if [[ "$reachable" -eq 0 ]]; then
    grep -rqF "$rel" .claude/skills 2>/dev/null && reachable=1
  fi
  if [[ "$reachable" -eq 1 ]]; then
    ok "$rel — 도달 가능"
  else
    bad "$rel — 고아 정본: 어떤 주입 경로(@import·스킬 참조)에도 안 걸림"
    orphan=$((orphan+1))
  fi
done < <(find "$CTX_DIR" -maxdepth 1 -name '*.md' | sort)
[[ "$canon" -eq 0 ]] && skip "정본 파일을 못 찾음 ($CTX_DIR/*.md)"

# ── 4) 지도(§2 표) ↔ 현실 참조 드리프트 ───────────────────────
# context-map.md §2 "소비자→정본" 표의 ✅ 엣지 집합과, 실제 md 가 참조하는 엣지 집합을
# 양방향 비교한다.
#   - 표에 있는데 실제 없음 → 표가 거짓말(참조가 제거됨)
#   - 실제 있는데 표에 없음 → 문서 안 된 참조(표가 낡음)
echo "[4] context-map §2 표 ↔ 실제 참조 (양방향 드리프트)"
if [[ ! -f "$CONTEXT_MAP" ]]; then
  skip "$CONTEXT_MAP 없음 — 드리프트 검사 불가"
else
  # 소비자 이름 → md 경로 (표의 행 이름을 "실제 파일 존재"로 해석)
  # 하드코딩 화이트리스트를 쓰면, 목록 밖 이름으로 표에 가짜 ✅ 를 넣어도 조용히 건너뛴다
  # (드리프트 검사 우회). 그래서 실제 파일 트리에서 동적으로 해석하고, 해석 불가한 이름은
  # 건너뛰지 않고 §4 에서 큰 소리로 실패시킨다.
  resolve_consumer() {
    local n="$1"
    if   [[ -f ".claude/skills/$n/SKILL.md" ]]; then echo ".claude/skills/$n/SKILL.md"
    elif [[ -f ".claude/skills/_shared/$n.md" ]]; then echo ".claude/skills/_shared/$n.md"
    else echo ""; fi   # 해석 불가 → 호출부에서 실패 처리
  }

  # 실제 md 가 거는 참조를 "소비자<TAB>정본파일" 엣지로 출력
  actual_edges() {
    local line src ref cons
    while IFS= read -r line; do
      src="${line%%:*}"; ref="${line#*:}"
      case "$src" in
        .claude/skills/_shared/*)  cons="$(basename "$src" .md)" ;;
        .claude/skills/*/SKILL.md) cons="$(basename "$(dirname "$src")")" ;;
        *) continue ;;
      esac
      printf '%s\t%s\n' "$cons" "$(basename "$ref")"
    done < <(grep -roE "\.claude/context/[a-z-]+\.md" .claude/skills 2>/dev/null)
  }

  # (가드) 파서가 §2 표 헤더를 실제로 찾았는가.
  # awk 표 파싱은 헤더 텍스트("소비자"+"categories")에 결합돼 있다. 표 형식이 바뀌어 헤더를
  # 못 찾으면 expected 가 비고, 그러면 아래 역방향 검사가 "문서 안 된 참조"를 무더기로 오탐한다.
  # 그런 혼란 대신 "파서가 표를 못 찾음"이라고 한 번 명확히 실패시킨다.
  header_found="$(awk -F'|' '/소비자/ && /categories/ {print "1"; exit}' "$CONTEXT_MAP")"
  if [[ "$header_found" != "1" ]]; then
    bad "§4 파서가 context-map §2 표 헤더('소비자'+'categories' 행)를 못 찾음 — 표 형식이 바뀌었으면 inject.sh 의 awk 파서를 갱신하라"
  else
    # (A) 표에서 기대 엣지 추출: "소비자<TAB>정본파일" (✅ 셀만)
    #     헤더 행(소비자 + categories...)에서 열→정본파일 매핑을 읽고, 데이터 행의 ✅ 를 엣지로.
    expected="$(awk -F'|' '
      /소비자/ && /categories/ {                 # §2 표 헤더 진입
        for (i=3; i<=NF; i++) { h=$i; gsub(/[[:space:]]/,"",h); if (h!="") col[i]=h }
        inhdr=1; next
      }
      inhdr && /^\|[[:space:]:-]+\|/ { started=1; inhdr=0; next }   # |---| 구분선
      started {
        if ($0 !~ /^\|/) { started=0; next }     # 표 끝
        cons=$2; gsub(/[[:space:]]/,"",cons)
        if (cons=="") { started=0; next }
        for (i=3; i<=NF; i++) {
          if (col[i] != "" && index($i,"✅")>0) print cons "\t" col[i] ".md"
        }
      }
    ' "$CONTEXT_MAP" | sort -u)"

    # (B) 실제 엣지 추출: 각 소비자 md 가 참조하는 .claude/context/<file>.md
    #     (case 문을 $() 안에 두면 파서가 오작동하므로 함수로 분리한다)
    actual="$(actual_edges | sort -u)"

    # (가드) 표 열 헤더가 실제 정본 파일명과 일치하는가.
    # 열이 번역·재배치되면 col[i] 가 존재하지 않는 파일명이 된다. 이때도 역방향 오탐 대신
    # "열 헤더가 정본 파일과 불일치"라고 명확히 실패시킨다.
    badcols="$(printf '%s\n' "$expected" | awk -F'\t' 'NF==2{print $2}' | sort -u \
                | while IFS= read -r f; do [[ -n "$f" && -f "$CTX_DIR/$f" ]] || echo "$f"; done)"

    drift=0
    if [[ -n "$badcols" ]]; then
      while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        bad "§2 표 열 헤더가 정본 파일과 불일치: '$f' (표 형식 변경? awk 파서/문서 갱신 필요)"
        drift=$((drift+1))
      done <<< "$badcols"
    else
      # 표에 있는데 실제 없음
      while IFS= read -r e; do
        [[ -z "$e" ]] && continue
        cons="${e%%$'\t'*}"; file="${e#*$'\t'}"
        p="$(resolve_consumer "$cons")"
        if [[ -z "$p" ]]; then
          # 화이트리스트 우회 방지: 해석 불가한 소비자는 건너뛰지 않고 실패시킨다
          bad "§2 표가 참조하는 소비자 '$cons' 를 실제 스킬/에이전트 파일로 해석 불가 (표에 없는 이름·오타이거나 파일 삭제됨)"
          drift=$((drift+1)); continue
        fi
        if ! printf '%s\n' "$actual" | grep -qxF "$e"; then
          bad "표 주장 '$cons → $file' 이 실제 참조에 없음 (지도가 거짓 / 참조 제거됨)"
          drift=$((drift+1))
        fi
      done <<< "$expected"
      # 실제 있는데 표에 없음
      while IFS= read -r a; do
        [[ -z "$a" ]] && continue
        if ! printf '%s\n' "$expected" | grep -qxF "$a"; then
          cons="${a%%$'\t'*}"; file="${a#*$'\t'}"
          bad "실제 참조 '$cons → $file' 이 §2 표에 없음 (문서 안 된 참조 / 표가 낡음)"
          drift=$((drift+1))
        fi
      done <<< "$actual"
    fi
    if [[ "$drift" -eq 0 ]]; then
      n="$(printf '%s\n' "$expected" | grep -c '.')"
      ok "§2 표 엣지 ${n}개가 실제 참조와 양방향 일치"
    fi
  fi
fi

# ── 5) README 정본 목록의 security=Eager 표기 ─────────────────
# security.md 는 "Eager"로 분류돼야 한다. 문서 표에서 이 표기가 지워지면(예: Lazy로 오기재)
# 정본 문서와 실제 배선(§1의 @import)이 어긋난다.
echo "[5] README 정본 목록: security.md = Eager 표기"
if [[ ! -f "$CONTEXT_README" ]]; then
  skip "$CONTEXT_README 없음"
else
  # security.md 를 언급하는 표 행에 'Eager' 가 같이 있는지 (대소문자 무시)
  if grep -i 'security\.md' "$CONTEXT_README" | grep -qi 'Eager'; then
    ok "$CONTEXT_README 에서 security.md 가 Eager 로 표기됨"
  else
    bad "$CONTEXT_README 정본 목록에서 security.md 의 Eager 표기가 없음 (문서↔배선 불일치)"
  fi
fi

echo "────────────────────────────────────────────────"
echo "주입검증 결과: ${PASS} pass / ${FAIL} fail"
[[ "$FAIL" -eq 0 ]]
