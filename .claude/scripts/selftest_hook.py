#!/usr/bin/env python3
"""Cases for the instrumentation hook and the public-repository guard. Pointed at a fake
project and a fake tree so it touches no real log.

    python3 selftest_hook.py <path to php-tooling-hook.py>

The guard hook (`guard-company-content.py`) is found in the same directory. Its cases
**actually build a temporary git repository** and call the hook after really committing and
pushing there. The moment the index is empty is where that guard's defect lived, so that
moment is built rather than imitated.

The fake tree's directory names are chosen by this file. Using the real checkout's names would
put company information in here, and then it could not be tracked. Fake names cost the checks
nothing - the hook judges by path shape and command position, not by name, and that is what
these cases set out to verify.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else None
if not HOOK or not os.path.isfile(HOOK):
    sys.exit("usage: selftest_hook.py <path to php-tooling-hook.py>")

BASE = tempfile.mkdtemp(prefix="phphook-")
PROJ = os.path.join(BASE, "proj")
CHECKOUT = os.path.join(BASE, "checkout")
MARKER = "src/tree"                       # fake. The real name is never written here
SVC = "svc/one"
TREE = os.path.join(CHECKOUT, MARKER)

os.makedirs(os.path.join(PROJ, ".claude", "config"), exist_ok=True)
os.makedirs(os.path.join(PROJ, ".claude", ".state", "index"), exist_ok=True)
os.makedirs(os.path.join(PROJ, ".claude", "scripts"), exist_ok=True)
os.makedirs(os.path.join(TREE, SVC), exist_ok=True)

json.dump({"legacy": {"root": CHECKOUT, "treeRoot": TREE, "treeMarker": MARKER,
                      "ours": {SVC: "one"}, "services": {SVC: "one"},
                      "primaryService": SVC}},
          open(os.path.join(PROJ, ".claude", "config", "workspace.json"), "w"))

S = os.path.join(PROJ, ".claude", "scripts")
for name in ("phpv", "phpgrep", "phpwhere", "phped", "phplint", "phpindex",
             "phpstats", "phpmove", "htmlsnap", "dualrun-report", "ctxstats",
             "ctxevolve", "pagecheck", "causestats"):
    open(os.path.join(S, name), "w").write("#!/usr/bin/env python3\n")
SRC = os.path.join(TREE, SVC, "page.php")
open(SRC, "w").write("<?php echo 1;")
DOC = os.path.join(CHECKOUT, "CLAUDE.md")
open(DOC, "w").write("a document talking about phpgrep and phpv\n")
IDX = os.path.join(PROJ, ".claude", ".state", "index", "one.json")
open(IDX, "w").write("{}")
LOG = os.path.join(PROJ, ".claude", ".state", "tooling.jsonl")
SESS = "hooktest"


def run(tool, payload, event="PreToolUse", session=SESS, extra=None):
    body = {"tool_name": tool, "tool_input": payload, "cwd": BASE,
            "session_id": session, "hook_event_name": event,
            "transcript_path": f"/x/{session}.jsonl"}
    body.update(extra or {})
    subprocess.run([sys.executable, HOOK], input=json.dumps(body),
                   capture_output=True, text=True,
                   env={**os.environ, "CLAUDE_PROJECT_DIR": PROJ}, timeout=60)


def lines():
    if not os.path.isfile(LOG):
        return []
    with open(LOG, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


CASES = [
    # (description, tool, input, tools expected to be recorded, steer expected)
    ("a call with the path quoted",
     "Bash", {"command": f'"{S}/phpgrep" "한글낱말"'}, ["phpgrep"], False),
    ("listing tool names is not a call",
     "Bash", {"command": f"{S}/phpv phpgrep phped phplint phpwhere phpindex"},
     ["phpv"], False),
    ("a command that reads the tool script",
     "Bash", {"command": f"cat {S}/phpgrep"}, [], False),
    ("a search for a tool name inside quotes",
     "Bash", {"command": f"grep -n 'phpgrep\\|phpv' {DOC}"}, [], False),
    ("a dedicated tool and a detour in one command",
     "Bash", {"command": f'{S}/phpgrep "x" ; grep -n "y" {SRC}'},
     ["phpgrep", "raw-grep"], True),
    ("a path outside the tree is not counted",
     # The path is assembled. A path literal ending in a source extension is caught by this
     # repository's content guard (that is what the pattern is for), so even a fake path cannot
     # be written as a literal. Fixing this side rather than adding an exception is the right
     # move - narrowing the guard's coverage for test convenience lets through what it must block.
     "Bash", {"command": "cat " + os.path.join(BASE, "outside", "other.php")},
     [], False),
    ("a call with an env prefix",
     "Bash", {"command": f"env -u PHP_LEGACY_ROOT {S}/phpwhere SomeName"},
     ["phpwhere"], False),
    ("a call with a python3 prefix",
     "Bash", {"command": f"python3 {S}/phpv {SRC}"}, ["phpv"], False),
    ("a bare grep detour",
     "Bash", {"command": f'rg -n "someKey" {SRC}'}, ["raw-grep"], True),
    ("a bare read detour",
     "Bash", {"command": f"sed -n '1,40p' {SRC}"}, ["raw-read"], True),
    ("a definition-shaped phpgrep is steered",
     "Bash", {"command": f"{S}/phpgrep '$someVar ='"}, ["phpgrep"], True),
    ("a search on an SQL condition is not definition-shaped",
     "Bash", {"command": f"{S}/phpgrep \"WHERE seq = 59\""}, ["phpgrep"], False),
    ("Read on markdown is not counted",
     "Read", {"file_path": DOC}, [], False),
    ("Read on PHP source is a detour",
     "Read", {"file_path": SRC}, ["Read"], True),
    ("Read on the index JSON - caught even outside the checkout",
     "Read", {"file_path": IDX}, ["read-index"], True),

    # The four v2 tools. While they were absent from the list these calls counted as neither
    # dedicated nor detour and dropped out entirely, and a dropped record looks like "the tool was not used".
    ("phpmove is a dedicated tool",
     "Bash", {"command": f"{S}/phpmove lint {SRC}"}, ["phpmove"], False),
    ("an htmlsnap subcommand is recorded as mode",
     "Bash", {"command": f"{S}/htmlsnap capture --observations c.json --out {BASE}/c"},
     ["htmlsnap"], False),
    ("dualrun-report is a dedicated tool even with a hyphen",
     "Bash", {"command": f"{S}/dualrun-report --json"}, ["dualrun-report"], False),
    ("ctxstats is a dedicated tool too",
     "Bash", {"command": f"{S}/ctxstats --days 1"}, ["ctxstats"], False),
]

print(f"{'':2} {'case':<40} {'recorded':<26} {'steer':<6} verdict")
print("-" * 96)
ok = 0
for i, (desc, tool, inp, want_tools, want_nudge) in enumerate(CASES, 1):
    before = len(lines())
    run(tool, inp)
    rows = lines()[before:]
    got_tools = [r["tool"] for r in rows]
    got_nudge = any(r.get("nudge") for r in rows)
    passed = got_tools == want_tools and got_nudge == want_nudge
    ok += passed
    print(f"{i:>2} {desc:<40} {str(got_tools):<26} {str(got_nudge):<6} "
          + ("pass" if passed else f"FAIL expected={want_tools}/{want_nudge}"))

# The subcommand regex has to know the v2 tools' words or `mode` comes back empty.
extra_cases = []
before = len(lines())
run("Bash", {"command": f"{S}/phpmove callers SomeName"})
_rows = lines()[before:]
_mode = _rows[0].get("mode") if _rows else None
extra_cases.append(_mode == "callers")
print(f"{len(CASES) + 1:>2} {'a phpmove subcommand stays in mode':<40} "
      f"{str(_mode):<26} {'':<6} "
      + ("pass" if _mode == "callers" else "FAIL expected='callers'"))

# ------------------------------------------------------------ attribution cases
print("-" * 96)
attrib_cases = []


def attrib_of(rows):
    return [(r.get("agent"), r.get("agents")) for r in rows]


def one(desc, want, extra=None):
    before = len(lines())
    run("Bash", {"command": f"{S}/phpv {SRC}"}, extra=extra)
    got = attrib_of(lines()[before:])
    passed = got == want
    attrib_cases.append(passed)
    print(f"{len(CASES) + len(extra_cases) + len(attrib_cases):>2} "
          f"{desc:<40} {str(got):<26} "
          + ("      pass" if passed else f"      FAIL expected={want}"))


one("outside a subagent → attributed to the parent", [(None, 0)])

run("Task", {"subagent_type": "php-behavior-analyst"})
one("one Task open → attributed to that agent", [("php-behavior-analyst", 1)])

run("Task", {"subagent_type": "php-rule-recheck"})
one("two Tasks open → recorded as ambiguous", [(None, 2)])

run("Task", {"subagent_type": "php-rule-recheck"}, event="PostToolUse")
one("one closed → attributed to the remaining one", [("php-behavior-analyst", 1)])

run("Task", {"subagent_type": "php-behavior-analyst"}, event="PostToolUse")
one("all closed → the parent again", [(None, 0)])

# Does a Task from another session contaminate this session's attribution
run("Task", {"subagent_type": "domain-scribe"}, session="othersess")
one("a Task from another session does not mix in", [(None, 0)])

# When the hook input states its own agent, that is canonical. `Task` registration is the fallback.
one("attributed by the input's agent_type", [("php-swap-extractor", 1)],
    extra={"agent_type": "php-swap-extractor", "agent_id": "ag-01"})

run("Task", {"subagent_type": "php-behavior-analyst"})
one("the input wins over the Task registration state", [("php-swap-extractor", 1)],
    extra={"agent_type": "php-swap-extractor", "agent_id": "ag-01"})
run("Task", {"subagent_type": "php-behavior-analyst"}, event="PostToolUse")


# ------------------------------------------------------ public-repository guard cases
# `guard-company-content.py` in the same directory. Three commands trigger this guard but only
# the index was checked, and the two commands whose index is empty (`commit -am` and `push`)
# passed without a single line being checked. So every case below walks a **failure path** - the
# moment the index is empty, the moment no baseline can be decided, the moment there is no config.
# The happy path is kept only as a control (that `commit -m`, which only reads the index, passes).
print("-" * 96)
GUARD = os.path.join(os.path.dirname(os.path.abspath(HOOK)),
                     "guard-company-content.py")
guard_cases = []

GBASE = os.path.join(BASE, "guard")
REPO = os.path.join(GBASE, "repo")
OTHER = os.path.join(GBASE, "other")
REMOTE = os.path.join(GBASE, "remote.git")
NOUP = os.path.join(GBASE, "noupstream")
IGNORED_DIR = "company-checkout"        # fake. The real name is never written here
HOST = "gate.internal.invalid"          # a reserved TLD. Not a real host
ISSUE = "TICKET-4471"                   # a fake tracker
CFG = os.path.join(REPO, ".claude", "config", "redaction.json")
PATTERNS = {"patterns": [{"name": "internal-hostname",
                          "regex": r"\b[a-z0-9-]+\.internal\.invalid\b"},
                         {"name": "issue-id", "regex": r"\bTICKET-\d+\b"}],
            "allowPaths": [".claude/config/redaction.json"]}


def git_in(repo, *args):
    p = subprocess.run(["git", "-c", "user.email=t@example.invalid",
                        "-c", "user.name=selftest", "-c", "commit.gpgsign=false",
                        "-C", repo, *args],
                       capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p


def init_repo(d, bare=False):
    os.makedirs(d, exist_ok=True)
    subprocess.run(["git", "init", "-q"] + (["--bare"] if bare else []) + [d],
                   capture_output=True, text=True, timeout=60)
    git_in(d, "symbolic-ref", "HEAD", "refs/heads/main")   # main regardless of version


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def guard(command, project=REPO):
    body = {"tool_name": "Bash", "tool_input": {"command": command},
            "hook_event_name": "PreToolUse", "cwd": project}
    return subprocess.run([sys.executable, GUARD], input=json.dumps(body),
                          capture_output=True, text=True, timeout=60,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": project})


def gtext(p):
    """The sentence the hook means to show a person. Unwraps the JSON on stdout and appends stderr."""
    out = ""
    try:
        out += json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        out += p.stdout or ""
    return out + (p.stderr or "")


def gcase(desc, p, want_rc, needles=(), absent=(), in_stdout=()):
    text = gtext(p)
    ok = (p.returncode == want_rc
          and all(n in text for n in needles)
          and all(n not in text for n in absent)
          and all(n in (p.stdout or "") for n in in_stdout))
    guard_cases.append(ok)
    no = len(CASES) + len(extra_cases) + len(attrib_cases) + len(guard_cases)
    print(f"{no:>2} {desc:<40} {'exit ' + str(p.returncode):<26} {'':<6} "
          + ("pass" if ok else
             f"FAIL expected exit={want_rc} needed={list(needles) + list(in_stdout)} "
             f"forbidden={list(absent)} :: " + " ".join(text.split())[:180]))


if not os.path.isfile(GUARD):
    # A missing hook is not a skip. A repository whose guard has disappeared printing green would
    # make this file create the very failure shape it exists to prevent.
    guard_cases.append(False)
    print(f"{len(CASES) + len(extra_cases) + len(attrib_cases) + 1:>2} "
          f"{'the guard hook is in the same directory':<40} {'none':<26} {'':<6} FAIL {GUARD}")
else:
    init_repo(REPO)
    init_repo(OTHER)
    init_repo(NOUP)
    init_repo(REMOTE, bare=True)
    write(os.path.join(REPO, ".gitignore"),
          f"/{IGNORED_DIR}/\nhandoff/\n/.claude/config/redaction.json\n")
    write(CFG, json.dumps(PATTERNS, ensure_ascii=False))
    write(os.path.join(REPO, "docs", "clean.md"), "# a clean document\none line of body.\n")
    git_in(REPO, "add", ".gitignore", "docs/clean.md")
    git_in(REPO, "commit", "-q", "-m", "baseline")
    git_in(REPO, "remote", "add", "origin", REMOTE)
    git_in(REPO, "push", "-q", "-u", "origin", "main")

    # (1) the index - the path that was caught even before. Kept as a control
    # Only the first match on a line is reported (break per line). So seeing both patterns
    # reported needs two lines - putting them on one line makes the second report unverifiable.
    write(os.path.join(REPO, "docs", "leak.md"),
          f"the production host is {HOST}.\nthe related ticket is {ISSUE}.\n")
    git_in(REPO, "add", "docs/leak.md")
    gcase("git add: blocks a leak in the index", guard("git add docs/leak.md"), 2,
          ["the index", "issue-id"])
    git_in(REPO, "reset", "-q")
    os.remove(os.path.join(REPO, "docs", "leak.md"))

    # (2)-(4) the index is empty and the leak is only in the working tree
    write(os.path.join(REPO, "docs", "clean.md"),
          f"# a clean document\nwrote the production host {HOST}.\n")
    gcase("commit -m: passes because only the index is committed (control)",
          guard('git commit -m "x"'), 0, absent=["internal-hostname"])
    gcase("commit -am: checks the working tree and blocks",
          guard('git commit -am "x"'), 2, ["the working tree", "internal-hostname"])
    gcase("a git later in a compound command is read separately",
          guard('echo hi && git commit -am "x"'), 2, ["the working tree"])

    # (5) A change that **removes** a leak is not blocked. Check that the property of reading only
    #     added lines carries into the working-tree check too.
    git_in(REPO, "add", "docs/clean.md")
    git_in(REPO, "commit", "-q", "-m", "leak lands")
    write(os.path.join(REPO, "docs", "clean.md"),
          "# a clean document\nremoved the host line.\n")
    gcase("commit -am: a change that removes a leak is not blocked",
          guard('git commit -am "removed"'), 0, absent=["internal-hostname"])

    # (6) push - the commits already exist and the index is empty
    gcase("push: checks commits absent from the remote and blocks", guard("git push"), 2,
          ["origin/main..HEAD", "internal-hostname"])

    # (7) When no baseline can be decided. It does not let it through and says why
    write(os.path.join(NOUP, "note.md"), f"ticket {ISSUE}\n")
    git_in(NOUP, "add", "note.md")
    git_in(NOUP, "commit", "-q", "-m", "x")
    gcase("push: blocks when no baseline can be decided and says what is missing",
          guard("git push", project=NOUP), 2,
          ["baseline", "@{upstream}", "origin/main", "that is not a pass"],
          absent=["redaction.example.json"])

    # (8)-(9) When there is no config. The content check blocks and the path check still runs
    os.rename(CFG, CFG + ".bak")
    gcase("a missing redaction config blocks", guard("git add docs/clean.md"), 2,
          ["not one line", "redaction.example.json"])
    write(os.path.join(REPO, IGNORED_DIR, "note.md"), "one line of company content\n")
    git_in(REPO, "add", "-f", IGNORED_DIR + "/note.md")
    gcase("the path check runs even with no config",
          guard("git add -f " + IGNORED_DIR + "/note.md"), 2,
          ["company path", IGNORED_DIR, "redaction.example.json"])
    git_in(REPO, "reset", "-q")
    os.rename(CFG + ".bak", CFG)

    # (10)-(11) The config exists but sees nothing
    write(CFG, json.dumps({"patterns": []}))
    gcase("zero patterns blocks", guard("git add docs/clean.md"), 2,
          ["0 usable patterns", "redaction.example.json"])
    write(CFG, json.dumps({"patterns": [{"name": "half-open",
                                         "regex": "[unclosed"}]}))
    gcase("a pattern that fails to compile is named and blocks",
          guard("git add docs/clean.md"), 2, ["half-open", "compiled"])
    write(CFG, json.dumps(PATTERNS, ensure_ascii=False))

    # (12) A command that publishes nothing is not a trigger
    gcase("git status is not a trigger", guard("git status"), 0,
          absent=["public-repository guard"])

    # (13) A command aimed at another repository. The fact that it did not judge has to stay
    #      **where Claude can see it** (additionalContext on stdout) - the stderr of an exit 0
    #      does not reach there, so stderr alone is indistinguishable from having checked.
    write(os.path.join(OTHER, "note.md"), f"{HOST}\n")
    git_in(OTHER, "add", "note.md")
    gcase("it says it did not judge when the target is another repository",
          guard(f"git -C {OTHER} commit -am x"), 0,
          ["did not judge"], in_stdout=["additionalContext"])

    # (14) It blocks when `-C` cannot be determined. A shell variable arrives at the hook
    #      unexpanded, and that repository might be this public one - not sending an unknown
    #      state out as a pass is a defect this guard has already fixed once.
    gcase("a shell variable in -C blocks as undeterminable",
          guard('git -C "$REPO" commit -am x'), 2,
          ["could not determine the repository", "write the absolute path as a literal", "that is not a pass"])

total = len(CASES) + len(extra_cases) + len(attrib_cases) + len(guard_cases)
passed = ok + sum(extra_cases) + sum(attrib_cases) + sum(guard_cases)
shutil.rmtree(BASE, ignore_errors=True)
print("-" * 96)
print(f"{passed}/{total} pass")
sys.exit(0 if passed == total else 1)
