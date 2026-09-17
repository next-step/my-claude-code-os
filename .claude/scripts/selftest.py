#!/usr/bin/env python3
"""Check that the tools and hooks actually work. From the project root, with no env vars.

    python3 .claude/scripts/selftest.py           everything
    python3 .claude/scripts/selftest.py --quick    skip the checks that sweep the tree

**This file holds no environment constants.** Target paths and service names are read from
`.claude/config/workspace.json`, the same place the tools read them. That is what lets this file
be tracked, and it stops the checks drifting from the config. The instrumentation-hook checks
build a fake tree and point at that, so they touch no real log or state file.

**It prints how long each check took.** A tool can be correct and still be routed around when
one call costs a minute, and that detour is recorded in the log as "did not use the tool",
which then reads as a design problem. Visible timings prevent that misreading. `--quick` drops
the checks that sweep the whole tree, and says at the end what was dropped.
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

# The tools this file runs nest the same quote inside an f-string - PEP 701, new in 3.12 -
# and on an older interpreter that is a **SyntaxError**: `.claude/scripts/phpmove` does not fail
# a case, it fails to parse, and the message names a quote rather than a version. On macOS
# `/usr/bin/python3` is still 3.9, so running this file on the wrong interpreter is the likeliest
# way to get a red run that has nothing to do with the code. Say the version, not the quote.
if sys.version_info < (3, 12):
    sys.exit("selftest: needs Python 3.12 or newer (running "
             f"{sys.version_info.major}.{sys.version_info.minor}). The tools in .claude/scripts/ "
             "nest the same quote inside an f-string (PEP 701), which older versions cannot parse "
             "at all - phpmove dies whole, and the error names a quote rather than the version.")

QUICK = "--quick" in sys.argv
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(HERE))
SCRATCH = tempfile.mkdtemp(prefix="phpselftest-")
ENV = {k: v for k, v in os.environ.items() if k != "PHP_LEGACY_ROOT"}

results = []
skipped = []


def check(name, ok, detail="", secs=None):
    results.append((name, ok, detail))
    t = f"  {secs:5.1f}s" if secs is not None else "        "
    print(f"  {'pass' if ok else 'FAIL'}{t}  {name}"
          + (f"   {detail}" if detail else ""))


def skip(name, why):
    skipped.append((name, why))
    print(f"  skipped      {name}   ({why})")


def run(cmd, timeout=180, env=None, **kw):
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT,
                       env=env or ENV, timeout=timeout, **kw)
    return p, time.time() - t0


def load_config():
    """(the `legacy` section, why it cannot be used). `workspace.json` is gitignored.

    A fresh clone has only `workspace.example.json`, so this file has to start without a bound
    environment. Exiting here put **every** check below out of reach - including the twelve
    cross-checks that compare this repository against itself and need no environment at all -
    and it exited on an unhandled traceback rather than naming the key, which is the one thing
    every tool in `.claude/scripts/` is built not to do. So the absence becomes a reason, and
    each check that needs a key is skipped **naming that key**.
    """
    p = os.path.join(PROJECT, ".claude", "config", "workspace.json")
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh).get("legacy") or {}, ""
    except FileNotFoundError:
        return {}, (".claude/config/workspace.json does not exist"
                    " - copy workspace.example.json and fill it in")
    except (OSError, ValueError) as exc:
        return {}, f".claude/config/workspace.json could not be read: {exc}"


LG, CONFIG_PROBLEM = load_config()


def without(*keys):
    """Why these `legacy.` keys cannot be used, or `""` when every one of them can.

    Every skip below names a key instead of saying "no environment". In a log the difference
    between a check that could not run and a check somebody deleted is exactly that name, and
    without it an honest run and an emptied one read the same.
    """
    if CONFIG_PROBLEM:
        return CONFIG_PROBLEM
    gone = []
    for k in keys:
        cur = LG
        for part in k.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
            if not cur:
                gone.append("legacy." + k)
                break
    return "workspace.json has no " + ", ".join(gone) if gone else ""


def needs(name, why):
    """False - and the check is recorded as skipped for `why` - when the environment is absent."""
    if why:
        skip(name, why)
    return not why


# The tools below find the project by walking up for `workspace.json` and stop when it is not
# there, so with no config their checks are about the environment, not about this repository.
NO_ENV = without("root")

TREE = (LG.get("treeRoot")
        or (os.path.join(LG["root"], LG["treeMarker"])
            if LG.get("root") and LG.get("treeMarker") else ""))
PRIMARY = LG.get("primaryService") or ""
SHARED = LG.get("sharedLibrary") or PRIMARY

# Why there is no file out of the legacy tree to check the tree-reading tools against. Computed
# once, so every skip gives the same true reason rather than "no CP949 file found" - which is
# what a tree that *is* present but holds no CP949 file would also say, and two different facts
# under one sentence is how a missing environment comes to look like a missing file.
# **It never prints the path.** This repository is public, and its selftest output is quoted into
# tracked documents and pull requests; a path out of the legacy checkout is company information
# just as much as the code inside it.
if CONFIG_PROBLEM:
    NO_TREE = CONFIG_PROBLEM
elif not TREE:
    NO_TREE = "workspace.json has no legacy.treeRoot (nor legacy.root + legacy.treeMarker)"
elif not os.path.isdir(TREE):
    NO_TREE = "the tree legacy.treeRoot names is not on this machine"
elif not PRIMARY:
    NO_TREE = "workspace.json has no legacy.primaryService"
else:
    NO_TREE = ""


def sample(prefix, want_encoding=None, limit=400):
    """One .php file from the tree to check against, so no symbol name is written into this file."""
    if NO_TREE or not prefix:
        return None
    sys.path.insert(0, HERE)
    from _phpenc import detect
    base = os.path.join(TREE, prefix)
    seen = 0
    # It must not pick a vendor bundle. `phplint` excludes those from checking, so verifying the
    # syntax check against a vendor file reads a "skip" as a "pass". For a check to measure real
    # behavior, its target has to be our code.
    SKIP = ("vendor", "node_modules", "bower_components", "external", "test",
            "tests", "old", "backup")
    for root, dirs, names in os.walk(base):
        dirs[:] = [d for d in dirs
                   if d != ".git" and d.lower() not in SKIP
                   and "excel" not in d.lower() and "editor" not in d.lower()]
        for n in names:
            if not n.endswith(".php"):
                continue
            p = os.path.join(root, n)
            seen += 1
            if seen > limit:
                return None
            try:
                with open(p, "rb") as fh:
                    enc = detect(fh.read(200000))
            except OSError:
                continue
            if want_encoding is None or enc == want_encoding:
                return p
    return None


print(f"# target tree present: {bool(TREE) and os.path.isdir(TREE)}"
      f" · {len(LG.get('services') or {})} services"
      f" · {len(LG.get('runtimes') or {})} runtimes"
      + ("  [--quick]" if QUICK else ""))
if CONFIG_PROBLEM or NO_TREE:
    print(f"# {CONFIG_PROBLEM or NO_TREE}")
    print("# the checks that need a bound environment are skipped below, each naming what was"
          " absent; everything else still runs. A skipped check is not a pass.")

# ------------------------------------------- 3–8. start the case modules first
# Each module builds its own synthetic fixtures and prints `N/M pass` on its last line. Below,
# only that number is read. The reason the modules are not folded into this file is one thing:
# once this file gets big nobody runs it to the end, and a check that does not run is no check.
#
# **All six start here and are collected in place (sections 3–8).** Waiting one at a time makes
# the wall clock the sum of six, and most of that sum is waiting for processes to start. The six
# know nothing of each other - each builds fixtures under `tempfile.mkdtemp`, looks only at its
# own `CLAUDE_PROJECT_DIR`, touches no container (the `pagecheck` cases put a fake `docker` on
# their own PATH), and only reads this repository. So overlapping them cannot change each
# other's verdicts.
#
# Output is printed **in the order they were started**. Printing in completion order makes the
# same repository produce a different log every run, and then two runs cannot be compared.
CASE_MODULES = [
    # (section, heading, check-name prefix, skip name, file, args, timeout)
    (3, "instrumentation hook - against a fake tree", "instrumentation", "instrumentation hook cases", "selftest_hook.py",
     [PROJECT + "/.claude/hooks/php-tooling-hook.py"], 300),
    (4, "phpmove - page shape · body hash · callers", None, None,
     "selftest_phpmove.py", [os.path.join(HERE, "phpmove")], 300),
    (5, "htmlsnap - capture and compare", None, None, "selftest_htmlsnap.py", [], 300),
    (6, "dualrun-report - the dual-run log", None, None, "selftest_dualrun.py",
     [], 300),
    (7, "context injection - against a fake project", None, None, "selftest_context.py",
     [PROJECT + "/.claude/hooks/context-inject.py"], 300),
    (8, "pagecheck - stages · toggle · rounds · check results", None, None,
     "selftest_pagecheck.py", [], 420),
    # The budget is the design's one binding cap (CLAUDE.md, growth rule 4). It ran only when
    # someone remembered to run it by hand, which means the cap was never in the number
    # anybody read before committing.
    (8.5, "injection budget - no consumer over 90%", None, None, "selftest_budget.py",
     [], 120),
    (8.6, "ctxevolve - record → proposed revision", None, None, "selftest_ctxevolve.py",
     [], 180),
    (8.7, "causestats - extra rounds → causes, repeats and metrics", None, None,
     "selftest_causestats.py", [], 240),
]


def launch_cases(filename, args, timeout):
    """Start a module and return its handle. None when the file does not exist.

    **Each module's waiting is done by its own thread.** Calling `communicate` in collection
    order makes a module collected late report not its own time but the time it spent waiting
    for the ones before it - 0.8 s looks like 5.4 s. The reason this file prints seconds is to
    show which tool is slow, so if that number changes with collection order there is no point
    printing it.
    """
    mod = os.path.join(HERE, filename)
    if not os.path.isfile(mod):
        return None
    h = {"t0": time.time(), "out": "", "err": "", "secs": None, "over": False,
         "proc": subprocess.Popen([sys.executable, mod, *args],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  text=True, cwd=PROJECT, env=ENV)}

    def wait():
        try:
            h["out"], h["err"] = h["proc"].communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            h["proc"].kill()
            h["out"], h["err"] = h["proc"].communicate()
            h["over"] = True
        h["secs"] = time.time() - h["t0"]

    h["thread"] = threading.Thread(target=wait, daemon=True)
    h["thread"].start()
    return h


def collect_cases(no, title, label, skipname, filename, timeout, handle):
    """Collect a started module and check its `N/M pass` line."""
    print(f"\n### {no}. {title}")
    if handle is None:
        skip(skipname or title, f"{filename} does not exist")
        return
    handle["thread"].join()
    out = handle["out"] or ""
    if handle["over"]:
        out += f"\n{filename} did not finish within {timeout}s"
    tail = [l for l in out.strip().splitlines() if " pass" in l]
    last = tail[-1] if tail else out.strip()[-120:]
    n = last.split("/")[0].strip() if "/" in last else "?"
    total = last.split("/")[1].split()[0] if "/" in last else "?"
    # Not finding the `N/M` line is not a pass. When it is missing, n and total are both "?",
    # and counting only `n == total` without noticing that makes **a module that died or timed
    # out print green** - running no cases at all is the fastest run, so that hole opens widest
    # precisely while speed is being measured.
    ok = "/" in last and n == total and not handle["over"]
    # Cases a module skipped internally **drop out of** that module's `N/M`. The parent then sees
    # `43/43 pass` and prints green, and from outside there is no way to know why a count that
    # was 44 yesterday is 43 today - the case looks like it vanished. A skip is not a pass, so
    # that line is lifted into the parent's summary.
    inner_skips = [l.strip() for l in out.splitlines()
                   if l.strip().startswith("skipped ") and " - " in l]
    detail = last.strip()
    if inner_skips:
        detail += "  · " + inner_skips[-1]
    check(f"{label or title}: {total} cases", ok, detail, secs=handle["secs"])
    if inner_skips:
        print(f"{'':2} {'':<44} ↳ {inner_skips[-1]} (skipped inside the module - not a pass)")
    if not ok:
        print(out)
        print((handle["err"] or "")[-1500:], file=sys.stderr)


handles = [launch_cases(m[4], m[5], m[6]) for m in CASE_MODULES]
print(f"# started {sum(h is not None for h in handles)} case modules first"
      " - the seconds in sections 3–8 overlap, so their sum is not wall clock")

# ---------------------------------------------------------------- 1. tools
print("\n### 1. the seven tree-reading tools - no env vars, from the project root")

cp949 = sample(SHARED, "cp949") or sample(PRIMARY, "cp949")
utf8 = sample(PRIMARY, "utf-8") or sample(PRIMARY)

if cp949:
    p, s = run([sys.executable, HERE + "/phpv", cp949, "1:3"])
    check("phpv decodes CP949", p.returncode == 0 and "cp949" in p.stdout,
          secs=s)
else:
    skip("phpv CP949 decode", NO_TREE or "no CP949 file found in the tree")

p, s = run([sys.executable, HERE + "/phpv"])
check("phpv with no arguments → help, exit 2", p.returncode == 2, secs=s)

if QUICK:
    skip("phpgrep normal search", "it sweeps the whole tree")
elif NO_TREE:
    skip("phpgrep normal search", NO_TREE)
else:
    p, s = run([sys.executable, HERE + "/phpgrep", "-l", "__nosuchsymbol__"])
    check("phpgrep prints its scope and answers zero as zero",
          p.returncode == 1 and "scope" in p.stderr and "no hits" in p.stderr, secs=s)

p, s = run([sys.executable, HERE + "/phpgrep", "-F", "x"])
check("phpgrep rejects an unknown option (does not use it as the term)",
      p.returncode == 2 and "unknown option" in p.stderr, secs=s)

p, s = run([sys.executable, HERE + "/phpgrep", "a", "b"])
check("phpgrep rejects two search terms", p.returncode == 2 and "exactly one" in p.stderr,
      secs=s)

if needs("phpindex --list finds the index", NO_ENV):
    p, s = run([sys.executable, HERE + "/phpindex", "--list"])
    check("phpindex --list finds the index",
          p.returncode == 0 and ".json" in p.stdout, secs=s)

# The claim in the name is that the index was not rebuilt, and nothing used to observe that.
# `!= 0` also passed on a traceback. Compare the index directory's mtimes across the call.
_IDX = os.path.join(PROJECT, ".claude", ".state", "index")


def _index_mtimes():
    if not os.path.isdir(_IDX):
        return {}
    return {n: os.path.getmtime(os.path.join(_IDX, n)) for n in os.listdir(_IDX)}


if needs("phpindex does not rebuild on an unknown option", NO_ENV):
    _before = _index_mtimes()
    p, s = run([sys.executable, HERE + "/phpindex", "--nosuchopt"])
    _after = _index_mtimes()
    check("phpindex does not rebuild on an unknown option",
          p.returncode == 1 and "unknown option --nosuchopt" in p.stderr and _after == _before,
          f"exit={p.returncode}" + ("" if _after == _before else " · the index was rewritten"),
          secs=s)

if needs("phpwhere reads the index", NO_ENV):
    p, s = run([sys.executable, HERE + "/phpwhere", "--conflicts"])
    check("phpwhere reads the index", p.returncode == 0 and "scope" in p.stdout, secs=s)

if needs("phpstats", NO_ENV):
    p, s = run([sys.executable, HERE + "/phpstats", "--days", "1"])
    check("phpstats", p.returncode == 0 and "last 1 days" in p.stdout, secs=s)

if needs("phped status", NO_ENV):
    p, s = run([sys.executable, HERE + "/phped", "status"])
    check("phped status", p.returncode == 0 and "open - run" in p.stderr,
          "" if "open - run" in p.stderr else (p.stdout + p.stderr).strip()[:70], secs=s)

if utf8:
    t0 = time.time()
    p = subprocess.run([sys.executable, HERE + "/phplint", "--as", utf8, "-"],
                       input="<?php function f() { return 1; }", text=True,
                       capture_output=True, cwd=PROJECT, env=ENV, timeout=180)
    check("phplint good source → 0, and it picked the right runtime",
          p.returncode == 0 and "OK on PHP" in p.stderr,
          p.stderr.strip()[:70] if p.returncode else "", secs=time.time() - t0)
    t0 = time.time()
    p = subprocess.run([sys.executable, HERE + "/phplint", "--as", utf8, "-"],
                       input="<?php function f( { return 1; }", text=True,
                       capture_output=True, cwd=PROJECT, env=ENV, timeout=180)
    check("phplint broken source → 1", p.returncode == 1 and "FAILS" in p.stderr,
          secs=time.time() - t0)
else:
    skip("phplint pass and fail", NO_TREE or "no target file found in the tree")

outside = os.path.join(SCRATCH, "outside.php")
open(outside, "w").write("<?php echo 1;")
p, s = run([sys.executable, HERE + "/phplint", outside])
check("phplint could-not-check → 3 (not a pass)", p.returncode == 3, secs=s)

if needs("the config verdict points at the checkout", NO_ENV):
    p, s = run([sys.executable, "-c",
                f"import sys; sys.path.insert(0, {HERE!r});\n"
                "from _phpenc import checkout_root, config_problem;\n"
                "print(config_problem() or checkout_root())"])
    _want = os.path.abspath(os.path.expanduser(LG["root"]))
    check("the config verdict points at the checkout", p.stdout.strip() == _want,
          "" if p.stdout.strip() == _want else p.stdout.strip()[:60], secs=s)

# Does it stop rather than give a narrowed answer when the config is missing
empty = os.path.join(SCRATCH, "emptyproj")
os.makedirs(empty + "/.claude/config", exist_ok=True)
with open(empty + "/.claude/config/workspace.json", "w") as fh:
    json.dump({}, fh)
p, s = run([sys.executable, HERE + "/phpwhere", "x"],
           env={**ENV, "CLAUDE_PROJECT_DIR": empty})
check("an empty config stops and says why",
      p.returncode != 0 and ("legacy" in p.stderr or "workspace" in p.stderr),
      secs=s)

# ------------------------------------------------------- 2. encoding guard
print("\n### 2. encoding guard - with an isolated state file")
GPROJ = os.path.join(SCRATCH, "guardproj")
os.makedirs(GPROJ + "/.claude/config", exist_ok=True)
# **Pass the whole config.** Before, only three keys were copied, and then `phplint` could not
# pick a runtime and ended in "could not check". Because the check was "is there no warning",
# that state read as a pass. Isolation is needed only for the state file; trimming the config is
# not isolation but changing what is being checked.
with open(GPROJ + "/.claude/config/workspace.json", "w") as fh:
    json.dump({"legacy": LG}, fh)
# The guard looks for tools under `CLAUDE_PROJECT_DIR/.claude/scripts`. Create that place in the
# isolated project too.
os.symlink(HERE, os.path.join(GPROJ, ".claude", "scripts"))
GUARD = PROJECT + "/.claude/hooks/php-encoding-guard.py"


def hook_text(p):
    """The sentence the hook means to show a person. Unwraps the JSON on stdout and appends stderr.

    The hook emits via `json.dump`, so Korean is escaped as `\\uXXXX`. Searching for the original
    wording without unwrapping makes **every positive condition fail and every negative condition
    pass.** The latter is worse - the check passes while verifying nothing. This suite had two
    such checks.
    """
    out = ""
    try:
        out += json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        out += p.stdout or ""
    return out + (p.stderr or "")


def guard(path, event="PreToolUse", project=None):
    body = {"tool_name": "Edit", "tool_input": {"file_path": path},
            "hook_event_name": event}
    t0 = time.time()
    p = subprocess.run([sys.executable, GUARD], input=json.dumps(body),
                       text=True, capture_output=True,
                       env={**ENV, "CLAUDE_PROJECT_DIR": project or GPROJ},
                       timeout=180)
    return p, time.time() - t0


if cp949:
    p, s = guard(cp949)
    check("warns before editing a CP949 file", p.returncode == 0 and "CP949" in hook_text(p),
          "" if "CP949" in hook_text(p) else hook_text(p)[:80], secs=s)
else:
    skip("warning before a CP949 edit", NO_TREE or "no CP949 file found in the tree")

p, s = guard(os.path.join(SCRATCH, "outside.php"))
check("a file outside the tree passes silently",
      p.returncode == 0 and not hook_text(p).strip(), secs=s)

if utf8:
    guard(utf8, "PreToolUse")          # the post-edit check needs the pre-edit record
    p, s = guard(utf8, "PostToolUse")
    out = hook_text(p)
    check("no syntax-failure warning after a valid PHP edit", "does not run on" not in out, secs=s)
    # **This line is the point.** The absence of "was not checked" means the check ran and
    # passed, which differs from silently skipping because the tool could not be found. While the
    # tool path pointed at the old location this distinction was missing and a defect passed.
    check("the syntax check really ran (not an unchecked state)",
          "was not checked" not in out,
          "" if "was not checked" not in out else out.strip()[-90:])
    # Deliberately create the situation where the tool cannot be found, and see that it does not pass silently.
    BARE = os.path.join(SCRATCH, "bareproj")
    os.makedirs(BARE + "/.claude/config", exist_ok=True)
    with open(BARE + "/.claude/config/workspace.json", "w") as fh:
        json.dump({"legacy": LG}, fh)
    # Run the pre-edit stage first. PostToolUse starts by comparing against the encoding recorded
    # then, so with no record it ends quietly before reaching the syntax check.
    t0 = time.time()
    for ev in ("PreToolUse", "PostToolUse"):
        p, _ = guard(utf8, ev, project=BARE)
    _o = hook_text(p).strip()
    check("it says so when the syntax-check tool is missing (no silent pass)",
          "could not find" in _o,
          "" if "could not find" in _o else f"exit={p.returncode} output={_o[:120]!r}",
          secs=time.time() - t0)
else:
    # With no `else` these three simply **disappeared** when no sample file was found, and a
    # count that quietly drops from 42 to 39 cannot be told from three checks that passed.
    # Naming them here is what makes their absence countable.
    for _n in ("no syntax-failure warning after a valid PHP edit",
               "the syntax check really ran (not an unchecked state)",
               "it says so when the syntax-check tool is missing (no silent pass)"):
        skip(_n, NO_TREE or "no target file found in the tree")

# ------------------------------------------- 3–8. collect the started case modules
for (no, title, label, skipname, filename, _args, timeout), h in zip(
        CASE_MODULES, handles):
    collect_cases(no, title, label, skipname, filename, timeout, h)

# ------------------------------------------------------- 9. cross-checks
# **When one fact is written in two files, they drift eventually.** With no path for a person to
# notice the drift, the mismatch lives quietly - in v1 one completeness verdict was absent from
# the routing table, so every time it came back it vanished with nowhere to go. Here a canonical
# copy is named and the copies are compared. A failure is not "one of the two is wrong" but "the two drifted".
print("\n### 9. cross-checks - places where the same fact is written twice")

AGENTS = os.path.join(PROJECT, ".claude", "agents")
SKILLS = os.path.join(PROJECT, ".claude", "skills")
PAGE = os.path.join(SKILLS, "legacy-migrate")
ROW = re.compile(r"^\| `?([^|`]+)`?\s*(?:\([^)]*\))?\s*\|")


def read(*parts):
    try:
        with open(os.path.join(*parts), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def table_first_col(text, header_needle):
    """First column of the table **body** rows, after the header line.

    The body starts at the separator (`|---|`). Without using that as the anchor the table header
    comes in as the first item, and then two identical files are reported as different - not worse
    than missing a drift, but a check that is wrong every time gets switched off.
    """
    out, seen, started = [], False, False
    for line in text.splitlines():
        if not seen:
            seen = header_needle in line
            continue
        if not line.startswith("|"):
            if started and out:
                break
            continue
        if set(line.replace("|", "").strip()) <= set("-: "):
            started = True
            continue
        if not started:
            continue
        m = ROW.match(line)
        if m:
            out.append(m.group(1).strip())
    return out


# (a) completeness verdict vocabulary - canonical in the checker file alone ---
# In v3 the routing table left SKILL.md for references/routing.md. If this check went quietly
# empty during that move (both being `[]` could pass as "equal"), nobody would know after the
# vocabulary drifted. So it also checks that **neither side is empty**.
checker = read(AGENTS, "domain-placement-checker.md")
skill = read(PAGE, "SKILL.md")
routing = read(PAGE, "references", "routing.md")
canon = table_first_col(checker, "## Verdict vocabulary")
routed = table_first_col(routing, "| Verdict |")
# `domain-leftover/SKILL.md` keeps a third copy, and it declares itself a copy. routing.md
# exists because in v2 this table had been copied into four places and had already drifted;
# a copy no check compares is exactly how that happened. So all three are compared here.
leftover = table_first_col(read(PROJECT, ".claude", "skills", "domain-leftover", "SKILL.md"),
                           "| Verdict |")
_v = {"checker": canon, "routing table": routed, "domain-leftover": leftover}
_empty = [k for k, v in _v.items() if not v]
_differ = [k for k, v in _v.items() if v and v != canon]
check("the completeness verdict vocabulary matches across all three copies",
      not _empty and not _differ,
      (f"empty: {_empty} " if _empty else "")
      + (f"differs from the checker: {_differ} · " + " · ".join(f"{k}={_v[k]}" for k in _differ)
         if _differ else "")
      or f"{len(canon)} words × 3 copies")

# If the table moved, the orchestrator has to point at its new place. If it does not, a returning
# verdict has nowhere to route.
check("the orchestrator points at the canonical routing table",
      "references/routing.md" in skill,
      "" if "references/routing.md" in skill
      else "legacy-migrate/SKILL.md does not mention references/routing.md")

# (a2) the cause vocabulary - canonical in pagecheck's CAUSE dict ------------
# The same shape as (a), for the other closed vocabulary this OS has. One copy decides what a
# round may be blamed on at the moment the round is counted (`pagecheck`), and one copy is what a
# person reads and an agent is told to choose from (the two-layer table in the design canon). A
# drift is silent in both directions: a word the design tells an agent to use is refused at the
# counter, or a word the counter accepts is one the metrics have no upper layer for and drop.
# It is extracted rather than written here - a third copy inside the checker is still a copy.
def literal_dict(rel, want):
    """A module-level dict assigned to `want`, read **without running the file**."""
    try:
        tree = ast.parse(read(PROJECT, rel))
    except (SyntaxError, ValueError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == want for t in node.targets):
            try:
                val = ast.literal_eval(node.value)
            except (ValueError, TypeError, SyntaxError):
                return None
            return val if isinstance(val, dict) else None
    return None


def table_two_cols(text, header_needle):
    """{second column: first column} of a table's body rows, backticks stripped.

    The vocabulary table is written upper-layer first because that is the order a person reads
    it in; the code is keyed by the lower layer because that is what arrives on the command
    line. Flipping it here rather than in either copy keeps both readable.
    """
    out, seen, started = {}, False, False
    for line in text.splitlines():
        if not seen:
            seen = header_needle in line
            continue
        if not line.startswith("|"):
            if started and out:
                break
            continue
        if set(line.replace("|", "").strip()) <= set("-: "):
            started = True
            continue
        if not started:
            continue
        cells = [c.strip().strip("`").strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] and cells[1]:
            out[cells[1]] = cells[0]
    return out


code_vocab = literal_dict(".claude/scripts/pagecheck", "CAUSE")
doc_vocab = table_two_cols(read(PROJECT, "docs/legacy-migration-os.md"),
                           "| 위층 | 아래층 |")
# Both empty would compare equal, and "the check went blind" would then read as "they agree" -
# the same hole (a) has to guard. So an empty side is a failure on its own.
_cv = code_vocab or {}
_dv = doc_vocab or {}
_only_code = sorted(k for k in _cv if _cv.get(k) != _dv.get(k))
_only_doc = sorted(k for k in _dv if _dv.get(k) != _cv.get(k))
check("the cause vocabulary matches between pagecheck and the design canon",
      bool(_cv) and bool(_dv) and _cv == _dv,
      ("pagecheck's CAUSE could not be extracted " if not _cv else "")
      + ("no vocabulary table in §4 of the design canon " if not _dv else "")
      + (f"code-only/differing {_only_code} · canon-only/differing {_only_doc}"
         if _cv and _dv and _cv != _dv else "")
      or f"{len(_cv)} words × 2 layers")

# (b) artifacts - canonical in artifacts.json --------------------------------
try:
    with open(os.path.join(PAGE, "references", "artifacts.json"),
              encoding="utf-8") as fh:
        art = json.load(fh)
except (OSError, ValueError) as exc:
    art, art_err = {}, str(exc)
else:
    art_err = ""
# The v3 skill writes its artifacts as prose rather than a table. Instead of following the format,
# the **set of names** is matched - this check survives another format change. Two things are
# caught: an artifact the skill mentions that is absent from the JSON (a ghost), and one in the
# JSON the skill never mentions (an artifact nobody will use).
named = set(re.findall(r"`(\d\d-[\w.-]+)`", skill))
check("artifact names match artifacts.json",
      bool(art) and named == set(art),
      art_err or (f"JSON {sorted(art)} vs SKILL.md {sorted(named)}"
                  if named != set(art) else f"{len(art)} names"))

# (c) experiment helper constants ↔ config keys ---------------------------------
tpl = read(PROJECT, ".claude", "templates", "MigrationExperiment.php")
# Five helper constants. The last two are `pagecheck`'s instrumentation variables, and if those
# drift the variable never reaches PHP while the stage ends looking exactly like "no mismatch".
HELPER_CONSTS = ("VALUE_DUAL", "VALUE_MIGRATED", "LOG_ENV", "NOISE_ENV",
                 "FAKEVALUE_ENV")
consts = [c for c in HELPER_CONSTS
          if re.search(r"\bconst\s+" + c + r"\s*=", tpl)]
try:
    with open(os.path.join(PROJECT, ".claude", "config",
                           "workspace.example.json"), encoding="utf-8") as fh:
        ex = json.load(fh)
except (OSError, ValueError):
    ex = {}
exl = (ex.get("legacy") or {})
want_keys = [("legacy.switch.values.dual",
              "dual" in ((exl.get("switch") or {}).get("values") or {})),
             ("legacy.switch.values.migrated",
              "migrated" in ((exl.get("switch") or {}).get("values") or {})),
             ("legacy.dualRun.logEnvVar",
              "logEnvVar" in (exl.get("dualRun") or {})),
             ("legacy.dualRun.noiseEnvVar",
              "noiseEnvVar" in (exl.get("dualRun") or {})),
             ("legacy.dualRun.fakeValueEnvVar",
              "fakeValueEnvVar" in (exl.get("dualRun") or {})),
             ("legacy.dualRun.coveragePath",
              "coveragePath" in (exl.get("dualRun") or {}))]
missing = [k for k, ok in want_keys if not ok]
check(f"the helper's {len(HELPER_CONSTS)} constants and the example's {len(want_keys)} keys "
      "are both present",
      len(consts) == len(HELPER_CONSTS) and not missing,
      f"missing constants {[c for c in HELPER_CONSTS if c not in consts]} · "
      f"missing keys {missing}"
      if len(consts) != len(HELPER_CONSTS) or missing else "")

# If the real config filled that section, compare the values too. If it did not, skip -
# an absent value is not a drift but something not yet written.
real = {}
try:
    with open(os.path.join(PROJECT, ".claude", "config", "workspace.json"),
              encoding="utf-8") as fh:
        real = (json.load(fh).get("legacy") or {})
except (OSError, ValueError):
    pass
rv = (real.get("switch") or {}).get("values") or {}
rlog = (real.get("dualRun") or {}).get("logEnvVar")
if rv.get("dual") and rv.get("migrated") and rlog:
    lit = {c: (re.search(r"\bconst\s+" + c + r"\s*=\s*'([^']*)'", tpl)
               or [None, None])[1] for c in HELPER_CONSTS}
    same = (rv["dual"] == lit["VALUE_DUAL"]
            and rv["migrated"] == lit["VALUE_MIGRATED"]
            and rlog == lit["LOG_ENV"])
    check("the real config's toggle values match the helper constants", same,
          "" if same else f"config {rv}/{rlog} vs template {lit}")
    # A checkout may not have filled the instrumentation variables yet. Compare when filled, skip
    # when not - an absent value is not a drift.
    for key, const in (("noiseEnvVar", "NOISE_ENV"),
                       ("fakeValueEnvVar", "FAKEVALUE_ENV")):
        got = (real.get("dualRun") or {}).get(key)
        if not got:
            skip(f"compare the real config's {key}", f"workspace.json has no {key} yet")
        else:
            check(f"the real config's {key} matches the helper's {const}",
                  got == lit[const], "" if got == lit[const]
                  else f"config {got} vs template {lit[const]}")
else:
    skip("compare the real config's toggle values", "workspace.json has no dualRun or dual value yet")

# (c2) does each surface's loggedOutMarker catch every logged-out shape that surface produces ----
# An auth failure here is not a 302 or a 401 - it is **200 with a script that navigates**, and
# the marker is the only thing that separates it from a real page. A marker that catches one of
# the shapes and not the other is worse than none: the pages it misses get a logged-out capture
# recorded as a valid baseline, and a baseline taken while logged out compares green forever.
# That happened - `confirm\(` alone missed every mobile page, whose guard emits `location.href`
# with no confirm. The two samples below were captured from the running help surface on
# 2026-09-15 (one PC detail page and one mobile list page on that surface), trimmed to
# the script element. admin has no captured sample yet, so it is skipped by name rather than
# silently passed.
LOGGED_OUT_SAMPLES = {
    "help": {
        "confirmGoUrl (PC pages)":
            "<script type=\"text/javascript\">\n\tif ( confirm( '로그인 후 이용해 주십시오.' ) ) {\n"
            "\tlocation.href = 'https://auth.example.com/login?url=x';\n} else {\nhistory.back();\n}\n</script>",
        "moveLinkUrl (mobile pages)":
            "<script type=\"text/javascript\">\n\tlocation.href = "
            "'https://auth.example.com/login?url=x';\n\t</script>",
    },
}
for _skey, _surface in sorted((real.get("surfaces") or {}).items()):
    _samples = LOGGED_OUT_SAMPLES.get(_skey)
    _marker = (_surface or {}).get("loggedOutMarker")
    if not _samples:
        skip(f"the {_skey} surface's loggedOutMarker catches its logged-out shapes",
             f"no captured sample for the {_skey} surface yet")
    elif not _marker:
        check(f"the {_skey} surface's loggedOutMarker catches its logged-out shapes", False,
              "the surface has no loggedOutMarker - every logged-out capture reads as valid")
    else:
        _missed = [n for n, body in sorted(_samples.items()) if not re.search(_marker, body)]
        check(f"the {_skey} surface's loggedOutMarker catches its logged-out shapes",
              not _missed, "" if not _missed else "misses " + " · ".join(_missed))

# (d) do the context files' injection targets exist ------------------------------
inject = os.path.join(PROJECT, ".claude", "hooks", "context-inject.py")
if not os.path.isfile(inject):
    skip("compare context injection targets", "context-inject.py is missing")
else:
    p, s = run([sys.executable, inject, "--check", "--strict"], timeout=60)
    _out = p.stdout + p.stderr
    # `--check --strict` answers **two** questions, and only one of them needs an environment:
    # the agent and skill names are files of this repository, the path globs are `${legacy.root}`
    # and `${backend.root}` out of the config. Counting the pair as one check meant that in a
    # clone with no config the *name* half could not run either - and dropping `--strict` to get
    # past that is not an option, because without it a context file naming an agent that does not
    # exist exits 0. So the two are counted apart: the names stay verified, the globs skip by name.
    _bad = [l.strip() for l in _out.splitlines()
            if l.startswith("error") or (l.startswith("warn") and "path glob" not in l)]
    _globs = [l.strip() for l in _out.splitlines() if "path glob" in l]
    check("the context files' inject.agents and inject.skills match real files",
          p.returncode in (0, 1) and not _bad,
          "; ".join(_bad)[:200]
          or ("" if p.returncode in (0, 1) else _out.strip()[-200:]), secs=s)
    if needs("the context files' path globs resolve to a config key", NO_ENV):
        check("the context files' path globs resolve to a config key", not _globs,
              "; ".join(_globs)[:200])

# (e) are old names absent from tracked files -------------------------------
# One surviving v1 name makes the orchestrator call an agent that does not exist or wait for a
# file that does not exist. Both appear as a stall, not as a failure.
# The names are assembled from fragments. This file is tracked too, so writing the list as
# literals would make **the check catch itself** - then this file becomes an exception, and the
# moment an exception exists the check has a blind spot. The same trade `selftest_phpmove.py`
# made for the content guard.
# v1 names, then the ones the v3 vocabulary rename retired. Extending this list is part of
# renaming: a guard that only knows the previous rename is green for every later one, which is
# exactly how this check stayed green across 75 changed files while old names survived in 20.
# NOTE: these fragments are data, not prose. A bulk rename that rewrites a word inside one
# of them silently empties that slot - `00-` + `ledger.md` was turned into `00-` + `rules.md`
# once, and the name it guarded went unguarded while the check stayed green.
OLD_NAMES = ["e2e-baseline" + "-author", "00-" + "ledger.md",
             "01-" + "design.md", "02-" + "swap.md",
             "03-" + "audit.md", "04-" + "domain-doc.md",
             # agents
             "php-" + "seam-extractor", "php-rule-" + "redteam",
             "equivalence-" + "corpus-author", "backend-" + "slice-designer",
             "backend-" + "slice-builder", "domain-boundary-" + "auditor",
             # Two names the guard never covered, found in a measurement table in
             # docs/context-system.md. The second is worse than a leftover: a bulk rename
             # rewrote the word inside an already-stale name and produced a third name that
             # was never any agent, so no fragment of an old name could ever have caught it.
             "php-swap-" + "engineer", "backend-slice-" + "implementer",
             "backend-page-" + "implementer",
             "goal-" + "gauge-author",
             # skills
             "legacy-" + "slice", "slice-" + "scout", "golden-" + "master",
             "boundary-" + "audit",
             # context and references
             "ledger-" + "contract", "equivalence-" + "oracles", "seam-" + "shape",
             "equivalence-" + "observation",
             "ledger-" + "format", "journal-" + "format",
             # tools
             "php" + "seam", "slice" + "check",
             # artifacts and config keys
             "00-" + "seam.md", "01-" + "ledger.jsonl", "02-" + "design-delta.md",
             "04-" + "audit.md", "corpus" + ".json", "pins" + ".json",
             "legacy." + "seam.", "slices" + "Dir", "journal" + "Dir",
             "poison" + "EnvVar",
             # The Korean metaphors this rename removed. They survive longest in the skills'
             # trigger phrases, where nothing reads them and no check ever looked.
             "이음" + "새", "골든 " + "마스터", "저" + "널", "델" + "타",
             "코퍼" + "스", "게이" + "지", "원" + "장", "슬라이" + "스"]
# Records of the time are excluded. Rewriting yesterday under today's names is not a record.
EXCLUDE_FILES = {"docs/first-run-retrospective.md"}
EXCLUDE_PREFIXES = ("docs/retrospectives/", "docs/handoffs/", "docs/reviews/",
                    "docs/lecture-notes/")
EXCLUDE_RANGES = {"docs/legacy-migration-os.md": [("## 9.", "## 10."),
                                                 ("## 변경 이력", None)]}
# Add `--others --exclude-standard`. A new file not yet `git add`ed is a file that will be
# tracked, and an old name left in it only becomes visible after the commit.
tracked = subprocess.run(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
    cwd=PROJECT, capture_output=True, text=True, timeout=60).stdout
hits = []
for rel in tracked.splitlines():
    if not rel or rel in EXCLUDE_FILES or rel.startswith(EXCLUDE_PREFIXES):
        continue
    if os.path.splitext(rel)[1] not in (".md", ".json", ".py", ".sh", ".php",
                                        ".ts", ".yml", ".yaml", ""):
        continue
    body = read(PROJECT, rel)
    if not body:
        continue
    skipping, ranges = False, EXCLUDE_RANGES.get(rel, [])
    for i, line in enumerate(body.splitlines(), 1):
        for start, end in ranges:
            if line.startswith(start):
                skipping = True
            elif end and skipping and line.startswith(end):
                skipping = False
        if skipping:
            continue
        for name in OLD_NAMES:
            if name in line:
                hits.append(f"{rel}:{i}: {name}")
# **Zero files scanned prints exactly like zero hits.** `git ls-files` answers nothing when the
# working directory is not a git tree - a downloaded tarball, or a CI job whose checkout step did
# not run - and then this check reports a clean repository having read no file at all.
check("no retired name remains in a tracked file", bool(tracked.strip()) and not hits,
      "git listed no file, so nothing was scanned - this is not a git working tree"
      if not tracked.strip() else
      "; ".join(hits[:4]) + (f" (and {len(hits) - 4} more)" if len(hits) > 4 else ""))

# (f) have the three tool-name lists drifted --------------------------------
# `phpstats` had written down that it "must be the same list as the hook's `OUR_TOOLS`" and
# nobody compared them, so they had already drifted - a name present on one side only is
# recorded by the hook but not counted by the report as a dedicated call, which tips the usage
# ratio downward. Writing the list here as a literal would make a **fourth copy**, so it is
# extracted from the three files and compared. Failing to extract is not a pass.
def _str_seq(node):
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        names = {e.value for e in node.elts
                 if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        return names or None
    return None


def tool_names(rel, want):
    """An assignment named `want`, or failing that the iterable of `for want in (...)`."""
    try:
        tree = ast.parse(read(PROJECT, rel))
    except (SyntaxError, ValueError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == want:
                    return _str_seq(node.value)
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name) \
                and node.target.id == want:
            seq = _str_seq(node.iter)
            if seq and "phpv" in seq:
                return seq
    return None


LISTS = [(".claude/scripts/phpstats", "OURS"),
         (".claude/hooks/php-tooling-hook.py", "OUR_TOOLS"),
         (".claude/scripts/selftest_hook.py", "name")]
got = [(rel, tool_names(rel, want)) for rel, want in LISTS]
missing = [rel for rel, names in got if not names]
if missing:
    check("the three tool-name lists match", False,
          "could not extract the lists: " + ", ".join(os.path.basename(m) for m in missing))
else:
    base = got[0][1]
    diffs = []
    for rel, names in got[1:]:
        only_a, only_b = base - names, names - base
        if only_a or only_b:
            diffs.append(f"{os.path.basename(got[0][0])}↔{os.path.basename(rel)}: "
                         + " ".join(sorted(f"-{n}" for n in only_a)
                                    + sorted(f"+{n}" for n in only_b)))
    check(f"the three tool-name lists match ({len(base)} names)", not diffs, " · ".join(diffs))

# (g) do the lists cover the tools that actually exist ----------------------
# Comparing the three lists only to each other cannot see a name missing from all three, and
# that is what happened: `pagecheck` was in none of them, so every call to the v3 pipeline's
# central tool was recorded as neither dedicated use nor detour and dropped out of the
# measurement. A dropped record reads as "the tool was not used".
_sdir = os.path.join(PROJECT, ".claude", "scripts")
on_disk = {n for n in os.listdir(_sdir)
           if not n.startswith(("selftest", "_", ".")) and "." not in n
           and os.access(os.path.join(_sdir, n), os.X_OK)}
if missing:
    check("the tool lists name every tool in .claude/scripts", False,
          "the lists could not be extracted")
else:
    union = set().union(*(names for _, names in got))
    gap = on_disk - union
    check(f"the tool lists name every tool in .claude/scripts ({len(on_disk)} on disk)",
          not gap, "not named anywhere: " + " ".join(sorted(gap)) if gap else "")

# (h) is every hook actually registered -------------------------------------
# Every hook case runs the hook file directly, so a hook that lost its settings.json entry
# stays green here while nothing ever calls it. For `guard-company-content.py` that is the
# difference between this repository staying publishable and not.
_hdir = os.path.join(PROJECT, ".claude", "hooks")
hook_files = {n for n in os.listdir(_hdir) if n.endswith(".py")}
try:
    with open(os.path.join(PROJECT, ".claude", "settings.json"), encoding="utf-8") as fh:
        _settings = json.load(fh)
    registered = {os.path.basename(h.get("command", "").strip('"').split("/")[-1].strip('"'))
                  for groups in (_settings.get("hooks") or {}).values()
                  for g in groups for h in g.get("hooks", [])}
    unregistered = {n for n in hook_files if n not in registered}
    check(f"every hook is registered in settings.json ({len(hook_files)} hooks)",
          not unregistered, "not registered: " + " ".join(sorted(unregistered))
          if unregistered else "")
except (OSError, ValueError) as exc:
    check("every hook is registered in settings.json", False,
          f"settings.json could not be read: {exc}")

# ------------------------------------------------------------------ wrap-up
shutil.rmtree(SCRATCH, ignore_errors=True)
print("\n" + "=" * 64)
bad = [n for n, ok, _ in results if not ok]
# **Three states, three numbers.** One green light covering all three is the denial this file
# exists to prevent: a run with no bound environment skips a fifth of what is here, and
# "42/42 pass" printed over that cannot be told from a run that checked everything.
print(f"{len(results) - len(bad)}/{len(results)} pass"
      f" · {len(bad)} fail · {len(skipped)} skipped"
      + ("" if not bad else "   failed: " + ", ".join(bad)))
if skipped:
    # The reason, not just the name. "no environment" is not actionable; the key or the file is.
    for _n, _why in skipped:
        print(f"  skipped  {_n}   ({_why})")
    print("  a skipped check is not a pass. Each line says which key or file was absent"
          + (" (--quick drops the tree sweeps)" if QUICK else "") + ".")
sys.exit(1 if bad else 0)
