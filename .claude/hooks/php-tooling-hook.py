#!/usr/bin/env python3
"""PreToolUse(Bash|Read|Task) + PostToolUse(Task) — point calls at the legacy tools,
record use, and attribute it to the pipeline stage that made the call.

Never blocks. Three jobs:

  steer   A `phpgrep` whose pattern is definition-shaped (`$X =`, `function foo`,
          `class Foo`, `define('X'`) returns zero whenever the real definition is
          written as `$X[key] = value`, and that zero reads as "does not exist".
          Say so and point at `phpwhere`. Also catch reading the index JSON by hand.

  log     Append one line per call that touches the legacy checkout to
          <project>/.claude/.state/tooling.jsonl. The point is not a call count -
          it is whether the purpose-built tool was used or bypassed: `phpv` vs the
          Read tool, `phpgrep` vs raw grep, `phpwhere` vs a definition-shaped grep.
          `phpstats` reads it back.

  attribute  Track which subagent is running, so a call can be attributed to the
          pipeline stage that made it. `session_id` cannot do this - a subagent
          gets the same one as its parent, which is why the stage-by-stage tool
          assignment in docs/php-legacy-tooling.md §5 was unverifiable. Registered
          on Task for both PreToolUse and PostToolUse to open and close the record.

Nothing that touches the legacy checkout is named here: this file is tracked and
the repository is public. `legacy.root` and `legacy.treeRoot`/`legacy.ours` come
from .claude/config/workspace.json, which is gitignored. Without that config the
nudging and logging do nothing — attribution still runs, because it is about this
session rather than about the checkout. Every failure path is swallowed: a broken
logger must never break a tool call.
"""
import json
import os
import re
import shlex
import sys
import time

MAX_LOG = 5 * 1024 * 1024

# A definition here is `$variable` (optionally subscripted) followed by `=`, not any `=`
# at all. Measured: matching a bare `=` fires on SQL conditions (`WHERE col = `),
# HTML attributes (`name="x"`) and config strings (`iconv=UTF-8`) — 4 of 12
# representative cases wrong. Requiring the `$` brings that to 0.
DEF_SHAPED = re.compile(
    r"(\\?\$[A-Za-z_]\w*(?:\[[^\]]*\])?\s*(?:\\s\*)?=(?![=>])"
    r"|\bfunction\s|\bclass\s|\binterface\s|\btrait\s|\bdefine\s*\\?\s*\()")
NAME_IN_PATTERN = re.compile(r"\$?([A-Za-z_]\w{2,})")
# While the four v2 tools were absent from here, a command calling them was counted neither as a
# detour nor as dedicated and dropped out entirely - and a dropped record looks like low usage.
OUR_TOOLS = ("phpv", "phpgrep", "phped", "phplint", "phpindex", "phpwhere",
             "phpstats", "phpmove", "htmlsnap", "dualrun-report", "ctxstats",
             "ctxevolve", "pagecheck", "causestats")
STOP = {"function", "class", "interface", "trait", "define", "scope", "all",
        "tests", "web", "php", "inc"}
# The index moved to `.claude/.state/index/` on 2026-09-08. While only the old path was watched,
# reading the index directly passed in silence.
INDEX_REF = re.compile(r"\.claude/\.state/index/\S*\.json")

RE_HEREDOC = re.compile(r"<<-?\s*'?\"?(\w+)'?\"?.*?^\1", re.S | re.M)


def strip_heredocs(cmd):
    """A heredoc body is data, not a command. Writing a file whose *content*
    mentions `.claude/index/x.json` is not an attempt to read the index."""
    return RE_HEREDOC.sub("", cmd)


PREFIX_CMDS = {"env", "s" "udo", "time", "nohup", "command", "exec"}
SOURCE_EXT = (".php", ".inc")
READ_CMDS = ("cat", "head", "tail", "less", "more", "sed", "awk", "nl")
GREP_CMDS = ("rg", "grep", "egrep", "fgrep", "ag", "ack")


def _segments(cmd):
    """Split a command line where a new command can begin."""
    cmd = re.sub(r"\d?>&\d", " ", cmd)          # the & in 2>&1 is not a separator
    return re.split(r"&&|\|\||[;\n|&]", cmd)


def _leading_command(seg):
    """(basename of argv0, remaining argv) for one segment, prefixes stripped.

    A tool name counts only when it stands where a command stands. Quoting is
    not the test: `"$S/phpgrep" 'x'` is an ordinary call and used to be dropped
    entirely, while `phpv phpgrep phped ...` merely lists names and used to be
    logged as seven calls. Both errors were silent and pointed opposite ways.
    """
    try:
        toks = shlex.split(seg, posix=True)
    except ValueError:
        toks = seg.split()
    i = 0
    while i < len(toks):
        t = toks[i]
        if re.match(r"^[A-Za-z_]\w*=", t):        # VAR=value
            i += 1
            continue
        base = os.path.basename(t)
        if base in PREFIX_CMDS:
            i += 1
            while i < len(toks) and (toks[i].startswith("-")
                                     or re.match(r"^[A-Za-z_]\w*=", toks[i])):
                i += 2 if toks[i] in ("-u", "--unset") else 1
            continue
        if re.match(r"^python[\d.]*$", base):
            i += 1
            continue
        return base, toks[i + 1:]
    return None


def _targets_source(seg, root_abs, cwd_in_tree):
    """Does this segment actually touch source in the tree?

    Judged by path. Searching for the tree directory's basename as a string also catches a
    directory of the same name outside the tree.
    """
    if INDEX_REF.search(seg):
        return True
    if root_abs and re.search(re.escape(root_abs) + r"/\S+\.(php|inc)\b", seg):
        return True
    if cwd_in_tree and re.search(r"\S+\.(php|inc)\b", seg):
        return True
    return False


def config(project_dir):
    cfg = os.path.join(project_dir, ".claude", "config", "workspace.json")
    try:
        with open(cfg, encoding="utf-8") as fh:
            return json.load(fh).get("legacy") or {}
    except (OSError, json.JSONDecodeError):
        return {}


def service_of(path, tree_root, ours):
    """Short name of the owner dir this path sits in, or None."""
    if not tree_root or not ours:
        return None
    try:
        rel = os.path.relpath(os.path.abspath(path), os.path.abspath(tree_root))
    except ValueError:
        return None
    if rel.startswith(".."):
        return None
    for prefix, name in ours.items():
        if rel == prefix or rel.startswith(prefix + "/"):
            return name
    return None


def _agents_path(project_dir):
    return os.path.join(project_dir, ".claude", ".state", "open-agents.json")


def open_agents(project_dir, sess):
    """Subagent types currently running in this session, oldest first.

    It lives in the state file. The hook is a new process per call, so memory does not carry over.
    """
    try:
        with open(_agents_path(project_dir), encoding="utf-8") as fh:
            return [r["type"] for r in json.load(fh).get(sess, [])]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def mark_agent(project_dir, sess, kind, opening):
    """Record a Task starting or finishing. Never raises.

    On close, the **oldest** entry of the same kind is removed. Running two of the same agent in
    parallel makes it impossible to tell which finished, and in that case the remaining count is
    the same whichever is removed. With the count right, the verdict "how many are open" is preserved.
    """
    try:
        p = _agents_path(project_dir)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        try:
            with open(p, encoding="utf-8") as fh:
                state = json.load(fh)
            if not isinstance(state, dict):
                state = {}
        except (OSError, ValueError):
            state = {}
        rows = [r for r in state.get(sess, []) if isinstance(r, dict)]
        if opening:
            rows.append({"type": kind, "ts": int(time.time())})
        else:
            for i, r in enumerate(rows):
                if r.get("type") == kind:
                    del rows[i]
                    break
            else:
                if rows:
                    del rows[0]
        # The state file survives the session. Entries older than a day are discarded so the file
        # does not grow and a dead entry does not stay "open" forever.
        cut = int(time.time()) - 86400
        state[sess] = [r for r in rows if r.get("ts", 0) >= cut]
        state = {k: v for k, v in state.items() if v}
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
    except Exception:
        pass


def transcript_mark(payload):
    """Short fingerprint of transcript_path, or ''.

    Where a subagent uses its own transcript, this value differs from the parent's.
    Whether it actually differs is answered by the collected log, so this records without judging.
    """
    tp = payload.get("transcript_path") or ""
    if not tp:
        return ""
    base = os.path.basename(tp)
    return os.path.splitext(base)[0][-8:]


def log(project_dir, rec):
    """Append one record to the project's gitignored state dir.

    Here rather than inside the checkout. Put inside, the log would vanish when the checkout is
    rebuilt, and instrumentation only means something measured over time. `phpstats` reads the
    same path.
    """
    if not project_dir:
        return
    try:
        d = os.path.join(project_dir, ".claude", ".state")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "tooling.jsonl")
        if os.path.exists(p) and os.path.getsize(p) > MAX_LOG:
            os.replace(p, p + ".1")
        rec["ts"] = int(time.time())
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def emit(message):
    try:
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": message,
        }}, sys.stdout)
    except Exception:
        pass
    sys.exit(0)


def classify(cmd, root_abs, cwd_in_tree):
    """Every tool call in one command, as [(tool, mode, arg), ...].

    A general-purpose tool counts as a bypass only when it actually targets
    source in the tree - appending to a doc is not a bypass of `phpv`. Dedicated
    and general calls are both collected: returning early on the first dedicated
    hit erased the bypass sitting in the same command, and every such erasure
    moved the ratio the same way.
    """
    out = []
    for seg in _segments(cmd):
        head = _leading_command(seg)
        if not head:
            continue
        base, args = head
        clean = []
        for a in args:                       # a redirect is not an argument
            if a.startswith(">") or a.startswith("<"):
                break
            clean.append(a)
        if base in OUR_TOOLS:
            sub = ""
            if clean and re.match(
                    r"^(--?[\w-]+|open|save|discard|status|replace"
                    r"|lint|hash|check|callers|fields|capture|compare|observations)$",
                    clean[0]):
                sub = clean[0]
            out.append((base, sub, " ".join(clean)[:60]))
            continue
        if not _targets_source(seg, root_abs, cwd_in_tree):
            continue
        if base in GREP_CMDS:
            out.append(("raw-grep", "", ""))
        elif base in READ_CMDS and not re.search(r"(^|[^>])>>?\s*\S", seg):
            out.append(("raw-read", "", ""))
    return out


def service_for(cmd, cwd, tree_root, ours):
    """Which service a call touched. A path in the command wins over cwd.

    Going by cwd alone leaves almost every call from this OS unattributed, because it runs one
    level above the checkout and never uses `cd`. Measured, 76% of records were empty.
    """
    if tree_root and cmd:
        m = re.search(re.escape(os.path.abspath(tree_root)) + r"/\S+", cmd)
        if m:
            svc = service_of(m.group(0), tree_root, ours)
            if svc:
                return svc
    return service_of(cwd, tree_root, ours)


def attribution(payload, project_dir, sess):
    """Which pipeline stage made this call, and where that answer came from.

    When the hook input states its own `agent_type`/`agent_id`, **that is canonical.**
    The `Task` registration state remains only as a fallback for environments without those
    fields - registration is built on the session-shared `session_id`, so running two of the same
    kind in parallel makes it impossible to say which, and that ambiguity could only be marked by the `agents` count.

    `src` is recorded alongside. The two paths differ in accuracy, so without being able to tell
    which one an attribution came from when reading the log later, the difference cannot be measured either.
    """
    kind = payload.get("agent_type") or ""
    aid = payload.get("agent_id") or ""
    if kind or aid:
        return {"agent": kind or None, "agent_id": aid or None,
                "agents": 1, "src": "input", "tp": transcript_mark(payload)}
    # Nothing open means the parent. One means that is the answer. Two or more **records it as
    # ambiguous** - picking one writes a wrong attribution into the log as fact, and that log
    # then becomes the basis for judging the per-phase assignment.
    agents = open_agents(project_dir, sess)
    return {"agent": agents[0] if len(agents) == 1 else None,
            "agents": len(agents), "src": "task",
            "tp": transcript_mark(payload)}


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    tool = payload.get("tool_name") or ""
    ti = payload.get("tool_input") or {}
    cwd = payload.get("cwd") or os.getcwd()
    sess = (payload.get("session_id") or "")[:8]

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    event = payload.get("hook_event_name") or ""

    # ---- attribution: record which subagent is running --------------------
    # This comes before the config. It has nothing to do with the legacy checkout, and the
    # attribution state has to stay correct even in a session where instrumentation is off for lack of config.
    if tool == "Task":
        kind = ti.get("subagent_type") or ti.get("agent_type") or "?"
        mark_agent(project_dir, sess, kind, opening=(event != "PostToolUse"))
        return
    if event == "PostToolUse":
        return          # the PostToolUse of other tools is not this hook's job

    legacy = config(project_dir)
    root = legacy.get("root")
    if not root:
        return
    attrib = attribution(payload, project_dir, sess)
    root_abs = os.path.abspath(root)
    tree_root = legacy.get("treeRoot")
    ours = legacy.get("ours") or {}
    # The tools live in this project. If the path a steering message points at is wrong, the
    # message is worse than none - it points in the wrong direction with a plausible sentence
    # every time, and nothing signals that it is wrong.
    scripts_hint = os.path.join(project_dir, ".claude", "scripts")
    index_dir = os.path.join(project_dir, ".claude", ".state", "index")

    # ---- Read tool on a file in the checkout = bypassing phpv ---------------
    if tool == "Read":
        fp = ti.get("file_path") or ""
        if not fp:
            return
        ap = os.path.abspath(fp).replace("\\", "/")
        # The index check comes before the checkout check. The index now lives in this project's
        # state directory, outside the checkout, and in the opposite order reading the index
        # directly passes in silence.
        if ap.startswith(index_dir.replace("\\", "/") + "/"):
            log(project_dir, {"tool": "read-index", "mode": "", "svc": None,
                              "arg": os.path.basename(fp), "nudge": 1,
                              "sess": sess, **attrib})
            emit("Never read the index JSON directly. One file is several MB. "
                 f"Look it up with `{scripts_hint}/phpwhere <name>` / `--tpl` / `--entry`.")
        if not ap.startswith(root_abs):
            return
        svc = service_of(fp, tree_root, ours)
        # Only source counts as a detour. Markdown and config files are not something `phpv` can
        # stand in for, and counting them presses the read ratio down with reads that have no substitute.
        if not ap.lower().endswith(SOURCE_EXT):
            return
        log(project_dir, {"tool": "Read", "mode": "", "svc": svc,
                   "arg": os.path.basename(fp), "nudge": 1, "sess": sess,
                   **attrib})
        emit("Encoding differs per file in this tree. Read shows the Korean in a CP949 file as "
             "mojibake, and that loss leaves no mark on screen. "
             f"Read it with `{scripts_hint}/phpv <file>`.")
        return

    if tool != "Bash":
        return
    cmd = strip_heredocs(ti.get("command") or "")

    # Whether it is of interest is decided by `classify`. There used to be a gate before it asking
    # "is the checkout path in the command", and while the tools lived inside the checkout, calling
    # them by absolute path satisfied that condition automatically. Moving the tools into this
    # repository on 2026-09-08 broke that coincidence, and **dedicated tool calls stopped being
    # recorded at all.** Only calls carrying a tree path in their arguments (`phpv <file>`)
    # remained, and calls passing a name or a pattern (`phpwhere <name>`, `phpgrep <word>`) all
    # dropped out - and the dropped side was exactly what this instrumentation was measuring.
    #
    # A dedicated tool only handles the target tree, so the fact that it was called at the command
    # position already means it is of interest. On the detour side, `_targets_source` inside
    # `classify` still confirms it points at the tree - otherwise every `grep` would be recorded.
    cwd_in_tree = os.path.abspath(cwd).startswith(root_abs)
    calls = [c for c in classify(cmd, root_abs, cwd_in_tree)
             if c[0] != "phpstats"]
    if not calls:
        return          # a stats lookup does not record itself
    svc = service_for(cmd, cwd, tree_root, ours)
    what, mode, arg = calls[0]

    # ---- steering toward the right tool ---------------------------------------
    # The record field below stays `nudge`. Renaming it would read every record written
    # before the rename as zero, and `phpstats` would report a quiet run as a clean one -
    # which is the failure this whole file exists to make visible.
    # It only decides which steering message to emit, and emits after every record is written.
    # `emit` ends the process, so calling it before recording loses the rest of the same command's
    # calls entirely. Then the more a command is steered, the fewer records it leaves, and the metric tips quietly.
    nudge_msg = None
    marked = None           # the tool to mark with nudge=1 inside calls
    marked_mode = None      # the value to overwrite that line's mode with
    extra = []              # a line to record separately from the call

    if INDEX_REF.search(cmd) and any(c[0] == "raw-read" for c in calls):
        extra.append(("read-index", "", arg))
        nudge_msg = ("Never read `.claude/index/*.json` directly. One file is several MB and "
                     "only burns context. Look it up with `phpwhere <name>`.")

    elif any(c[0] == "phpwhere" for c in calls) and not os.path.isdir(index_dir):
        marked = "phpwhere"
        nudge_msg = (f"There is no index yet. Run `{scripts_hint}/phpindex --all` first "
                     f"(about 10 seconds).")

    else:
        # Only what phpgrep itself received. A different command's long option
        # (`grep --include='*.md'`) must not reach the definition test.
        grep_args = " ".join(a for t, _, a in calls if t == "phpgrep")
        if grep_args and DEF_SHAPED.search(grep_args):
            names = [n for n in NAME_IN_PATTERN.findall(grep_args)
                     if n not in STOP]
            hint = f"`phpwhere {names[0]}`" if names else "`phpwhere <name>`"
            marked, marked_mode = "phpgrep", "def-shaped"
            nudge_msg = ("This looks like a search for a definition. In this tree grep often "
                         "cannot find one - when the real definition is `$X[CONST] = value`, a "
                         f"`$X =` search returns zero, and that zero is not 'there is none'. Use {hint} "
                         "first. phpgrep is for asking who uses something.")

        # Tell the detour side too. If the steering message only fires on calls already using the
        # dedicated tool, a caller who does not know the tool at all gets no signal and is recorded
        # in one line. In that state the steer count is still 0, so the metric cannot tell
        # "the rule has stuck" from "the tool was never used".
        elif any(c[0] == "raw-grep" for c in calls):
            marked = "raw-grep"
            nudge_msg = ("Encoding differs per file in this tree. Searching for Korean in one "
                         "encoding drops every file in the other, and it comes back as zero hits "
                         f"rather than an error. `{scripts_hint}/phpgrep <term>` sweeps both "
                         "encodings and prints what it swept every time.")

        elif any(c[0] == "raw-read" for c in calls):
            marked = "raw-read"
            nudge_msg = ("Encoding differs per file in this tree. A general-purpose read shows "
                         "the Korean in a CP949 file as mojibake, and that loss leaves no mark. "
                         f"Read it with `{scripts_hint}/phpv <file>`.")

    # ---- record, then speak -------------------------------------------------
    done = False
    for t, md, a in calls:
        n = 0
        if not done and t == marked:
            n, done = 1, True
            md = marked_mode or md
        log(project_dir, {"tool": t, "mode": md, "svc": svc, "arg": a,
                   "nudge": n, "sess": sess, **attrib})
    for t, md, a in extra:
        log(project_dir, {"tool": t, "mode": md, "svc": svc, "arg": a,
                   "nudge": 1, "sess": sess, **attrib})
    if nudge_msg:
        emit(nudge_msg)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
