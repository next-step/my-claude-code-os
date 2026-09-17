#!/usr/bin/env python3
"""Context injection hook cases. Pointed at a fake project so it touches no real state or log.

    python3 selftest_context.py [hook path] [--strict]

Once injection is deterministic, the injection itself can be tested - that is why a hook was chosen
over leaving it to LLM judgment, and this file is what actually verifies that claim.

It separates three things.
  routing    does it inject into the right target, and **does it not inject into the wrong one**.
           Over-injection is a bug too - context is a finite resource
  output     the form of `SubagentStart` is undocumented. Both forms and the fallback are run and
           only **whether all three are formally valid** is checked. Which one actually reaches a
           subagent this process cannot answer - the probe in a new session answers that
  names      do the agents and skills a context file names actually exist.
           Some names may not exist yet at this point, so the default is a **warning**,
           and only `--strict` fails

The fake directory names are chosen by this file. Using the real checkout's names would put
company information in here, and then it could not be tracked.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ARGS = [a for a in sys.argv[1:]]
STRICT = "--strict" in ARGS
ARGS = [a for a in ARGS if not a.startswith("--")]
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(HERE))
HOOK = ARGS[0] if ARGS else os.path.join(PROJECT, ".claude", "hooks",
                                         "context-inject.py")
if not os.path.isfile(HOOK):
    sys.exit(f"hook not found: {HOOK}")

results, skipped = [], []


def check(name, ok, detail="", secs=None):
    results.append(bool(ok))
    mark = "pass" if ok else "FAIL"
    t = f" {secs * 1000:6.1f}ms" if secs is not None else ""
    print(f"{len(results):>2} {name:<44} {mark}{t}"
          + (f"  {detail}" if detail and not ok else ""))


def skip(name, why):
    """A case that cannot be answered. **Not counted**, with the reason printed.

    Putting it in `results` skews the `N/M` that `selftest.py` reads and arrives as a failure,
    and then "could not measure" takes the same shape as "red". They are different facts.
    """
    skipped.append(name)
    print(f"{'':2} {name:<44} skipped  {why}")


# ------------------------------------------------------------------ the fake environment
BASE = tempfile.mkdtemp(prefix="ctxtest-")
PROJ = os.path.join(BASE, "proj")
CHECKOUT = os.path.join(BASE, "checkout")       # fake. The real name is never written here
BACKEND = os.path.join(BASE, "backend")
CTX = os.path.join(PROJ, ".claude", "context")
STATE = os.path.join(PROJ, ".claude", ".state")
CONFIG = os.path.join(PROJ, ".claude", "config", "workspace.json")
for d in (CTX, STATE, os.path.dirname(CONFIG),
          os.path.join(PROJ, ".claude", "agents"),
          os.path.join(CHECKOUT, "svc"), os.path.join(BACKEND, "mod")):
    os.makedirs(d, exist_ok=True)
SRC = os.path.join(CHECKOUT, "svc", "page.php")
open(SRC, "w").write("<?php echo 1;")
DOC = os.path.join(PROJ, "docs", "note.md")
os.makedirs(os.path.dirname(DOC), exist_ok=True)
open(DOC, "w").write("# note\n")
OUTSIDE = os.path.join(BASE, "elsewhere", "other.md")
os.makedirs(os.path.dirname(OUTSIDE), exist_ok=True)
open(OUTSIDE, "w").write("x\n")

json.dump({"legacy": {"root": CHECKOUT}, "backend": {"root": BACKEND}},
          open(CONFIG, "w"))


def ctxfile(name, kind, agents, skills, paths, token, tools=None, body=None,
            priority=None):
    lines = ["---", f"name: {name}", f"kind: {kind}", "inject:",
             f"  agents: [{', '.join(agents)}]",
             f"  skills: [{', '.join(skills)}]",
             "  paths: [" + ", ".join(f'"{p}"' for p in paths) + "]"]
    if tools:
        lines.append(f"  tools: [{', '.join(tools)}]")
    if priority is not None:
        lines.append(f"  priority: {priority}")
    lines += [f"token: {token}", "---", "", body or f"# {name}", "Body."]
    open(os.path.join(CTX, name + ".md"), "w",
         encoding="utf-8").write("\n".join(lines) + "\n")


ctxfile("alpha", "expertise", ["php-behavior-analyst"], ["php-legacy-io"], [],
        "CTX-T-ALPHA")
ctxfile("beta", "expertise", [], [], ["${legacy.root}/**"], "CTX-T-BETA")
ctxfile("gamma", "team", [], [], ["${project.root}/**"], "CTX-T-GAMMA",
        tools=["Write", "Edit"])
ctxfile("delta", "domain", ["domain-scribe"], [], ["${backend.root}/**"],
        "CTX-T-DELTA")


def run(payload, hook=HOOK, project=PROJ, timeout=60):
    t0 = time.time()
    p = subprocess.run([sys.executable, hook], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, "CLAUDE_PROJECT_DIR": project})
    return p, time.time() - t0


def tokens_in(proc):
    """The tokens carried in the output. Inside additionalContext for JSON, otherwise in plain text."""
    out = proc.stdout or ""
    text = out
    try:
        data = json.loads(out)
        text = (data.get("hookSpecificOutput") or {}).get("additionalContext", "")
        upd = (data.get("hookSpecificOutput") or {}).get("updatedInput")
        if isinstance(upd, dict):
            text += str(upd.get("prompt", ""))
    except ValueError:
        pass
    return {t for t in ("CTX-T-ALPHA", "CTX-T-BETA", "CTX-T-GAMMA",
                        "CTX-T-DELTA") if t in text}


def logs():
    p = os.path.join(STATE, "context-injections.jsonl")
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def reset():
    for n in ("context-injections.jsonl", "context-injected.json"):
        try:
            os.remove(os.path.join(STATE, n))
        except OSError:
            pass


def pre(tool, tool_input, sess="s1", **kw):
    return {"hook_event_name": "PreToolUse", "tool_name": tool,
            "tool_input": tool_input, "session_id": sess, "cwd": BASE, **kw}


def sub(agent_type, sess="s1", agent_id="a1"):
    return {"hook_event_name": "SubagentStart", "agent_type": agent_type,
            "agent_id": agent_id, "session_id": sess, "cwd": BASE}


print(f"{'':2} {'case':<44} verdict")
print("-" * 84)

# ---------------------------------------------------------------- 1. routing
reset()
p, s = run(sub("php-behavior-analyst"))
check("injects by agent name", tokens_in(p) == {"CTX-T-ALPHA"},
      f"got={tokens_in(p)} rc={p.returncode} err={p.stderr[:120]}", s)

reset()
p, s = run(sub("backend-builder"))
check("does not inject into an agent that is not a target", tokens_in(p) == set(),
      f"got={tokens_in(p)}", s)

reset()
p, s = run(pre("Skill", {"skill": "php-legacy-io"}))
check("injects by skill name", tokens_in(p) == {"CTX-T-ALPHA"}, f"got={tokens_in(p)}", s)

reset()
p, s = run(pre("Skill", {"skill": "plugin:php-legacy-io"}))
check("a skill name with a plugin prefix matches too", tokens_in(p) == {"CTX-T-ALPHA"},
      f"got={tokens_in(p)}", s)

reset()
p, s = run(pre("Skill", {"skill": "git-commit"}))
check("does not inject into a skill that is not a target", tokens_in(p) == set(), f"got={tokens_in(p)}", s)

reset()
p, s = run(pre("Read", {"file_path": SRC}))
check("injects by path glob (Read)", tokens_in(p) == {"CTX-T-BETA"},
      f"got={tokens_in(p)}", s)

reset()
p, s = run(pre("Bash", {"command": f"/bin/cat {SRC} | head -5"}))
check("injects on an absolute path inside a Bash command", tokens_in(p) == {"CTX-T-BETA"},
      f"got={tokens_in(p)}", s)

reset()
p, s = run(pre("Read", {"file_path": OUTSIDE}))
check("does not inject for a path outside the glob", tokens_in(p) == set(), f"got={tokens_in(p)}", s)

reset()
p, s = run(pre("Write", {"file_path": DOC, "content": "x"}))
check("tools restriction: Write passes", tokens_in(p) == {"CTX-T-GAMMA"},
      f"got={tokens_in(p)}", s)

reset()
p, s = run(pre("Read", {"file_path": DOC}))
check("tools restriction: Read does not match", tokens_in(p) == set(), f"got={tokens_in(p)}", s)

reset()
p, s = run(pre("Read", {"file_path": os.path.join(BACKEND, "mod", "A.kt")}))
check("${backend.root} substitution works too", tokens_in(p) == {"CTX-T-DELTA"},
      f"got={tokens_in(p)}", s)

# ---------------------------------------------------------------- 2. duplicate suppression
reset()
run(sub("php-behavior-analyst"))
p, s = run(sub("php-behavior-analyst"))
check("same session, same agent: the second is suppressed", tokens_in(p) == set(),
      f"got={tokens_in(p)}", s)

p, s = run(sub("php-behavior-analyst", agent_id="a2"))
check("injects again for a different subagent", tokens_in(p) == {"CTX-T-ALPHA"},
      f"got={tokens_in(p)}", s)

p, s = run(sub("php-behavior-analyst", sess="s2", agent_id="a1"))
check("injects again for a different session", tokens_in(p) == {"CTX-T-ALPHA"},
      f"got={tokens_in(p)}", s)

try:
    st = json.load(open(os.path.join(STATE, "context-injected.json"),
                        encoding="utf-8"))
    row = (st.get("__counts") or {}).get("s1") or {}
    ok = row.get("matched", 0) > row.get("injected", 0)
except Exception as exc:
    ok, row = False, repr(exc)
check("the suppressed count is aggregated into the state (ctxstats suppression rate)", ok, str(row))

# ---------------------------------------------------------------- 3. the log
reset()
run(sub("php-behavior-analyst"))
rows = logs()
want = {"ts", "session_id", "agent_id", "agent_type", "trigger", "tool",
        "file", "bytes"}
ok = len(rows) == 1 and want <= set(rows[0]) and rows[0]["trigger"] == "agent" \
    and rows[0]["file"] == "alpha.md" and rows[0]["bytes"] > 0
check("the injection log is written as JSONL", ok, str(rows[:1]))

reset()
run(pre("Read", {"file_path": SRC}))
rows = logs()
check("a path trigger records trigger=path", bool(rows) and rows[0]["trigger"] == "path",
      str(rows[:1]))

# ------------------------------------------------------- 4. no config / broken file
reset()
NOCFG = os.path.join(BASE, "nocfg")
shutil.copytree(PROJ, NOCFG, dirs_exist_ok=True)
os.remove(os.path.join(NOCFG, ".claude", "config", "workspace.json"))
p, s = run(pre("Read", {"file_path": SRC}), project=NOCFG)
ok = tokens_in(p) == set() and p.returncode == 0 and "workspace.json" in p.stderr
check("with no config only the path trigger switches off, and it says why", ok,
      f"rc={p.returncode} err={p.stderr[:100]!r}", s)

p, s = run(sub("php-behavior-analyst"), project=NOCFG)
check("the agent trigger works even with no config", tokens_in(p) == {"CTX-T-ALPHA"},
      f"got={tokens_in(p)} err={p.stderr[:100]!r}", s)

p2, _ = run(pre("Read", {"file_path": SRC}, sess="s9"), project=NOCFG)
p3, _ = run(pre("Read", {"file_path": SRC}, sess="s9"), project=NOCFG)
check("the config warning appears once per session", "workspace.json" in p2.stderr
      and "workspace.json" not in p3.stderr,
      f"2nd err={p3.stderr[:80]!r}")

BROKEN = os.path.join(CTX, "zbroken.md")
open(BROKEN, "w", encoding="utf-8").write("name: nope\ninject: {}\n")
reset()
p, s = run(sub("php-behavior-analyst"))
ok = p.returncode == 0 and tokens_in(p) == {"CTX-T-ALPHA"} and "zbroken" in p.stderr
check("a broken context file: the rest live and only the reason is stated", ok,
      f"rc={p.returncode} got={tokens_in(p)} err={p.stderr[:100]!r}", s)

c = subprocess.run([sys.executable, HOOK, "--check"], capture_output=True,
                   text=True, env={**os.environ, "CLAUDE_PROJECT_DIR": PROJ})
check("--check exits 2 on a frontmatter error",
      c.returncode == 2 and "zbroken.md" in c.stdout,
      f"rc={c.returncode} {c.stdout[:120]}")
os.remove(BROKEN)

# ---------------------------------------------------------------- 5. safety
reset()
p, s = run({"hook_event_name": "PreToolUse", "tool_name": "Read",
            "tool_input": "a string arrived here"})
check("exit 0 even when the tool input is not a dict", p.returncode == 0,
      f"rc={p.returncode}", s)

t0 = time.time()
raw = subprocess.run([sys.executable, HOOK], input="garbage input",
                     capture_output=True, text=True,
                     env={**os.environ, "CLAUDE_PROJECT_DIR": PROJ})
check("exit 0 even for input that is not JSON", raw.returncode == 0,
      f"rc={raw.returncode}", time.time() - t0)

reset()
# This case **measures the floor alongside.** The claim is "this hook does not spend more than 45ms
# on its own work", and the Python interpreter start-up is not the hook's work, so **it is subtracted.**
# It used to assert 60ms for the whole thing including start-up, and while `selftest.py` overlapped
# six case modules that intermittently hit 67ms and went red - the hook was unchanged, only the load differed.
#
# **An intermittently breaking check is worse than no check.** It teaches people to ignore failures,
# and then a real regression arrives as the same red. So rather than raising the threshold to make
# it quiet (weakening the measurement), **what is measured was narrowed to the hook's own share.**
#
# When the load is so heavy that even the floor wobbles, it says it cannot answer and skips. Taking
# the minimum of three runs is the same on both sides.
#
# Measured on a quiet machine: floor 22ms, whole 36ms, own 14ms against the 45ms budget. Under
# four concurrent agents it has been seen at own 139ms with the floor still under 50ms, so the
# skip guard did not fire and the case went red with the hook unchanged. **Do not widen the floor
# to cover reading the context files** - the hook reading them IS its own work, and subtracting it
# drops `own` to about 1ms, which is an assertion that can no longer fail. Re-run alone instead.
def _best(argv, payload=None):
    out = []
    for _ in range(3):
        t0 = time.time()
        subprocess.run(argv, input=payload, capture_output=True, text=True,
                       env={**os.environ, "CLAUDE_PROJECT_DIR": PROJ})
        out.append(time.time() - t0)
    return min(out)


floor = _best([sys.executable, "-c", "pass"])
best = _best([sys.executable, HOOK], json.dumps(sub("php-behavior-analyst")))
own = best - floor
if floor >= 0.05:
    skip("the hook's own share is within 45ms",
         f"an empty interpreter start alone is {floor*1000:.0f}ms - under this load the value "
         f"left after subtracting the floor cannot be trusted (whole {best*1000:.0f}ms)")
else:
    check("the hook's own share is within 45ms (floor subtracted · min of 3)",
          own < 0.045,
          f"own share {own*1000:.0f}ms = whole {best*1000:.0f}ms − floor {floor*1000:.0f}ms",
          best)

reset()
t0 = time.time()
off = subprocess.run([sys.executable, HOOK], input=json.dumps(
    sub("php-behavior-analyst")), capture_output=True, text=True,
    env={**os.environ, "CLAUDE_PROJECT_DIR": PROJ, "CONTEXT_INJECT_OFF": "1"})
ok = (off.returncode == 0 and tokens_in(off) == set()
      and "CONTEXT_INJECT_OFF" in off.stderr and not logs())
check("CONTEXT_INJECT_OFF: injects nothing and says so (the B of the A/B)", ok,
      f"rc={off.returncode} err={off.stderr[:80]!r}", time.time() - t0)

# ---------------------------------------------------------------- 6. output forms
reset()
p, s = run(sub("php-behavior-analyst"))
try:
    d = json.loads(p.stdout)
    ok = d["hookSpecificOutput"]["hookEventName"] == "SubagentStart" \
        and "CTX-T-ALPHA" in d["hookSpecificOutput"]["additionalContext"]
except Exception as exc:
    ok = False
    d = repr(exc)
check("the SubagentStart json form is valid", ok, str(d)[:120], s)

STDOUT_HOOK = os.path.join(BASE, "hook_stdout.py")
src = open(HOOK, encoding="utf-8").read()
open(STDOUT_HOOK, "w", encoding="utf-8").write(
    src.replace('SUBAGENT_OUTPUT = "json"', 'SUBAGENT_OUTPUT = "stdout"'))
reset()
p, s = run(sub("php-behavior-analyst"), hook=STDOUT_HOOK)
ok = p.stdout.lstrip().startswith("#") and "CTX-T-ALPHA" in p.stdout
check("the SubagentStart stdout form is implemented too", ok, p.stdout[:80], s)

TASK_HOOK = os.path.join(BASE, "hook_task.py")
open(TASK_HOOK, "w", encoding="utf-8").write(
    src.replace("TASK_FALLBACK = False", "TASK_FALLBACK = True"))
reset()
p, s = run(pre("Task", {"subagent_type": "php-behavior-analyst",
                        "prompt": "the original prompt", "description": "x"}),
           hook=TASK_HOOK)
try:
    d = json.loads(p.stdout)
    upd = d["hookSpecificOutput"]["updatedInput"]
    ok = (upd["prompt"].startswith("the original prompt")
          and "CTX-T-ALPHA" in upd["prompt"]
          and upd["description"] == "x"
          and upd["subagent_type"] == "php-behavior-analyst")
except Exception as exc:
    ok, upd = False, repr(exc)
check("the Task fallback returns the input whole", ok, str(upd)[:120], s)

reset()
p, s = run(pre("Task", {"subagent_type": "php-behavior-analyst",
                        "prompt": "the original prompt"}))
check("with the fallback off it does nothing to Task", p.stdout.strip() == "",
      p.stdout[:80], s)

# ------------------------------------------------------- 7. the real context files
real = subprocess.run([sys.executable, HOOK, "--check"], capture_output=True,
                      text=True, env={**os.environ, "CLAUDE_PROJECT_DIR": PROJECT})
check("the real .claude/context/ passes --check", real.returncode == 0,
      real.stdout[-300:] + real.stderr[-200:])

realdir = os.path.join(PROJECT, ".claude", "context")
files = sorted(f for f in os.listdir(realdir) if f.endswith(".md"))
# `len(files) >= 5` with seven present meant two could be deleted and this stayed green.
# Name them: each one is a shared judgment rule that some agent is deterministically given.
WANT_CONTEXT = {"backend-architecture.md", "equivalence-checks.md", "legacy-tree.md",
                "rules-contract.md", "silent-failure-catalog.md", "swap-point-shape.md",
                "team-boundary.md"}
check("every context file is present", WANT_CONTEXT <= set(files),
      f"missing {sorted(WANT_CONTEXT - set(files))}" if WANT_CONTEXT - set(files)
      else f"{len(files)} files")

long = []
for f in files:
    n = len(open(os.path.join(realdir, f), encoding="utf-8").read().splitlines())
    if n > 60:
        long.append(f"{f}:{n}")
check("each file is 60 lines or fewer", not long, " ".join(long))

hard = []
for f in files:
    text = open(os.path.join(realdir, f), encoding="utf-8").read()
    for line in text.splitlines():
        s2 = line.strip()
        if s2.startswith("paths:") and "${" not in s2 and s2 != "paths: []":
            hard.append(f"{f}: {s2[:40]}")
check("every path glob is a ${key} reference (no company information)", not hard, " ".join(hard))

# ------------------------------------------------- 8. name consistency (warn or fail)
agents_dir = os.path.join(PROJECT, ".claude", "agents")
skills_dir = os.path.join(PROJECT, ".claude", "skills")
have_agents = {os.path.splitext(f)[0] for f in os.listdir(agents_dir)
               if f.endswith(".md")} if os.path.isdir(agents_dir) else set()
have_skills = {n for n in (os.listdir(skills_dir) if os.path.isdir(skills_dir)
                           else [])
               if os.path.isfile(os.path.join(skills_dir, n, "SKILL.md"))}
missing = []
for f in files:
    text = open(os.path.join(realdir, f), encoding="utf-8").read()
    for key, have in (("agents", have_agents), ("skills", have_skills)):
        for line in text.splitlines():
            s2 = line.strip()
            if s2.startswith(key + ":") and "[" in s2:
                for n in s2.split("[", 1)[1].rstrip("]").split(","):
                    n = n.strip().strip("'\"")
                    if n and n.split(":")[-1] not in have:
                        missing.append(f"{f}→{key}:{n}")
if STRICT:
    check("every inject target name exists (--strict)", not missing,
          " ".join(missing))
else:
    print(f"{'':2} {'inject target name comparison':<44} "
          + ("all present" if not missing
             else f"{len(missing)} warnings: {' '.join(missing)}"))
    print("   (a missing name fails only under --strict - it may not be built yet)")

# ---------------------------------------------------------------- 9. ctxstats
CTXSTATS = os.path.join(HERE, "ctxstats")
if os.path.isfile(CTXSTATS):
    reset()
    run(sub("php-behavior-analyst"))
    run(pre("Read", {"file_path": SRC}))
    r = subprocess.run([sys.executable, CTXSTATS, "--config", CONFIG, "--all"],
                       capture_output=True, text=True)
    # `"agent" in r.stdout` was a fixed row label of the `by trigger` block, printed even when
    # that axis counted zero. Assert what the run actually produced.
    ok = (r.returncode == 0 and "alpha.md" in r.stdout and "beta.md" in r.stdout
          and "2 injections" in r.stdout and "php-behavior-analyst" in r.stdout)
    check("ctxstats --config reads the fake project", ok,
          r.stdout[-200:] + r.stderr[-120:])
    r = subprocess.run([sys.executable, CTXSTATS, "--config", CONFIG, "--all",
                        "--probe"], capture_output=True, text=True)
    ok = r.returncode == 0 and "CTX-T-ALPHA" in r.stdout
    check("ctxstats --probe prints the tokens to ask about", ok,
          r.stdout[-200:] + r.stderr[-120:])

    # The probe comparison takes "everything injected" as its expectation. So these two cases are
    # measured with only the agent trigger left - a leftover path injection showing up as
    # unconfirmed is not a bug but what this tool does.
    reset()
    run(sub("php-behavior-analyst"))
    probe = os.path.join(STATE, "context-probe.jsonl")
    sid = [x["session_id"] for x in logs() if x.get("trigger") == "agent"][0]
    open(probe, "w", encoding="utf-8").write(json.dumps(
        {"session": sid, "agent_type": "php-behavior-analyst",
         "reported": ["CTX-T-ALPHA"]}, ensure_ascii=False) + "\n")
    r = subprocess.run([sys.executable, CTXSTATS, "--config", CONFIG, "--all",
                        "--probe"], capture_output=True, text=True)
    check("a reported token matching the expectation is confirmed · exit 0",
          r.returncode == 0 and "confirmed" in r.stdout and "unconfirmed" not in r.stdout,
          f"rc={r.returncode} {r.stdout[-200:]}")

    open(probe, "w", encoding="utf-8").write(json.dumps(
        {"session": sid, "agent_type": "php-behavior-analyst",
         "reported": ["CTX-NOSUCHTOKEN"]}, ensure_ascii=False) + "\n")
    r = subprocess.run([sys.executable, CTXSTATS, "--config", CONFIG, "--all",
                        "--probe"], capture_output=True, text=True)
    check("a mismatched report is unconfirmed and a mismatch, exit 1",
          r.returncode == 1 and "unconfirmed" in r.stdout and "mismatch" in r.stdout,
          f"rc={r.returncode} {r.stdout[-200:]}")
    os.remove(probe)
else:
    check("ctxstats exists", False, CTXSTATS)

# ------------------------------------------------- 10. budget and priority
# **What survives** when the budget overflows. Leaving the packing order to filenames makes the
# alphabet the policy, and the last in that order happened to be the public-repository boundary
# file. So here the budget is actually overflowed - the happy path never walks this defect.
def injected_text(proc):
    out = proc.stdout or ""
    try:
        return (json.loads(out).get("hookSpecificOutput")
                or {}).get("additionalContext", "")
    except ValueError:
        return out


BIG = ("Body text to fill the budget. " * 47 + "\n") * 10     # ~14KB: one fits in the
# 24KB budget and two do not. Sized against MAX_INJECT_BYTES on purpose - shrink it and this
# case stops overflowing, which turns the check green while testing nothing.
# One fits in the budget and two do not - the same condition as the real shape (the sum of six
# small files). Overflowing with a single file would only walk the "always pack the first item"
# branch and never the priority comparison.
ctxfile("ya-big", "expertise", ["budget-probe"], [], [], "CTX-T-BIG", body=BIG)
ctxfile("zz-keep", "team", ["budget-probe"], [], [], "CTX-T-KEEP", body=BIG,
        priority=0)
reset()
p, s = run(sub("budget-probe", agent_id="b1"))
text = injected_text(p)
check("budget overflow: the higher priority survives",
      "CTX-T-KEEP" in text and "CTX-T-BIG" not in text,
      f"len={len(text)} err={p.stderr[:100]!r}", s)
check("the cut file names stay inside the injected block",
      "ya-big.md" in text and "budget" in text, text[:200])
check("the injection log records only the files that were packed",
      [r["file"] for r in logs()] == ["zz-keep.md"], str([r["file"] for r in logs()]))

# A file whose frontmatter could not be read is, on the receiving side, indistinguishable from a file that never comes.
ctxfile("zprio", "expertise", ["budget-probe"], [], [], "CTX-T-PRIO",
        priority="high")
reset()
p, s = run(sub("budget-probe", agent_id="b2"))
text = injected_text(p)
check("a non-integer priority is recorded in the block too",
      "zprio" in text and "CTX-T-KEEP" in text,
      f"err={p.stderr[:120]!r} text={text[:120]!r}", s)
c = subprocess.run([sys.executable, HOOK, "--check"], capture_output=True,
                   text=True, env={**os.environ, "CLAUDE_PROJECT_DIR": PROJ})
check("a non-integer priority makes --check exit 2",
      c.returncode == 2 and "priority" in c.stdout, f"rc={c.returncode} {c.stdout[:160]}")
for n in ("ya-big", "zz-keep", "zprio"):
    os.remove(os.path.join(CTX, n + ".md"))

# Fixing only the hook without giving the real files a priority changes nothing.
prios = {}
for f in files:
    prios[f] = 50
    for line in open(os.path.join(realdir, f), encoding="utf-8").read().splitlines():
        s2 = line.strip()
        if s2.startswith("priority:"):
            prios[f] = int(s2.split(":", 1)[1].split("#")[0].strip())
lowest = min(prios.values())
check("the real boundary file uniquely holds the highest priority",
      prios.get("team-boundary.md") == lowest
      and sum(1 for v in prios.values() if v == lowest) == 1, str(prios))

shutil.rmtree(BASE, ignore_errors=True)
print("-" * 84)
passed = sum(results)
if skipped:
    print(f"skipped {len(skipped)} - " + ", ".join(skipped))
print(f"{passed}/{len(results)} pass")
sys.exit(0 if passed == len(results) else 1)
