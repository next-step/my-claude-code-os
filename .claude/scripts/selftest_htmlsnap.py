#!/usr/bin/env python3
"""htmlsnap cases. Serves a synthetic page from a thread, checking without a real surface.

    python3 selftest_htmlsnap.py [path to htmlsnap]

This file **never reads the real workspace.json.** It writes a synthetic config into a scratch
directory and points `--config` at it. So it runs with the stack down and with an empty config,
and sends not one request to a local surface.

It serves one page per place this tool can get things wrong.
  normal     CP949 body with no charset in the header  - is it stored as bytes
  logged out 200 + `<script>confirm(...)</script>`     - is the verdict not made from the status code
  5xx        server error                              - is it caught as error_page
  token      a value that changes per request          - does normalization take effect
  list       two editions differing only in text       - does structure mode call them identical
  read-back  prints the current mode                   - does --toggle-expect really read it
  slow       longer than the timeout                   - is timeout told apart from unreachable
  cookie     reflects the received Cookie header       - does storageState ride on the request
"""
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "htmlsnap")
if not os.path.isfile(TOOL):
    sys.exit(f"usage: selftest_htmlsnap.py [path to htmlsnap]  (looked at: {TOOL})")

BASE = tempfile.mkdtemp(prefix="htmlsnap-selftest-")
SURFACE = "synth"                       # a fake surface name. The real one is never written here.
KO = "가나다 공지사항".encode("cp949")   # CP949 bytes. The very bytes that must not be decoded.

results = []


def check(name, ok, detail="", secs=None):
    results.append((name, ok, detail))
    t = f"  {secs:5.1f}s" if secs is not None else "        "
    print(f"  {'pass' if ok else 'FAIL'}{t}  {name}" + (f"   {detail}" if detail else ""))


# ------------------------------------------------------------- the synthetic server

STATE = {"mode": "php"}                 # the value the read-back page will state
COUNTER = {"n": 0}


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):          # quietly
        pass

    def _send(self, code, body, ctype="text/html"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)      # deliberately without a charset
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
        cookie = self.headers.get("Cookie", "")
        if path == "/ok.php":
            self._send(200, b"<html><body><h1>" + KO + b"</h1>"
                       + f"<!--cookie:{cookie}-->".encode("ascii", "replace")
                       + b"</body></html>")
        elif path == "/loggedout.php":
            self._send(200, b"<html><script>confirm('login?');"
                            b"location.href='/sso';</script></html>")
        elif path == "/boom.php":
            self._send(500, b"<html><!--server-error-->500</html>")
        elif path == "/token.php":
            COUNTER["n"] += 1
            self._send(200, b"<html><input name='x' value='csrf_token="
                       + f"{COUNTER['n']:08x}".encode() + b"'>" + KO + b"</html>")
        elif path == "/list.php":
            v = params.get("v", "1")
            rows = b"".join(b"<li class='row'><a href='/d.php?seq=" + str(i).encode()
                            + b"'>" + f"{v}-{i} ".encode() + KO + b"</a></li>"
                            for i in range(3))
            self._send(200, b"<html><ul id='listbox'>" + rows + b"</ul></html>")
        elif path == "/readback.php":
            self._send(200, b"<html><p>toggle=" + STATE["mode"].encode() + b"</p></html>")
        elif path == "/slow.php":
            time.sleep(3)
            self._send(200, b"<html>slow</html>")
        else:
            self._send(404, b"<html>404</html>")


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


srv = Server(("127.0.0.1", 0), Handler)
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE_URL = f"http://127.0.0.1:{PORT}"

# ------------------------------------------------------------- the synthetic config

CONFIG = os.path.join(BASE, "workspace.json")
SESSION = os.path.join(BASE, "storageState.json")


def write_config(logged_out=r"confirm\(|history\.back\(", snapshot=True):
    cfg = {"legacy": {
        "surfaces": {SURFACE: {"localBaseUrl": BASE_URL, "charset": "cp949"}},
        "dualRun": {"readbackPath": "/readback.php"},
        "switch": {"values": {"legacy": "php", "dual": "dual", "migrated": "spring"}}}}
    if logged_out:
        cfg["legacy"]["surfaces"][SURFACE]["loggedOutMarker"] = logged_out
    if snapshot:
        cfg["legacy"]["snapshot"] = {
            "normalize": [{"pattern": r"csrf_token=[0-9a-f]+",
                           "replace": "csrf_token=<TOKEN>"}],
            "errorMarker": "<!--server-error-->", "timeoutSeconds": 5}
    cfg["e2e"] = {"storageState": {SURFACE: SESSION}}
    with open(CONFIG, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False)


write_config()
with open(SESSION, "w", encoding="utf-8") as fh:
    json.dump({"cookies": [
        {"name": "SESSIONID", "value": "abc123", "domain": "127.0.0.1", "path": "/"},
        {"name": "ELSEWHERE", "value": "nope", "domain": "other.example", "path": "/"},
    ], "origins": []}, fh)


def observations(name, entries, surface=SURFACE):
    path = os.path.join(BASE, f"observations-{name}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"surface": surface, "entries": entries}, fh, ensure_ascii=False)
    return path


def run(args, timeout=90):
    t0 = time.time()
    p = subprocess.run([sys.executable, TOOL] + args, capture_output=True, text=True,
                       timeout=timeout, cwd=BASE)
    return p, time.time() - t0


def capture(name, entries, extra=None, timeout=90):
    out = os.path.join(BASE, "cap-" + name)
    args = ["capture", "--observations", observations(name, entries), "--out", out,
            "--config", CONFIG] + (extra or [])
    p, secs = run(args, timeout=timeout)
    return p, out, secs


def manifest(out):
    with open(os.path.join(out, "manifest.json"), encoding="utf-8") as fh:
        doc = json.load(fh)
    return {e["id"]: e for e in doc["entries"]}


E_OK = {"id": "ok", "path": "/ok.php", "mode": "full", "rules": ["R-01"]}
E_OUT = {"id": "loggedout", "path": "/loggedout.php"}
E_BOOM = {"id": "boom", "path": "/boom.php"}
E_TOKEN = {"id": "token", "path": "/token.php"}
E_SLOW = {"id": "slow", "path": "/slow.php"}


print(f"# synthetic surface {BASE_URL} · tool {TOOL}")
print("\n### 1. capture - does it attach the right flags")

p, out_flags, secs = capture("flags", [E_OK, E_OUT, E_BOOM, E_SLOW],
                             extra=["--timeout", "1"])
m = manifest(out_flags) if os.path.isfile(os.path.join(out_flags, "manifest.json")) else {}
check("a normal page is valid and its CP949 bytes are stored unchanged",
      bool(m) and m["ok"]["valid"]
      and open(os.path.join(out_flags, "ok.raw.html"), "rb").read().find(KO) > 0,
      "" if m else f"exit={p.returncode} {p.stderr[-200:]}", secs=secs)
check("an unauthenticated 200 + confirm() is caught as logged_out (by body, not status code)",
      bool(m) and m["loggedout"]["status"] == 200
      and m["loggedout"]["flags"] == ["logged_out"],
      str(m.get("loggedout", {}).get("flags")))
check("a 5xx is caught as error_page",
      bool(m) and m["boom"]["flags"] == ["error_page"],
      str(m.get("boom", {}).get("flags")))
check("a timeout is caught as timeout (told apart from unreachable)",
      bool(m) and m["slow"]["flags"] == ["timeout"] and m["slow"]["error"],
      str(m.get("slow", {}).get("flags")))
check("capture exits 1 when an invalid is mixed in",
      p.returncode == 1 and "valid 1 · invalid 3" in p.stdout, f"exit={p.returncode}")

p2, out_dead, secs2 = capture("dead", [E_SLOW], extra=["--timeout", "1"])
check("every transport failing is exit 2 - not a check failure but 'cannot answer'",
      p2.returncode == 2 and "Check the surface is up" in p2.stderr,
      f"exit={p2.returncode}", secs=secs2)

print("\n### 2. cookies - does storageState ride on the request header")
cookie_body = open(os.path.join(out_flags, "ok.raw.html"), "rb").read().decode("cp949")
check("cookies from storageState go out in the Cookie header",
      "cookie:SESSIONID=abc123" in cookie_body, cookie_body.split("<!--")[-1][:60])
check("cookies for another domain are dropped, and the drop is stated",
      "ELSEWHERE" not in cookie_body and "1 dropped" in p.stderr,
      "" if "ELSEWHERE" not in cookie_body else "a cookie for another domain leaked out")

print("\n### 3. normalization and structure mode")
pa, out_t1, _ = capture("tok1", [E_TOKEN])
pb, out_t2, _ = capture("tok2", [E_TOKEN])
pa_m, pb_m = manifest(out_t1), manifest(out_t2)
_norm_same = pa_m["token"]["sha256_norm"] == pb_m["token"]["sha256_norm"]
_raw_diff = pa_m["token"]["sha256_raw"] != pb_m["token"]["sha256_raw"]
check("a per-request token is normalized away so both normalized copies match",
      _norm_same and _raw_diff,
      "" if _norm_same and _raw_diff
      else ("raw is identical so the check does not hold" if not _raw_diff else "normalization did not take"))

L1 = {"id": "list", "path": "/list.php", "params": {"v": "1"}, "mode": "structure"}
L2 = {"id": "list", "path": "/list.php", "params": {"v": "2"}, "mode": "structure"}
F1 = {"id": "list", "path": "/list.php", "params": {"v": "1"}, "mode": "full"}
F2 = {"id": "list", "path": "/list.php", "params": {"v": "2"}, "mode": "full"}
_, out_s1, _ = capture("s1", [L1])
_, out_s2, _ = capture("s2", [L2])
_, out_f1, _ = capture("f1", [F1])
_, out_f2, _ = capture("f2", [F2])
ps, _ = run(["compare", out_s1, out_s2, "--config", CONFIG])
pf, _ = run(["compare", out_f1, out_f2, "--config", CONFIG])
check("structure mode: two editions differing only in text are identical",
      ps.returncode == 0 and "identical 1 · different 0" in ps.stdout, f"exit={ps.returncode}")
check("the same pair is different in full mode - structure mode really drops something",
      pf.returncode == 1 and "different 1" in pf.stdout, f"exit={pf.returncode}")

print("\n### 4. compare - four results and their exit codes")
pc, _ = run(["compare", out_t1, out_t1, "--config", CONFIG])
check("identical directories are identical, exit 0",
      pc.returncode == 0 and "identical 1 · different 0 · missing 0 · invalid 0" in pc.stdout,
      f"exit={pc.returncode}")

_, out_two, _ = capture("two", [E_TOKEN, E_OK])
pm, _ = run(["compare", out_t1, out_two, "--config", CONFIG])
check("an id present on one side only is missing, exit 1",
      pm.returncode == 1 and "missing 1" in pm.stdout, f"exit={pm.returncode}")

rep = os.path.join(BASE, "report.md")
pd, _ = run(["compare", out_f1, out_f2, "--config", CONFIG, "--report", rep,
             "--context", "1"])
body = open(rep, encoding="utf-8").read() if os.path.isfile(rep) else ""
check("--report writes a markdown table and a diff",
      "| id | result | note |" in body and "```diff" in body, f"{len(body)} bytes")

_, out_bad, _ = capture("bad", [E_OUT])
pi, _ = run(["compare", out_bad, out_bad, "--config", CONFIG])
check("an invalid capture on either side is exit 2 - a logged-out page cannot be a baseline",
      pi.returncode == 2 and "cannot be a baseline" in pi.stderr, f"exit={pi.returncode}")

print("\n### 5. toggle read-back")
STATE["mode"] = "php"
pt, _, secs = capture("tog-bad", [E_OK], extra=["--toggle-expect", "dual"])
check("a read-back stating another mode captures nothing and exits 2",
      pt.returncode == 2 and "'legacy'" in pt.stderr and "'dual'" in pt.stderr,
      f"exit={pt.returncode} {pt.stderr.strip()[-90:]}", secs=secs)
STATE["mode"] = "dual"
pt2, out_tog, secs2 = capture("tog-ok", [E_OK], extra=["--toggle-expect", "dual"])
check("a matching read-back captures and records it in the manifest",
      pt2.returncode == 0 and manifest(out_tog) and
      json.load(open(os.path.join(out_tog, "manifest.json")))["toggle_readback"] == "dual",
      f"exit={pt2.returncode}", secs=secs2)
STATE["mode"] = "php"

print("\n### 6. observations validate · a missing config")
good = observations("valid-ok", [E_OK])
pv, _ = run(["observations", "validate", good, "--config", CONFIG])
check("a valid observation list is exit 0",
      pv.returncode == 0 and "1 entries · 0 problems" in pv.stdout, f"exit={pv.returncode}")

bad_observations = os.path.join(BASE, "observations-broken.json")
with open(bad_observations, "w", encoding="utf-8") as fh:
    json.dump({"surface": "nosuchsurface", "entries": [
        {"id": "a b", "path": "relative", "mode": "weird"},
        {"id": "dup", "path": "/x.php"}, {"id": "dup", "path": "/y.php"}]}, fh,
        ensure_ascii=False)
pv2, _ = run(["observations", "validate", bad_observations, "--config", CONFIG])
# Not `>= 5`: the count is 6 (five problem lines plus the word in the summary), so one lost
# detection still cleared the threshold. The tool prints the number - assert the number.
check("a broken observation list names each problem and exits 1",
      pv2.returncode == 1 and "3 entries · 5 problems" in pv2.stdout,
      f"exit={pv2.returncode} {pv2.stdout.count('problem') - 1} problems")

write_config(logged_out=None)
pn, _, _ = capture("nomarker", [E_OK])
check("without loggedOutMarker it captures nothing and says why (exit 2)",
      pn.returncode == 2 and "loggedOutMarker" in pn.stderr,
      f"exit={pn.returncode}")
write_config(snapshot=False)
pn2, _, _ = capture("nosnap", [E_OK])
check("it stops when legacy.snapshot is missing too",
      pn2.returncode == 2 and "legacy.snapshot" in pn2.stderr, f"exit={pn2.returncode}")
write_config()

pu, _ = run(["capture", "--observations", good, "--out", os.path.join(BASE, "x"),
             "--config", CONFIG, "--nosuchoption", "1"])
check("an unknown option is not ignored in silence",
      pu.returncode == 2 and "unknown option" in pu.stderr, f"exit={pu.returncode}")

# ------------------------------------------------------------------ wrap-up
srv.shutdown()
shutil.rmtree(BASE, ignore_errors=True)
bad = [n for n, ok, _ in results if not ok]
print("\n" + "=" * 64)
print(f"{len(results) - len(bad)}/{len(results)} pass"
      + ("" if not bad else "   failed: " + ", ".join(bad)))
sys.exit(1 if bad else 0)
