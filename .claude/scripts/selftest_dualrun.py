#!/usr/bin/env python3
"""dualrun-report cases. With synthetic JSONL, and with the real PHP helper where available.

    python3 selftest_dualrun.py [path to dualrun-report] [path to MigrationExperiment.php]

A synthetic log alone exercises the aggregation, the exit codes and the ignore matching. But a
synthetic log proves **only that we understood the schema correctly**. Whether the helper really
writes that schema can only be known by running it, so when php is present locally the template
is actually executed and the resulting log joins the same cases. Without php that case is marked
'skipped' - a skipped check is not a pass.

This file never reads the real workspace.json. It writes a synthetic config and passes it with `--config`.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "dualrun-report")
TEMPLATE = (sys.argv[2] if len(sys.argv) > 2
            else os.path.join(os.path.dirname(HERE), "templates",
                              "MigrationExperiment.php"))
if not os.path.isfile(TOOL):
    sys.exit(f"usage: selftest_dualrun.py [path to dualrun-report]  (looked at: {TOOL})")

BASE = tempfile.mkdtemp(prefix="dualrun-selftest-")
results, skipped = [], []


def check(name, ok, detail="", secs=None):
    results.append((name, ok, detail))
    t = f"  {secs:5.1f}s" if secs is not None else "        "
    print(f"  {'pass' if ok else 'FAIL'}{t}  {name}" + (f"   {detail}" if detail else ""))


def skip(name, why):
    skipped.append((name, why))
    print(f"  skipped      {name}   ({why})")


def run(args, timeout=60):
    t0 = time.time()
    p = subprocess.run([sys.executable, TOOL] + args, capture_output=True, text=True,
                       timeout=timeout, cwd=BASE)
    return p, time.time() - t0


def row(experiment="list-page", equal=True, diff=None, control=None, candidate=None,
        ts="2026-09-08T12:00:00+09:00", **extra):
    rec = {"ts": ts, "experiment": experiment, "mode": "dual",
           "input": {"page": 1}, "control_sha": "a" * 8, "candidate_sha": "b" * 8,
           "equal": equal, "diff_keys": diff or [], "ignored_keys": [],
           "truncated": False, "control_ms": 12, "candidate_ms": 40,
           "page": "/<page>.php", "caller": "<page>.php:42"}
    if not equal:
        rec["control"] = control if control is not None else {"total": 120}
        rec["candidate"] = candidate if candidate is not None else {"total": 7}
    rec.update(extra)
    return json.dumps(rec, ensure_ascii=False)


def log(name, lines):
    path = os.path.join(BASE, f"{name}.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(l + "\n" for l in lines))
    return path


def ignore_file(name, rules):
    path = os.path.join(BASE, f"ignore-{name}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"rules": rules}, fh, ensure_ascii=False)
    return path


CONFIG = os.path.join(BASE, "workspace.json")
DEFAULT_LOG = log("configured", [row(), row(equal=False, diff=["total"])])
with open(CONFIG, "w", encoding="utf-8") as fh:
    json.dump({"legacy": {"dualRun": {"logPath": DEFAULT_LOG,
                                      "logEnvVar": "MIGRATION_EXPERIMENT_LOG"}}}, fh)
EMPTY_CONFIG = os.path.join(BASE, "workspace-empty.json")
with open(EMPTY_CONFIG, "w", encoding="utf-8") as fh:
    json.dump({"legacy": {}}, fh)

print(f"# tool {TOOL}")
print("\n### 1. aggregation and exit codes")

lg = log("equal", [row(), row(), row()])
p, secs = run(["--log", lg])
check("all equal is exit 0 and it says 'no unexpected'",
      p.returncode == 0 and "No unexpected mismatches" in p.stdout,
      f"exit={p.returncode}", secs=secs)

lg = log("unexpected", [row(), row(equal=False, diff=["total"]),
                        row(equal=False, diff=["total"]),
                        row(equal=False, diff=["items[0].title", "total"])])
p, _ = run(["--log", lg])
check("an unexpected mismatch is exit 1",
      p.returncode == 1, f"exit={p.returncode}")
check("it groups by diff_keys signature and reports two (2 signatures, not 4 hits)",
      "2 diff_keys signatures" in p.stdout
      and len([l for l in p.stdout.splitlines() if l.startswith(" [")]) == 2,
      [l for l in p.stdout.splitlines() if "signature" in l][:1])
check("it counts hits per signature (2 under the same signature)",
      "list-page  2 hits" in p.stdout,
      [l.strip() for l in p.stdout.splitlines() if "hits" in l][:2])

ig = ignore_file("total", [{"experiment": "list-page", "keys": ["total"],
                            "rules": "R-17", "reason": "의도수정: corrected the default-value defect"}])
p, _ = run(["--log", lg, "--ignore", ig])
check("a mismatch covered by ignore drops out as 'expected', leaving the rest",
      p.returncode == 1 and "1 diff_keys signatures" in p.stdout, f"exit={p.returncode}")
check("a partially covered mismatch carries the rule-row hint",
      "R-17" in p.stdout, "" if "R-17" in p.stdout else "no hint")

ig2 = ignore_file("both", [{"experiment": "list-page",
                            "keys": ["total", "items[].title"], "rules": "R-17",
                            "reason": "의도수정"}])
p, _ = run(["--log", lg, "--ignore", ig2])
check("the array-index wildcard works (items[].title covers items[0].title)",
      p.returncode == 0 and "No unexpected mismatches" in p.stdout, f"exit={p.returncode}")

lg_other = log("other", [row(experiment="detail-page", equal=False, diff=["body"]),
                         row(experiment="list-page", equal=False, diff=["total"])])
p, _ = run(["--log", lg_other, "--ignore", ig])
check("an ignore entry's experiment does not cover another experiment",
      p.returncode == 1 and "detail-page" in p.stdout and "1 diff_keys signatures" in p.stdout,
      f"exit={p.returncode}")

print("\n### 2. truncation, errors and filters")

lg = log("trunc", [row(equal=False, diff=["items"], truncated=True,
                       control=None, candidate=None)])
p, _ = run(["--log", lg])
out_trunc = "\n".join(l for l in p.stdout.splitlines() if "truncated" in l)
check("a truncated row shows only the sha, no body, and the truncation count",
      p.returncode == 1 and "(truncated - sha only, no body: " in p.stdout
      and '"total": 120' not in p.stdout,
      out_trunc.strip()[:70])

lg = log("boom", [json.dumps({"ts": "2026-09-08T12:00:00+09:00",
                              "experiment": "detail-page", "mode": "dual",
                              "input": {"seq": 9}, "equal": False, "diff_keys": [],
                              "candidate_error": {"class": "RuntimeException",
                                                  "message": "backend said no"}},
                             ensure_ascii=False)])
p, _ = run(["--log", lg])
check("a candidate error stays unexpected (empty diff_keys never passes in silence)",
      p.returncode == 1 and "RuntimeException" in p.stdout, f"exit={p.returncode}")

lg = log("filter", [row(ts="2026-09-01T00:00:00+09:00", equal=False, diff=["old"]),
                    row(ts="2026-09-08T12:00:00+09:00", equal=False, diff=["new"])])
p, _ = run(["--log", lg, "--since", "2026-09-05T00:00:00+09:00"])
# Read it from the signature line. A temp directory path appears in the report and may contain 'old'.
check("--since filters out the lines before it",
      p.returncode == 1 and "signature: new" in p.stdout and "signature: old" not in p.stdout,
      f"exit={p.returncode} filtered " + ("1" if "filtered 1" in p.stdout else "?"))
p, _ = run(["--log", lg, "--since", "yesterday"])
check("an unreadable --since is exit 2",
      p.returncode == 2 and "ISO" in p.stderr, f"exit={p.returncode}")
p, _ = run(["--log", lg, "--since", "2030-01-01T00:00:00+09:00"])
check("no line left after filtering is exit 2 - zero and 'could not read' differ",
      p.returncode == 2 and "not one line matched" in p.stderr, f"exit={p.returncode}")

p, _ = run(["--log", lg_other, "--experiment", "detail-page"])
check("--experiment leaves one experiment only",
      p.returncode == 1 and "list-page" not in p.stdout, f"exit={p.returncode}")

print("\n### 3. when it cannot read")

lg = log("broken", [row(), "{this is not JSON", row(equal=False, diff=["total"]),
                    json.dumps({"ts": "x", "mode": "dual"})])
p, _ = run(["--log", lg])
check("a broken line is exit 2 and it names the line number",
      p.returncode == 2 and "[2]" in p.stderr and "[4]" in p.stderr,
      p.stderr.strip().splitlines()[-1][:80] if p.stderr else "")
# `"experiment" in p.stdout` was the table's column header, which prints even when every line
# failed to parse - the exact state this case exists to rule out. Assert the counts instead.
check("it still emits the report for what it did read",
      "lines 4 · counted 2" in p.stdout and "signature: total" in p.stdout,
      "" if "signature: total" in p.stdout else "the report vanished entirely")

p, _ = run(["--log", os.path.join(BASE, "nosuchfile.jsonl")])
check("a missing log is exit 2 (told apart from an empty one)",
      p.returncode == 2 and "no log" in p.stderr, f"exit={p.returncode}")

p, _ = run(["--config", EMPTY_CONFIG])
check("with neither the logPath config nor --log it stops and names the key",
      p.returncode == 2 and "legacy.dualRun.logPath" in p.stderr, f"exit={p.returncode}")

p, _ = run(["--config", CONFIG])
check("without --log it uses legacy.dualRun.logPath",
      p.returncode == 1 and os.path.basename(DEFAULT_LOG) in p.stdout,
      f"exit={p.returncode}")

bad_ig = os.path.join(BASE, "ignore-bad.json")
with open(bad_ig, "w", encoding="utf-8") as fh:
    json.dump({"rules": [{"experiment": "x", "keys": "total"}]}, fh)
p, _ = run(["--log", lg_other, "--ignore", bad_ig])
check("a malformed ignore is exit 2, never ignored in silence",
      p.returncode == 2 and "keys" in p.stderr, f"exit={p.returncode}")

print("\n### 4. --as-regressions · --json")

fx = os.path.join(BASE, "regressions.json")
p, _ = run(["--log", lg_other, "--as-regressions", fx])
doc = json.load(open(fx, encoding="utf-8")) if os.path.isfile(fx) else None
check("--as-regressions writes a list of {experiment, input, control, candidate}",
      isinstance(doc, list) and len(doc) == 2
      and sorted(doc[0]) == ["candidate", "control", "experiment", "input"],
      f"{doc if not isinstance(doc, list) else len(doc)} entries")

p, _ = run(["--log", lg_other, "--json"])
try:
    j = json.loads(p.stdout)
except ValueError:
    j = None
check("--json emits a machine summary (per-experiment counts and the signature list)",
      isinstance(j, dict) and j.get("unexpected") == 2
      and len(j.get("groups") or []) == 2
      and set(j["experiments"]) == {"list-page", "detail-page"},
      "" if j else p.stdout[:120])

print("\n### 5. does the template parse on 5.6 too")

# `php -l` runs on the local 8.x binary and cannot prove 5.6 compatibility - it accepts a superset.
# So syntax absent from 5.6 is blocked by name. One runtime in this tree is 5.6, and a parse error
# there ends as one blank page that no test catches.
BANNED = {
    "?? operator": r"\?\?",
    "spaceship operator": r"<=>",
    "arrow function": r"\bfn\s*\(",
    "scalar type declaration": r"function\s+\w+\s*\([^)]*\b(int|float|string|bool|iterable|object)\s+\$",
    "return type declaration": r"function\s+\w+\s*\([^)]*\)\s*:\s*[\\\w]",
    "strict_types": r"declare\s*\(\s*strict_types",
    "PHP7+ builtin": r"\b(str_contains|str_starts_with|str_ends_with|array_key_first|"
                    r"random_int|is_iterable|intdiv)\s*\(",
    "JSON_THROW_ON_ERROR": r"JSON_THROW_ON_ERROR",
}
if not os.path.isfile(TEMPLATE):
    skip("template 5.6 syntax check", f"no template: {TEMPLATE}")
else:
    raw = open(TEMPLATE, "rb").read()
    nonascii = [i for i, b in enumerate(raw) if b > 127]
    where = ""
    if nonascii:
        # Name the line. "45 non-ASCII bytes" alone means scanning the whole file by eye
        # to find those 45 bytes.
        lines = sorted({raw[:i].count(b"\n") + 1 for i in nonascii})
        where = (f"{len(nonascii)} non-ASCII bytes · {len(lines)} lines "
                 f"({', '.join(str(n) for n in lines[:6])}"
                 + (" and more" if len(lines) > 6 else "") + ")")
    check("the template is pure ASCII (encoding differs per file in the legacy tree)",
          not nonascii, where)
    # `errors="replace"`. If this line died with an exception while the check above is red,
    # **the checks after it would not run at all** - one failure making everything else skip is
    # the worst property a check suite can have. Even with one broken line the 5.6 syntax check
    # can still answer.
    code = re.sub(r"/\*.*?\*/", "", raw.decode("ascii", "replace"), flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)
    hits = {name: len(re.findall(rx, code)) for name, rx in BANNED.items()
            if re.search(rx, code)}
    check("it uses no syntax absent from 5.6 (php -l is 8.x and cannot prove this)",
          not hits, str(hits) if hits else "")

print("\n### 6. a log written by the real PHP helper")

php = shutil.which("php")
if not php:
    skip("a log made by actually running the template", "no php")
elif not os.path.isfile(TEMPLATE):
    skip("a log made by actually running the template", f"no template: {TEMPLATE}")
else:
    driver = os.path.join(BASE, "driver.php")
    with open(driver, "w", encoding="ascii") as fh:
        fh.write(
            "<?php\n"
            "require_once " + json.dumps(TEMPLATE) + ";\n"
            "$ko = \"\\xb0\\xa1\\xb3\\xaa\";\n"
            "$control = function () use ($ko) {\n"
            "    return array('items' => array(array('seq' => 1, 'title' => $ko)),\n"
            "                 'total' => 120);\n"
            "};\n"
            "$same = function () use ($ko) {\n"
            "    return array('items' => array(array('seq' => 1, 'title' => $ko)),\n"
            "                 'total' => 120);\n"
            "};\n"
            "$candidate = function () use ($ko) {\n"
            "    return array('items' => array(array('seq' => 1, 'title' => $ko)),\n"
            "                 'total' => 7);\n"
            "};\n"
            "MigrationExperiment::run('list-page', 'T_MODE', $control, $same,\n"
            "    array(), array('input' => array('page' => 1)));\n"
            "MigrationExperiment::run('list-page', 'T_MODE', $control, $candidate,\n"
            "    array(), array('input' => array('page' => 2)));\n"
            "echo MigrationExperiment::mode('T_MODE');\n")
    php_log = os.path.join(BASE, "php.jsonl")
    env = dict(os.environ, T_MODE="dual", MIGRATION_EXPERIMENT_LOG=php_log)
    t0 = time.time()
    r = subprocess.run([php, driver], capture_output=True, text=True, timeout=60,
                       env=env, cwd=BASE)
    secs = time.time() - t0
    lines = (open(php_log, encoding="utf-8").read().splitlines()
             if os.path.isfile(php_log) else [])
    check("the helper writes one line per call in dual mode",
          r.returncode == 0 and r.stdout.strip() == "dual" and len(lines) == 2,
          f"exit={r.returncode} lines={len(lines)} {r.stderr.strip()[:60]}", secs=secs)
    p, _ = run(["--log", php_log])
    check("dualrun-report reads that log as-is and names one mismatch",
          p.returncode == 1 and "1 diff_keys signatures" in p.stdout and "total" in p.stdout,
          f"exit={p.returncode} {p.stderr.strip()[:80]}")
    check("the caller file:line rides in the report (another page calls the same method)",
          "driver.php:" in p.stdout,
          [l.strip() for l in p.stdout.splitlines() if "caller" in l][:1])
    ig3 = ignore_file("php", [{"experiment": "list-page", "keys": ["total"],
                               "rules": "R-17", "reason": "의도수정"}])
    p, _ = run(["--log", php_log, "--ignore", ig3])
    check("the diff_keys the helper wrote use the same vocabulary as ignore.json keys",
          p.returncode == 0, f"exit={p.returncode}")

# ------------------------------------------------------------------ wrap-up
shutil.rmtree(BASE, ignore_errors=True)
bad = [n for n, ok, _ in results if not ok]
print("\n" + "=" * 64)
if skipped:
    print(f"skipped {len(skipped)} - " + ", ".join(n for n, _ in skipped))
    print("  a skipped check is not a pass.")
print(f"{len(results) - len(bad)}/{len(results)} pass"
      + ("" if not bad else "   failed: " + ", ".join(bad)))
sys.exit(1 if bad else 0)
