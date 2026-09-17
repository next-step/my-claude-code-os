#!/usr/bin/env python3
"""ctxevolve checks - runs on synthetic records only. It requires no company tree.

Walking the failure paths is the purpose of this file. Checking only the happy path leaves nobody
watching the case where this tool goes quietly empty - the defect this repository has fixed again and again.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "ctxevolve")
ok = fail = 0


def run(args, cwd=None):
    p = subprocess.run([sys.executable, TOOL] + args, capture_output=True, text=True, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def case(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  pass   {name}   {detail}")
    else:
        fail += 1
        print(f"  FAIL   {name}   {detail}")


def jl(d, role, rows):
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{role}.jsonl"), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def item(**kw):
    base = {"ts": "2026-09-11T00:00:00+09:00", "page": "p1", "role": "php-behavior-analyst",
            "lesson": "L", "trigger": "T", "evidence": ".claude/context/rules-contract.md:1",
            "scope": "global"}
    base.update(kw)
    return base


print("### 1. the form check catches failures")
with tempfile.TemporaryDirectory() as td:
    d = os.path.join(td, "area")
    jl(d, "php-behavior-analyst", [
        item(),
        item(evidence=""),
        item(trigger=""),
        item(scope="everywhere"),
        item(role=""),
    ])
    open(os.path.join(d, "php-behavior-analyst.jsonl"), "a", encoding="utf-8").write("{not json\n")
    rc, out = run(["--check", "--record-dir", d])
    case("an entry with no evidence is caught as FAIL", "missing fields" in out and "evidence" in out)
    case("an entry with no trigger is caught as FAIL", out.count("missing fields") >= 2)
    case("a scope outside the vocabulary is caught as FAIL", "scope is" in out)
    case("an entry with no role is caught as FAIL", "no role" in out)
    case("a broken JSON line is not passed over in silence", "not JSON" in out)
    case("a failure means exit 1", rc == 1, f"exit={rc}")

print("\n### 2. one broken line leaves the rest alive")
with tempfile.TemporaryDirectory() as td:
    d = os.path.join(td, "area")
    jl(d, "php-behavior-analyst", [item(lesson="a living entry")])
    open(os.path.join(d, "php-behavior-analyst.jsonl"), "a", encoding="utf-8").write("{broken\n")
    rc, out = run(["--propose", "--record-dir", d])
    case("a valid entry after a broken line still becomes a candidate", "a living entry" in out)

print("\n### 3. scope decides how far it propagates")
with tempfile.TemporaryDirectory() as td:
    d = os.path.join(td, "area")
    jl(d, "php-behavior-analyst", [
        item(lesson="a global lesson", scope="global"),
        item(lesson="a surface lesson", scope="surface"),
        item(lesson="an area lesson", scope="area"),
    ])
    rc, out = run(["--propose", "--record-dir", d])
    case("only global becomes a candidate", "a global lesson" in out and "a surface lesson" not in out and "an area lesson" not in out)
    case("it states the candidate count", "1 candidates" in out)

print("\n### 4. an entry whose evidence is gone is not a candidate")
with tempfile.TemporaryDirectory() as td:
    d = os.path.join(td, "area")
    jl(d, "php-behavior-analyst", [
        item(lesson="living evidence"),
        item(lesson="dead evidence", evidence="no-such-evidence.md:12"),
    ])
    rc, out = run(["--stale", "--propose", "--record-dir", d])
    case("it marks it an expiry candidate", "expiry candidate" in out and "no-such-evidence.md" in out)
    case("it drops it from the revision candidates", "excluded:" in out and "1 candidates" in out)
    case("it says why it dropped it", "evidence is gone" in out)

print("\n### 5. it applies nothing")
with tempfile.TemporaryDirectory() as td:
    d = os.path.join(td, "area")
    jl(d, "php-behavior-analyst", [item()])
    target = os.path.join(HERE, "..", "context", "rules-contract.md")
    before = open(target, "rb").read()
    rc, out = run(["--propose", "--record-dir", d])
    case("it does not edit the context file", open(target, "rb").read() == before)
    case("it says nothing was applied", "Nothing was applied" in out)
    case("it says to decide what to delete", "replaces" in out)

print("\n### 6. it separates could-not-find from there-is-none")
with tempfile.TemporaryDirectory() as td:
    rc, out = run(["--check", "--record-dir", os.path.join(td, "nosuchdir")])
    case("a missing record directory stops with exit 3", rc == 3, f"exit={rc}")
    case("it says what is missing", "no record directory" in out)
    d = os.path.join(td, "area")
    os.makedirs(d)
    rc, out = run(["--propose", "--record-dir", d])
    case("an empty record says 'no entry' (told apart from zero candidates)", "no entry" in out, f"exit={rc}")

print("\n### 7. called with no argument, usage and exit 2")
rc, out = run([])
case("no argument is exit 2", rc == 2, f"exit={rc}")
case("it prints usage", "--propose" in out)

print("\n" + "-" * 70)
print(f"{ok}/{ok + fail} pass")
sys.exit(0 if fail == 0 else 1)
