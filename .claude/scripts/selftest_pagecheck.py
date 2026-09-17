#!/usr/bin/env python3
"""pagecheck cases. Runs on synthetic fixtures only - no company tree, no docker, no stack.

    python3 selftest_pagecheck.py [path to pagecheck]

Four fixtures are the whole of this file.

1. **A fake surface** - a single-threaded HTTP server serving the legacy page and the toggle
   read-back page, appending one JSONL line to the dual-run log per request. What the helper does.
2. **A fake `docker`** - a script placed on PATH. `up -d --force-recreate` **copies** the compose
   env file into a "delivered environment" file. That is the core of this fixture: it splits
   writing a value and that value reaching PHP into two separate facts, so cutting delivery
   actually exercises whether `pagecheck` refuses to capture.
3. **A synthetic config** - passed with `--config`. The real `workspace.json` is never read.
4. **Two editions of the helper** - the template as-is, and one with `NOISE_ENV` and `FAKEVALUE_ENV` removed.
   The second exercises "never quietly skip something unsupported".

**What is checked here is the verdict and the exit code.** In particular that 3 (could not check)
never mixes with 0, and that the failure paths are actually walked - a cap stop, a read-back
mismatch, a missing config key, a red fake-value injection, a recorded coverage skip, a broken `state.json`.
"""
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "pagecheck")
TEMPLATE = os.path.join(os.path.dirname(HERE), "templates", "MigrationExperiment.php")
if not os.path.isfile(TOOL):
    sys.exit(f"usage: selftest_pagecheck.py [path to pagecheck]  (looked at: {TOOL})")

BASE = tempfile.mkdtemp(prefix="pagecheck-selftest-")
PHP = shutil.which("php")
results, skipped = [], []


def check(name, ok, detail="", secs=None):
    results.append((name, ok, detail))
    t = f"  {secs:5.1f}s" if secs is not None else "        "
    print(f"  {'pass' if ok else 'FAIL'}{t}  {name}" + (f"   {detail}" if detail else ""))


def skip(name, why):
    skipped.append((name, why))
    print(f"  skipped      {name}   ({why})")


# ------------------------------------------------------------ the fake surface

CONTAINER = "surface-web"            # a name this fixture invented. It appears only in the config.
DELIVERED = os.path.join(BASE, "delivered.env")
FLAGS = os.path.join(BASE, "flags")
LOG = os.path.join(BASE, "dual.jsonl")
MODE_VALUES = {"php": "legacy", "dual": "dual", "spring": "migrated"}


def flag(name):
    return os.path.exists(os.path.join(FLAGS, name))


def set_flag(name, on=True):
    os.makedirs(FLAGS, exist_ok=True)
    p = os.path.join(FLAGS, name)
    if on:
        open(p, "w").close()
    elif os.path.exists(p):
        os.remove(p)


def delivered():
    """What `getenv()` sees inside the container. Only what was delivered."""
    out = {}
    try:
        with open(DELIVERED, encoding="utf-8") as fh:
            for line in fh:
                if "=" in line and not line.strip().startswith("#"):
                    k, _, v = line.strip().partition("=")
                    out[k.strip()] = v.strip()
    except OSError:
        pass
    return out


def append_log(rec):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


class App(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def do_GET(self):
        env = delivered()
        raw = env.get("X_BACKEND_DEMO_PAGE", "")
        mode = MODE_VALUES.get(raw, "legacy")
        noise = env.get("MIGRATION_EXPERIMENT_NOISE") or ""
        fakevalue = env.get("MIGRATION_EXPERIMENT_FAKEVALUE") or ""
        path = self.path.split("?")[0]

        if path == "/__toggle.php":
            # The read-back page prints exactly one mode token. No heading, no explanation.
            return self.send(raw.encode("ascii") or b"php")
        if path == "/":
            return self.send(b"ok")
        if path != "/page.php":
            return self.send(b"not found", 404)

        if flag("coverage_on"):
            # Imitates Xdebug dropping executed lines. The content is decided by the case.
            with open(os.path.join(FLAGS, "coverage_content"), encoding="utf-8") as fh:
                body = fh.read()
            with open(COVERAGE, "w", encoding="utf-8") as fh:
                fh.write(body)

        ts = datetime.datetime.now().astimezone().isoformat()
        if flag("nolog"):
            # The state where the log path is not inside the container. The screen is fine and only the file is empty.
            pass
        elif noise:
            # Legacy against legacy. A key that moves when the same code runs twice is the run-to-run difference.
            append_log({"ts": ts, "experiment": "demo-page", "mode": "dual",
                        "equal": False, "diff_keys": ["rendered_at"],
                        "ignored_keys": [], "truncated": False,
                        "context": {"noise": True},
                        "control": {"rendered_at": 1}, "candidate": {"rendered_at": 2}})
        elif mode == "dual":
            bad = flag("mismatch")
            append_log({"ts": ts, "experiment": "demo-page", "mode": "dual",
                        "equal": not bad,
                        "diff_keys": ["items[0].title"] if bad else [],
                        "ignored_keys": [], "truncated": False,
                        **({"control": {"items": [{"title": "a"}]},
                            "candidate": {"items": [{"title": "b"}]}} if bad else {})})
        elif mode == "migrated" and fakevalue:
            append_log({"ts": ts, "experiment": "demo-page", "mode": "migrated",
                        "fakevalue": fakevalue, "equal": True, "diff_keys": [],
                        "ignored_keys": [], "truncated": False})

        value = "42"
        if mode == "migrated" and fakevalue and flag("leaky"):
            # The screen still uses the legacy return value - the fake value renders as-is.
            value = "FAKEVALUE:" + fakevalue
        self.send(f"<html><body><p>total {value}</p></body></html>".encode())

    def send(self, body, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


PORT = free_port()
BFF_PORT = free_port()
server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), App)
threading.Thread(target=server.serve_forever, daemon=True).start()
# What stage 1's BFF port-reachability check looks at. It only listens.
bff = socket.socket()
bff.bind(("127.0.0.1", BFF_PORT))
bff.listen(8)


# ------------------------------------------------------------ the fake docker

BIN = os.path.join(BASE, "bin")
os.makedirs(BIN, exist_ok=True)
COMPOSE_DIR = os.path.join(BASE, "compose")
ENV_FILE = os.path.join(COMPOSE_DIR, ".env")
os.makedirs(COMPOSE_DIR, exist_ok=True)
with open(ENV_FILE, "w", encoding="utf-8") as fh:
    fh.write("# Other services' values live in this file too. Not one line may be touched.\n"
             "OTHER_SERVICE_FLAG=keep-me\n")

FAKE_DOCKER = f'''#!/usr/bin/env python3
"""An imitation of compose. `up` copies the env file into the delivered environment - that is the
pair of facts this fixture separates: writing a value, and that value reaching PHP."""
import os, shutil, sys
FLAGS, DELIVERED = {FLAGS!r}, {DELIVERED!r}
args = sys.argv[1:]
def has(name): return os.path.exists(os.path.join(FLAGS, name))
env_file = None
for i, a in enumerate(args):
    if a == "--env-file" and i + 1 < len(args):
        env_file = args[i + 1]
if "ps" in args:
    # Three fields, because two axes carry a name here: the compose **service** and the
    # **container** it runs as. A fixture that prints only the service can never reproduce the
    # state where the config names the wrong axis - which is exactly how this shipped, and the
    # real stack then read as "this project has no such container" while it was running.
    if has("container_gone"):
        print("other\\trunning\\tos-other")
    elif has("wrong_axis"):
        print("svc-{CONTAINER}\\trunning\\t{CONTAINER}")
    else:
        print("{CONTAINER}\\trunning\\tos-{CONTAINER}")
    sys.exit(0)
if "up" in args:
    if has("nodeliver"):          # the state where the container could not be recreated
        sys.exit(0)
    shutil.copyfile(env_file, DELIVERED)
    sys.exit(0)
if "exec" in args:
    mods = ["Core", "json", "pcre"] + (["xdebug"] if has("xdebug") else [])
    print("[PHP Modules]"); print("\\n".join(mods))
    sys.exit(0)
sys.exit(0)
'''
with open(os.path.join(BIN, "docker"), "w", encoding="utf-8") as fh:
    fh.write(FAKE_DOCKER)
os.chmod(os.path.join(BIN, "docker"), 0o755)


# ------------------------------------------------------------ the synthetic config

TREE = os.path.join(BASE, "tree")
HELPER_DIR = os.path.join(TREE, "helper")
NOHELPER_DIR = os.path.join(TREE, "helper-old")
SCHEMA_DIR = os.path.join(BASE, "backend", "schema")
for d in (HELPER_DIR, NOHELPER_DIR, SCHEMA_DIR, os.path.join(TREE, "marker")):
    os.makedirs(d, exist_ok=True)
with open(os.path.join(SCHEMA_DIR, "demo.graphqls"), "w", encoding="utf-8") as fh:
    fh.write("type Query { demo: String }\n")

if os.path.isfile(TEMPLATE):
    shutil.copyfile(TEMPLATE, os.path.join(HELPER_DIR, "MigrationExperiment.php"))
    body = open(TEMPLATE, encoding="utf-8").read()
    old = (body.replace("const NOISE_ENV", "const UNRELATED_A")
               .replace("const FAKEVALUE_ENV", "const UNRELATED_B"))
    with open(os.path.join(NOHELPER_DIR, "MigrationExperiment.php"), "w",
              encoding="utf-8") as fh:
        fh.write(old)

SWAP_PHP = os.path.join(TREE, "swap.php")
with open(SWAP_PHP, "w", encoding="utf-8") as fh:
    fh.write("<?php\nfunction demo_body($p)\n{\n    return array('total' => 42);\n}\n")

COVERAGE = os.path.join(BASE, "coverage.json")
PROJ = os.path.join(BASE, "proj")
os.makedirs(os.path.join(PROJ, ".claude", "config"), exist_ok=True)


def write_config(name, **over):
    cfg = {
        "legacy": {
            "root": BASE, "treeRoot": TREE, "treeMarker": "marker",
            "services": {"helper": "helper"}, "sharedLibrary": "helper",
            "primaryService": "helper",
            "tooling": {"phpBinary": PHP or "php"},
            "swap": {"hashesFile": "body-hashes.json"},
            "snapshot": {"normalize": [], "errorMarker": "__NEVER_AN_ERROR__",
                         "timeoutSeconds": 10},
            "dualRun": {"logPath": LOG, "logEnvVar": "MIGRATION_EXPERIMENT_LOG",
                        "readbackPath": "/__toggle.php",
                        "ignoreFile": "ignore.json",
                        "noiseEnvVar": "MIGRATION_EXPERIMENT_NOISE",
                        "fakeValueEnvVar": "MIGRATION_EXPERIMENT_FAKEVALUE",
                        "coveragePath": COVERAGE},
            "surfaces": {"demo": {
                "docroot": TREE, "localBaseUrl": f"http://127.0.0.1:{PORT}",
                "container": CONTAINER, "daoPaths": [],
                "loggedOutMarker": "__NEVER_LOGGED_OUT__", "charset": "utf-8"}},
            "docker": {"composeDir": COMPOSE_DIR, "envFile": ENV_FILE},
            "switch": {"envVarPattern": "X_BACKEND_{PAGE}",
                       "values": {"legacy": "php", "dual": "dual",
                                  "migrated": "spring"},
                       "helperPath": HELPER_DIR},
        },
        "backend": {"root": BASE, "graphqlSchemaDir": SCHEMA_DIR,
                    "proxy": {"module": ":apps:x", "port": BFF_PORT,
                              "packageBase": "x"}},
        "docs": {"root": BASE, "pagesDir": "pages", "domainDir": "domain"},
    }
    for dotted_key, val in over.items():
        key = dotted_key.replace("__", ".")
        cur, parts = cfg, key.split(".")
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        if val is None:
            cur.pop(parts[-1], None)
        else:
            cur[parts[-1]] = val
    path = os.path.join(PROJ, ".claude", "config", name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=1)
    return path


CONFIG = write_config("workspace.json")
NO_COMPOSE = write_config("no-compose.json", legacy__docker__envFile=None)
NO_READBACK = write_config("no-readback.json",
                           legacy__dualRun__readbackPath="<relative path>")
OLD_HELPER = write_config("old-helper.json",
                          legacy__switch__helperPath=NOHELPER_DIR)
NO_COVERAGE = write_config("no-coverage.json",
                           legacy__dualRun__coveragePath=None)


# ------------------------------------------------------------ run helpers

ENVIRON = dict(os.environ)
ENVIRON["PATH"] = BIN + os.pathsep + ENVIRON.get("PATH", "")
ENVIRON.pop("CLAUDE_PROJECT_DIR", None)


def run(args, timeout=180):
    t0 = time.time()
    p = subprocess.run([sys.executable, TOOL] + args, capture_output=True,
                       text=True, timeout=timeout, cwd=BASE, env=ENVIRON)
    return p, time.time() - t0


def htmlsnap(args, timeout=120):
    return subprocess.run([sys.executable, os.path.join(HERE, "htmlsnap")] + args,
                          capture_output=True, text=True, timeout=timeout,
                          cwd=BASE, env=ENVIRON)


def deliver(mode, **extra):
    """Deliver the toggle directly - to place the fixture in any mode without pagecheck."""
    value = {"legacy": "php", "dual": "dual", "migrated": "spring"}[mode]
    lines = [f"X_BACKEND_DEMO_PAGE={value}"]
    lines += [f"{k}={v}" for k, v in extra.items()]
    with open(DELIVERED, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


PAGE_ID = "demo_page"          # the toggle variable name comes from this: X_BACKEND_DEMO_PAGE


def new_page(name, observations=True, init=True, caps="L2=9,L3=9"):
    """One page directory. **Every id is the same; only the directory differs.**

    The id decides the toggle env var name (`X_BACKEND_{PAGE}`), so a different id per fixture
    splits the variable the fake app reads from the variable pagecheck writes - and that split
    arrives in exactly the same shape as "the toggle never reached PHP".
    The fixture imitates a tool failure only through the `nodeliver` flag that cuts delivery.
    """
    d = os.path.join(BASE, "pages", name)
    os.makedirs(d, exist_ok=True)
    if observations:
        with open(os.path.join(d, "observations.json"), "w", encoding="utf-8") as fh:
            json.dump({"surface": "demo", "entries": [
                {"id": "page", "path": "/page.php", "params": {"id": "1"},
                 "mode": "full", "rules": ["R-07"]}]}, fh)
    if init:
        p, _ = run([d, "--init", "--page", PAGE_ID, "--cap", caps])
        if p.returncode != 0:
            sys.exit(f"--init failed: {p.stdout}{p.stderr}")
    return d


def state_of(d):
    with open(os.path.join(d, "state.json"), encoding="utf-8") as fh:
        return json.load(fh)


def migrated_baseline(d):
    """The `migrated` capture stage 5 compares against, made without spending a pagecheck round.

    Going through `--stage 4` would spend an L2 round, and the one case that needs this capture
    is the one that caps L2 deliberately. Capturing directly keeps the cap arithmetic intact.
    """
    deliver("migrated")
    r = htmlsnap(["capture", "--observations", os.path.join(d, "observations.json"),
                  "--out", os.path.join(d, "captures", "migrated"),
                  "--toggle-expect", "migrated", "--config", CONFIG])
    if r.returncode != 0:
        sys.exit(f"migrated capture failed: {r.stdout}{r.stderr}")


def baseline(d):
    """The legacy baseline capture Phase 1 has to leave behind."""
    deliver("legacy")
    r = htmlsnap(["capture", "--observations", os.path.join(d, "observations.json"),
                  "--out", os.path.join(d, "captures", "legacy"),
                  "--toggle-expect", "legacy", "--config", CONFIG])
    if r.returncode != 0:
        sys.exit(f"baseline capture failed: {r.stdout}{r.stderr}")


def make_pins(d):
    """Record the body hash with `phpmove hash`. None when php is missing."""
    if not PHP:
        return None
    path = os.path.join(d, "body-hashes.json")
    r = subprocess.run([sys.executable, os.path.join(HERE, "phpmove"), "hash",
                        SWAP_PHP, "demo_body", "--hashes", path,
                        "--config", CONFIG], capture_output=True, text=True,
                       timeout=180, cwd=BASE, env=ENVIRON)
    return path if r.returncode == 0 and os.path.isfile(path) else None


print(f"# tool {TOOL}   surface 127.0.0.1:{PORT}   php {'present' if PHP else 'absent'}")

# ------------------------------------------------------------ 1. usage and stage parsing
print("\n### 1. usage and stage parsing")

p, _ = run([])
check("no arguments → exit 2", p.returncode == 2, f"exit={p.returncode}")

d = new_page("stages")
p, _ = run([d, "--stage", "9", "--config", CONFIG])
check("an unknown stage is exit 2 and it lists the stages that exist",
      p.returncode == 2 and "1-7" in p.stderr, f"exit={p.returncode}")

p, _ = run([d, "--stage", "1..7", "--dry-run", "--config", CONFIG])
listed = [l for l in p.stdout.splitlines() if l.strip().startswith("stage")]
check("the range `1..7` expands to seven stages",
      p.returncode == 0 and len(listed) == 7, f"exit={p.returncode} · {len(listed)} lines")

p, _ = run([d, "--stage", "3,4,7", "--dry-run", "--config", CONFIG])
listed = [l.split()[1] for l in p.stdout.splitlines() if l.strip().startswith("stage")]
check("the list `3,4,7` arrives in the order it was written",
      listed == ["3", "4", "7"], f"{listed}")

p, _ = run([d, "--stage", "1", "--init", "--page", "x", "--config", CONFIG])
check("--init does not overwrite an existing state.json (exit 3)",
      p.returncode == 3 and "does not overwrite" in p.stderr, f"exit={p.returncode}")

# ------------------------------------------------------------ 2. state.json
print("\n### 2. state.json - missing or broken")

bare = os.path.join(BASE, "pages", "bare")
os.makedirs(bare, exist_ok=True)
p, _ = run([bare, "--stage", "7", "--config", CONFIG])
check("a missing state.json is exit 3 and points at --init",
      p.returncode == 3 and "--init" in p.stderr, f"exit={p.returncode}")
check("it does not quietly create a missing state.json",
      not os.path.exists(os.path.join(bare, "state.json")))

broken = new_page("broken")
with open(os.path.join(broken, "state.json"), "w", encoding="utf-8") as fh:
    fh.write("{ this is not json")
p, _ = run([broken, "--stage", "7", "--config", CONFIG])
check("a broken state.json is exit 3 and is not overwritten",
      p.returncode == 3 and "could not be read" in p.stderr, f"exit={p.returncode}")
check("the broken content is left as it was",
      open(os.path.join(broken, "state.json")).read().startswith("{ this"))

half = new_page("half")
doc = state_of(half)
del doc["loops"]
with open(os.path.join(half, "state.json"), "w", encoding="utf-8") as fh:
    json.dump(doc, fh)
p, _ = run([half, "--stage", "7", "--config", CONFIG])
check("a state.json whose shape differs from the contract is also exit 3 (no loops)",
      p.returncode == 3 and "loops" in p.stderr, f"exit={p.returncode}")

fresh = state_of(new_page("fresh"))
check("a freshly created check result is null, not 0 (nothing unmeasured is recorded green)",
      all(fresh["checks"][g] is None for g in
          ("unexpected", "baseline_diff", "fakevalue", "legacy_lines")),
      str(fresh["checks"]))

# ------------------------------------------------------------ 3. missing config keys
print("\n### 3. a missing config key names the key and exits 3")

d = new_page("cfg")
p, _ = run([d, "--stage", "7", "--config", NO_COMPOSE])
check("a missing compose env file key is exit 3 plus the key name",
      p.returncode == 3 and "legacy.docker.envFile" in p.stderr,
      f"exit={p.returncode} · {p.stderr.strip()[:70]}")

p, _ = run([d, "--stage", "7", "--config", os.path.join(BASE, "nope.json")])
check("a missing config file itself is exit 3",
      p.returncode == 3 and "nope.json" in p.stderr,
      f"exit={p.returncode} · {p.stderr.strip()[:70]}")

d2 = new_page("cfg2")
baseline(d2)
p, _ = run([d2, "--stage", "1", "--config", NO_READBACK])
check("a read-back path still holding the skeleton placeholder makes stage 1 exit 3",
      p.returncode == 3 and "read-back config X" in p.stdout,
      f"exit={p.returncode}")

# ------------------------------------------------------------ 4. stage 1 environment
print("\n### 4. stage 1 - the four environment checks")

d = new_page("env")
deliver("legacy")
p, secs = run([d, "--stage", "1", "--config", CONFIG])
# `"pass" in p.stdout` did not count four. Three of the four could stop running and the stage
# would still print pass and exit 0. Name each of the four.
check("all four passing is exit 0",
      p.returncode == 0 and all(n in p.stdout for n in (
          "backend schema OK", "upstream reachable OK",
          "read-back config OK", "container comparison OK")),
      p.stdout.strip().splitlines()[-2:][0] if p.stdout.strip() else "", secs=secs)

set_flag("container_gone")
p, _ = run([d, "--stage", "1", "--config", CONFIG])
set_flag("container_gone", False)
check("a container absent from the compose project is exit 3 (not 0)",
      p.returncode == 3 and "container comparison X" in p.stdout, f"exit={p.returncode}")

# The state this check shipped blind to: the value is a real name on the **other** axis. Reported
# as a bare "absent" it reads as a broken environment and sends the next person to docker, when
# the fix is one line of config. Failing is not enough - it has to say which axis.
set_flag("wrong_axis")
p, _ = run([d, "--stage", "1", "--config", CONFIG])
set_flag("wrong_axis", False)
check("a container name where a compose service is expected names the axis, not just 'absent'",
      p.returncode == 3 and "container comparison X" in p.stdout
      and "is a container name, not a compose service" in p.stderr,   # note() writes to stderr
      f"exit={p.returncode}")

# ------------------------------------------------------------ 5. toggle read-back
print("\n### 5. the toggle - a differing read-back means no capture")

d = new_page("readback")
baseline(d)
deliver("legacy")
set_flag("nodeliver")
p, secs = run([d, "--stage", "3", "--config", CONFIG])
set_flag("nodeliver", False)
check("a value written to env that never reaches PHP is exit 3",
      p.returncode == 3 and "read-back" in p.stderr, f"exit={p.returncode}", secs=secs)
check("a read-back mismatch creates no capture directory",
      not os.path.isdir(os.path.join(d, "captures", "dual")))
check("the round was still counted (the attempt is recorded)",
      state_of(d)["loops"]["L2"]["n"] == 1, str(state_of(d)["loops"]["L2"]))

check("no env line belonging to another service was touched",
      "OTHER_SERVICE_FLAG=keep-me" in open(ENV_FILE).read())

# ------------------------------------------------------------ 6. stage 2 noise
print("\n### 6. stage 2 - the run-to-run difference and its seeds")

d = new_page("noise")
deliver("legacy")
p, _ = run([d, "--stage", "2", "--config", OLD_HELPER])
check("a helper that does not support noise mode is exit 3, never a skip",
      p.returncode == 3 and "does not support" in p.stdout,
      f"exit={p.returncode}")

ign = os.path.join(d, "ignore.json")
with open(ign, "w", encoding="utf-8") as fh:
    json.dump({"rules": [{"experiment": "demo-page", "keys": ["total"],
                          "rules": "R-17", "reason": "의도수정"}]}, fh)
open(LOG, "w").close()
p, secs = run([d, "--stage", "2", "--config", CONFIG])
rules = json.load(open(ign))["rules"]
seeds = [r for r in rules if r.get("origin") == "noise"]
check("the run-to-run difference runs and seeds are created → exit 0",
      p.returncode == 0, f"exit={p.returncode} · {p.stdout.strip()[-120:]}", secs=secs)
check("a seed is distinguished by `origin: \"noise\"`",
      len(seeds) == 1 and seeds[0]["keys"] == ["rendered_at"], str(seeds))
check("a seed carries no rule row (because it points at no approved row)",
      seeds and seeds[0]["rules"] is None)
check("a human-approved rule is left as it was",
      any(r.get("rules") == "R-17" for r in rules), f"{len(rules)} rules")
check("stage 2 leaves the toggle at legacy", state_of(d)["toggle"] == "legacy",
      str(state_of(d)["toggle"]))

# ------------------------------------------------------------ 7. stage 3 dual
print("\n### 7. stage 3 - unexpected mismatches")

d = new_page("dual")
baseline(d)
open(LOG, "w").close()
p, secs = run([d, "--stage", "3", "--config", CONFIG])
check("zero unexpected is exit 0 and the check result is recorded as 0",
      p.returncode == 0 and state_of(d)["checks"]["unexpected"] == 0,
      f"exit={p.returncode} · {state_of(d)['checks']}", secs=secs)

d = new_page("dual-bad")
baseline(d)
open(LOG, "w").close()
set_flag("mismatch")
p, _ = run([d, "--stage", "3", "--config", CONFIG])
set_flag("mismatch", False)
check("an unexpected mismatch is exit 1 (not 3 - the check did run)",
      p.returncode == 1 and state_of(d)["checks"]["unexpected"] >= 1,
      f"exit={p.returncode} · {state_of(d)['checks']}")

open(LOG, "w").close()
set_flag("nolog")
p, _ = run([d, "--stage", "3", "--note", "환경", "--config", CONFIG])
set_flag("nolog", False)
# The page is deliberately the one above, which already measured `unexpected 1`. So the
# assertion can be exact: an unreadable log neither measures nor clears - the 1 is still a 1.
# Asserting only the exit code would leave the failure this case exists for undetected,
# because writing 0 here and exiting 3 are not mutually exclusive.
check("an empty log is exit 3 - never read as 'no mismatch'",
      p.returncode == 3 and "could not read the dual-run log" in p.stdout
      and state_of(d)["checks"]["unexpected"] == 1,
      f"exit={p.returncode} · {state_of(d)['checks']}")

# ------------------------------------------------------------ 8. stage 4 migrated
print("\n### 8. stage 4 - the migrated capture")

d = new_page("mig")
p, _ = run([d, "--stage", "4", "--config", CONFIG])
check("no baseline capture is exit 3 (nothing to compare against)",
      p.returncode == 3 and "baseline" in p.stdout, f"exit={p.returncode}")

baseline(d)
open(LOG, "w").close()
p, secs = run([d, "--stage", "4", "--config", CONFIG])
check("a migrated screen matching the baseline is exit 0",
      p.returncode == 0 and state_of(d)["checks"]["baseline_diff"] == 0,
      f"exit={p.returncode} · {state_of(d)['checks']}", secs=secs)

# ------------------------------------------------------------ 9. stage 5 fake-value injection
print("\n### 9. stage 5 - fake-value injection (identical to pass)")

d = new_page("fakevalue")
baseline(d)
open(LOG, "w").close()
p, _ = run([d, "--stage", "4", "--config", CONFIG])
hashes = make_pins(d)

p, _ = run([d, "--stage", "5", "--config", OLD_HELPER])
check("a helper that does not support fake-value injection is exit 3",
      p.returncode == 3 and "does not support" in p.stdout, f"exit={p.returncode}")

set_flag("leaky")
p, secs = run([d, "--stage", "5", "--config", CONFIG])
set_flag("leaky", False)
check("it fails when the fake value appears on screen (the legacy value renders)",
      p.returncode == 1 and state_of(d)["checks"]["fakevalue"] == "fail",
      f"exit={p.returncode} · {state_of(d)['checks']['fakevalue']}", secs=secs)
check("it states the reason as 'comes from legacy'",
      "from legacy" in p.stderr, p.stderr.strip()[-90:])

if hashes:
    p, secs = run([d, "--stage", "5", "--note", "이관결함", "--config", CONFIG])
    check("an identical screen under the fake value passes, with body hashes unchanged",
          p.returncode == 0 and state_of(d)["checks"]["fakevalue"] == "pass"
          and "body hashes unchanged" in p.stdout,
          f"exit={p.returncode} · {p.stdout.strip().splitlines()[-2][-60:]}", secs=secs)
    with open(SWAP_PHP, "w", encoding="utf-8") as fh:   # edit inside the body
        fh.write("<?php\nfunction demo_body($p)\n{\n"
                 "    return array('total' => 43);\n}\n")
    p, _ = run([d, "--stage", "5", "--note", "확인만", "--config", CONFIG])
    # `!= 0` admitted exit 3, which is "could not check" - the substitution this OS exists to
    # block. The stage must have run and failed, and recorded that failure.
    check("a moved body hash stops fake-value injection passing",
          p.returncode == 1 and "a body hash moved" in p.stdout
          and state_of(d)["checks"]["fakevalue"] == "fail",
          f"exit={p.returncode} · {state_of(d)['checks']['fakevalue']}")
else:
    skip("fake-value pass · body hash comparison", "no php, so phpmove hash cannot run")

check("the fake-value variable is cleared again inside the stage",
      "MIGRATION_EXPERIMENT_FAKEVALUE" not in open(ENV_FILE).read(),
      open(ENV_FILE).read().replace("\n", " ")[:90])

# ------------------------------------------------------------ 10. stage 6 coverage
print("\n### 10. stage 6 - without Xdebug it skips and records that")

d = new_page("cov")
baseline(d)
p, secs = run([d, "--stage", "6", "--config", CONFIG])
st = state_of(d)
check("without Xdebug it skips (exit 0)", p.returncode == 0 and "skipped" in p.stdout,
      f"exit={p.returncode}", secs=secs)
check("the skip is recorded in state.json skips",
      "6" in (st.get("skips") or {}) and "Xdebug" in st["skips"]["6"],
      str(st.get("skips")))
check("a skipped stage's check result is null, not 0",
      st["checks"]["legacy_lines"] is None, str(st["checks"]["legacy_lines"]))

set_flag("xdebug")
p, _ = run([d, "--stage", "6", "--note", "환경", "--config", NO_COVERAGE])
check("Xdebug present but no coveragePath key is exit 3",
      p.returncode == 3 and "coveragePath" in p.stdout, f"exit={p.returncode}")

p, _ = run([d, "--stage", "6", "--note", "환경", "--config", CONFIG])
check("Xdebug present but no artifact produced is exit 3 (unwired coverage is never 0)",
      p.returncode == 3 and "wired up" in p.stdout, f"exit={p.returncode}")

if hashes:
    shutil.copyfile(hashes, os.path.join(d, "body-hashes.json"))
    recorded = list(json.load(open(hashes))["hashes"].values())[0]
    lo, hi = recorded["lines"][:2]
    set_flag("coverage_on")

    def coverage_is(payload):
        with open(os.path.join(FLAGS, "coverage_content"), "w",
                  encoding="utf-8") as fh:
            json.dump(payload, fh)

    coverage_is({recorded["file"]: {str(lo): 1, str(hi): 1}})
    p, _ = run([d, "--stage", "6", "--note", "환경", "--config", CONFIG])
    check("the moved body executing under migrated is a failure (exit 1)",
          p.returncode == 1 and state_of(d)["checks"]["legacy_lines"] == 2,
          f"exit={p.returncode} · {state_of(d)['checks']['legacy_lines']}")
    coverage_is({recorded["file"]: {str(hi + 500): 3}})
    p, _ = run([d, "--stage", "6", "--note", "확인만", "--config", CONFIG])
    check("lines outside the body are not counted (exit 0, check result 0)",
          p.returncode == 0 and state_of(d)["checks"]["legacy_lines"] == 0,
          f"exit={p.returncode}")
    set_flag("coverage_on", False)
else:
    skip("coverage line-range verdict", "no php, so the recorded line range cannot be built")
set_flag("xdebug", False)
if os.path.exists(COVERAGE):
    os.remove(COVERAGE)

# ------------------------------------------------------------ 11. caps
# --------------------------------------- 10.5 a could-not-measure round spends no budget
print("\n### 10.5 a could-not-measure round (exit 3) is returned to the budget")

# Counting the round **before** it runs is right - a run that died partway still spent one. But a
# round where the check itself could not run says nothing about the loop, so it spends no budget.
# The return is not left silent but recorded as a consecutive count.
d = new_page("unmeas", caps="L2=9,L3=2")
baseline(d)
set_flag("xdebug")

p, _ = run([d, "--stage", "6", "--config", CONFIG])
st = state_of(d)
check("ending could-not-measure is exit 3", p.returncode == 3, f"exit={p.returncode}")
check("that round is returned to the budget (L3 is 0)",
      st["loops"]["L3"]["n"] == 0, str(st["loops"]["L3"]))
check("the return is not left silent (it appears in the output)",
      "the round was returned" in p.stdout + p.stderr)
check("the could-not-measure streak is counted", (st.get("unmeasurable") or {}).get("L3") == 1,
      str(st.get("unmeasurable")))

p, _ = run([d, "--stage", "6", "--config", CONFIG])
st = state_of(d)
check("the second is returned too (it does not consume a cap of 2)",
      st["loops"]["L3"]["n"] == 0 and (st.get("unmeasurable") or {}).get("L3") == 2,
      f"{st['loops']['L3']} · {st.get('unmeasurable')}")

p, _ = run([d, "--stage", "6", "--config", CONFIG])
check("twice in a row is announced loudly", "in a row" in p.stderr, p.stderr[-140:])
check("but it does not block - blocking removes the way to confirm a fix, which deadlocks",
      p.returncode == 3 and "did not proceed" not in p.stderr,
      f"exit={p.returncode}")

# A round where measurement happened resets the streak to 0. Without Xdebug stage 6 skips, and a
# skip is also "the check ran and said it could not answer", so it is exit 0.
set_flag("xdebug", on=False)
p, _ = run([d, "--stage", "6", "--config", CONFIG])
st = state_of(d)
check("a round where measurement happened (including a skip) resets the streak to 0",
      not (st.get("unmeasurable") or {}).get("L3"),
      f"exit={p.returncode} · {st.get('unmeasurable')}")

print("\n### 11. caps - on reaching one, it does not proceed")

d = new_page("cap", caps="L2=1,L3=2")
migrated_baseline(d)
baseline(d)
make_pins(d)          # so the stage 5 below is a real round, not a stop at a missing file
open(LOG, "w").close()
p, _ = run([d, "--stage", "3", "--config", CONFIG])
check("the first round runs", p.returncode == 0, f"exit={p.returncode}")

deliver("legacy")
before = open(ENV_FILE).read()
p, _ = run([d, "--stage", "3,4", "--config", CONFIG])
check("reaching the cap is exit 4 - distinct from 1 (red)",
      p.returncode == 4 and "reached its cap" in p.stderr, f"exit={p.returncode}")
check("a cap stop touches neither the toggle nor the env file",
      open(ENV_FILE).read() == before)
check("a cap stop does not increment the round further",
      state_of(d)["loops"]["L2"]["n"] == 1, str(state_of(d)["loops"]["L2"]))
check("a cap stop states the check results alongside", "Check results" in p.stderr)

p, _ = run([d, "--stage", "5", "--config", CONFIG])
# Asserting only `!= 4` was green while stage 5 never ran at all: without a migrated baseline
# it exits 3 before the cap logic is reached, so L2's cap could have wrongly capped L3 and this
# case would not have noticed. The round L3 actually spent is the evidence.
# Asserting only `!= 4` was green while stage 5 never ran at all: with no migrated baseline it
# exits 3 before the cap logic is reached, so L2's cap could have wrongly capped L3 and this
# case would not have noticed. The round L3 took is the evidence. A round that ran and then
# could not measure is returned to the budget but leaves the streak behind, so either counter
# proves the same thing - that L3's budget was consulted while L2 sat at its cap.
_st = state_of(d)
_l3_ran = (_st["loops"]["L3"]["n"] == 1
           or (_st.get("unmeasurable") or {}).get("L3") == 1)
check("another loop's cap is counted separately (L3 runs even when L2 is capped)",
      p.returncode != 4 and "reached its cap" not in p.stderr and _l3_ran,
      f"exit={p.returncode} · L3={_st['loops']['L3']} · "
      f"unmeasurable={_st.get('unmeasurable')}")

# ------------------------------------------------------------ 12. stage 7 restore and order
print("\n### 12. stage 7 restore, and stopping at a failure")

d = new_page("restore")
baseline(d)
deliver("migrated")
p, secs = run([d, "--stage", "7", "--config", CONFIG])
check("stage 7 puts the toggle back to legacy and confirms it by read-back",
      p.returncode == 0 and state_of(d)["toggle"] == "legacy",
      f"exit={p.returncode} · {delivered().get('X_BACKEND_DEMO_PAGE')}", secs=secs)

d = new_page("stop")
baseline(d)
open(LOG, "w").close()
set_flag("mismatch")
p, _ = run([d, "--stage", "3,4,7", "--config", CONFIG])
set_flag("mismatch", False)
lines = [l for l in p.stdout.splitlines() if l.strip().startswith("stage")]
check("it stops at the failed stage and does not run the later ones",
      p.returncode == 1 and len(lines) == 1 and " 3 " in lines[0],
      f"exit={p.returncode} · {len(lines)} stages ran")
check("a stage that did not run is not recorded as a pass (baseline_diff is still null)",
      state_of(d)["checks"]["baseline_diff"] is None,
      str(state_of(d)["checks"]))

d = new_page("full")
baseline(d)
open(LOG, "w").close()
p, secs = run([d, "--stage", "1,2,3,4,6,7", "--config", CONFIG], timeout=300)
check("environment through restore passes in one go (stage 5 is left out, it needs hashes)",
      p.returncode == 0, f"exit={p.returncode} · {p.stdout.strip()[-100:]}", secs=secs)
st = state_of(d)
check("rounds are recorded per loop (L2 1 · L3 1)",
      st["loops"]["L2"]["n"] == 1 and st["loops"]["L3"]["n"] == 1,
      str({k: v["n"] for k, v in st["loops"].items()}))
check("rounds accumulates one line per stage", len(st["rounds"]) == 6,
      f"{len(st['rounds'])} lines")

p, _ = run([d, "--show", "--json", "--config", CONFIG])
check("--show --json emits state.json unchanged",
      p.returncode == 0 and json.loads(p.stdout)["page"] == PAGE_ID,
      f"exit={p.returncode}")

# ------------------------------------------------------------ 13. the cause loop
# The five loops, the cause each round after the first one carries, and the record a cap change
# leaves. Before this existed, three of the five had a cap that no line of code could reach:
# `STAGE_LOOP` covers L2 and L3 only, so L0, coverage and L1 counted nothing and their caps were
# decoration. The cases are ordered the way the loop is used: count, explain, refuse, then raise
# the cap in the open.
print("\n### 13. the cause loop - five counters, a cause from the second round, a cap in the open")

d = new_page("cause")
p, _ = run([d, "--round", "L0"])
st = state_of(d)
check("the first round of a stage-less loop needs no cause",
      p.returncode == 0 and st["loops"]["L0"]["n"] == 1,
      f"exit={p.returncode} · {st['loops']['L0']}")
check("the first round is recorded with an empty cause",
      st["rounds"][-1]["note"] == "" and st["rounds"][-1]["loop"] == "L0",
      str(st["rounds"][-1]))

p, _ = run([d, "--round", "L0"])
st = state_of(d)
check("the second round without a cause is refused (exit 2)",
      p.returncode == 2 and "second round" in p.stderr, f"exit={p.returncode}")
check("the refused round moved neither the counter nor the record",
      st["loops"]["L0"]["n"] == 1 and len(st["rounds"]) == 1,
      f"{st['loops']['L0']} · {len(st['rounds'])} lines")

p, _ = run([d, "--round", "L0", "--note", "대충"])
check("a cause outside the vocabulary is refused and the vocabulary is printed",
      p.returncode == 2 and "outside the cause vocabulary" in p.stderr
      and "환경" in p.stderr, f"exit={p.returncode}")
check("the refused word was not stored", state_of(d)["loops"]["L0"]["n"] == 1)

p, _ = run([d, "--round", "L0", "--note", "기타"])
check("`기타` with no sentence is refused", p.returncode == 2 and "--why" in p.stderr,
      f"exit={p.returncode}")

p, _ = run([d, "--round", "L0", "--why", "이유만 적었다"])
check("a sentence with no cause word is refused (free text through the back door)",
      p.returncode == 2 and "--note" in p.stderr, f"exit={p.returncode}")

p, _ = run([d, "--round", "L0", "--note", "기타", "--why", "맞는 칸이 없다"])
st = state_of(d)
check("`기타` with a sentence passes, and both are recorded",
      p.returncode == 0 and st["rounds"][-1]["note"] == "기타"
      and st["rounds"][-1]["why"] == "맞는 칸이 없다", str(st["rounds"][-1]))

p, _ = run([d, "--round", "L2", "--note", "환경"])
check("--round refuses the loops the stages spend (one counter, one owner)",
      p.returncode == 2 and "L2" in p.stderr, f"exit={p.returncode}")

# --------------------------------------- all five are counted
# This is the reason for the section. The three that no stage runs had caps and no counter, so
# the design canon claimed five counted loops while two counted.
d = new_page("five")
baseline(d)
open(LOG, "w").close()
p, _ = run([d, "--stage", "3,6", "--config", CONFIG], timeout=300)
for name in ("L0", "cov", "L1"):
    run([d, "--round", name])
st = state_of(d)
counted = {k: v["n"] for k, v in st["loops"].items()}
check("all five loops count a round (L0 · cov · L1 by --round, L2 · L3 by stages)",
      all(counted.get(k) == 1 for k in ("L0", "cov", "L1", "L2", "L3")), str(counted))

# --------------------------------------- a stage loop obeys the same rule
d = new_page("stagecause")
baseline(d)
open(LOG, "w").close()
p, _ = run([d, "--stage", "3", "--config", CONFIG])
check("a stage loop's first round needs no cause either", p.returncode == 0,
      f"exit={p.returncode}")

deliver("legacy")
before = open(ENV_FILE).read()
p, _ = run([d, "--stage", "3", "--config", CONFIG])
st = state_of(d)
check("a stage loop's second round without a cause is refused (exit 2)",
      p.returncode == 2 and "second round" in p.stderr, f"exit={p.returncode}")
check("that refusal touched neither the toggle nor the env file nor the counter",
      delivered().get("X_BACKEND_DEMO_PAGE") == "php"
      and open(ENV_FILE).read() == before and st["loops"]["L2"]["n"] == 1,
      f"toggle={delivered().get('X_BACKEND_DEMO_PAGE')} · {st['loops']['L2']}")

p, _ = run([d, "--stage", "3", "--dry-run", "--config", CONFIG])
check("a dry run is not asked for a cause - it spends no round", p.returncode == 0,
      f"exit={p.returncode}")

d = new_page("onecause")
baseline(d)
open(LOG, "w").close()
run([d, "--stage", "3", "--config", CONFIG])
p, _ = run([d, "--stage", "3,4", "--note", "확인만", "--config", CONFIG], timeout=300)
st = state_of(d)
carried = [r for r in st["rounds"] if r.get("note")]
check("the second round with a cause proceeds and the cause is stored",
      p.returncode == 0 and st["loops"]["L2"]["n"] == 2 and carried
      and carried[-1]["note"] == "확인만",
      f"exit={p.returncode} · {st['loops']['L2']} · {[r.get('note') for r in st['rounds']]}")
# Two stages of one L2 round are one retry. Writing the cause on both lines would make every
# `--stage 3,4` count twice wherever these lines are counted, and the metric would climb
# without a single extra round having happened.
check("one round with two stages carries the cause once, not twice",
      len([r for r in st["rounds"] if r.get("note") == "확인만"]) == 1,
      f"{[(r.get('stage'), r.get('note')) for r in st['rounds']]}")

# --------------------------------------- a cap change is recorded, not forbidden
d = new_page("capchange", caps="L2=2,L3=2")
st = state_of(d)
at_init = [c for c in st.get("cap_changes") or [] if c.get("at_init")]
check("a starting cap that is not the default is recorded as a cap change",
      len(at_init) == 2 and {c["loop"] for c in at_init} == {"L2", "L3"},
      str(st.get("cap_changes")))

p, _ = run([d, "--cap", "L2=7", "--why", "설계로 돌아가는 편이 비쌌다"])
st = state_of(d)
mid = [c for c in st["cap_changes"] if not c.get("at_init")]
check("changing a cap on an existing page records loop, from, to and reason",
      p.returncode == 0 and len(mid) == 1 and mid[0]["loop"] == "L2"
      and mid[0]["from"] == 2 and mid[0]["to"] == 7
      and mid[0]["why"] == "설계로 돌아가는 편이 비쌌다", str(mid))
check("the cap itself moved", st["loops"]["L2"]["cap"] == 7, str(st["loops"]["L2"]))
check("a cap change is reported apart, never folded into the rounds",
      "cap change" in p.stdout + p.stderr
      and not [r for r in st["rounds"] if r.get("verdict") == "cap"],
      p.stdout.strip()[-80:])

p, _ = run([d, "--show"])
check("--show prints the cap change so it cannot pass unseen",
      "cap change" in p.stdout and "2 → 7" in p.stdout, p.stdout.strip()[-120:])

d = new_page("roundcap", caps="L0=1")
run([d, "--round", "L0"])
p, _ = run([d, "--round", "L0", "--note", "환경"])
check("--round stops at the cap too (exit 4, not 0)",
      p.returncode == 4 and "reached its cap" in p.stderr, f"exit={p.returncode}")
check("the cap stop did not count the round", state_of(d)["loops"]["L0"]["n"] == 1,
      str(state_of(d)["loops"]["L0"]))

# The `--show` block is embedded in the orchestrator skill and read by a person every session,
# so its round line is checked as output, not only as state. It used to print `round 1  loop L0
# round` - the same word in the count slot and the verdict slot.
d = new_page("roundshow")
run([d, "--round", "cov"])
run([d, "--round", "cov", "--note", "확인만"])
p, _ = run([d, "--show"])
rline = [l for l in p.stdout.splitlines() if l.strip().startswith("round 2")]
check("--show says what a counted round was, without repeating the word",
      len(rline) == 1 and "loop cov" in rline[0] and "counted" in rline[0]
      and "확인만" in rline[0] and rline[0].split().count("round") == 1,
      rline[0].strip() if rline else p.stdout.strip()[-120:])

# ------------------------------------------------------------ wrap-up
server.shutdown()
bff.close()
shutil.rmtree(BASE, ignore_errors=True)
print("\n" + "=" * 64)
bad = [n for n, ok, _ in results if not ok]
print(f"{len(results) - len(bad)}/{len(results)} pass"
      + ("" if not bad else "   failed: " + ", ".join(bad)))
if skipped:
    print(f"skipped {len(skipped)} - " + ", ".join(n for n, _ in skipped))
    print("  a skipped check is not a pass.")
sys.exit(1 if bad else 0)
