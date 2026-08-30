#!/usr/bin/env bash
# 루프가 사람을 불러낸 지점을 기록한다.
# .claude/settings.json 의 PreToolUse/PostToolUse(AskUserQuestion) · Notification · Stop · UserPromptSubmit 훅이 실행한다.
#
# 왜 이 로그인가 — OS.md 원칙 6. 사람 개입은 오른쪽으로 밀어낸다:
#   의사결정 → 승인 → 기준 제공 → 시작 버튼.
# 어느 개입이 아직 왼쪽에 남아 있는지 세어보지 않으면 밀어낼 대상을 고를 수 없다.
#
# 이름을 「관문(gate)」으로 하지 않은 이유 — OS.md 2026-08-30 결정 로그.
#   관문이라 부르면 통과·실패 판정이 딸려 온다. 이건 판정 장치가 아니라 관측이다.
#
# stdin  : 훅 입력 JSON (이벤트마다 다르다)
#          PreToolUse/PostToolUse {tool_input:{questions}, tool_response}
#          Notification           {message}
#          Stop                   {transcript_path}
#          UserPromptSubmit       {prompt}
# stdout : 아무것도 출력하지 않는다.
#          특히 UserPromptSubmit 의 stdout 은 그대로 대화 컨텍스트에 주입되므로 반드시 조용해야 한다.
# 산출물 : .claude/human-intervention.jsonl (append-only)
#
# 한 줄의 뜻:
#   ev   ask    = 루프가 멈추고 사람을 기다린 순간
#        answer = 사람이 답한 순간 (dur_s = 사람이 붙잡고 있던 시간)
#   kind 는 이벤트에서 나온 사실이다. 원칙 6의 네 단계(의사결정/승인/기준/버튼) 분류는
#        기계가 하지 않는다 — summary 를 읽고 사람이 한다. 추측한 분류를 남기면 그게 사실로 굳는다.
#
# 읽는 법:
#   jq -r 'select(.ev=="ask") | "\(.ts) [\(.kind)] \(.loop) \(.summary)"' .claude/human-intervention.jsonl
#   jq -r 'select(.ev=="answer") | "\(.bytes)B \(.dur_s // "-")s \(.summary)"' .claude/human-intervention.jsonl
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
LOG="$ROOT/.claude/human-intervention.jsonl"
HANDOFF="$ROOT/.claude/agent-handoff.jsonl"
STATE="$ROOT/.claude/.hook-state"

payload="$(cat)"
ev_name="$(printf '%s' "$payload" | jq -r '.hook_event_name // ""' 2>/dev/null)"
session="$(printf '%s' "$payload" | jq -r '.session_id // ""' 2>/dev/null)"
tool="$(printf '%s' "$payload" | jq -r '.tool_name // ""' 2>/dev/null)"

# 이 세션이 루프 세션일 때만 기록한다. 범위 판정은 loop-session.sh 한 곳에서 한다.
# 아무 세션이나 남기면 로그가 잡담으로 채워져 루프를 읽을 수 없다(실제로 훅을 만드는 대화가 찍혔다).
# 예외 하나 — 루프를 시작하는 입력(`/feature-loop ...`)은 표식이 찍히기 전에 도착한다.
# 그 한 줄이 루프의 시작 버튼(원칙 6의 가장 오른쪽)이라 빠지면 안 된다.
if [ ! -f "$STATE/loop.$session" ]; then
  printf '%s' "$payload" | jq -r '.prompt // ""' 2>/dev/null | grep -qE '^/feature-loop' || exit 0
fi

mkdir -p "$(dirname "$LOG")" "$STATE" || exit 0

ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
now="$(date +%s)"

# 주고받은 정보 — 2줄 이하. log-agent-handoff.sh 와 같은 규칙이다.
# 두 훅은 서로를 source 하지 않는다. 한쪽 파일이 없어도 다른 쪽은 계속 돌아야 한다.
two_lines() {   # 앞에서 2줄 — 질문·선택지는 앞이 본문이다
  # awk 는 바이트로 자르므로 한글 한 글자 가운데가 잘린다(로그에 깨진 문자가 실제로 찍혔다).
  # iconv -c 로 잘린 꼬리 바이트를 떨어뜨린다.
  awk '{ gsub(/^[ \t#>*-]+|[ \t]+$/, ""); if ($0 == "") next;
         if (n < 2) { if (length($0) > 120) $0 = substr($0, 1, 117) "…";
                      out = (n == 0 ? $0 : out " ⏎ " $0); n++ } }
       END { print out }' | iconv -c -f UTF-8 -t UTF-8 2>/dev/null
}
tail_lines() {  # 뒤에서 2줄 — 어시스턴트 메시지에서 사람에게 묻는 문장은 대개 끝에 있다
  awk '{ gsub(/^[ \t#>*-]+|[ \t]+$/, ""); if ($0 != "") { a[++n] = $0 } }
       END { for (i = (n > 1 ? n - 1 : 1); i <= n; i++) {
               s = a[i]; if (length(s) > 120) s = substr(s, 1, 117) "…";
               out = (out == "" ? s : out " ⏎ " s) } print out }' | iconv -c -f UTF-8 -t UTF-8 2>/dev/null
}

# 루프 귀속 — 텍스트에 경로가 찍혀 있으면 거기서, 없으면 같은 세션의 마지막 서브에이전트 기록에서 물려받는다.
# 두 로그를 같은 루프 키로 묶어야 "이 루프에서 사람이 몇 번 불려나왔나"를 셀 수 있다.
loop_of() {
  local hay="$1" l
  l="$(printf '%s' "$hay" | grep -oE 'projects/[^"/[:space:]]+/loops/[0-9]{3}-[^"/[:space:],)]+' | head -1 | sed 's|projects/||; s|/loops/|/|')"
  [ -n "$l" ] || l="$(printf '%s' "$hay" | grep -oE 'loops/[0-9]{3}-[^"/[:space:],)]+' | head -1 | sed 's|^loops/||')"
  if [ -z "$l" ] && [ -f "$HANDOFF" ]; then
    l="$(grep -F "\"session\":\"$session\"" "$HANDOFF" 2>/dev/null | grep -v '"loop":"-"' | tail -1 | jq -r '.loop // ""' 2>/dev/null)"
  fi
  printf '%s' "${l:--}"
}

record() {  # $1 ev  $2 kind  $3 원문  $4 요약  $5 dur(json)  $6 extra(json object)
  # bytes 는 요약이 아니라 원문의 길이다. 요약 길이를 재면 긴 답이 전부 상한에 붙어
  # "응/ㅇㅋ" 같은 형식적 승인과 길게 쓴 답이 구별되지 않는다.
  jq -cn --arg ts "$ts" --arg ev "$1" --arg kind "$2" --arg loop "$(loop_of "$3")" \
         --arg summary "$4" --argjson dur "$5" \
         --argjson bytes "$(printf '%s' "$3" | wc -c | tr -d ' ')" \
         --argjson extra "$6" --arg session "$session" \
    '{ts:$ts, ev:$ev, kind:$kind, loop:$loop, summary:$summary, dur_s:$dur, bytes:$bytes, session:$session} + $extra' \
    >> "$LOG" 2>/dev/null
}

case "$ev_name" in

  # ── 선택지를 주고 고르게 한 것. 원칙 6에서 가장 왼쪽(= 가장 비싼) 개입이다 ──
  PreToolUse)
    [ "$tool" = "AskUserQuestion" ] || exit 0
    q="$(printf '%s' "$payload" | jq -r '[.tool_input.questions[]? | .question, ([.options[]?.label] | join(" / "))] | join("\n")' 2>/dev/null)"
    printf '%s' "$now" > "$STATE/ask.$session" 2>/dev/null
    record ask 의사결정 "$q" "$(printf '%s' "$q" | two_lines)" null '{"question":true}'
    ;;

  PostToolUse)
    [ "$tool" = "AskUserQuestion" ] || exit 0
    a="$(printf '%s' "$payload" | jq -r '
      def totext:
        if . == null then "" elif type == "string" then .
        elif type == "array" then ([.[] | totext] | join("\n"))
        elif type == "object" then ([to_entries[] | "\(.key): \(.value | totext)"] | join("\n"))
        else tostring end;
      .tool_response | totext' 2>/dev/null)"
    dur=null
    if [ -f "$STATE/ask.$session" ]; then
      s="$(cat "$STATE/ask.$session" 2>/dev/null)"; rm -f "$STATE/ask.$session"
      case "$s" in ''|*[!0-9]*) ;; *) dur=$(( now - s )) ;; esac
    fi
    record answer 의사결정 "$a" "$(printf '%s' "$a" | two_lines)" "$dur" '{}'
    ;;

  # ── 권한·알림. 되돌릴 수 없는 조작 앞의 승인(원칙 2)은 설계상 남는 개입이지만,
  #    같은 승인을 매 루프 반복해서 묻고 있다면 그건 settings 로 밀어낼 수 있는 개입이다 ──
  Notification)
    msg="$(printf '%s' "$payload" | jq -r '.message // ""' 2>/dev/null)"
    [ -n "$msg" ] || exit 0
    kind=알림; q=false
    printf '%s' "$msg" | grep -qiE 'permission|승인|허가|approve' && { kind=승인요청; q=true; }
    record ask "$kind" "$msg" "$(printf '%s' "$msg" | two_lines)" null "{\"question\":$q}"
    ;;

  # ── 메인이 턴을 끝내고 사람 차례가 된 순간. 자유 텍스트로 물은 승인(feature-loop ②·⑤)이 여기 잡힌다 ──
  Stop)
    tp="$(printf '%s' "$payload" | jq -r '.transcript_path // ""' 2>/dev/null)"
    last=""
    if [ -n "$tp" ] && [ -f "$tp" ]; then
      # 마지막 '텍스트' 블록을 꺼낸다. 마지막 어시스턴트 항목을 그냥 집으면 안 된다 —
      # 트랜스크립트의 끝은 대개 thinking·tool_use 블록이라 본문이 비어서 나온다(실제로 첫 기록이 빈 줄로 찍혔다).
      # 서브에이전트 대화(isSidechain)는 뺀다. 사람에게 물은 것은 메인의 말이다.
      # 깨진 줄이 섞여도 전체가 실패하지 않게 fromjson? 로 거른다.
      last="$(tail -n 300 "$tp" 2>/dev/null \
              | jq -R 'fromjson? // empty' 2>/dev/null \
              | jq -rs '[ .[] | select(.type == "assistant" and (.isSidechain | not))
                          | .message.content[]? | select(.type == "text") | .text ] | last // ""' 2>/dev/null)"
    fi
    q=false
    printf '%s' "$last" | tr -d ' \t' | tail -c 400 | grep -qE '\?|까요|하시겠|골라|고르|정해|승인|알려줘|알려주|말해줘|말해주|주세요|하겠다$' && q=true
    printf '%s' "$now" > "$STATE/stop.$session" 2>/dev/null
    record ask 턴종료 "$last" "$(printf '%s' "$last" | tail_lines)" null "{\"question\":$q}"
    ;;

  # ── 사람이 답한 순간. bytes 가 계속 작으면("응", "ㅇㅋ") 그 개입은 형식적 승인이다 —
  #    OS.md 2절 "승인이 형식이 된다 → 기준 검증자를 떼어낼 신호" 가 숫자로 보이는 자리다 ──
  UserPromptSubmit)
    p="$(printf '%s' "$payload" | jq -r '.prompt // ""' 2>/dev/null)"
    dur=null
    if [ -f "$STATE/stop.$session" ]; then
      s="$(cat "$STATE/stop.$session" 2>/dev/null)"; rm -f "$STATE/stop.$session"
      case "$s" in ''|*[!0-9]*) ;; *) dur=$(( now - s )) ;; esac
    fi
    record answer 사람입력 "$p" "$(printf '%s' "$p" | two_lines)" "$dur" '{}'
    ;;
esac

find "$STATE" -type f -mmin +1440 -delete 2>/dev/null
exit 0
