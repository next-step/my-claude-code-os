#!/usr/bin/env bash
# 메인 ↔ 서브에이전트의 왕복을 기록한다.
# .claude/settings.json 의 PreToolUse / PostToolUse (matcher: "Agent|Task") 훅이 실행한다.
#
# 왜 훅인가 — OS.md 원칙 4. 부를 때만 도는 것(스킬)은 잊으면 사라진다.
#             구간을 넘길 때마다 자동으로 남아야 원칙 5(측정되지 않으면 개선되지 않는다)가 성립한다.
#
# stdin  : 훅 입력 JSON
#          PreToolUse  {session_id, tool_name, tool_input:{description, prompt, subagent_type}}
#          PostToolUse 위 + {tool_response}
# stdout : 아무것도 출력하지 않는다. 훅의 stdout은 대화에 끼어들므로 조용해야 한다.
# 산출물 : .claude/agent-handoff.jsonl  (append-only, 한 왕복이 두 줄 — dispatch / return)
#          .claude/.hook-state/         (왕복 짝짓기용 임시 파일. 자동 정리)
#
# SubagentStop 이 아니라 Pre/PostToolUse 를 쓰는 이유:
#   SubagentStop 에는 "무엇을 주고 무엇을 받았는지"가 없다. 시간만 남고 정보가 안 남는다.
#
# 읽는 법:
#   jq -r 'select(.loop=="review-scheduler/002-http-api")
#          | "\(.ts) \(.ev) \(.label) \(.dur_s // "") \(.summary)"' .claude/agent-handoff.jsonl
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
LOG="$ROOT/.claude/agent-handoff.jsonl"
STATE="$ROOT/.claude/.hook-state"

payload="$(cat)"
tool="$(printf '%s' "$payload" | jq -r '.tool_name // ""' 2>/dev/null)"

# 서브에이전트 호출이 아니면 기록할 것이 없다. 훅은 조용히 성공해야 한다.
case "$tool" in Agent|Task) ;; *) exit 0 ;; esac

ev="$(printf '%s' "$payload" | jq -r '.hook_event_name // ""' 2>/dev/null)"
session="$(printf '%s' "$payload" | jq -r '.session_id // ""' 2>/dev/null)"
agent="$(printf '%s' "$payload" | jq -r '.tool_input.subagent_type // "-"' 2>/dev/null)"
label="$(printf '%s' "$payload" | jq -r '.tool_input.description // "-"' 2>/dev/null)"
prompt="$(printf '%s' "$payload" | jq -r '.tool_input.prompt // ""' 2>/dev/null)"
tuid="$(printf '%s' "$payload" | jq -r '.tool_use_id // ""' 2>/dev/null)"

# 이 세션이 루프 세션일 때만 기록한다. 범위 판정은 loop-session.sh 한 곳에서 한다.
# 아무 세션이나 남기면 로그가 잡담으로 채워져 루프를 읽을 수 없다(실제로 훅을 만드는 대화가 찍혔다).
[ -f "$STATE/loop.$session" ] || exit 0

# tool_response 는 문자열일 수도, content 블록 배열일 수도, 객체일 수도 있다. 셋 다 텍스트로 편다.
resp="$(printf '%s' "$payload" | jq -r '
  def totext:
    if . == null then ""
    elif type == "string" then .
    elif type == "array" then ([.[] | totext] | join("\n"))
    elif type == "object" then ((.text // .content // .result // .output // "") | totext)
    else tostring end;
  .tool_response | totext' 2>/dev/null)"

mkdir -p "$(dirname "$LOG")" "$STATE" || exit 0

# 주고받은 정보 — 2줄 이하로 줄인다.
# 전문을 남기면 로그가 대화 사본이 되고, 그러면 아무도 읽지 않아 측정이 아니라 쓰레기가 된다.
two_lines() {
  # awk 는 바이트로 자르므로 한글 한 글자 가운데가 잘린다(로그에 깨진 문자가 실제로 찍혔다).
  # iconv -c 로 잘린 꼬리 바이트를 떨어뜨린다.
  # 격리 보일러플레이트는 빼고 센다. isolation_line 필드가 이미 그것을 기록하므로 두 번 적을 이유가 없다.
  awk '/다른 파일을 읽지/ { next }
       { gsub(/^[ \t#>*-]+|[ \t]+$/, ""); if ($0 == "") next;
         if (n < 2) { if (length($0) > 120) $0 = substr($0, 1, 117) "…";
                      out = (n == 0 ? $0 : out " ⏎ " $0); n++ } }
       END { print out }' | iconv -c -f UTF-8 -t UTF-8 2>/dev/null
}

# 루프 귀속 — 프롬프트·응답에 찍힌 루프 경로에서 뽑는다.
# 못 찾으면 "-" 로 둔다. 최근 수정된 루프로 추측하면 조용히 틀린 데이터가 쌓인다.
hay="$label
$prompt
$resp"
loop="$(printf '%s' "$hay" | grep -oE 'projects/[^"/[:space:]]+/loops/[0-9]{3}-[^"/[:space:],)]+' | head -1 | sed 's|projects/||; s|/loops/|/|')"
[ -n "$loop" ] || loop="$(printf '%s' "$hay" | grep -oE 'loops/[0-9]{3}-[^"/[:space:],)]+' | head -1 | sed 's|^loops/||')"
[ -n "$loop" ] || loop="-"

# 왕복 짝짓기 키. tool_use_id 가 있으면 그것을, 없으면 호출 내용의 체크섬을 쓴다.
if [ -n "$tuid" ]; then
  key="$tuid"
else
  key="$(printf '%s' "$session|$label|$prompt" | cksum | tr -cd '0-9')"
fi

ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
now="$(date +%s)"

case "$ev" in
  PreToolUse)
    # 시각과 함께 루프도 적어둔다. return 쪽 페이로드에 루프 경로가 안 보여도 짝이 물려받는다.
    printf '%s\t%s' "$now" "$loop" > "$STATE/$key" 2>/dev/null

    # 격리 점검 — OS.md 4절 규칙 3. "저장소의 다른 파일을 읽지 마라"가 프롬프트에 있었는가.
    # 이건 판정이 아니라 관측이다. 막지 않고 기록만 한다(막으려면 exit 2 를 쓴다).
    iso=false
    printf '%s' "$prompt" | grep -q '다른 파일을 읽지' && iso=true

    jq -cn --arg ts "$ts" --arg loop "$loop" --arg agent "$agent" --arg label "$label" \
           --arg summary "$(printf '%s' "$prompt" | two_lines)" \
           --argjson bytes "$(printf '%s' "$prompt" | wc -c | tr -d ' ')" \
           --argjson iso "$iso" --arg key "$key" --arg session "$session" \
      '{ts:$ts, ev:"dispatch", loop:$loop, agent:$agent, label:$label,
        summary:$summary, bytes:$bytes, isolation_line:$iso, key:$key, session:$session}' >> "$LOG" 2>/dev/null
    ;;

  PostToolUse)
    dur=null
    if [ -f "$STATE/$key" ]; then
      pending="$(cat "$STATE/$key" 2>/dev/null)"
      rm -f "$STATE/$key"
      started="${pending%%$'\t'*}"
      from_loop="${pending#*$'\t'}"
      case "$started" in ''|*[!0-9]*) ;; *) dur=$(( now - started )) ;; esac
      # 한 왕복은 같은 루프에 속한다. 응답에서 경로를 못 찾았으면 보낸 쪽의 것을 쓴다.
      if [ "$loop" = "-" ] && [ -n "$from_loop" ] && [ "$from_loop" != "$pending" ]; then loop="$from_loop"; fi
    fi

    jq -cn --arg ts "$ts" --arg loop "$loop" --arg agent "$agent" --arg label "$label" \
           --argjson dur "$dur" \
           --arg summary "$(printf '%s' "$resp" | two_lines)" \
           --argjson bytes "$(printf '%s' "$resp" | wc -c | tr -d ' ')" \
           --arg key "$key" --arg session "$session" \
      '{ts:$ts, ev:"return", loop:$loop, agent:$agent, label:$label, dur_s:$dur,
        summary:$summary, bytes:$bytes, key:$key, session:$session}' >> "$LOG" 2>/dev/null
    ;;
esac

# 짝을 못 만난 임시 파일 청소(중단·에러로 return 이 안 온 호출). 하루 지난 것만 지운다.
find "$STATE" -type f -mmin +1440 -delete 2>/dev/null

exit 0
