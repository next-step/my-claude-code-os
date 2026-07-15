#!/usr/bin/env bash
# check-injection.sh — 서브에이전트 컨텍스트 주입 검증 (결정적 · AI 판단 없음)
#
# 격리 서브에이전트가 자기 .md의 "먼저 Read(주입 컨텍스트)" 계약을 실제로 지켰는지 검사한다.
# lazy-loading이라 "Read 호출 = 주입". 서브에이전트 transcript(JSONL)의 Read 도구 호출을 확인해
# .claude/context 파일을 "실제로 읽었나"를 팩트로 본다. 출력 판단(canary)이 아니다.
#
# 서브에이전트만 대상이다. 스킬은 메인 컨텍스트를 공유해 격리 로그가 없어 이 방식으로 검증 못 한다.
#
# transcript 위치: 표준은 ~/.claude 다. (이 사용자는 회사 계정과 세션을 분리하려고
#   ~/.claude-personal 을 쓴다 — 둘 다 뒤지되 가장 최근 세션을 고른다. ~/.claude 가 정본.)
#
# 사용법:
#   check-injection.sh --agent NAME     # NAME 서브에이전트 스폰을 run별로 독립 검사.
#                                       #   메인의 Agent tool_use.id ↔ 서브 meta.json 의 toolUseId 로 조인(ID 기반).
#                                       #   같은 세션에서 N번 돌렸으면 N개를 각각 대조 — 한 run이라도 선언 context를
#                                       #   빠뜨리면 exit 1. 메인/다른 run 의 읽기에 오염되지 않는다.
#   check-injection.sh --agent NAME --transcript F   # 특정 메인 transcript 지정
#   check-injection.sh --hook           # 훅 모드. SubagentStop payload(JSON)를 stdin 으로 받아
#                                       #   그 서브 하나만 검증. 실패면 additionalContext 로 표면화(블로킹 안 함),
#                                       #   통과/대상 아님이면 조용히 exit 0. settings.json SubagentStop 훅이 호출.
#
# 새 세션 테스트 흐름(수동):
#   1) 서브에이전트를 실제로 돌린다 (예: dag-reviewer로 DAG 하나 리뷰)
#   2) .claude/tests/check-injection.sh --agent dag-reviewer

set -uo pipefail

# repo 루트 = 위로 거슬러 올라가며 .claude 를 품은 첫 디렉토리 (스크립트 위치 무관)
REPO="$(cd "$(dirname "$0")" && pwd)"
while [ "$REPO" != "/" ] && [ ! -d "$REPO/.claude" ]; do REPO="$(dirname "$REPO")"; done
enc="$(echo "$REPO" | sed 's#/#-#g')"

AGENT=""; TRANSCRIPT=""; HOOK=0
while [ $# -gt 0 ]; do
  case "$1" in
    --agent) AGENT="${2:-}"; shift 2;;
    --transcript) TRANSCRIPT="${2:-}"; shift 2;;
    --hook) HOOK=1; shift;;
    *) echo "unknown arg: $1"; exit 2;;
  esac
done

# --- 최근 메인 transcript 찾기 (두 base 통틀어 가장 최근; ~/.claude 정본) ---
find_main() {
  local newest="" d f
  for base in "$HOME/.claude" "$HOME/.claude-personal"; do
    d="$base/projects/$enc"
    [ -d "$d" ] || continue
    for f in "$d"/*.jsonl; do
      [ -e "$f" ] || continue
      if [ -z "$newest" ] || [ "$f" -nt "$newest" ]; then newest="$f"; fi
    done
  done
  printf '%s' "$newest"
}

# --- 모드별 argv 구성 (검증 로직은 아래 하나의 python이 공유) ---
if [ "$HOOK" = 1 ]; then
  # 훅 모드: SubagentStop payload(JSON)를 stdin 으로 받는다. heredoc이 stdin을
  # program 전달에 쓰므로 payload는 env(_PAYLOAD)로 넘긴다.
  _PAYLOAD="$(cat)"; export _PAYLOAD
  set -- hook "$REPO"
else
  [ -n "$AGENT" ] || { echo "❌ --agent NAME 필수 — 이 도구는 서브에이전트 주입만 검증한다 (스킬 아님)"; exit 2; }
  main="$TRANSCRIPT"
  [ -n "$main" ] || main="$(find_main)"
  [ -n "$main" ] || { echo "❌ transcript 못 찾음 (~/.claude 또는 ~/.claude-personal 의 projects/$enc)"; exit 2; }
  md="$REPO/.claude/agents/$AGENT.md"
  [ -f "$md" ] || { echo "❌ 에이전트 없음: $md"; exit 2; }
  set -- agent "$REPO" "$main" "$md" "$AGENT"
fi

python3 - "$@" <<'PY'
import sys, json, os, glob, re
mode, repo = sys.argv[1], sys.argv[2]

ref_re  = re.compile(r'\.claude/context/[A-Za-z0-9_./-]+')
read_re = re.compile(r'\.claude/context/[A-Za-z0-9_./-]+\.md')

def parse_declared(md):
    # .md의 "먼저 Read/주입" 섹션에서 선언 context 파싱.
    # 조건부 bullet("- (…) …" 괄호로 시작 = 특정 모드에서만)은 optional로 분리.
    req, opt = set(), set()
    found = grab = False
    for line in open(md):
        if re.match(r'^##\s', line):
            grab = ("먼저 Read" in line) or ("주입" in line)
            found = found or grab
            continue
        if not grab: continue
        refs = ref_re.findall(line)
        if not refs: continue
        conditional = bool(re.match(r'^\s*[-*]\s*\(', line))
        (opt if conditional else req).update(refs)
    if not found:  # 섹션 못 찾으면 파일 전체를 필수로 (보수적)
        req = set(ref_re.findall(open(md).read()))
    return req, opt

def reads_of(log):  # 그 로그의 Read 도구 호출에서 읽은 context
    got = set()
    for ln in open(log):
        if '"name":"Read"' in ln:
            got.update(read_re.findall(ln))
    return got

def is_read(exp, got):
    if exp.endswith(".md"): return exp in got
    return any(g.startswith(exp.rstrip("/") + "/") for g in got)  # 디렉토리 = 접두어 매칭

# ================= 훅 모드: stdin payload 로 서브 하나만 검증 =================
if mode == "hook":
    try:
        p = json.loads(os.environ.get("_PAYLOAD", "") or "{}")
    except Exception:
        sys.exit(0)  # payload 못 읽으면 조용히 통과 (검증 불가 ≠ 실패)
    name = p.get("agent_type") or ""
    log  = p.get("agent_transcript_path") or ""
    md   = os.path.join(repo, ".claude", "agents", name + ".md") if name else ""
    # 검증 대상 아니면 조용히 통과: 이름 없음 / .md 없음 / 로그 없음
    if not (name and md and os.path.isfile(md) and log and os.path.isfile(log)):
        sys.exit(0)
    req, _ = parse_declared(md)
    if not req:            # 선언 context 없는 에이전트 → 검증 안 함
        sys.exit(0)
    miss = [e for e in sorted(req) if not is_read(e, reads_of(log))]
    if not miss:
        sys.exit(0)        # 통과 = 조용히 (노이즈 안 만듦)
    # 실패 → additionalContext 로 부모 모델에 표면화. 블로킹 안 함(서브 계속 강제 X).
    msg = (f"⚠️ 컨텍스트 주입 검증 실패 — 서브에이전트 '{name}' 가 선언한 필수 context 중 "
           f"다음을 읽지 않았다: {', '.join(miss)}. 주입 배선/실행 버그일 수 있다.")
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SubagentStop", "additionalContext": msg}}))
    sys.exit(0)

# ================= 에이전트 모드: 세션 전체를 run별 독립 검증 =================
main, md, name = sys.argv[3], sys.argv[4], sys.argv[5]

# 메인에서 subagent_type==NAME 스폰을 "스폰 순서대로" 수집.
# 조인 키는 Agent tool_use 의 id (= 서브 meta.json 의 toolUseId). prompt 매칭 안 씀.
spawns = []  # [(toolUseId, description)] — 순서 = run 번호
for ln in open(main):
    try: d = json.loads(ln)
    except Exception: continue
    for b in ((d.get("message") or {}).get("content") or []):
        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Agent":
            inp = b.get("input") or {}
            if inp.get("subagent_type") == name and b.get("id"):
                spawns.append((b["id"], inp.get("description", "")))
if not spawns:
    print(f"❌ 이 세션에서 '{name}' 서브에이전트가 실행된 적 없음 — 먼저 돌리고 다시 검사."); sys.exit(2)

# subagents/*.meta.json 의 toolUseId → 로그 경로 매핑 (ID 조인, 1:1)
subdir = os.path.splitext(main)[0] + "/subagents"
id2log = {}
for meta in glob.glob(os.path.join(subdir, "*.meta.json")):
    try: m = json.load(open(meta))
    except Exception: continue
    tid = m.get("toolUseId")
    if not tid: continue
    lg = meta[:-len(".meta.json")] + ".jsonl"
    if os.path.exists(lg): id2log[tid] = lg

req, opt = parse_declared(md)
any_fail = 0
print(f"== '{name}' 스폰 {len(spawns)}개를 run별 독립 검증 (ID 조인) ==\n")
for i, (tid, desc) in enumerate(spawns, 1):
    label = f"run #{i} [{tid[:16]}…]" + (f'  "{desc}"' if desc else "")
    log = id2log.get(tid)
    if not log:
        print(f"🔴 {label} — 대응 서브로그 못 찾음 (아직 실행 중이거나 meta 없음)\n"); any_fail = 1; continue
    got = reads_of(log)
    miss = [e for e in sorted(req) if not is_read(e, got)]
    if miss:
        any_fail = 1
        print(f"🔴 {label} — 필수 누락:")
        for e in miss: print("    ✗", e)
    else:
        print(f"✅ {label} — 필수 선언 context 전부 읽음")
    for e in sorted(opt):
        print(("    ✓ " if is_read(e, got) else "    – ") + e + ("" if is_read(e, got) else " (조건부, 이 run 미사용)"))
    print()

if any_fail:
    print(f"🔴 주입 검증 실패 — 위 run 중 필수 context를 빠뜨린 게 있다 (배선/실행 버그)."); sys.exit(1)
print(f"✅ 전체 통과 — {name} 의 모든 run이 각자 필수 선언 context를 독립적으로 다 읽었다.")
PY
