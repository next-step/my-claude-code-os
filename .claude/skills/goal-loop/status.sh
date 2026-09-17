#!/usr/bin/env bash
# goal-loop state. SKILL.md runs this inline with `!`.
# Never fails: an unreadable state is an inconvenience, a blocked skill is an accident.
set -uo pipefail

PROJECT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
LOOP_DIR="$PROJECT/.claude/loop"

if [ ! -d "$LOOP_DIR" ]; then
  echo "loop : none (first run starts at Phase 0)"
  exit 0
fi

python3 - "$LOOP_DIR" <<'PY' 2>/dev/null || echo "loop : state unreadable (inspect $LOOP_DIR)"
import json, os, sys

loop = sys.argv[1]
tasks = sorted(d for d in os.listdir(loop) if os.path.isdir(os.path.join(loop, d)))
if not tasks:
    print("loop : none (first run starts at Phase 0)")
    raise SystemExit(0)

for t in tasks:
    d = os.path.join(loop, t)
    reports = sorted(f for f in os.listdir(d) if f.endswith(".md") and f != "goal.md")
    try:
        with open(os.path.join(d, "state.json"), encoding="utf-8") as fh:
            s = json.load(fh)
    except Exception as e:
        print(f"loop : {t} - no/broken state.json ({type(e).__name__}). {len(reports)} "
              f"report{'' if len(reports) == 1 else 's'}")
        continue

    g = s.get("criteria", {})
    rounds = s.get("rounds", [])
    cap = s.get("cap", "?")
    conf = s.get("confirm", "?")
    unit = g.get("unit", "")
    goal = f"{g.get('direction','?')} {g.get('threshold','?')}{unit}"

    vals = [r.get("value") for r in rounds if r.get("value") is not None]
    trail = " -> ".join(str(v) for v in vals[-6:]) if vals else "no measurement"
    last = rounds[-1] if rounds else {}
    n = last.get("n", 0)
    inv = last.get("invariants", "?")

    print(f"loop : {t} - goal {goal} / round {n}/{cap} (confirm {conf})")
    print(f"       trail {trail} · last invariants {inv} · {len(reports)} "
          f"report{'' if len(reports) == 1 else 's'}")
    if len(reports) < n:
        print(f"       ! fewer reports than rounds ({len(reports)} < {n}): a round started blind")
    done = (s.get("result") or {}).get("outcome")
    if done:
        nxt = f"{done} at round {(s.get('result') or {}).get('at_round', '?')} - nothing to run"
    elif not rounds:
        nxt = "measure the baseline"
    elif isinstance(cap, int) and n >= cap:
        nxt = "cap reached; the user decides whether to raise it"
    else:
        nxt = f"round {n+1}"
    print(f"       next : {nxt}")
PY
