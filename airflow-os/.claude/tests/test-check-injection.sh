#!/usr/bin/env bash
# test-check-injection.sh — check-injection.sh 자가 테스트 (결정적, 외부 세션 불필요)
#
# 합성 transcript/서브로그 fixture를 만들어 check-injection.sh 를 케이스별로 돌리고
# exit code·핵심 출력을 assert 한다. 실제 에이전트 실행에 의존하지 않는다.
#
# 실행:  .claude/tests/test-check-injection.sh   (통과=exit 0, 하나라도 실패=exit 1)

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SUT="$HERE/check-injection.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

pass=0; fail=0
ok()   { pass=$((pass+1)); echo "  ✅ $1"; }
bad()  { fail=$((fail+1)); echo "  ❌ $1"; }

# fixture 빌더: (이름, 스폰개수 목록...) — 각 run이 읽을 context 를 인자로 받는다.
# dag-reviewer.md 필수 선언 = antipatterns / airflow3-knowledge / platform / conventions(디렉토리)
read_line() { echo "{\"message\":{\"content\":[{\"type\":\"tool_use\",\"name\":\"Read\",\"input\":{\"file_path\":\"/x/$1\"}}]}}"; }
spawn_line() { echo "{\"message\":{\"content\":[{\"type\":\"tool_use\",\"name\":\"Agent\",\"id\":\"$1\",\"input\":{\"subagent_type\":\"dag-reviewer\",\"description\":\"$2\"}}]}}"; }
FULL=".claude/context/airflow-antipatterns.md .claude/context/airflow3-knowledge.md .claude/context/platform.md .claude/context/conventions/defaults.md"

# run(main, sub, id, desc, reads...) — 스폰 1개 + 대응 meta/log 생성
add_run() {
  local main="$1" sub="$2" id="$3" desc="$4"; shift 4
  spawn_line "$id" "$desc" >> "$main"
  : > "$sub/agent-$id.jsonl"
  local r; for r in "$@"; do read_line "$r" >> "$sub/agent-$id.jsonl"; done
  echo "{\"agentType\":\"dag-reviewer\",\"toolUseId\":\"$id\"}" > "$sub/agent-$id.meta.json"
}

# --- 케이스 실행 헬퍼: 기대 exit code + (선택) 출력 grep ---
run_case() {  # name, expect_exit, transcript(or ""=none), [grep_pat...]
  local name="$1" want="$2" tr="$3"; shift 3
  local out ec
  if [ -n "$tr" ]; then out="$($SUT --agent dag-reviewer --transcript "$tr" 2>&1)"; else out="$($SUT 2>&1)"; fi
  ec=$?
  [ "$ec" = "$want" ] && ok "$name: exit=$ec" || bad "$name: exit=$ec (기대 $want)"
  local p; for p in "$@"; do
    echo "$out" | grep -qF "$p" && ok "$name: 출력에 '$p'" || bad "$name: 출력에 '$p' 없음"
  done
}

# 훅 모드: payload JSON 을 stdin 으로. 항상 exit 0(non-block). want="" 면 무출력(조용히 통과) 기대.
run_hook() {  # name, payload_json, want("" = 무출력 기대)
  local name="$1" payload="$2" want="$3"
  local out ec
  out="$(printf '%s' "$payload" | $SUT --hook 2>&1)"; ec=$?
  [ "$ec" = 0 ] && ok "$name: exit=0(non-block)" || bad "$name: exit=$ec (기대 0)"
  if [ -z "$want" ]; then
    [ -z "$out" ] && ok "$name: 무출력(조용히 통과)" || bad "$name: 출력 있음 '$out'"
  else
    echo "$out" | grep -qF "$want" && ok "$name: 출력에 '$want'" || bad "$name: 출력에 '$want' 없음"
  fi
}

echo "== check-injection.sh 자가 테스트 =="

# 1) 정상 1 run → exit 0
m="$TMP/c1.jsonl"; s="$TMP/c1/subagents"; mkdir -p "$s"; : > "$m"
add_run "$m" "$s" toolu_c1 "정상" $FULL
run_case "정상 run" 0 "$m" "✅ 전체 통과"

# 2) --agent 없이 호출 → exit 2 (서브에이전트 전용, 스킬 거부)
run_case "no-agent 거부" 2 ""

# 3) run별 실패 격리: run2만 platform.md 누락 → exit 1, run2만 🔴
m="$TMP/c3.jsonl"; s="$TMP/c3/subagents"; mkdir -p "$s"; : > "$m"
add_run "$m" "$s" toolu_c3a "정상A" $FULL
add_run "$m" "$s" toolu_c3b "platform 누락" .claude/context/airflow-antipatterns.md .claude/context/airflow3-knowledge.md .claude/context/conventions/defaults.md
add_run "$m" "$s" toolu_c3c "정상C" $FULL
run_case "실패 격리" 1 "$m" "run #2" ".claude/context/platform.md" "주입 검증 실패"

# 4) 스폰은 있는데 로그/meta 없음 → exit 1
m="$TMP/c4.jsonl"; mkdir -p "$TMP/c4/subagents"; : > "$m"
spawn_line toolu_c4 "고아 스폰" >> "$m"
run_case "고아 스폰" 1 "$m" "대응 서브로그 못 찾음"

# 5) 스폰 자체가 없음 → exit 2
m="$TMP/c5.jsonl"; mkdir -p "$TMP/c5/subagents"; echo '{"message":{"content":[]}}' > "$m"
run_case "스폰 없음" 2 "$m" "실행된 적 없음"

# --- 훅 모드 (--hook): payload 의 agent_transcript_path 로 서브 하나만 검증 ---
# fixture: 독립 로그 파일 (parent transcript/meta 불필요)
hl_full="$TMP/hl_full.jsonl"; : > "$hl_full"; for r in $FULL; do read_line "$r" >> "$hl_full"; done
hl_miss="$TMP/hl_miss.jsonl"; : > "$hl_miss"
for r in .claude/context/airflow-antipatterns.md .claude/context/airflow3-knowledge.md .claude/context/conventions/defaults.md; do
  read_line "$r" >> "$hl_miss"   # platform.md 만 빠짐
done

# 6) 훅 통과 → 조용히(무출력) exit 0
run_hook "훅 통과" "{\"agent_type\":\"dag-reviewer\",\"agent_transcript_path\":\"$hl_full\"}" ""
# 7) 훅 실패 → additionalContext 로 표면화, 누락 파일명 포함, 여전히 exit 0
run_hook "훅 실패-표면화" "{\"agent_type\":\"dag-reviewer\",\"agent_transcript_path\":\"$hl_miss\"}" "additionalContext"
run_hook "훅 실패-누락명" "{\"agent_type\":\"dag-reviewer\",\"agent_transcript_path\":\"$hl_miss\"}" "platform.md"
# 8) 대상 아님(빈 agent_type — .*matcher 오발 이벤트) → 조용히
run_hook "훅 빈 agent_type" "{\"agent_type\":\"\",\"agent_transcript_path\":\"$hl_full\"}" ""
# 9) 없는 에이전트(.md 부재) → 조용히
run_hook "훅 미존재 에이전트" "{\"agent_type\":\"nope\",\"agent_transcript_path\":\"$hl_full\"}" ""
# 10) 로그 경로 부재 → 조용히(검증 불가 ≠ 실패)
run_hook "훅 로그 없음" "{\"agent_type\":\"dag-reviewer\",\"agent_transcript_path\":\"$TMP/none.jsonl\"}" ""

echo
echo "== 결과: pass=$pass fail=$fail =="
[ "$fail" = 0 ] && { echo "✅ 전부 통과"; exit 0; } || { echo "🔴 실패 있음"; exit 1; }
