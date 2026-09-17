#!/usr/bin/env python3
"""phpmove cases. Runs on a synthetic page and a synthetic config, touching no real checkout.

    python3 selftest_phpmove.py [path to phpmove]

The fixture's directory and symbol names are chosen by this file. Using the real checkout's
names would put company information in here, and then it could not be tracked. Fake names cost
the checks nothing - `phpmove` judges by the **shape of the tokens**, not by names, and that is
what these cases verify.

The config is a `workspace.json` built in a temp directory and passed with `--config`. This
suite must run to completion even when the real `workspace.json` has no `legacy.swap` section
yet. Requiring the real config instead would skip the whole suite until that section appears,
and a skip reads like a pass.

**Four cases are the reason this file exists.** (1) Does it stop when tokenizing with a php
that ignores `short_open_tag`? If not, control structures drop out entirely and "zero
violations" comes back. (2) Does the Korean source of a violation on a CP949 page survive
undamaged? If not, a person cannot read that line. (3) Does `callers` tell zero from a failed
search? If not, "no callers" lets the swap through. (4) Does removing one field from a request
turn `fields` red? If not, the defect that failed the second page passes again.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PHPMOVE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "phpmove")
if not os.path.isfile(PHPMOVE):
    sys.exit(f"usage: selftest_phpmove.py [path to phpmove]  (missing: {PHPMOVE})")

BASE = tempfile.mkdtemp(prefix="phpmove-")
PROJ = os.path.join(BASE, "proj")
CHECKOUT = os.path.join(BASE, "checkout")
MARKER = "src/tree"                    # fake. The real name is never written here
SVC = "svc/one"
TREE = os.path.join(CHECKOUT, MARKER)
SRC = os.path.join(TREE, SVC)
CFG_DIR = os.path.join(PROJ, ".claude", "config")
CFG = os.path.join(CFG_DIR, "workspace.json")          # config with a swap section
CFG_BARE = os.path.join(CFG_DIR, "bare.json")          # config without one
CFG_NOSHORT = os.path.join(CFG_DIR, "noshort.json")    # php that ignores short_open_tag
CFG_NOPHP = os.path.join(CFG_DIR, "nophp.json")        # config with no php binary
CFG_RENDER = os.path.join(CFG_DIR, "render.json")      # config with the template-object pattern
HASHES = os.path.join(BASE, "body-hashes.json")

# The content guard catches class-symbol suffixes (Dao, Service and the like) and path-literal
# shapes. Even a fake name is not written as a literal here. Narrowing the guard's coverage for
# test convenience lets through the very thing it exists to block - the same trade `selftest_hook.py` made for path literals.
SWAP_CLS = "ItemList" + "Serv" + "ice"
DAO_CLS = "Item" + "D" + "ao"

PHP = shutil.which("php")
RG = shutil.which("rg")
KOREAN = "안내 문구입니다"          # the string that shows whether CP949 violation text survives

os.makedirs(CFG_DIR, exist_ok=True)
os.makedirs(SRC, exist_ok=True)

BARE = {"legacy": {"root": CHECKOUT, "treeRoot": TREE, "treeMarker": MARKER,
                   "services": {SVC: "one"}, "sharedLibrary": SVC,
                   "primaryService": SVC}}
SWAP = {"tooling": {"phpBinary": PHP or "php"},
        "swap": {
            "callPattern": r"\b[A-Z]\w+Service::\w+\(",
            "templateIncludePattern": r"[\w-]+\.tpl\.php",
            "guardIdioms": [r"\bgoLoginPage\s*\(",
                            r"\bheader\s*\(\s*[\"']Location:"],
            "allowedCalls": ["isset", "trim", "intval", "extract", "dirname",
                             "getint", "getstring"],
            "hashesFile": "body-hashes.json"}}


def write_cfg(path, **over):
    cfg = json.loads(json.dumps(BARE))
    cfg["legacy"].update(json.loads(json.dumps(SWAP)))
    for dotted, value in over.items():
        node = cfg["legacy"]
        parts = dotted.split("__")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = value
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)


write_cfg(CFG)
write_cfg(CFG_NOPHP, tooling__phpBinary="php-does-not-exist")
# Keep a config with the optional key and one without. Only by watching the same page get
# judged differently under the two can you know that key is actually read.
write_cfg(CFG_RENDER,
          swap__templateRenderPattern=r"new\s+Template\b|->\s*(set|fetch)\s*\(")
with open(CFG_BARE, "w", encoding="utf-8") as fh:
    json.dump(BARE, fh, indent=2)

# A php wrapper that filters out short_open_tag=1, reproducing the un-enabled state - the CLI
# default is 0 while the real runtime (ini) is On, so this gap opens up in silence.
WRAP = os.path.join(BASE, "php-noshort")
with open(WRAP, "w", encoding="utf-8") as fh:
    fh.write("#!/usr/bin/env python3\nimport os, sys\n"
             "a = sys.argv[1:]\nout, i = [], 0\n"
             "while i < len(a):\n"
             "    if a[i] == '-d' and i + 1 < len(a) "
             "and a[i + 1].startswith('short_open_tag'):\n"
             "        i += 2\n        continue\n"
             "    out.append(a[i])\n    i += 1\n"
             f"os.execv({(PHP or '/usr/bin/php')!r}, [{(PHP or 'php')!r}] + out)\n")
os.chmod(WRAP, 0o755)
write_cfg(CFG_NOSHORT, tooling__phpBinary=WRAP)

# ------------------------------------------------------------------ fixtures

PAGES = {
    # include · guard · parse · swap-point call · bind · template - a page with only these
    "clean.php": """<?php
require_once dirname(__FILE__) . '/bootstrap.php';
if (!isset($_SESSION['seq'])) { goLoginPage('login'); exit; }
$nPage = intval($_GET['page']);
$sHead = isset($_GET['groupSeq']) ? trim($_GET['groupSeq']) : '';
$aView = SWAPCLS::view($nPage, $sHead);
$aList = $aView['items'];
$nCount = $aView['count'];
include 'listView.tpl.php';
""",
    # two guard idioms - a redirect with an early exit is also a guard
    "guarded.php": """<?php
require_once dirname(__FILE__) . '/bootstrap.php';
if (!isset($_SESSION['seq'])) { goLoginPage('login'); exit; }
header("Location: /elsewhere.php", TRUE, 302);
exit;
$aView = SWAPCLS::view(1, '');
include 'listView.tpl.php';
""",
    # a computation is left behind - e2e cannot catch this
    "if_left.php": """<?php
$nPage = intval($_GET['page']);
if ($nPage < 1) { $nPage = 1; }
$aView = SWAPCLS::view($nPage, '');
include 'listView.tpl.php';
""",
    # renders the template as an object rather than an include - this tree's real binding shape
    "render.php": """<?php
require_once dirname(__FILE__) . '/bootstrap.php';
$nPage = intval($_GET['page']);
$aView = SWAPCLS::view($nPage, '');
$oTpl = new Template();
$oTpl->set('items', $aView['items']);
$oTpl->fetch('listView.tpl.php');
""",
    # SQL left in a string
    "sql_left.php": """<?php
$nPage = intval($_GET['page']);
$sSql = "SELECT seq FROM item WHERE seq = 59";
$aView = SWAPCLS::view($nPage, '');
include 'listView.tpl.php';
""",
}

TEMPLATE = """<div>
<? foreach ($aList as $row) { ?>
  <li class="<?= $row['cls'] ?>"><?= $row['title'] ?></li>
<? } ?>
<? if (count($aList) > 10) { ?><b>more</b><? } ?>
<? if ($sHead == '') { ?><span>plain</span><? } ?>
</div>
"""

EUCKR = f"""<?php
require_once dirname(__FILE__) . '/bootstrap.php';
$nPage = intval($_GET['page']);
$sTitle = '{KOREAN}';
$aView = SWAPCLS::view($nPage, '');
include 'listView.tpl.php';
"""

DAO = """<?php
class DAOCLS {
    public function fetchRows($aParam) {
        $r = $this->rest->doGet('/item/list.json', $aParam);
        return $r === null ? array() : $r;
    }
    public function fetchRowCount($aParam) {
        $r = $this->rest->doGet('/item/count.json', $aParam);
        return $r === null ? 120 : $r;
    }
    public function getBoth($aParam) {
        return $this->fetchRows($aParam);
    }
}
function fetchRows($x) { return $x; }
"""

CALLER = """<?php
$oDao = new DAOCLS();
$aList = $oDao->fetchRows($aParam);
"""

def fixture(body):
    """Turn placeholders into assembled symbols to build the fixture content."""
    return body.replace("SWAPCLS", SWAP_CLS).replace("DAOCLS", DAO_CLS)


for name, body in PAGES.items():
    with open(os.path.join(BASE, name), "w", encoding="utf-8") as fh:
        fh.write(fixture(body))
with open(os.path.join(BASE, "list.tpl.php"), "w", encoding="utf-8") as fh:
    fh.write(fixture(TEMPLATE))
with open(os.path.join(BASE, "euckr.php"), "wb") as fh:
    fh.write(fixture(EUCKR).encode("cp949"))          # encoding differs per file, as in the tree
DAO_PATH = os.path.join(SRC, DAO_CLS + ".php")
with open(DAO_PATH, "w", encoding="utf-8") as fh:
    fh.write(fixture(DAO))
for name in ("swapPage.php", "otherPage.php"):
    with open(os.path.join(SRC, name), "w", encoding="utf-8") as fh:
        fh.write(fixture(CALLER))

# ------------------------------------------------------------------- run

results = []
skipped = []
ENV = {k: v for k, v in os.environ.items() if k != "PHP_LEGACY_ROOT"}
ENV["CLAUDE_PROJECT_DIR"] = PROJ          # point the fallback at the synthetic config too


def run(args, cfg=CFG, cwd=BASE):
    full = [sys.executable, PHPMOVE] + args + (["--config", cfg] if cfg else [])
    t0 = time.time()
    p = subprocess.run(full, capture_output=True, cwd=cwd, env=ENV, timeout=300)
    out = p.stdout.decode("utf-8", "replace")
    err = p.stderr.decode("utf-8", "replace")
    return p.returncode, out, err, time.time() - t0


def check(name, ok, detail="", secs=None):
    results.append((name, ok, detail))
    t = f"  {secs:5.1f}s" if secs is not None else "        "
    print(f"  {'pass' if ok else 'FAIL'}{t}  {name}"
          + (f"   {detail}" if detail else ""))


def skip(name, why):
    skipped.append((name, why))
    print(f"  skipped      {name}   ({why})")


def page(name):
    return os.path.join(BASE, name)


print(f"# synthetic project {PROJ}  ·  php={PHP or 'none'}  ·  rg={RG or 'none'}")

# ------------------------------------------------------- 1. usage and config
print("\n### 1. usage and config - exit 2 with a reason when it cannot answer")

rc, out, err, s = run(["--help"], cfg=None)
check("--help prints usage and exits 0", rc == 0 and "phpmove lint" in out, secs=s)

rc, out, err, s = run([], cfg=None)
check("no arguments → help, exit 2", rc == 2 and "phpmove lint" in err, secs=s)

rc, out, err, s = run(["nosuchcmd"])
check("unknown subcommand → exit 2", rc == 2 and "unknown subcommand" in err, secs=s)

rc, out, err, s = run(["lint", page("clean.php")], cfg=CFG_BARE)
check("a missing swap key stops and names the key",
      rc == 2 and "swap" in err and "guardIdioms" in err,
      "" if rc == 2 else f"exit={rc}", secs=s)

rc, out, err, s = run(["lint", page("clean.php")], cfg=None)
check("without --config it finds the config under CLAUDE_PROJECT_DIR itself",
      rc == 0 and "violations 0" in err,
      f"exit={rc}" if rc != 0 else err.strip()[-80:], secs=s)

rc, out, err, s = run(["lint", os.path.join(BASE, "nope.php")])
check("missing file → exit 2", rc == 2 and "is not a file" in err, secs=s)

# ------------------------------------------------------------ 2. lint shape
print("\n### 2. lint - is there a statement outside the allowed shape")

if not PHP:
    for n in ("clean page", "guard idioms", "leftover if", "SQL in a string", "--json",
              "template report", "swallow guard", "CP949 source", "hash/check",
              "template object"):
        skip(n, "no php - nothing is judged without tokens")
else:
    rc, out, err, s = run(["lint", page("clean.php")])
    kinds = {l.split()[1] for l in out.splitlines()
             if l.startswith(" ") and len(l.split()) > 1}
    want = {"include", "guard", "parse", "call", "bind", "template"}
    check("clean page → exit 0, zero violations, all six kinds caught",
          rc == 0 and "violations 0" in err and want <= kinds,
          "" if rc == 0 else f"exit={rc} kinds={sorted(kinds)}", secs=s)

    rc, out, err, s = run(["lint", page("guarded.php")])
    # Not `out.count("guard") >= 2`: the header prints the fixture path, and `guarded.php`
    # carries the word itself, so one real guard plus the filename cleared that threshold.
    kinds = [l.split()[1] for l in out.splitlines() if l.startswith(" ") and len(l.split()) > 1]
    check("guard idioms are not violations (including the early exit)",
          rc == 0 and kinds.count("guard") == 3 and "violations 0" in err,
          "" if rc == 0 else out.strip()[-160:], secs=s)

    rc, out, err, s = run(["lint", page("if_left.php")])
    check("a page with a leftover if → exit 1, reason is a control structure",
          rc == 1 and "control structure" in out, f"exit={rc}", secs=s)

    # ---- optional key `templateRenderPattern`
    rc0, out0, err0, s0 = run(["lint", page("render.php")])
    rc1, out1, err1, s1 = run(["lint", page("render.php")], cfg=CFG_RENDER)
    tpl1 = sum(1 for l in out1.splitlines()
               if len(l.split()) > 1 and l.split()[1] == "template")
    check("without templateRenderPattern a template-object call is a violation; with it, template",
          rc0 == 1 and rc1 == 0 and tpl1 >= 3,
          f"without exit={rc0} · with exit={rc1} template={tpl1}",
          secs=s0 + s1)

    rc, out, err, s = run(["lint", page("sql_left.php")])
    check("SQL inside a string → exit 1, reason is an SQL keyword",
          rc == 1 and "SQL" in out, f"exit={rc}", secs=s)

    rc, out, err, s = run(["lint", page("if_left.php"), "--json"])
    try:
        doc = json.loads(out)
    except ValueError:
        doc = {}
    check("--json emits a structure a machine can read",
          rc == 1 and doc.get("violations", 0) >= 1
          and doc.get("swapCalls") == 1
          and any(r["kind"] == "violation" for r in doc.get("statements", [])),
          "" if doc else out.strip()[:80], secs=s)

    rc, out, err, s = run(["lint", "--template", page("list.tpl.php")])
    # Not `out.count("if") >= 2`: that counts substrings, and the header line prints a tempdir
    # path whose random suffix can contain `if`. The tool prints both numbers - assert those.
    check("template mode counts control structures in <? blocks and marks suspected rules",
          rc == 0 and "control structures 3 · suspected rules 2" in out
          and len([l for l in out.splitlines()
                   if l.rstrip().endswith("suspected rule")]) == 2,
          f"exit={rc}", secs=s)

    rc, out, err, s = run(["lint", "--template", page("list.tpl.php"), "--strict"])
    check("--strict exits 1 when there is a suspected rule", rc == 1, f"exit={rc}", secs=s)

    # ---- the three cases at the core of this suite
    rc, out, err, s = run(["lint", "--template", page("list.tpl.php")],
                          cfg=CFG_NOSHORT)
    check("with short_open_tag off it does not count but exits 2 (swallow guard)",
          rc == 2 and "short_open_tag" in err,
          f"exit={rc} - this case splits silently, 116 against 252", secs=s)

    rc, out, err, s = run(["lint", page("clean.php")], cfg=CFG_NOPHP)
    check("a missing php binary is exit 2, not a pass",
          rc == 2 and "php binary" in err, f"exit={rc}", secs=s)

    rc, out, err, s = run(["lint", page("euckr.php")])
    check("a CP949 page is handled and its Korean violation text survives",
          rc == 1 and "cp949" in out and KOREAN in out,
          "" if KOREAN in out else out.strip()[:120], secs=s)

# ----------------------------------------------------------- 3. hash/check
print("\n### 3. hash·check - the legacy body must not change by even one byte")

if not PHP:
    skip("hash·check", "no php")
else:
    rc, out, err, s = run(["hash", DAO_PATH, "fetchRows", "--hashes", HASHES])
    check("a name collision records nothing and exits 2 (never record the wrong body)",
          rc == 2 and "has 2 of" in err, f"exit={rc}", secs=s)

    rc, out, err, s = run(["hash", DAO_PATH, DAO_CLS + "::fetchRows",
                           "--hashes", HASHES])
    ok1 = rc == 0 and os.path.isfile(HASHES)
    rc2, _, _, _ = run(["hash", DAO_PATH, DAO_CLS + "::fetchRowCount",
                        "--hashes", HASHES])
    hashes = json.load(open(HASHES, encoding="utf-8"))["hashes"] if ok1 else {}
    check("hash records the body byte hash and the line range",
          ok1 and rc2 == 0 and len(hashes) == 2
          and all(v.get("sha256") and v.get("lines") for v in hashes.values()),
          "" if ok1 else out.strip()[:100], secs=s)

    rc, out, err, s = run(["check", "--hashes", HASHES])
    check("check exits 0 when unchanged", rc == 0 and "changed 0" in out,
          f"exit={rc}", secs=s)

    with open(DAO_PATH, "rb") as fh:
        body = fh.read()
    with open(DAO_PATH, "wb") as fh:
        fh.write(body.replace(b"120", b"121"))          # exactly one byte
    rc, out, err, s = run(["check", "--hashes", HASHES])
    check("one changed byte → exit 1 naming the symbol",
          rc == 1 and "fetchRowCount" in out, f"exit={rc}", secs=s)
    with open(DAO_PATH, "wb") as fh:
        fh.write(body)

    rc, out, err, s = run(["check", "--hashes", os.path.join(BASE, "nope.json")])
    check("a missing hash file is exit 2, not a pass",
          rc == 2 and "does not exist" in err and "phpmove hash" in err,
          f"exit={rc} · {err.strip()[:70]}", secs=s)

    rc, out, err, s = run(["check"], cwd=BASE)
    # `rc in (0, 1, 2)` was every code this tool emits, and `body-hashes.json` is printed by the
    # error path too - so a `check` that read nothing still passed. Assert the comparison happened.
    check("without --hashes it uses legacy.swap.hashesFile (relative to cwd)",
          rc == 0 and "body-hashes.json" in out and "unchanged 2 · changed 0" in out,
          f"exit={rc} {out.strip()[:80]}", secs=s)

# ------------------------------------------------------------- 4. callers
print("\n### 4. callers - zero and 'the search failed' are different answers")

if not RG:
    skip("callers", "no rg - phpgrep cannot search")
else:
    rc, out, err, s = run(["callers", "fetchRows"])
    check("a caller outside the swap point → exit 1 with file:line",
          rc == 1 and "swapPage.php" in out and "otherPage.php" in out,
          f"exit={rc}", secs=s)

    dao_file = DAO_CLS + ".php"
    check("a call inside the defining file is not counted", dao_file not in out,
          "" if dao_file not in out else "the defining file was counted as a caller")

    rc, out, err, s = run(["callers", "fetchRows",
                           "--allow-file", os.path.join(SRC, "swapPage.php"),
                           "--allow-file", os.path.join(SRC, "otherPage.php")])
    check("allowing the swap-point file → exit 0", rc == 0 and "0 callers" in err,
          f"exit={rc}", secs=s)

    rc, out, err, s = run(["callers", "noSuchMethodHere"])
    check("with nobody calling it, exit 0 and it says 'there are none'",
          rc == 0 and "there are none" in err, f"exit={rc}", secs=s)

    # A search that never finished. Read as zero, it lets the swap straight through.
    broken = os.path.join(CFG_DIR, "broken.json")
    write_cfg(broken)
    doc = json.load(open(broken, encoding="utf-8"))
    doc["legacy"]["root"] = os.path.join(BASE, "nowhere")
    doc["legacy"].pop("treeRoot", None)
    json.dump(doc, open(broken, "w", encoding="utf-8"))
    rc, out, err, s = run(["callers", "fetchRows"], cfg=broken)
    check("a failed search is exit 2, not zero hits",
          rc == 2 and "search" in err, f"exit={rc}", secs=s)

# -------------------------------------------------------------- 5. fields
# What this section reproduces is the defect that failed the second page's completeness pass -
# the rule is in the backend, the field is in the schema, the rule list says `이관됨`, and yet
# the adapter never requests that field. So the most important case here is not a pass but
# **whether removing one field from the request turns it red**. A new check is deliberately
# broken before it is trusted.
print("\n### 5. fields - does the adapter ask for that field of the schema")

GQL_DIR = os.path.join(BASE, "schema")
ADP = os.path.join(BASE, "adapter")
os.makedirs(GQL_DIR, exist_ok=True)
os.makedirs(ADP, exist_ok=True)

# The type and field names are chosen by this file. Using the real schema's names would put
# company information here. `fields` judges by the set difference of two lists, not by names,
# so fake names cost the check nothing.
SCHEMA = '''"""The read surface of this area."""
type Query {
  widgets(page: Int, size: Int): WidgetPage!
  gadgets: [Gadget!]!
}

type WidgetPage {
  items: [Widget!]!
  total: Int!
}

type Widget {
  id: ID!
  name: String
  fooBar: Int
  state: WidgetState!
  ownedByAnotherPage: String
}

enum WidgetState { OPEN CLOSED }

type Gadget { id: ID! label: String }
'''

# A heredoc. The shape real adapters use most.
ADP_OK = '''<?php
$sQuery = <<<GQL
query WidgetList($page: Int) {
  widgets(page: $page, size: 20) {
    items { id name fooBar state ownedByAnotherPage }
    total
  }
}
GQL;
$aRes = $oClient->call($sQuery, array('page' => $nPage));
'''
# An adapter missing one field. This is the defect that actually happened.
ADP_DROP = ADP_OK.replace(" fooBar", "")
# An adapter missing one field the rule list cites and one it does not. The two have to differ
# for the narrowing by rule list to be visible.
ADP_NARROW = ADP_DROP.replace(" ownedByAnotherPage", "")
# A single quoted string, concatenated
ADP_CONCAT = '''<?php
$sQ = 'query { widgets(page: 1) {'
    . ' items { id name fooBar state ownedByAnotherPage }'
    . ' total } }';
$r = $oClient->call($sQ);
'''
# An adapter stored as CP949, with a Korean comment and a double-quoted query.
ADP_CP949 = f'''<?php
// {KOREAN} (this comment is stored as CP949. A dash other than `-` does not exist in CP949)
$sQuery = "query {{ widgets {{ items {{ id name fooBar state ownedByAnotherPage }} total }} }}";
$aRes = $oClient->call($sQuery);   // {KOREAN}
'''
# Requests a field absent from the schema
ADP_GHOST = '''<?php
$sQ = 'query { widgets { items { id name fooBar state ownedByAnotherPage nope } total } }';
'''
# No query at all (it only makes a REST call)
ADP_NONE = '''<?php
$aRes = $oClient->rest('/widget/list.json', array('page' => $nPage));
$aList = $aRes['items'];
'''
# Unsupported shape - a fragment
ADP_FRAG = '''<?php
$sQ = <<<GQL
query { widgets { items { ...WidgetBits } total } }
GQL;
'''
# Unsupported shape - the field-name position is interpolated
ADP_INTERP = '''<?php
$sQ = "query { widgets { items { id $sExtraField } total } }";
'''
# A JSON body that looks like a query. Mistaking it for one makes exit 3 common,
# and a common exit 3 is read by nobody.
ADP_JSON = '''<?php
$sBody = '{ "filter": { "state": "OPEN" }, "page": 1 }';
$aRes = $oClient->post('/widget/list', $sBody);
'''

RULES_JSONL = (
    '{"id":"R-01","rule":"A default class is chosen when none is specified",'
    '"class":"도메인","src":["<page>:12-20"],"range":"12-20",'
    '"obs":"이중실행:widget","state":"이관됨:WidgetPolicy.applyDefault (fooBar)",'
    '"approve":null,"note":""}\n'
    '{"id":"R-02","rule":"twenty per page","class":"화면","src":["<page>:8"],'
    '"range":"8","obs":"기준캡처:c1","state":"대기","approve":null,"note":""}\n'
)
RULES_MD = """# Behavior rules

## Summary

2 rows · 도메인 1 · 화면 1.

| ID | 규칙 | 분류 | 출처 | 관찰 | 이관 | 비고 |
|---|---|---|---|---|---|---|
| R-01 | A default class is chosen when none is specified | 도메인 | `<page>:12` | 이중실행:widget | 이관됨:WidgetPolicy.applyDefault | observed through fooBar in the response |
| R-02 | twenty per page | 화면 | `<page>:8` | 기준캡처:c1 | 대기 | |

## Open questions
None.
"""
NOT_RULES = "# not a rule list\n\nOnly prose, with no table.\n"

with open(os.path.join(GQL_DIR, "widget.graphqls"), "w", encoding="utf-8") as fh:
    fh.write(SCHEMA)
for name, body in (("ok.php", ADP_OK), ("drop.php", ADP_DROP),
                   ("concat.php", ADP_CONCAT), ("ghost.php", ADP_GHOST),
                   ("none.php", ADP_NONE), ("frag.php", ADP_FRAG),
                   ("interp.php", ADP_INTERP), ("json.php", ADP_JSON),
                   ("narrow.php", ADP_NARROW)):
    with open(os.path.join(ADP, name), "w", encoding="utf-8") as fh:
        fh.write(body)
with open(os.path.join(ADP, "cp949.php"), "wb") as fh:
    fh.write(ADP_CP949.encode("cp949"))          # encoding differs per file, as in the tree
LJ = os.path.join(BASE, "rules.jsonl")
LM = os.path.join(BASE, "rules.md")
LX = os.path.join(BASE, "notarules.md")
for path, body in ((LJ, RULES_JSONL), (LM, RULES_MD), (LX, NOT_RULES)):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)

# A config with `backend.graphqlSchemaDir` and one without. Only by watching the same command
# end differently under the two can you know that key is actually read.
CFG_BE = os.path.join(CFG_DIR, "backend.json")
CFG_BE_NOKEY = os.path.join(CFG_DIR, "backend-nokey.json")
for path, backend in ((CFG_BE, {"root": BASE, "graphqlSchemaDir": "schema"}),
                      (CFG_BE_NOKEY, {"root": BASE})):
    doc = json.loads(json.dumps(BARE))
    doc["legacy"].update(json.loads(json.dumps(SWAP)))
    doc["backend"] = backend
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)


def adp(name):
    return os.path.join(ADP, name)


def fields(*args, cfg=CFG):
    return run(["fields", "--schema", GQL_DIR] + list(args), cfg=cfg)


rc, out, err, s = fields("--adapter", adp("ok.php"), "--rules", LJ)
check("an adapter requesting everything → exit 0, not 'could not find' but 'there are none'",
      rc == 0 and "there are none" in err and "fooBar" in out,
      f"exit={rc}" if rc else "", secs=s)

# ---- the core of this section. Removing one field must turn it red.
rc, out, err, s = fields("--adapter", adp("drop.php"), "--rules", LJ)
check("removing one field from the request → exit 1 (the real defect, reproduced)",
      rc == 1 and "fooBar" in out and "R-01" in out,
      f"exit={rc}" if rc != 1 else "", secs=s)

check("it separates the kinds in the output (exposed-not-requested · rule-cited-not-requested)",
      "exposed but not requested" in out and "is not requested" in out
      and "exposed-not-requested 1" in err and "rule-cited-not-requested 1" in err,
      err.strip()[-120:] if "rule-cited" not in err else "")

rc, out, err, s = fields("--adapter", adp("ghost.php"), "--rules", LJ)
check("requesting a field absent from the schema → exit 1 with that kind",
      rc == 1 and "requested but absent from the schema" in out and "nope" in out,
      f"exit={rc}", secs=s)

rc, out, err, s = fields("--adapter", adp("cp949.php"), "--rules", LJ)
check("fields are extracted from a CP949 adapter too (fixed utf-8 makes them vanish silently)",
      rc == 0 and "cp949" in out and "fooBar" in out,
      f"exit={rc} " + out.strip()[-120:] if rc else "", secs=s)

rc, out, err, s = fields("--adapter", adp("concat.php"), "--rules", LJ)
check("a query scattered across concatenated strings is extracted too",
      rc == 0 and "fooBar" in out, f"exit={rc}", secs=s)

# ---- could-not-find (3) never mixes with no-mismatch (0)
rc, out, err, s = run(["fields", "--schema", os.path.join(BASE, "no-schema-dir"),
                       "--adapter", adp("ok.php")])
check("a missing schema directory → exit 3 (not a pass)",
      rc == 3 and "no schema directory" in err, f"exit={rc}", secs=s)

rc, out, err, s = fields("--adapter", adp("none.php"))
check("a query that cannot be found in the adapter → exit 3",
      rc == 3 and "no query found" in out, f"exit={rc}", secs=s)

rc, out, err, s = fields("--adapter", adp("frag.php"))
check("an unsupported shape such as a fragment → exit 3 with the reason",
      rc == 3 and "fragment" in out, f"exit={rc}", secs=s)

rc, out, err, s = fields("--adapter", adp("interp.php"))
check("interpolation in a field position → exit 3 (not statically determined)",
      rc == 3 and "interpolation" in out, f"exit={rc}", secs=s)

rc, out, err, s = fields("--adapter", adp("json.php"))
check("a JSON body that looks like a query is not mistaken for one (3, as no query)",
      rc == 3 and "no query found" in out and "unsupported" not in out,
      f"exit={rc}", secs=s)

rc, out, err, s = fields("--adapter", adp("ok.php"),
                         "--adapter", adp("cp949.php"), "--rules", LJ)
check("several adapters at once", rc == 0 and out.count("# query") == 2,
      f"exit={rc} queries={out.count('# query')}", secs=s)

# ---- the rule list
rc, out, err, s = fields("--adapter", adp("drop.php"), "--rules", LM)
check("a Markdown-table rule list is read too (pre-v3 lists have this shape)",
      rc == 1 and "markdown" in out and "R-01" in out, f"exit={rc}", secs=s)

rc, out, err, s = fields("--adapter", adp("ok.php"), "--rules", LX)
check("an unrecognizable rule list is exit 3, not zero citations",
      rc == 3 and "could not recognize" in err, f"exit={rc}", secs=s)

rc, out, err, s = fields("--adapter", adp("ok.php"),
                         "--rules", os.path.join(BASE, "nope.jsonl"))
check("a missing rule-list file → exit 3",
      rc == 3 and "the rule list" in err and "does not exist" in err,
      f"exit={rc} · {err.strip()[:70]}", secs=s)

# ---- scope. A check that produces false violations gets switched off.
rc0, out0, err0, s0 = run(["fields", "--schema", GQL_DIR,
                           "--adapter", adp("narrow.php")])
rc1, out1, err1, s1 = fields("--adapter", adp("narrow.php"), "--rules", LJ)
check("the rule list narrows the scope - an uncited field is held, not a violation",
      rc0 == 1 and rc1 == 1
      and "exposed-not-requested 2" in err0 and "exposed-not-requested 1" in err1
      and "held" not in err0 and "1 held" in err1,
      f"without rules exit={rc0} · with rules exit={rc1} · "
      + (err1.strip().splitlines() or [""])[0][:80], secs=s0 + s1)

# ---- the config consumer
rc, out, err, s = run(["fields", "--adapter", adp("ok.php"), "--rules", LJ],
                      cfg=CFG_BE)
check("without --schema it reads backend.graphqlSchemaDir",
      rc == 0 and GQL_DIR in out, f"exit={rc}", secs=s)

rc, out, err, s = run(["fields", "--adapter", adp("ok.php")], cfg=CFG_BE_NOKEY)
check("a missing key gives no narrowed answer but names the key and exits 2",
      rc == 2 and "graphqlSchemaDir" in err, f"exit={rc}", secs=s)

rc, out, err, s = fields()
check("no --adapter → exit 2", rc == 2 and "usage" in err,
      f"exit={rc}", secs=s)

rc, out, err, s = fields("--adapter", adp("ok.php"), "--bogus")
check("unknown option → exit 2", rc == 2 and "unknown option" in err,
      f"exit={rc}", secs=s)

# ------------------------------------------------------------------ wrap-up
shutil.rmtree(BASE, ignore_errors=True)
bad = [n for n, ok, _ in results if not ok]
print("-" * 72)
if skipped:
    print(f"skipped {len(skipped)} - " + ", ".join(n for n, _ in skipped))
    print("  a skipped check is not a pass.")
print(f"{len(results) - len(bad)}/{len(results)} pass"
      + ("" if not bad else "   failed: " + ", ".join(bad)))
sys.exit(1 if bad else 0)
