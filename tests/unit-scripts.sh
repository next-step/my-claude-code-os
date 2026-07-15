#!/usr/bin/env bash
#
# unit-scripts.sh — 순수 결정적 셸 스크립트 단위 테스트 (L2)
#
# 대상:
#   - .claude/hooks/log-skill-invocation.sh  (자기 관찰 루프의 write: 스킬 호출 → 로그 append)
#   - .claude/skills/_shared/usage-report.sh (자기 관찰 루프의 read: 로그 → 빈도·연쇄·유휴 집계)
#
# 왜 여기 있나:
#   두 스크립트는 telegram-listener·remind-cron 같은 외부 의존(네트워크·데몬·claude)이
#   전혀 없는 순수 함수형이다(stdin→파일 append / 로그→stdout). 그래서 detect-todo.js 처럼
#   결정적 단위 테스트가 가능하다. 실데이터(skill-invocations.log)를 건드리지 않으려고
#   SKILL_LOG 환경변수로 임시 로그를 주입해 검증한다.
#
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOK="$ROOT/.claude/hooks/log-skill-invocation.sh"
REPORT="$ROOT/.claude/skills/_shared/usage-report.sh"
DIGEST="$ROOT/.claude/skills/_shared/digest-report.sh"
SEND="$ROOT/.claude/skills/_shared/telegram-send.sh"

pass=0; fail=0
ok(){ printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
ng(){ printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
LOG="$TMP/log.txt"

echo "── log-skill-invocation.sh (write) ──"

# 1) Skill payload → 한 줄 append, "#1 스킬명" 포맷
: > "$LOG"
echo '{"tool_name":"Skill","tool_input":{"skill":"capture"}}' | SKILL_LOG="$LOG" bash "$HOOK"
if [[ "$(wc -l <"$LOG" | tr -d ' ')" == "1" ]] && grep -qE '\| #1 \| capture$' "$LOG"; then
  ok "Skill 호출 → '#1 | capture' 한 줄 기록"
else
  ng "Skill 호출 append 실패: $(cat "$LOG")"
fi

# 2) 카운터 증가: 다음 호출 → #2
echo '{"tool_name":"Skill","tool_input":{"skill":"plan"}}' | SKILL_LOG="$LOG" bash "$HOOK"
grep -qE '\| #2 \| plan$' "$LOG" && ok "다음 호출 → #2 로 증가" || ng "카운터 증가 실패: $(tail -1 "$LOG")"

# 3) 비-Skill 툴(.skill 없음) → 무기록·exit 0
before="$(wc -l <"$LOG")"
echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | SKILL_LOG="$LOG" bash "$HOOK"; rc=$?
after="$(wc -l <"$LOG")"
[[ "$before" == "$after" && "$rc" -eq 0 ]] && ok "비-Skill 호출 → 무기록·exit0" || ng "비-Skill 처리 오류 (rc=$rc, $before→$after)"

# 4) 네임스페이스 스킬명 그대로 보존
: > "$LOG"
echo '{"tool_name":"Skill","tool_input":{"skill":"oh-my-claudecode:autopilot"}}' | SKILL_LOG="$LOG" bash "$HOOK"
grep -qE '\| #1 \| oh-my-claudecode:autopilot$' "$LOG" && ok "네임스페이스 스킬명 보존" || ng "네임스페이스 처리 실패: $(cat "$LOG")"

echo ""
echo "── usage-report.sh (read) ──"

# 픽스처: capture,plan,capture,plan,capture,list
#   빈도 → capture 3 / plan 2 / list 1
#   연쇄 → capture→plan 2회 (그 외 1회씩)
cat > "$LOG" <<'EOF'
2026-07-10 09:00:00 | #1 | capture
2026-07-10 09:01:00 | #2 | plan
2026-07-11 09:00:00 | #3 | capture
2026-07-11 09:01:00 | #4 | plan
2026-07-12 09:00:00 | #5 | capture
2026-07-12 09:02:00 | #6 | list
EOF
out="$(SKILL_LOG="$LOG" bash "$REPORT")"
grep -qE '3회  /capture'        <<<"$out" && ok "빈도: capture 3회 집계"        || ng "빈도 집계 오류"
grep -qE '2회  capture → plan'  <<<"$out" && ok "연쇄: capture → plan 2회 집계" || ng "연쇄 집계 오류"
grep -qE '/done'                <<<"$out" && ok "유휴: 호출 없는 /done 표기"     || ng "유휴 판정 오류"

# 빈 로그 → 안내 메시지·exit 0 (실패 아님)
: > "$LOG"
out="$(SKILL_LOG="$LOG" bash "$REPORT")"; rc=$?
grep -q "아직 기록된 스킬 호출이 없어요" <<<"$out" && [[ "$rc" -eq 0 ]] \
  && ok "빈 로그 → 안내·exit0" || ng "빈 로그 처리 오류 (rc=$rc)"

echo ""
echo "── digest-report.sh (집계) ──"

# 픽스처: draft 2(하나는 5일 전=방치) / planned 1 / done 2, 업무 2건
DFIX="$TMP/items.json"
cat > "$DFIX" <<'EOF'
[
 {"id":"1","title":"세미나 신청","category":"스터디","status":"draft","captured_at":"2026-07-10 09:00:00"},
 {"id":"2","title":"장보기","category":"일상","status":"draft","captured_at":"2026-07-14 09:00:00"},
 {"id":"3","title":"리포트","category":"업무","status":"planned","captured_at":"2026-07-12 09:00:00"},
 {"id":"4","title":"운동","category":"건강","status":"done","captured_at":"2026-07-11 09:00:00"},
 {"id":"5","title":"코드리뷰","category":"업무","status":"done","captured_at":"2026-07-13 09:00:00"}
]
EOF
out="$(ITEMS_JSON_FILE="$DFIX" bash "$DIGEST")"
grep -qE '전체 5개'                 <<<"$out" && ok "집계: 전체 5개"           || ng "집계 총계 오류"
grep -qE 'draft 2 · 📅 planned 1 · ✅ done 2' <<<"$out" && ok "집계: 상태 분포 정확" || ng "상태 분포 오류"
grep -qE '업무 2개'                 <<<"$out" && ok "집계: 카테고리 분포(업무 2개)" || ng "카테고리 분포 오류"
grep -qE '세미나 신청 \(5일 전 캡처\)' <<<"$out" && ok "집계: 2일+ 방치 draft 강조"  || ng "방치 draft 판정 오류"

# 빈 항목 → 안내·정상 종료
echo '[]' > "$DFIX"
out="$(ITEMS_JSON_FILE="$DFIX" bash "$DIGEST")"; rc=$?
grep -q "아직 등록된 할일이 없어요" <<<"$out" && [[ "$rc" -eq 0 ]] && ok "빈 항목 → 안내·exit0" || ng "빈 항목 처리 오류"

echo ""
echo "── telegram-send.sh (가드) ──"
# 빈 메시지 → 값 노출 없이 실패(exit1). 자격증명 검사 이전 단계라 네트워크 미접촉.
printf '' | bash "$SEND" >/dev/null 2>&1; rc=$?
[[ "$rc" -eq 1 ]] && ok "빈 메시지 → exit1 (발송 안 함)" || ng "빈 메시지 가드 오류 (rc=$rc)"

echo ""
echo "────────────────────────────────────────────────"
echo "unit-scripts 결과: $pass pass / $fail fail"
[[ "$fail" -eq 0 ]]
