#!/usr/bin/env python3
"""Pre/PostToolUse(Edit|Write) — preserve per-file encoding in the legacy checkout.

The legacy PHP tree is not uniformly encoded. Measured in the target checkout:
two data-access files of the same service, two directories apart, are UTF-8 and
EUC-KR/CP949 respectively. An agent that writes Korean into the wrong one produces
a file that decodes as neither, and the page renders mojibake in production.
Nothing in the test suite catches it, because the bytes are only wrong for humans.

Two phases, two different postures:

  PreToolUse   record path -> encoding in .claude/.state/php-encoding.json, and
               warn — target is CP949, or sits outside the dirs we own. Never
               blocks: old files have to be editable too.
  PostToolUse  re-detect and BLOCK if the encoding changed, became undecodable,
               or replacement characters appeared. By then the damage is done and
               there is a definite thing to restore. Also nudges when a `phped`
               working copy was edited but not written back, and reports a file
               that no longer parses on the runtime it ships on.

No path from the legacy tree is written here: this file is tracked and the
repository is public, and such a path is company information just as much as the
code inside it. Everything environment-specific comes from
.claude/config/workspace.json (`legacy.treeRoot`, `legacy.ours`), which is
gitignored. Missing config disables the hook rather than blocking work.
"""
import json
import os
import subprocess
import sys

STATE = os.path.join(".claude", ".state", "php-encoding.json")
WATCHED_SUFFIXES = (".php", ".inc", ".html", ".htm", ".js", ".css", ".tpl")
LINT_SUFFIXES = (".php", ".inc", ".tpl", ".phtml")
MOJIBAKE = b"\xef\xbf\xbd"          # U+FFFD encoded as UTF-8
WORKDIR = os.sep + os.path.join(".claude", ".edit") + os.sep


def detect(path):
    """'ascii' | 'utf-8' | 'cp949' | 'undecodable' | None(missing)."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    if not raw:
        return "ascii"
    try:
        raw.decode("ascii")
        return "ascii"
    except UnicodeDecodeError:
        pass
    # UTF-8 first: a byte sequence valid as UTF-8 is almost never CP949 Korean by
    # accident, while the reverse happens often. This is the same order `file` uses.
    for enc in ("utf-8", "cp949"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "undecodable"


def config(project_dir):
    cfg = os.path.join(project_dir, ".claude", "config", "workspace.json")
    try:
        with open(cfg, encoding="utf-8") as fh:
            return json.load(fh).get("legacy") or {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_state(project_dir):
    try:
        with open(os.path.join(project_dir, STATE), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(project_dir, state):
    path = os.path.join(project_dir, STATE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Keep the file from growing without bound across a long session.
    if len(state) > 200:
        state = dict(list(state.items())[-100:])
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh)


def emit(event, messages):
    """Advisory output. Several warnings go out as one block, not one each."""
    json.dump({"hookSpecificOutput": {
        "hookEventName": event,
        "additionalContext": "\n\n".join(messages),
    }}, sys.stdout)
    sys.exit(0)


def outside_ours(path, tree_root, ours):
    """treeRoot-relative name of the owner dir, or None when inside one.

    Ownership decides who may *edit* a file. It says nothing about whether a file
    is worth reading, which is why nothing here narrows a search.
    """
    if not tree_root or not ours:
        return None
    try:
        rel = os.path.relpath(os.path.abspath(path), os.path.abspath(tree_root))
    except ValueError:
        return None
    if rel.startswith(".."):
        return None                  # outside the tree entirely; not our business
    if any(rel == d or rel.startswith(d + "/") for d in ours):
        return None
    return rel


def restore_hint(path):
    """The command that undoes this edit, or a warning that nothing can."""
    d = os.path.dirname(os.path.abspath(path))
    try:
        top = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=5)
        if top.returncode == 0:
            root = top.stdout.strip()
            rel = os.path.relpath(os.path.abspath(path), root)
            tracked = subprocess.run(
                ["git", "-C", root, "ls-files", "--error-unmatch", rel],
                capture_output=True, timeout=5)
            if tracked.returncode == 0:
                return f"git -C {root} checkout -- {rel}"
            return ("git does not track this file - there is no way to undo it. "
                    "Do not overwrite it again.")
    except (OSError, subprocess.SubprocessError):
        pass
    return "no git repository was found for this path."


# The timeouts **have to nest.** This hook gets 35s for PostToolUse from settings.json, calls
# `phplint` with 25s inside that, and `phplint` gives docker 20s inside that. It used to be that
# the inner one (docker 60s x retries) was larger than the outer one (25s). Then the outer died
# first, `TimeoutExpired` was caught as `SubprocessError` and became `None`, and **the fact that
# the check never ran arrived in the same shape as a pass.**
LINT_TIMEOUT = 25
DOCKER_TIMEOUT = 20


def lint_failure(path, scripts):
    """`phped` lints before it saves; a direct Write/Edit does not. This is the net.

    Returns (kind, message) - kind is "fails" when the file will not parse on the
    runtime it ships on, "unchecked" when the checker could not answer at all.
    The second one used to arrive as exit 0, which reads as a pass; a check that
    silently reports success is worse than no check.
    """
    if not path.lower().endswith(LINT_SUFFIXES):
        return None
    tool = os.path.join(scripts, "phplint")
    if not os.path.isfile(tool):
        # A missing tool does not mean "the syntax is fine". Passing over it quietly means nobody
        # knows the check disappeared, and that state is indistinguishable from a pass.
        return "unchecked", f"could not find the syntax-check tool: {tool}"
    try:
        p = subprocess.run(
            [sys.executable, tool, path], capture_output=True,
            timeout=LINT_TIMEOUT,
            env={**os.environ, "PHPLINT_DOCKER_TIMEOUT": str(DOCKER_TIMEOUT)})
    except subprocess.TimeoutExpired:
        # A timeout is not a result. Returning `None` for it makes it indistinguishable from
        # "checked and fine".
        return "unchecked", (
            f"could not check the syntax (timed out after {LINT_TIMEOUT}s). "
            f"The container may be slow or the image missing - "
            f"run {tool} {path} directly to find out.")
    except (OSError, subprocess.SubprocessError):
        return None                  # cannot check is not the same as failed
    msg = p.stderr.decode("utf-8", "replace").strip()
    if p.returncode == 1:
        return "fails", msg
    if p.returncode == 3:
        return "unchecked", msg
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not path:
        return 0

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    legacy = config(project_dir)
    root = legacy.get("root")
    if not root or not os.path.abspath(path).startswith(os.path.abspath(root)):
        return 0

    event = payload.get("hook_event_name", "PreToolUse")
    # The tools live in this project. They moved out of the legacy checkout on 2026-09-08, and
    # this path was not fixed at the same time, so `phplint` was not found. When it is not found
    # `lint_failure` returns None, so **the check passed quietly without ever running.**
    # That is exactly the failure this hook exists to prevent.
    scripts = os.path.join(project_dir, ".claude", "scripts")
    in_workdir = WORKDIR in os.path.abspath(path)

    # ---- a `phped` working copy is UTF-8 by construction -------------------
    if in_workdir:
        if event == "PreToolUse":
            return 0
        meta = os.path.splitext(path)[0] + ".json"
        try:
            with open(meta, encoding="utf-8") as fh:
                source = json.load(fh).get("source", "")
        except (OSError, ValueError):
            source = ""
        if source:
            emit(event, [f"You edited the working copy. It is not in the original yet:\n"
                         f"  {scripts}/phped save {source}"])
        return 0

    if not path.endswith(WATCHED_SUFFIXES):
        return 0

    state = load_state(project_dir)

    # ---- Pre: record, then advise ------------------------------------------
    if event == "PreToolUse":
        before = detect(path)
        if before is not None:
            state[path] = before
            save_state(project_dir, state)

        notes = []
        rel = outside_ours(path, legacy.get("treeRoot"), legacy.get("ours") or {})
        if rel:
            notes.append(
                f"Ownership: {rel} is another team's code. Reading it is free, but do not "
                f"edit it unless that was the agreed plan.")
        if before == "cp949":
            notes.append(
                f"Encoding warning: this file is CP949. Writing it with this tool rewrites the "
                f"whole file as UTF-8, not just the line you meant to change, destroying every "
                f"Korean character inside it.\nUse the round trip:\n"
                f"  {scripts}/phped open {path}\n"
                f"  ...edit the working copy it prints...\n"
                f"  {scripts}/phped save {path}")
        if notes:
            emit(event, notes)
        return 0

    # ---- Post: block on damage --------------------------------------------
    before = state.pop(path, None)
    save_state(project_dir, state)
    after = detect(path)

    if after == "undecodable":
        sys.stderr.write(
            f"The encoding is broken: {path}\n"
            f"  before the edit: {before or 'unknown'} -> after: decodable in no encoding\n\n"
            "Bytes of different encodings are mixed inside one file. Undo the edit.\n"
            f"  {restore_hint(path)}\n"
            + (
                f"This file's original encoding is {before} - write it only in that encoding.\n"
                if before in ("utf-8", "cp949")
                else "Undo it, then confirm the original encoding first.\n"
            )
            + f"Go through {scripts}/phped when you edit it again.\n"
            "  (writing ASCII only, with no Korean, avoids this problem entirely)\n"
        )
        return 2

    if before in ("utf-8", "cp949") and after in ("utf-8", "cp949") and before != after:
        sys.stderr.write(
            f"The file encoding changed: {path}\n"
            f"  {before} -> {after}\n\n"
            "Encoding differs per file in this legacy tree, and the page header declares the\n"
            "original encoding. Changing the encoding breaks the screen. Undo it.\n"
            f"  {restore_hint(path)}\n"
            f"Go through {scripts}/phped when you edit it again.\n"
            "  (writing ASCII identifiers only, with no Korean, avoids this problem entirely)\n"
        )
        return 2

    # Encoding held, but the bytes may still have been mangled in place: a
    # decode-with-replacement upstream leaves valid UTF-8 full of U+FFFD.
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return 0
    n = raw.count(MOJIBAKE)
    if n:
        sys.stderr.write(
            f"The encoding was damaged: {path}\n"
            f"  {n} replacement characters (U+FFFD) appeared. The Korean in this file is destroyed.\n\n"
            "Undo it.\n"
            f"  {restore_hint(path)}\n"
            f"Go through {scripts}/phped when you edit it again.\n"
        )
        return 2

    checked = lint_failure(path, scripts)
    if checked:
        kind, msg = checked
        if kind == "fails":
            emit(event, ["Syntax: this file does not run on the PHP version it "
                         f"is deployed to.\n{msg}"])
        else:
            emit(event, ["Syntax: this file was not checked - that is not the same "
                         f"as passing.\n{msg}"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
