"""Shared config, encoding and scope helpers for the legacy-reading tools.

A legacy PHP checkout is a per-file mix of CP949 and UTF-8. Nothing here may
assume one of them. CP949 (not EUC-KR) is the right legacy codec: it is a
superset, so choosing it costs nothing, while choosing EUC-KR risks a decode
exception that reaches the caller as an empty result.

**This module holds no environment constants.** Which directory is which service, which tree is
the shared library, and what counts as a vendor bundle are all read from the `legacy` section of
`.claude/config/workspace.json`. That file is gitignored and its public skeleton is
`workspace.example.json`. That is why the tools can be tracked in this repository, and two hooks
made the same trade first.

When the config cannot be found a tool **stops rather than quietly giving a narrowed answer.**
The failure these tools exist to prevent is exactly "reading what was not found as what is not
there", so leaving a path where a missing config disguises itself as zero hits would make the tool betray its purpose.
"""
import json
import os
import sys

TEXT_EXT = (".php", ".inc", ".tpl", ".html", ".htm", ".js", ".css", ".txt", ".xml")

CONFIG_REL = os.path.join(".claude", "config", "workspace.json")

# Third-party names present in any checkout. Not company information, so they stay here.
# Vendor trees that differ per checkout come from `legacy.vendorGlobs` in workspace.json.
GENERIC_BUNDLES = [
    "!**/vendor/**", "!**/node_modules/**", "!**/bower_components/**",
    "!**/[Pp][Hh][Pp][Ee]xcel/**", "!**/phpExcel/**", "!**/namo*/**",
    "!**/CodeIgniter*/**", "!**/AdminLTE*/**", "!**/ckeditor/**",
    "!**/sheetjs/**",
]
# Real code, but rarely the answer. Excluded by default and named in the scope
# line so a narrow result is never mistaken for an absent one.
SIDE_GLOBS = [
    "!**/test/**", "!**/tests/**", "!**/old/**", "!**/backup/**",
    "!**/*_bak/**", "!**/*_back/**", "!**/*_del/**", "!**/*_old/**",
]


# ------------------------------------------------------------------ config

def _walk_up_for(start, rel):
    """First ancestor of `start` (inclusive) that contains `rel`."""
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, rel)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def project_dir():
    """The OS checkout that holds `.claude/config/workspace.json`.

    It looks in three places - `CLAUDE_PROJECT_DIR`, upward from this file's own location, and
    upward from the working directory. The second is the point. This module sits in the project's
    `.claude/scripts/`, so its own path is the answer for the project, and a caller can therefore
    invoke these tools by one absolute path wherever it stands. A value a caller has to remember
    every time must not be one the tool can work out for itself.
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        d = os.path.abspath(os.path.expanduser(env))
        if os.path.isfile(os.path.join(d, CONFIG_REL)):
            return d
    here = os.path.dirname(os.path.abspath(__file__))
    return _walk_up_for(here, CONFIG_REL) or _walk_up_for(os.getcwd(), CONFIG_REL)


_cfg_cache = None
_cfg_reason = None


def config():
    """The `legacy` section of workspace.json. `{}` when it cannot be read.

    The reason for a failure is held by `config_problem()`. Returning an empty config with no
    reason leaves the caller unable to tell "the config is empty" from "the config was not found".
    """
    global _cfg_cache, _cfg_reason
    if _cfg_cache is not None:
        return _cfg_cache
    root = project_dir()
    if not root:
        _cfg_cache, _cfg_reason = {}, (
            f"could not find {CONFIG_REL}. This tool has to sit inside the project's "
            ".claude/scripts/ to find the project from its own location.")
        return _cfg_cache
    path = os.path.join(root, CONFIG_REL)
    try:
        with open(path, encoding="utf-8") as fh:
            lg = json.load(fh).get("legacy") or {}
    except (OSError, ValueError) as exc:
        _cfg_cache, _cfg_reason = {}, f"{path} could not be read: {exc}"
        return _cfg_cache
    missing = [k for k in ("root", "treeMarker", "services", "primaryService")
               if not lg.get(k)]
    if missing:
        _cfg_cache, _cfg_reason = {}, (
            f"the legacy section of {path} has no {', '.join(missing)}. "
            "Fill it in following the `_tooling` entry in workspace.example.json.")
        return _cfg_cache
    _cfg_cache = lg
    return _cfg_cache


def config_problem():
    """Why `config()` came back empty, or None."""
    config()
    return _cfg_reason


def require_config(tool):
    """Config, or exit with the reason. Stopping beats a narrowed answer."""
    lg = config()
    if not lg:
        sys.exit(f"{tool}: {config_problem()}")
    return lg


# ------------------------------------------------------------------- scope

def _services():
    return list((config().get("services") or {}).items())


def shared_library():
    """The tree every service loads, relative to treeRoot. `''` if unset."""
    return config().get("sharedLibrary") or ""


def primary_service():
    """(prefix, name) of the service being migrated, or None."""
    lg = config()
    p = lg.get("primaryService")
    if not p:
        return None
    return p, (lg.get("services") or {}).get(p, p)


def bundle_globs():
    """Vendored trees to fold out of a search.

    Generic names are in this module; the checkout's own vendored trees come
    from config. Both are excludes, so a wrong entry costs one folded line
    rather than a hidden answer.
    """
    return GENERIC_BUNDLES + ["!" + g.lstrip("!")
                              for g in (config().get("vendorGlobs") or [])]


def runtime_for_prefix(prefix):
    """{'php': ..., 'image': ..., 'howto': ...} for a service prefix, or None."""
    return (config().get("runtimes") or {}).get(prefix)


# Module-level aliases. Keep the names the existing tools imported as constants, so moving them
# into config does not spread into the call sites.
SERVICES = _services()
PHPLIB = shared_library()
SOLE_SERVICE = primary_service()
BUNDLE_GLOBS = bundle_globs()


def checkout_root():
    """The legacy checkout root, verified by `treeMarker`.

    `PHP_LEGACY_ROOT` wins. Use it to point at a different checkout. When the marker is absent
    under what it names, that is announced rather than ignored, and the config value is used
    instead. A typo disguising itself as "outside the tree" is the failure this function prevents.
    """
    lg = config()
    marker = lg.get("treeMarker") or ""
    env = os.environ.get("PHP_LEGACY_ROOT")
    if env:
        d = os.path.abspath(os.path.expanduser(env))
        if marker and os.path.isdir(os.path.join(d, marker)):
            return d
        print(f"{marker or '<treeMarker unset>'} is not under "
              f"PHP_LEGACY_ROOT={env}. Ignoring it and using the config value.", file=sys.stderr)
    root = lg.get("root")
    if not root:
        return None
    root = os.path.abspath(os.path.expanduser(root))
    if marker and not os.path.isdir(os.path.join(root, marker)):
        print(f"{marker} is not under legacy.root in workspace.json.",
              file=sys.stderr)
        return None
    return root


def tree_root():
    """The source tree root the service prefixes are relative to."""
    lg = config()
    explicit = lg.get("treeRoot")
    if explicit:
        return os.path.abspath(os.path.expanduser(explicit))
    root = checkout_root()
    return os.path.join(root, lg["treeMarker"]) if root else None


def service_of(path, root=None):
    """Which service tree a path belongs to. Returns (prefix, name) or None."""
    root = root or tree_root()
    if not root:
        return None
    rel = os.path.relpath(os.path.abspath(path), root)
    if rel.startswith(".."):
        return None
    for prefix, name in _services():
        if rel == prefix or rel.startswith(prefix + "/"):
            return prefix, name
    return None


def current_service(cwd=None):
    """The service the caller is standing in.

    Standing outside the tree or somewhere that is not a service falls back to the service being
    migrated. This OS runs one level above the checkout and a global rule forbids `cd`, so that
    case is the default rather than the exception. The caller always prints the scope it used, so
    this default is never hidden.
    """
    return service_of(cwd or os.getcwd()) or primary_service()


# ---------------------------------------------------------------- encoding

def detect(data):
    """Return 'ascii' | 'utf-8' | 'cp949' | None (undecodable)."""
    if not data:
        return "ascii"
    if all(b < 0x80 for b in data):
        return "ascii"
    try:
        data.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        data.decode("cp949")
        return "cp949"
    except UnicodeDecodeError:
        pass
    return None


def read_text(path):
    """Return (text, encoding). Undecodable files fall back to cp949/replace."""
    with open(path, "rb") as fh:
        raw = fh.read()
    enc = detect(raw)
    if enc is None:
        return raw.decode("cp949", "replace"), "unknown"
    return raw.decode("ascii" if enc == "ascii" else enc), enc


def sibling_encoding(path):
    """Dominant non-ascii encoding among neighbouring files.

    Used when the target file is pure ASCII and we are about to add Korean:
    a file should match the encoding of the files around it.
    """
    d = os.path.dirname(os.path.abspath(path))
    counts = {"utf-8": 0, "cp949": 0}
    try:
        names = os.listdir(d)
    except OSError:
        return None
    for name in names[:400]:
        p = os.path.join(d, name)
        if not os.path.isfile(p) or not name.lower().endswith(TEXT_EXT):
            continue
        try:
            with open(p, "rb") as fh:
                enc = detect(fh.read(65536))
        except OSError:
            continue
        if enc in counts:
            counts[enc] += 1
    if counts["utf-8"] == counts["cp949"] == 0:
        return None
    return "utf-8" if counts["utf-8"] >= counts["cp949"] else "cp949"


# ------------------------------------------------------------- work dirs

def state_dir(*parts):
    """A directory under the project's gitignored `.claude/.state/`.

    The index and the instrumentation log live here. Put inside the legacy checkout they would
    vanish with it on a re-clone, and instrumentation only means something measured over time.
    Editing working copies do not come here - those are decoded copies of company source, so they
    stay inside the tree rather than in a public repository's directory.
    """
    root = project_dir()
    if not root:
        return None
    d = os.path.join(root, ".claude", ".state", *parts)
    os.makedirs(d, exist_ok=True)
    return d


# ------------------------------------------------- the whole config (v2 and v3 tools)

def workspace(explicit=None):
    """(document, path, problem). The whole-document edition of `config()`, which gives only `legacy`.

    Tools reading sections outside `legacy` (`backend`, `e2e`, `docs`) numbered three in v2 and one
    more in v3, and **all four rewrote the same twenty lines** - walking up to find the project,
    opening the file, turning the reason it failed into a string. The reason it lives here once is
    not line count but the verdict: if four of them each define "could not find the config"
    differently, one of them eventually treats it as an empty config.

    Problems are returned rather than raised - the exit code differs per tool
    (`htmlsnap` 2, `pagecheck` 3). The verdict belongs to the caller.
    """
    if explicit:
        path = os.path.abspath(os.path.expanduser(explicit))
    else:
        root = project_dir()
        if not root:
            return {}, None, (
                f"could not find {CONFIG_REL}. Give its location with --config, or call this "
                "tool from inside the project's .claude/scripts/.")
        path = os.path.join(root, CONFIG_REL)
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        return {}, path, f"{path} could not be read: {exc}"
    if not isinstance(doc, dict):
        return {}, path, f"the top level of {path} is not an object"
    return doc, path, None


PLACEHOLDER = ("<", ">")


def dotted(cfg, key, default=None):
    """One config value by `a.b.c`. An empty string and None both count as absent."""
    cur = cfg
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return default if cur in ("", None) else cur


def is_placeholder(value):
    """Is it still the placeholder from `workspace.example.json`?

    A key copied from the skeleton and never filled is **more dangerous than a missing one.** A
    missing key stops the tool; `"<abs path>"` passes as though it had a value and aims every
    later verdict at the wrong place.
    """
    if not isinstance(value, str):
        return False
    v = value.strip()
    return v.startswith(PLACEHOLDER[0]) and v.endswith(PLACEHOLDER[1])
