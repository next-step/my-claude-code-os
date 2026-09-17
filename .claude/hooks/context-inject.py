#!/usr/bin/env python3
"""Deterministic context injection hook (SubagentStart · PreToolUse)

The frontmatter of `.claude/context/*.md` is the routing table. Three triggers fire it.

  agent   SubagentStart - inject when the starting subagent's name is in `inject.agents`
  skill   PreToolUse(Skill) - inject when the invoked skill's name is in `inject.skills`
  path    PreToolUse(Read|Edit|Write|Bash) - inject when an absolute path in the arguments
          matches an `inject.paths` glob. `${key}` inside a path glob is substituted from workspace.json

Why a hook. Leaving it to the LLM as "read it if you need it" is slow (seconds) and
non-deterministic - and the fact that it was skipped is recorded nowhere. A hook is milliseconds,
deterministic, and **logs what it injected, so the injection itself can be tested.** That last item is why this file exists.

Budget and priority. There is a cap on how much goes in at once (`MAX_INJECT_BYTES`), and the
overflow is cut per file. The cutting order is set by `inject.priority` in the frontmatter (lower
goes in first; absent means `DEFAULT_PRIORITY`). **The names of the cut files stay at the head of
the injected block** - the receiving agent has to know what it did not get, and stderr does not reach it.

Duplicate suppression. The same file is never injected twice into the same session and agent.
Context is a finite resource that rots as it is used, and repeating the same paragraph burns that
resource while telling nobody anything new. The state lives in `.claude/.state/context-injected.json` -
the hook is a new process per call, so memory does not carry over.

**This hook never blocks a tool call, whatever happens.** On failure it exits 0 quietly and leaks
only the reason to stderr. Failing to inject context is an inconvenience; blocking a tool is an accident.

With no config, **only the path trigger** switches off. The agent and skill triggers do not read the
config and keep running. That fact is written to stderr once per session - a quietly narrowed
behavior is the failure shape this repository has recorded again and again.

Starting a session with `CONTEXT_INJECT_OFF=1` injects nothing. That is the B side of an A/B
comparison - a switch for running the same skill without context - and being off is stated on stderr.

Called with `--check` it runs as a checker rather than a hook (validating the routing table). Only
then does it emit a non-zero code: 0 clean, 1 name mismatch (--strict), 2 frontmatter unreadable.
"""
import fnmatch
import json
import os
import re
import sys
import time

# ---------------------------------------------------------------- constants (switches)

# The output form of SubagentStart is not documented. Both forms are implemented and the choice
# is made by measurement (the probe procedure in docs/context-system.md). Before the probe,
# "unknown" is the correct answer, so the code does not assert which one is right.
#   "json"   -> {"hookSpecificOutput": {"hookEventName": "SubagentStart", ...}}
#   "stdout" -> plain text straight to stdout
SUBAGENT_OUTPUT = "json"

# The fallback for when neither of the two above reaches the subagent. It returns the whole tool
# input at PreToolUse(Task) with the context appended to the end of `prompt`. Off by default - it
# lengthens the prompt, and where SubagentStart works the same content goes in twice.
TASK_FALLBACK = False

# The maximum bytes injectable at once. Overflow is cut per file (never mid-paragraph).
# A device built to save context must not burn context.
MAX_INJECT_BYTES = 24 * 1024

# **What gets dropped first** when the budget fills. `inject.priority` in the frontmatter decides
# it - lower goes in first, and absent means this value.
#
# Leaving the packing order to filenames makes the alphabet the policy. The six files reaching the
# completeness checker were using nine tenths of the budget, and the last in that order happened
# to be the public-repository boundary file - which is to say, the first thing dropped when the
# budget overflowed was the rule "do not write company content into a tracked file". Priority
# exists so that outcome is decided by judgment rather than by a name.
DEFAULT_PRIORITY = 50
MAX_LOG = 5 * 1024 * 1024
STATE_TTL = 86400
COUNTS = "__counts"
BASH_PATH_LIMIT = 60

PATH_TOOLS = ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit")
RE_ABS_PATH = re.compile(r"(?<![\w=])(/[A-Za-z0-9._/\-]{3,})")
RE_SUBST = re.compile(r"\$\{([A-Za-z0-9_.]+)\}")


def warn(msg):
    try:
        sys.stderr.write("context-inject: " + msg + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------- project and config

def project_dir(payload=None):
    """This OS checkout. The nearest ancestor holding `.claude/context/`."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        d = os.path.abspath(os.path.expanduser(env))
        if os.path.isdir(os.path.join(d, ".claude", "context")):
            return d
    here = os.path.dirname(os.path.abspath(__file__))
    for start in (here, (payload or {}).get("cwd") or os.getcwd()):
        d = os.path.abspath(start)
        while True:
            if os.path.isdir(os.path.join(d, ".claude", "context")):
                return d
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    return None


def load_config(project, override=None):
    """The whole workspace.json. `(dict, problem reason or None)`.

    Unlike the existing tools that read only the `legacy` section, the whole thing is needed here -
    a path glob can point at another section, such as `${backend.root}`.
    """
    path = override or (os.path.join(project, ".claude", "config", "workspace.json")
                        if project else None)
    if not path:
        return {}, "the project was not found, so the config path is unknown"
    if not os.path.isfile(path):
        return {}, f"{path} does not exist - only the path trigger switches off"
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return {}, f"{path} could not be read: {exc}"
    return (data if isinstance(data, dict) else {}), None


def resolve(spec, cfg, project):
    """Replace `${a.b}` with the config value. None when it cannot be replaced (= this glob is unusable).

    `${project.root}` alone is not the config but this checkout itself. This OS's boundary rule has
    to fire without a config, so it is an exception.
    """
    missing = []

    def one(m):
        key = m.group(1)
        if key == "project.root":
            if not project:
                missing.append(key)
                return ""
            return project
        cur = cfg
        for part in key.split("."):
            if not isinstance(cur, dict) or part not in cur:
                missing.append(key)
                return ""
            cur = cur[part]
        if not isinstance(cur, str) or not cur:
            missing.append(key)
            return ""
        return cur

    out = RE_SUBST.sub(one, spec)
    return None if missing else out


# ---------------------------------------------------------------- frontmatter

def parse_front(text, name):
    """Minimal YAML of the `---` frontmatter. On failure it raises ValueError with the reason."""
    if not text.startswith("---"):
        raise ValueError(f"{name}: the frontmatter does not start with `---`")
    end = text.find("\n---", 3)
    if end < 0:
        raise ValueError(f"{name}: the frontmatter is not closed")
    head = text[text.find("\n", 3) + 1:end]
    body = text[end + 4:].lstrip("\n")

    def value(raw):
        raw = raw.strip()
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            return [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
        if raw.startswith(("'", '"')):
            q = raw[0]
            j = raw.find(q, 1)
            return raw[1:j] if j > 0 else raw[1:]
        raw = raw.split(" #")[0].strip()
        return raw

    meta, cur_map, cur_list = {}, None, None
    for line in head.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        s = line.strip()
        if s.startswith("- "):
            if cur_list is None:
                raise ValueError(f"{name}: a list item appeared with no key - {s!r}")
            cur_list.append(value(s[2:]))
            continue
        if ":" not in s:
            raise ValueError(f"{name}: a line that is not a key - {s!r}")
        key, raw = s.split(":", 1)
        key, raw = key.strip(), raw.strip()
        if indent == 0:
            cur_map, cur_list = None, None
            if raw == "":
                meta[key] = {}
                cur_map = meta[key]
            else:
                meta[key] = value(raw)
        else:
            if cur_map is None:
                raise ValueError(f"{name}: an indented key with no parent - {s!r}")
            if raw == "":
                cur_map[key] = []
                cur_list = cur_map[key]
            else:
                cur_map[key] = value(raw)
                cur_list = None
    for req in ("name", "kind", "token"):
        if not meta.get(req):
            raise ValueError(f"{name}: `{req}` is missing")
    inject = meta.get("inject")
    if not isinstance(inject, dict):
        raise ValueError(f"{name}: no `inject` section")
    for k in ("agents", "skills", "paths", "tools"):
        v = inject.get(k, [])
        if isinstance(v, str):
            v = [v] if v else []
        if not isinstance(v, list):
            raise ValueError(f"{name}: `inject.{k}` is not a list")
        inject[k] = v
    # Priority is an integer. If it is not a number it is said here - silently substituting the
    # default would let one typo push that file to the budget boundary with no record of it.
    prio = inject.get("priority", DEFAULT_PRIORITY)
    try:
        inject["priority"] = int(str(prio).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{name}: `inject.priority` is not an integer - {prio!r}")
    meta["inject"] = inject
    meta["body"] = body
    return meta


def load_context(project):
    """`(items, errors)`. One broken file leaves the rest alive."""
    items, errors = [], []
    d = os.path.join(project, ".claude", "context") if project else None
    if not d or not os.path.isdir(d):
        return items, [f"{d} does not exist"]
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".md") or fn.startswith("_"):
            continue
        p = os.path.join(d, fn)
        try:
            with open(p, encoding="utf-8") as fh:
                meta = parse_front(fh.read(), fn)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        meta["file"] = fn
        meta["path"] = p
        items.append(meta)
    return items, errors


# ---------------------------------------------------------------- state and log

def state_path(project):
    return os.path.join(project, ".claude", ".state", "context-injected.json")


def read_state(project):
    try:
        with open(state_path(project), encoding="utf-8") as fh:
            s = json.load(fh)
        return s if isinstance(s, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(project, state):
    try:
        p = state_path(project)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + f".{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        os.replace(tmp, p)
    except Exception:
        pass


def prune(state, now):
    for sess in list(state.keys()):
        if sess.startswith("__"):
            continue
        rows = state.get(sess)
        if not isinstance(rows, dict):
            del state[sess]
            continue
        for k, ts in list(rows.items()):
            if not isinstance(ts, (int, float)) or ts < now - STATE_TTL:
                del rows[k]
        if not rows:
            del state[sess]
    counts = state.get(COUNTS)
    if isinstance(counts, dict):
        for sess, row in list(counts.items()):
            if not isinstance(row, dict) or row.get("ts", 0) < now - STATE_TTL:
                del counts[sess]
        if not counts:
            del state[COUNTS]
    elif COUNTS in state:
        del state[COUNTS]
    return state


def bump(state, sess, matched, injected, now):
    """How often a trigger matched and how often it actually injected. The difference is the suppression.

    A suppressed call leaves no line in the log - the log has to be "what was injected", and if
    suppression took most of it the log would lose its purpose. So the numbers are counted into
    reserved keys of the state file. `ctxstats` derives the suppression rate from the two.
    """
    row = state.setdefault(COUNTS, {}).setdefault(sess or "-", {"matched": 0,
                                                                "injected": 0,
                                                                "ts": now})
    row["matched"] = row.get("matched", 0) + matched
    row["injected"] = row.get("injected", 0) + injected
    row["ts"] = now


def log(project, rec):
    try:
        d = os.path.join(project, ".claude", ".state")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "context-injections.jsonl")
        if os.path.exists(p) and os.path.getsize(p) > MAX_LOG:
            os.replace(p, p + ".1")
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------- matching

def short(name):
    return name.split(":")[-1].strip()


def match_agent(items, agent_type):
    if not agent_type:
        return []
    a = short(agent_type)
    return [it for it in items
            if a in [short(x) for x in it["inject"]["agents"]]]


def match_skill(items, skill):
    if not skill:
        return []
    s = short(skill)
    return [it for it in items
            if s in [short(x) for x in it["inject"]["skills"]]]


def candidate_paths(tool, tool_input):
    """The absolute paths from the tool input to judge against."""
    out = []
    if tool in PATH_TOOLS:
        for key in ("file_path", "notebook_path", "path"):
            v = tool_input.get(key)
            if isinstance(v, str) and v.startswith("/"):
                out.append(v)
    elif tool == "Bash":
        cmd = tool_input.get("command")
        if isinstance(cmd, str):
            for m in RE_ABS_PATH.finditer(cmd):
                out.append(m.group(1))
                if len(out) >= BASH_PATH_LIMIT:
                    break
    return out


def match_path(items, paths, tool, cfg, project):
    hit = []
    if not paths:
        return hit
    for it in items:
        tools = it["inject"].get("tools") or []
        if tools and tool not in tools:
            continue
        for spec in it["inject"]["paths"]:
            glob = resolve(spec, cfg, project)
            if not glob:
                continue
            if any(fnmatch.fnmatch(p, glob) for p in paths):
                hit.append(it)
                break
    return hit


# ---------------------------------------------------------------- assembly and output

def render(items, trigger, errors=()):
    """`(the text to inject, the items actually packed)`.

    **Pack in priority order and record what was cut inside the block.** Once the budget fills,
    everything after it is cut - slipping a smaller later file into the remaining room would invert the priority.

    Stating the cut on stderr alone is not enough. The stderr of a hook that exited 0 does not reach
    the receiving agent, so from there it is indistinguishable from "this file never comes". So one
    line stays at the head of the block - knowing what it did not get, the agent can read it
    directly; not knowing, it behaves as though the rule does not exist.
    """
    parts, kept, cut = [], [], []
    used = 0
    for it in sorted(items, key=lambda x: (x["inject"]["priority"], x["file"])):
        block = (f"\n<context name=\"{it['name']}\" kind=\"{it['kind']}\" "
                 f"token=\"{it['token']}\">\n{it['body'].rstrip()}\n</context>")
        b = len(block.encode("utf-8"))
        if cut or (used + b > MAX_INJECT_BYTES and kept):
            cut.append(it["file"])
            continue
        parts.append(block)
        used += b
        kept.append(it)
    head = ["# Automatically injected context - `.claude/context/` "
            f"(trigger: {trigger} · once per file per session and agent)"]
    if cut:
        warn(f"{', '.join(cut)} was cut from this injection (budget {MAX_INJECT_BYTES}B)")
        head.append(f"# files not packed because the budget ({MAX_INJECT_BYTES}B) filled: "
                    + ", ".join(cut)
                    + " - this content did not arrive, so read "
                      "`.claude/context/<file>` directly if you need it.")
    if errors:
        head.append("# some context files could not be read (frontmatter error): "
                    + " / ".join(str(e) for e in errors))
    return "\n".join(head + parts), kept


def emit_pre(text, updated_input=None):
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                  "additionalContext": text}}
    if updated_input is not None:
        out["hookSpecificOutput"]["updatedInput"] = updated_input
    json.dump(out, sys.stdout, ensure_ascii=False)


def emit_subagent(text):
    if SUBAGENT_OUTPUT == "stdout":
        sys.stdout.write(text)
    else:
        json.dump({"hookSpecificOutput": {"hookEventName": "SubagentStart",
                                          "additionalContext": text}},
                  sys.stdout, ensure_ascii=False)


# ---------------------------------------------------------------- checker

def check(argv):
    strict = "--strict" in argv
    project = project_dir()
    if not project:
        warn("the project was not found")
        return 2
    items, errors = load_context(project)
    for e in errors:
        print(f"error  {e}")
    if errors:
        return 2
    if not items:
        print("error  there is no context file at all")
        return 2
    tokens, dup = {}, []
    for it in items:
        if it["token"] in tokens:
            dup.append(f"{it['file']} and {tokens[it['token']]} have the same token")
        tokens[it["token"]] = it["file"]
    agents = {os.path.splitext(f)[0]
              for f in os.listdir(os.path.join(project, ".claude", "agents"))
              if f.endswith(".md")} if os.path.isdir(
                  os.path.join(project, ".claude", "agents")) else set()
    sk_root = os.path.join(project, ".claude", "skills")
    skills = {n for n in (os.listdir(sk_root) if os.path.isdir(sk_root) else [])
              if os.path.isfile(os.path.join(sk_root, n, "SKILL.md"))}
    unknown = []
    for it in items:
        for a in it["inject"]["agents"]:
            if short(a) not in agents:
                unknown.append(f"{it['file']}: no agent `{a}`")
        for s in it["inject"]["skills"]:
            if short(s) not in skills:
                unknown.append(f"{it['file']}: no skill `{s}`")
    cfg, problem = load_config(project)
    for it in items:
        for spec in it["inject"]["paths"]:
            if resolve(spec, cfg, project) is None:
                unknown.append(f"{it['file']}: the key of path glob `{spec}` was not found in the config")
    print(f"{len(items)} context files · {len(tokens)} tokens"
          + (f" · config problem: {problem}" if problem else ""))
    # Print in priority order. That is the order things are cut when the budget fills, and this is
    # the only place it can be seen.
    for it in sorted(items, key=lambda x: (x["inject"]["priority"], x["file"])):
        n = len(it["body"].splitlines())
        print(f"  {it['file']:<30} {it['kind']:<10} {it['token']:<26} "
              f"priority {it['inject']['priority']:>3} · body {n} lines")
    for d in dup:
        print(f"error  {d}")
    for u in unknown:
        print(f"warn   {u}")
    if dup:
        return 2
    if unknown and strict:
        return 1
    return 0


# ---------------------------------------------------------------- main

def main():
    if "--check" in sys.argv[1:]:
        sys.exit(check(sys.argv[1:]))
    if "--help" in sys.argv[1:] or "-h" in sys.argv[1:]:
        print(__doc__)
        sys.exit(0)

    # The A/B switch. To compare the same skill without injection, set this and start a session
    # (hooks are snapshotted at session start, so it cannot be toggled mid-session). Being off is
    # always stated - a hook that silently does nothing is misread as "injection was not needed".
    if os.environ.get("CONTEXT_INJECT_OFF"):
        warn("CONTEXT_INJECT_OFF is set, so nothing is injected (the B side of the A/B)")
        return

    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        warn("the hook input is not JSON")
        return
    project = project_dir(payload)
    if not project:
        warn("the project was not found - injecting nothing")
        return

    event = payload.get("hook_event_name") or ""
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    sess = payload.get("session_id") or ""
    agent_id = payload.get("agent_id") or ""
    agent_type = payload.get("agent_type") or ""

    items, errors = load_context(project)
    for e in errors:
        warn(e)          # one broken file does not block the rest of the injection
    if not items:
        return

    trigger, hits, updated = "", [], None
    if event == "SubagentStart":
        trigger = "agent"
        agent_type = agent_type or payload.get("subagent_type") or ""
        hits = match_agent(items, agent_type)
    elif event == "PreToolUse" and tool == "Skill":
        trigger = "skill"
        hits = match_skill(items, tool_input.get("skill") or "")
    elif event == "PreToolUse" and tool == "Task" and TASK_FALLBACK:
        trigger = "agent"
        agent_type = tool_input.get("subagent_type") or ""
        hits = match_agent(items, agent_type)
    elif event == "PreToolUse":
        trigger = "path"
        cfg, problem = load_config(project)
        if problem:
            hits = []
        else:
            hits = match_path(items, candidate_paths(tool, tool_input), tool,
                              cfg, project)
    if not hits and trigger != "path":
        return

    now = int(time.time())
    state = prune(read_state(project), now)
    room = state.setdefault(sess or "-", {})

    if trigger == "path":
        cfg, problem = load_config(project)
        if problem and "_cfgwarn" not in room:
            room["_cfgwarn"] = now
            write_state(project, state)
            warn(problem + " (the agent and skill triggers keep working)")
        if problem:
            return

    who = agent_id or (f"type:{agent_type}" if agent_type else "main")
    fresh = [it for it in hits if f"{who}|{it['name']}" not in room]
    if not fresh:
        if hits:
            bump(state, sess, len(hits), 0, now)
            write_state(project, state)
        return
    text, kept = render(fresh, trigger, errors)
    for it in kept:
        room[f"{who}|{it['name']}"] = now
        log(project, {"ts": now, "session_id": sess, "agent_id": agent_id,
                      "agent_type": agent_type, "trigger": trigger, "tool": tool,
                      "file": it["file"], "token": it["token"],
                      "bytes": len(it["body"].encode("utf-8"))})
    bump(state, sess, len(hits), len(kept), now)
    write_state(project, state)

    if event == "SubagentStart":
        emit_subagent(text)
    elif tool == "Task" and TASK_FALLBACK:
        updated = dict(tool_input)
        updated["prompt"] = (str(tool_input.get("prompt") or "")
                             + "\n\n" + text)
        emit_pre(text, updated)
    else:
        emit_pre(text)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:            # a hook failure never blocks a tool
        warn(f"backing off: {exc!r}")
    sys.exit(0)
