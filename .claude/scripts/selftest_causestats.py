#!/usr/bin/env python3
"""causestats cases. Synthetic page directories only - no company tree, no config, no stack.

    python3 selftest_causestats.py [path to causestats]

Two kinds of fixture, and the difference between them is the point.

1. **One page built by running `pagecheck --round` for real.** The record format is a contract
   between two tools, and a fixture that hand-writes `state.json` proves only that this file
   agrees with itself. This one reproduces the worked example in the design canon - the second
   page's ten L2 rounds - so the numbers below are checked against a figure a person computed
   separately: 7/10, two repeated causes, no `기타`.
2. **Hand-written `state.json` documents** for the shapes `pagecheck` cannot easily produce:
   a record that is all `기타`, a cause written in by hand that is outside the vocabulary, a
   round line belonging to no loop, a broken file.

**What is checked is the arithmetic and the refusal to round it off.** In particular that a
denominator of zero is reported as uncomputable rather than as 0% or 100%: that state is exactly
what the vocabulary's escape hatch would produce if it paid off, so printing a number there would
be printing the reward.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "causestats")
PAGECHECK = os.path.join(HERE, "pagecheck")
if not os.path.isfile(TOOL):
    sys.exit(f"usage: selftest_causestats.py [path to causestats]  (looked at: {TOOL})")

BASE = tempfile.mkdtemp(prefix="causestats-selftest-")
ENVIRON = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
results, skipped = [], []


def check(name, ok, detail="", secs=None):
    results.append((name, ok, detail))
    t = f"  {secs:5.1f}s" if secs is not None else "        "
    print(f"  {'pass' if ok else 'FAIL'}{t}  {name}" + (f"   {detail}" if detail else ""))


def skip(name, why):
    skipped.append((name, why))
    print(f"  skipped      {name}   ({why})")


def run(args, timeout=120):
    t0 = time.time()
    p = subprocess.run([sys.executable, TOOL] + args, capture_output=True, text=True,
                       timeout=timeout, cwd=BASE, env=ENVIRON)
    return p, time.time() - t0


def pagecheck(args, timeout=120):
    return subprocess.run([sys.executable, PAGECHECK] + args, capture_output=True,
                          text=True, timeout=timeout, cwd=BASE, env=ENVIRON)


def tree(name):
    d = os.path.join(BASE, name, "pages")
    os.makedirs(d, exist_ok=True)
    return d


def write_state(pages, page, doc):
    d = os.path.join(pages, page)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "state.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    return d


def state(rounds, loops=None, caps=None, page="demo_page"):
    """A `state.json` of the shape `pagecheck` writes. `rounds` is (loop, n, cause, sentence)."""
    return {"page": page, "loops": loops or {"L1": {"n": len(rounds), "cap": 20}},
            "checks": {}, "cap_changes": caps or [],
            "rounds": [{"n": n, "loop": lp, "stage": None, "verdict": "counted",
                        "at": "2026-09-15T00:00:00+09:00", "note": c, "why": w}
                       for lp, n, c, w in rounds]}


def tail(p, n=110):
    """The last of a report, flattened. A multi-line detail turns the log into the output it is
    reporting on, and then nobody reads either."""
    return (p.stdout + p.stderr).strip().replace("\n", " | ")[-n:]


def as_json(args):
    p, _ = run(args + ["--json"])
    try:
        return p, json.loads(p.stdout)
    except ValueError:
        return p, None


print(f"# tool {TOOL}")

# ------------------------------------------------------------ 1. the worked example
# The design canon computes this one by hand: 환경 2 · OS결함 3 · 확인만 2 · 이관결함 3, no 기타,
# so the denominator is 10 and the first metric is 7/10. The prose retrospective of the same ten
# rounds said "about half", and the first draft of the canon's own paragraph counted three
# repeated causes instead of two. Both were written while looking at the table. That is why the
# arithmetic is a tool's job, and why this case exists.
print("\n### 1. the worked example from the design canon, built by running pagecheck")

PAGES = tree("canon")
d = os.path.join(PAGES, "demo")
r = pagecheck([d, "--init", "--page", "demo_page", "--cap", "L1=20"])
r = pagecheck([d, "--round", "L1"])                       # the first round carries no cause
built = r.returncode == 0
for cause in ("환경", "환경", "OS결함", "OS결함", "OS결함", "확인만", "확인만",
              "이관결함", "이관결함", "이관결함"):
    r = pagecheck([d, "--round", "L1", "--note", cause])
    built = built and r.returncode == 0
check("ten rounds went in through pagecheck", built,
      "" if built else (r.stdout + r.stderr).strip()[-120:])

p, doc = as_json(["--pages", PAGES])
check("--json is valid JSON", doc is not None, p.stdout[-120:] if doc is None else "")
if doc:
    m = doc["metrics"]["migration_unrelated"]
    check("the first metric is 7/10 - the figure the canon computes by hand",
          m["numerator"] == 7 and m["denominator"] == 10 and abs(m["ratio"] - 0.7) < 1e-9,
          str(m))
    check("the first round carries no cause and is not an extra round",
          doc["extra_rounds"] == 10, f"{doc['extra_rounds']} extra rounds")
    check("two causes reached three, and the one with two did not",
          doc["metrics"]["repeated_causes"] == 2
          and {r["cause"] for r in doc["repeated"]} == {"OS결함", "이관결함"},
          str([(r["cause"], r["count"]) for r in doc["repeated"]]))
    check("a cause with two rounds is below the threshold, not absent from the count",
          doc["by_cause"].get("환경") == 2, str(doc["by_cause"]))
    check("`기타` share is 0 of 10", doc["metrics"]["other_share"]["numerator"] == 0
          and doc["metrics"]["other_share"]["denominator"] == 10,
          str(doc["metrics"]["other_share"]))

p, _ = run(["--pages", PAGES])
_ok = (p.returncode == 0 and "7/10" in p.stdout and "OS결함" in p.stdout
       and "repeated causes" in p.stdout)
check("the report prints the metric, the repeated causes and the threshold", _ok,
      "" if _ok else tail(p))
_ok = ("cap changes" in p.stdout and "L1 5 → 20" in p.stdout and "(at --init)" in p.stdout)
check("a cap raised at --init is reported, and apart from the rounds", _ok,
      "" if _ok else tail(p))

# ------------------------------------------------------------ 2. all 기타 → uncomputable
# The escape hatch must not pay. With no upper layer anywhere the first metric has no denominator,
# and the only honest report is that it cannot be computed - 0% would read as "nothing was
# unrelated to the migration" and 100% as the opposite, and both are inventions.
print("\n### 2. a record that is all `기타`")

PAGES = tree("other")
write_state(PAGES, "demo", state([("L1", 1, "", ""), ("L1", 2, "기타", "맞는 칸이 없다"),
                                  ("L1", 3, "기타", "여기도 없다"),
                                  ("L1", 4, "기타", "또 없다")]))
p, doc = as_json(["--pages", PAGES])
check("the first metric is null, not 0 and not 1",
      doc and doc["metrics"]["migration_unrelated"]["ratio"] is None
      and doc["metrics"]["migration_unrelated"]["denominator"] == 0,
      str(doc["metrics"]["migration_unrelated"]) if doc else p.stdout[-100:])
check("it says why it cannot be computed",
      bool(doc) and "upper layer" in (doc["metrics"]["migration_unrelated"]["why"] or ""),
      str(doc["metrics"]["migration_unrelated"]["why"]) if doc else "")
p, _ = run(["--pages", PAGES])
_ok = ("migration-unrelated rounds   not computable" in p.stdout
       and "0.0%   lower" not in p.stdout and "100.0%   lower" not in p.stdout)
check("the printed report says not computable, and prints no 0% or 100% in its place", _ok,
      "" if _ok else tail(p))
check("`기타` reaching three is reported as the vocabulary asking for a word",
      "asking for a new word" in p.stdout, "" if "asking for a new word" in p.stdout else tail(p))
check("`기타` share is still computed - it is the measure of the vocabulary itself",
      bool(doc) and doc["metrics"]["other_share"]["numerator"] == 3, "")

# ------------------------------------------------------------ 3. what is not an extra round
print("\n### 3. what does not count as an extra round")

PAGES = tree("shape")
write_state(PAGES, "demo", state([("L1", 1, "환경", "a first round may carry one"),
                                  ("", None, "환경", "a stage that spends no loop"),
                                  ("L1", 2, "환경", "this is the only extra round")]))
p, doc = as_json(["--pages", PAGES])
_ok = bool(doc) and doc["extra_rounds"] == 1 and doc["first_round_notes"] == 1
check("a first-round cause is not counted as an extra round", _ok,
      "" if _ok else str(doc and (doc["extra_rounds"], doc["first_round_notes"])))
check("a line belonging to no loop is not counted either",
      doc and doc["by_cause"].get("환경") == 1, str(doc["by_cause"]) if doc else "")
p, _ = run(["--pages", PAGES])
check("the dropped first-round notes are said out loud, not dropped in silence",
      "first-round notes" in p.stdout, "" if "first-round notes" in p.stdout else tail(p))

# ------------------------------------------------------------ 4. hand-written records
print("\n### 4. a record written by hand rather than by pagecheck")

PAGES = tree("byhand")
write_state(PAGES, "demo", state([("L1", 2, "그냥", "written straight into the file")]))
p, doc = as_json(["--pages", PAGES])
check("a cause outside the vocabulary is counted and named, not dropped",
      doc and doc["unknown_causes"].get("그냥") == 1, str(doc["unknown_causes"]) if doc else "")
p, _ = run(["--pages", PAGES])
check("the report marks it as outside the vocabulary",
      "outside the vocabulary" in p.stdout,
      "" if "outside the vocabulary" in p.stdout else tail(p))

PAGES = tree("broken")
write_state(PAGES, "good", state([("L1", 2, "환경", "")]))
os.makedirs(os.path.join(PAGES, "bad"), exist_ok=True)
with open(os.path.join(PAGES, "bad", "state.json"), "w", encoding="utf-8") as fh:
    fh.write("{ this is not json")
p, _ = run(["--pages", PAGES])
_ok = p.returncode == 0 and "unreadable state.json" in p.stdout and "bad" in p.stdout
check("an unreadable state.json is named rather than passed over", _ok,
      "" if _ok else tail(p))
p, doc = as_json(["--pages", PAGES])
check("the readable pages are still counted", doc and doc["extra_rounds"] == 1,
      str(doc["extra_rounds"]) if doc else "")

# ------------------------------------------------------------ 5. several pages
print("\n### 5. several pages, and a cap changed mid-run")

PAGES = tree("many")
write_state(PAGES, "one", state([("L1", 2, "OS결함", ""), ("L1", 3, "OS결함", "")]))
write_state(PAGES, "two", state(
    [("L2", 2, "OS결함", "")],
    loops={"L2": {"n": 2, "cap": 9}},
    caps=[{"at": "2026-09-15T01:00:00+09:00", "loop": "L2", "from": 5, "to": 9,
           "why": "", "at_init": False}]))
p, doc = as_json(["--pages", PAGES])
check("three of the same cause across two pages reaches the threshold",
      doc and doc["metrics"]["repeated_causes"] == 1
      and doc["repeated"][0]["count"] == 3
      and doc["repeated"][0]["pages"] == {"one": 2, "two": 1},
      str(doc["repeated"]) if doc else "")
check("the repeated cause carries which loop it was spent on",
      doc and doc["repeated"][0]["loops"] == {"L1": 2, "L2": 1},
      str(doc["repeated"][0]["loops"]) if doc else "")
p, _ = run(["--pages", PAGES])
_ok = ("L2 5 → 9" in p.stdout and "(no reason given)" in p.stdout
       and "(at --init)" not in p.stdout)
check("a cap changed mid-run is reported, and its missing reason is visible", _ok,
      "" if _ok else tail(p))

# ------------------------------------------------------------ 6. nothing to report
print("\n### 6. an empty tree is not a clean tree")

PAGES = tree("empty")
p, _ = run(["--pages", PAGES])
_ok = p.returncode == 0 and "no state.json" in p.stdout and "0.0%" not in p.stdout
check("no page at all says so, rather than printing zeros", _ok, "" if _ok else tail(p))

PAGES = tree("nocause")
write_state(PAGES, "demo", state([("L1", 1, "", "")]))
p, doc = as_json(["--pages", PAGES])
_ok = bool(doc) and doc["extra_rounds"] == 0 and doc["metrics"]["other_share"]["ratio"] is None
check("a page whose loops never turned twice reports no cause, not a zero rate", _ok,
      "" if _ok else str(doc and doc["metrics"]))

# ------------------------------------------------------------ 7. config and usage
print("\n### 7. the config - a missing key names the key")

cfg = os.path.join(BASE, "nokey.json")
with open(cfg, "w", encoding="utf-8") as fh:
    json.dump({"docs": {"root": BASE}}, fh)
p, _ = run(["--config", cfg])
check("a missing docs.pagesDir is exit 3 and names the key",
      p.returncode == 3 and "docs.pagesDir" in p.stderr, f"exit={p.returncode}")

cfg2 = os.path.join(BASE, "noroot.json")
with open(cfg2, "w", encoding="utf-8") as fh:
    json.dump({"docs": {"pagesDir": "pages"}}, fh)
p, _ = run(["--config", cfg2])
check("a missing docs.root is exit 3 and names the key",
      p.returncode == 3 and "docs.root" in p.stderr, f"exit={p.returncode}")

cfg3 = os.path.join(BASE, "skeleton.json")
with open(cfg3, "w", encoding="utf-8") as fh:
    json.dump({"docs": {"root": "<abs path>", "pagesDir": "pages"}}, fh)
p, _ = run(["--config", cfg3])
check("a key still holding the skeleton placeholder is refused as a missing one",
      p.returncode == 3 and "docs.root" in p.stderr, f"exit={p.returncode}")

os.makedirs(os.path.join(BASE, "real", "pages", "demo"), exist_ok=True)
write_state(os.path.join(BASE, "real", "pages"), "demo",
            state([("L1", 2, "설계결함", "")]))
cfg4 = os.path.join(BASE, "real.json")
with open(cfg4, "w", encoding="utf-8") as fh:
    json.dump({"docs": {"root": os.path.join(BASE, "real"), "pagesDir": "pages"}}, fh)
p, doc = as_json(["--config", cfg4])
check("with both keys it reads the configured directory",
      doc and doc["extra_rounds"] == 1 and doc["by_upper"].get("이관") == 1,
      str(doc.get("by_upper")) if doc else p.stderr[-100:])

p, _ = run(["--nosuchopt"])
check("an unknown option is exit 2, not a run with a default",
      p.returncode == 2 and "unknown option" in p.stderr, f"exit={p.returncode}")

# ------------------------------------------------------------ wrap-up
shutil.rmtree(BASE, ignore_errors=True)
print("\n" + "=" * 64)
bad = [n for n, ok, _ in results if not ok]
print(f"{len(results) - len(bad)}/{len(results)} pass"
      + ("" if not bad else "   failed: " + ", ".join(bad)))
if skipped:
    print(f"skipped {len(skipped)} - " + ", ".join(n for n, _ in skipped))
    print("  a skipped check is not a pass.")
sys.exit(1 if bad else 0)
