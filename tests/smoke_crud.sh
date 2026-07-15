#!/usr/bin/env bash
#
# tests/smoke_crud.sh — L3: plan·done·list 통합 스모크 (capture 는 smoke.sh 담당)
#
# "진짜로 상태가 바뀌나?"를 확인한다. 각 케이스는 고유 제목으로 항목을 직접 seed 한 뒤,
# 해당 스킬의 실동작(또는 그 스킬이 문서화한 결정적 계약)을 실행하고, Notion DB 의
# 상태 변화를 검증한 다음, 만든 테스트 항목을 반드시 아카이브해 DB 오염을 막는다.
#
# 커버리지 카운터(tests/coverage.sh)가 각 케이스에 달린 태그로 어떤 스킬이 검증되는지 센다.
# 정직성을 위해 검증 충실도를 태그로 구분한다 (태그의 단일 출처는 각 케이스 헤더):
#   @covers: <skill>          → 스킬을 실제로 실행하는 e2e 검증
#   @covers-contract: <skill> → 스킬이 문서화한 결정적 계약만 격리 검증(오케스트레이터 미실행)
#
# smoke.sh 와 동일하게, 자격증명·도구가 없으면 깔끔하게 SKIP 한다 (실패 아님):
#   - claude CLI 없음 / jq 없음 / notion.json 없음 → SKIP
#
# 종료 코드: 통과/스킵 → 0, 검증 실패 → 1
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$1"; }
skip() { printf '  \033[33m–\033[0m %s\n' "$1"; echo "L3(crud) 결과: SKIP"; exit 0; }

echo "── L3: plan·done·list 통합 스모크 ──────────────"

# ── 가드: 필요한 도구·자격증명 확인 (smoke.sh 와 동일 정책) ──────
command -v claude >/dev/null 2>&1 || skip "claude CLI 없음 → SKIP"
command -v jq     >/dev/null 2>&1 || skip "jq 없음 → SKIP"
NOTION_JSON=".claude/data/notion.json"
[[ -f "$NOTION_JSON" ]] || skip "notion.json 없음 (비밀값 부재) → SKIP"

TOKEN="$(jq -r '.token' "$NOTION_JSON")"
NOTION_VERSION="2022-06-28"
NOTION_SH=".claude/skills/_shared/notion.sh"
LIST_VIEW=".claude/skills/_shared/list-view.sh"
CACHE_SH=".claude/skills/_shared/cache.sh"

# 고유 접미사: 같은 DB 를 공유하는 실제 항목이나 병렬 실행과 절대 충돌하지 않도록.
U="$(date +%s)-$$"

FAIL=0
CREATED_IDS=()   # 만든 항목 id (종료 시 전부 아카이브)

# ── 공통 헬퍼 ──────────────────────────────────────────────────
# seed_draft <title> <category> → 생성된 항목 id 를 stdout 으로
seed_draft() {
  # jq -n --arg 로 안전 조립 (title/category 에 " \ 개행이 들어와도 JSON 안 깨짐)
  jq -n --arg t "$1" --arg c "$2" --arg d "$(date +%F)" \
    '{title:$t, category:$c, status:"draft", captured_at:$d}' \
    | "$NOTION_SH" write | jq -r '.id'
}

# status_of <id> → 그 항목의 현재 status (Notion 원본 기준)
status_of() { "$NOTION_SH" read | jq -r --arg i "$1" '.[]|select(.id==$i)|.status'; }

# wait_status <id> <target> <timeout_s> → Notion status 가 target 이 될 때까지 폴링(최대 timeout)
# 왜 필요한가: done 은 이제 완료를 캐시/오버레이에 즉시 반영하고 Notion 반영은 백그라운드
# (detached)로 던진다(응답 1초 미만 목적). 그래서 Notion 원본은 "곧" done 이 되지만
# 호출 직후엔 아직 아닐 수 있다. 동기 왕복을 가정한 즉시 검증 대신, 최종 일관성 계약에 맞게
# 백그라운드 write 가 착할 때까지 짧게 폴링해 "결국 done 이 되는가"를 검증한다.
wait_status() {
  local id="$1" target="$2" timeout="$3" i
  for ((i=0; i<timeout*2; i++)); do
    [[ "$(status_of "$id")" == "$target" ]] && return 0
    sleep 0.5
  done
  return 1
}

# field_of <id> <field> → 그 항목의 임의 필드 값
field_of() { "$NOTION_SH" read | jq -r --arg i "$1" --arg f "$2" '.[]|select(.id==$i)|.[$f]'; }

# archive <id> → Notion 페이지 아카이브(archived:true), 성공 시 "true"
archive() {
  curl -s -X PATCH "https://api.notion.com/v1/pages/$1" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Notion-Version: $NOTION_VERSION" \
    -H "Content-Type: application/json" \
    -d '{"archived": true}' | jq -r '.archived // false'
}

# 종료 시(성공·실패·중단 무관) 만든 항목을 전부 정리한다.
cleanup() {
  local id
  # bash 3.2 + set -u 에서 빈 배열 전개가 터지지 않도록 방어
  for id in ${CREATED_IDS[@]+"${CREATED_IDS[@]}"}; do
    [[ -n "$id" && "$id" != "null" ]] || continue
    if [[ "$(archive "$id")" == "true" ]]; then
      ok "정리(아카이브) 완료: ${id:0:8}…"
    else
      bad "정리 실패 — Notion 에서 id=$id 수동 삭제 필요"
    fi
  done
}
trap cleanup EXIT

# ══════════════════════════════════════════════════════════════
# @covers: list — /list 의 실제 엔진(list-view.sh)이 seed 한 draft 를 표시하는가
#
# 캐시 계약 주의: list-view.sh 는 이제 Notion 을 매번 직접 읽지 않고 로컬 read-model
# (cache.sh)을 읽는다(응답 1초 미만 목적). 이 테스트의 seed 는 notion.sh write 로 DB 에
# "직접" 꽂는 out-of-band 변경이라(정상 사용자 경로인 capture→outbox 를 우회) 캐시에 아직
# 없다. 그래서 seed 직후 read-model 을 동기화(cache.sh refresh)한 뒤 검증한다.
# (정상 /capture 는 outbox 오버레이로 즉시 보이므로 이 refresh 가 필요 없다.)
# ══════════════════════════════════════════════════════════════
echo "  [list] 조회·표시 검증"
L_TITLE="스모크리스트_$U"
L_ID="$(seed_draft "$L_TITLE" 생활)"
if [[ -z "$L_ID" || "$L_ID" == "null" ]]; then
  bad "list: seed 실패 (notion.sh write)"; FAIL=1
else
  CREATED_IDS+=("$L_ID")
  "$CACHE_SH" refresh >/dev/null 2>&1   # out-of-band seed 를 read-model 에 반영
  # /list 스킬은 인자를 그대로 list-view.sh 에 넘긴다 → 그 엔진을 직접 실행해 검증
  L_OUT="$("$LIST_VIEW" draft 2>/dev/null)"
  if grep -qF "$L_TITLE" <<<"$L_OUT" && grep -q "구체화 대기 (draft)" <<<"$L_OUT"; then
    ok "list: draft 그룹에 seed 항목이 표시됨"
  else
    bad "list: 출력에서 seed 항목/그룹 헤더를 못 찾음"; FAIL=1
  fi
fi

# ══════════════════════════════════════════════════════════════
# @covers-contract: plan — draft→planned 상태전이 + 인터뷰 필드 라운드트립 (계약만 검증, 아래 근거)
#
# 왜 full `/plan` 을 헤드리스로 돌리지 않나:
#   1) plan 은 대상 지정 인자가 없어 draft 전체를 순회한다 → 공유 DB 의 "실제" 할일까지
#      건드릴 위험이 있어 안전하지 않다.
#   2) 구체화 단계가 AskUserQuestion 대화형 인터뷰라 -p 헤드리스에서 비결정적이다.
#   → 그래서 plan 이 SKILL.md 에 문서화한 "결정적 업데이트 계약"만 격리 실행해
#     상태전이와 필드 저장을 검증한다. (echo/true 가 아니라 실제 Notion 상태를 바꾼다)
# ══════════════════════════════════════════════════════════════
echo "  [plan] draft→planned 전이 검증"
P_TITLE="스모크플랜_$U"
P_ID="$(seed_draft "$P_TITLE" 생활)"
if [[ -z "$P_ID" || "$P_ID" == "null" ]]; then
  bad "plan: seed 실패"; FAIL=1
else
  CREATED_IDS+=("$P_ID")
  # plan/SKILL.md Step 3-2 의 계약 그대로: printf '%s' 로 flat JSON 을 update 에 파이프
  printf '%s' '{"status":"planned","recurrence":"once","due_date":"2026-07-10","time":"저녁","detail":"스모크 상세"}' \
    | "$NOTION_SH" update "$P_ID" >/dev/null 2>&1
  P_ST="$(status_of "$P_ID")"
  P_DD="$(field_of "$P_ID" due_date)"
  P_DT="$(field_of "$P_ID" detail)"
  if [[ "$P_ST" == "planned" ]]; then
    ok "plan: status draft→planned"
  else
    bad "plan: status 가 planned 가 아님 (실제=$P_ST)"; FAIL=1
  fi
  if [[ "$P_DD" == "2026-07-10" && "$P_DT" == *"스모크"* ]]; then
    ok "plan: 인터뷰 필드 라운드트립 (due_date=$P_DD, detail 저장됨)"
  else
    bad "plan: 필드 라운드트립 실패 (due_date=$P_DD, detail=$P_DT)"; FAIL=1
  fi
fi

# ══════════════════════════════════════════════════════════════
# @covers: done — draft→done 을 실제 스킬로 e2e (고유 제목으로 우리 항목만 스코프)
#
# 캐시/비동기 계약 주의: /done 은 이제 (1) 미완료 목록을 read-model(cache.sh)에서 읽고,
# (2) 완료를 캐시/오버레이에 즉시 반영한 뒤 Notion 반영은 백그라운드(detached)로 던진다.
# 따라서 이 테스트는 두 가지를 맞춰준다:
#   - seed 는 out-of-band(직접 write)라 캐시에 없으므로, /done 이 대상을 볼 수 있도록
#     실행 전에 cache.sh refresh 로 read-model 에 반영한다.
#   - Notion 원본 done 반영은 백그라운드라 즉시가 아닐 수 있으므로, 즉시 검증 대신
#     wait_status 로 "결국 done 이 되는가"를 짧게 폴링해 확인한다(최종 일관성 계약).
# ══════════════════════════════════════════════════════════════
echo "  [done] draft→done e2e 검증"
D_TITLE="스모크던_$U"
D_ID="$(seed_draft "$D_TITLE" 생활)"
if [[ -z "$D_ID" || "$D_ID" == "null" ]]; then
  bad "done: seed 실패"; FAIL=1
else
  CREATED_IDS+=("$D_ID")
  "$CACHE_SH" refresh >/dev/null 2>&1   # out-of-band seed 를 read-model 에 반영 → /done 이 볼 수 있게
  # /done <고유제목> → 단일 매치 → 비대화형으로 그 항목만 done 처리 (SKILL.md 2-A)
  echo "    claude -p \"/done $D_TITLE\" 실행 중... (수십 초)"
  if claude -p "/done $D_TITLE" --dangerously-skip-permissions >/tmp/smoke_done_out.txt 2>&1; then
    # 백그라운드 Notion write 가 착할 때까지 최대 10초 폴링(최종 일관성)
    if wait_status "$D_ID" done 10; then
      ok "done: status draft→done (백그라운드 반영 확인)"
    else
      bad "done: 실행됐으나 status 가 done 이 아님 (실제=$(status_of "$D_ID"))"; FAIL=1
    fi
  else
    bad "done: claude 실행 실패 (출력 /tmp/smoke_done_out.txt)"
    sed 's/^/      /' /tmp/smoke_done_out.txt | head -20
    FAIL=1
  fi
fi

echo "────────────────────────────────────────────────"
if [[ "$FAIL" -eq 0 ]]; then
  echo "L3(crud) 결과: PASS"
else
  echo "L3(crud) 결과: ${FAIL} fail"
fi
exit "$FAIL"
