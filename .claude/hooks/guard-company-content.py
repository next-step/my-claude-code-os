#!/usr/bin/env python3
"""PreToolUse(Bash) — keep company content out of this public repository.

CLAUDE.md forbids moving anything from the gitignored company checkouts into a
tracked file: source, internal domains, issue IDs, people's names. git already
refuses to stage ignored paths, but it cannot see the case that actually bites —
a skill or doc that *quotes* company internals.

So this hook fires on the git commands that would publish, and checks two things:

  1. Path guard   — nothing being published lives under a gitignored company dir.
  2. Content guard — the published diff matches none of the redaction patterns.

**What gets checked differs per command.** With three triggers but only the index read, the two
commands whose index is empty pass without a single line being checked - and that pass arrives in
the same shape as a clean one.

  git add        the index                  (this hook runs **before** the tool, so what is about
                                            to be added is not there yet - that is caught by the
                                            `commit` that follows)
  git commit     the index
  git commit -a  the index plus tracked changes in the working tree  (it stages inside the commit)
  git push       the changes in commits not yet on the remote        (the index is already empty)

`-C` is read. This OS's rule writes every path as `git -C <absolute path>`, so ignoring it makes
the hook check a repository the command never touches and present that result as this repository's
verdict. When the target is not this repository it does not judge and says so, and when the target
**cannot be determined it blocks** - an undeterminable target might be this repository.

The patterns live in `.claude/config/redaction.json`, and that list itself holds internal system
names, so it is gitignored. **Missing, broken or zero patterns blocks it.** It used to skip the
content check quietly in that case, and since a new checkout does not have that file, "looked at
no pattern at all" was indistinguishable from "matched no pattern". The path check always runs regardless of config.

Exit 2 blocks the tool call and shows stderr to Claude.
"""
import json
import os
import re
import shlex
import subprocess
import sys

# Separators in a compound command. `&&` and `||` are read first, then the single characters.
SEP = re.compile(r"&&|\|\||[;\n|&]")

# Options before a `git` subcommand that consume the next token as a value.
GIT_PRE_VALUE = ("-C", "-c", "--exec-path", "--namespace", "--super-prefix",
                 "--work-tree", "--git-dir", "--config-env")

# Options in `git commit` that consume the next token as a value. Reading a value as a flag makes
# `git commit -m "-a"` switch on the working-tree check too.
COMMIT_VALUE = {"-m", "--message", "-F", "--file", "-t", "--template",
                "-c", "--reedit-message", "-C", "--reuse-message",
                "--author", "--date", "--fixup", "--squash", "--cleanup",
                "--gpg-sign", "-S", "--pathspec-from-file", "--trailer",
                "-u", "--untracked-files"}
SHORT_CLUSTER = re.compile(r"^-[A-Za-z]+$")

PUBLISHING = ("add", "commit", "push")

# Directories the repository declares as company checkouts. Derived from .gitignore
# so the two never drift; anything anchored there must never be staged.
#
# .gitignore writes a directory three ways, and reading only one of them is a
# guard that reports "clean" on the paths it never looked at:
#
#   /cs-system/          leading and trailing slash - anchored at the root
#   handoff/             trailing slash only        - matches at any depth
#   /docs/lecture-notes  leading slash only         - anchored, no trailing slash
#
# The first was the only shape this function read, so the handoff notes and the
# lecture material - both of which carry company content - passed the path guard
# silently. Returns [(path, anchored), ...].
def ignored_company_dirs(root):
    path = os.path.join(root, ".gitignore")
    dirs = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("!"):
                    continue
                if any(c in line for c in "*?["):
                    continue          # a glob is not a path prefix
                if not (line.startswith("/") or line.endswith("/")):
                    continue          # names one file, not a tree
                dirs.append((line.strip("/"), line.startswith("/")))
    except OSError:
        pass
    return dirs


def under(path, d, anchored):
    """Is `path` inside the ignored entry `d`?

    An anchored entry (`/cs-system/`) only matches from the repository root; an
    unanchored one (`handoff/`) matches at any depth, which is what gitignore
    itself means by the two shapes.
    """
    if anchored:
        return path == d or path.startswith(d + "/")
    return ("/" + path + "/").find("/" + d + "/") >= 0


def run_git(repo, *args):
    """`(exit code, stdout, stderr)`.

    **It never turns a failure into empty output.** The old implementation returned `""` for both
    an exception and a non-zero exit, and then "there is no change to check" and "could not check"
    became the same value. The latter reading as the former is exactly the failure shape this hook prevents.
    """
    try:
        p = subprocess.run(["git", *args], cwd=repo, capture_output=True,
                           text=True, timeout=10)
    except Exception as exc:
        return 127, "", repr(exc)
    return p.returncode, p.stdout, p.stderr


def toplevel(d):
    """`(repository root, failure reason)`. Exactly one of the two has a value."""
    if not d or not os.path.isdir(d):
        return None, f"the directory `{d}` does not exist"
    code, out, err = run_git(d, "rev-parse", "--show-toplevel")
    if code != 0 or not out.strip():
        return None, (err or out).strip().splitlines()[0] if (err or out).strip() \
            else f"`{d}` is not a git repository"
    return os.path.realpath(out.strip()), None


def commit_stages_worktree(args):
    """Does `git commit` stage inside the commit - `-a`, `--all`, a bundle such as `-am`.

    The value of a value-taking option is skipped. A bundle (`-am`) is read from the left and stops
    at the first character that consumes a value - the `a` in `-ma` is a message, not a flag.
    """
    i = 0
    while i < len(args):
        t = args[i]
        if t == "--":
            break
        if t in ("-a", "--all"):
            return True
        if t in COMMIT_VALUE:
            i += 2
            continue
        if t.startswith("--"):
            i += 1
            continue
        if SHORT_CLUSTER.match(t):
            for ch in t[1:]:
                if ch == "a":
                    return True
                if "-" + ch in COMMIT_VALUE:
                    break
            i += 2 if "-" + t[-1] in COMMIT_VALUE else 1
            continue
        i += 1
    return False


def git_parts(command):
    """Per `git add|commit|push` in a compound command, `(subcommand, -C path, whether -a)`.

    Fragments joined by `&&`, `;`, a newline or a pipe are each read separately. Reading the whole
    command with one regex overwrites the commit in `echo x && git commit -am y` with the first fragment's verdict.

    `-C` is read because this OS's rule writes every path as `git -C <absolute path>`. Ignoring it
    makes the hook check a repository the command never touches and report that result as "clean".
    """
    out = []
    for raw in SEP.split(command or ""):
        if "git" not in raw:
            continue
        try:
            toks = shlex.split(raw, posix=True)
        except ValueError:
            toks = raw.split()
        i = 0
        while i < len(toks) and os.path.basename(toks[i]) != "git":
            i += 1                      # `env A=1 git ...`, `/usr/bin/git ...`
        if i >= len(toks):
            continue
        i += 1
        cdir = None
        while i < len(toks) and toks[i].startswith("-"):
            t = toks[i]
            if t in GIT_PRE_VALUE:
                if t == "-C" and i + 1 < len(toks):
                    cdir = toks[i + 1]
                i += 2
                continue
            i += 1
        if i >= len(toks):
            continue
        sub = toks[i]
        if sub not in PUBLISHING:
            continue
        out.append((sub, cdir,
                    sub == "commit" and commit_stages_worktree(toks[i + 1:])))
    return out


def push_base(repo):
    """The baseline for what a push newly publishes. `(baseline, why it could not be decided)`.

    It looks at the upstream, then `origin/HEAD`, then `origin/main`. With none of the three
    it **does not let it through.** Without a baseline there is no way to know what is going out,
    and quietly emitting 0 then is indistinguishable from "checked and clean".
    """
    code, out, _ = run_git(repo, "rev-parse", "--abbrev-ref",
                           "--symbolic-full-name", "@{upstream}")
    if code == 0 and out.strip():
        return out.strip(), None
    code, out, _ = run_git(repo, "symbolic-ref", "refs/remotes/origin/HEAD")
    ref = out.strip()
    if code == 0 and ref.startswith("refs/remotes/"):
        return ref[len("refs/remotes/"):], None
    code, _, _ = run_git(repo, "rev-parse", "--verify", "--quiet", "origin/main")
    if code == 0:
        return "origin/main", None
    return None, (
        "could not decide the baseline for what this push newly publishes.\n"
        "    no upstream (@{upstream}) - no origin/HEAD - no origin/main\n"
        "    action: attach an upstream with `git branch --set-upstream-to=origin/<branch>`, or\n"
        "          set the remote default branch with `git remote set-head origin -a`, then push again.")


def scopes_for(repo, sub, stages_worktree):
    """`([(name, name-only args, unified=0 args)], reason to block)`."""
    index = ("the index", ["diff", "--cached", "--name-only"],
             ["diff", "--cached", "--unified=0"])
    if sub == "add":
        return [index], []
    if sub == "commit":
        scopes = [index]
        if stages_worktree:
            # `-a` stages inside the commit. The index at the moment the hook runs can be empty,
            # and that empty index used to read as "there is nothing to check".
            scopes.append(("the working tree", ["diff", "--name-only"],
                           ["diff", "--unified=0"]))
        return scopes, []
    base, why = push_base(repo)
    if not base:
        return [], [why]
    rng = f"{base}..HEAD"
    return [(rng, ["diff", "--name-only", rng],
             ["diff", "--unified=0", rng])], []


def load_redaction(root):
    """`(pattern list, allowPaths, reason)`. When there is a problem the patterns are None.

    **Missing, broken or zero patterns blocks it.** This file is gitignored so a new checkout does not
    have it, and that state used to be indistinguishable from a pass. A single pattern failing to
    compile is the same - dropped quietly, only leaks of that shape fall out of the check, and the fact is recorded nowhere.
    """
    path = os.path.join(root, ".claude", "config", "redaction.json")
    example = os.path.join(root, ".claude", "config", "redaction.example.json")
    hint = (f"action: copy it with `cp {example} {path}` and fill in the values.\n"
            "    redaction.json is gitignored, so a new checkout does not have it.")
    if not os.path.isfile(path):
        return None, set(), f"{path} is missing, so not one line of the content check ran.\n    {hint}"
    try:
        with open(path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError) as exc:
        return None, set(), f"{path} could not be read: {exc}\n    {hint}"
    if not isinstance(cfg, dict):
        return None, set(), f"the top level of {path} is not an object.\n    {hint}"
    entries = cfg.get("patterns")
    if not isinstance(entries, list) or not entries:
        return None, set(), (f"{path} has 0 usable patterns - "
                             "the content check would see nothing.\n    " + hint)
    compiled, broken = [], []
    for n, entry in enumerate(entries, 1):
        name = (entry.get("name") if isinstance(entry, dict) else None) or f"#{n}"
        if not isinstance(entry, dict) or not entry.get("regex"):
            broken.append(f"{name}: no `regex`")
            continue
        # Default to case-insensitive: that is what the first patterns were written
        # against. A pattern whose whole signal is CamelCase must opt out, or `re.I`
        # turns `[A-Z]\w+Service` into a match for the word "microservice" — and a
        # guard that blocks ordinary English is a guard someone switches off.
        flags = 0 if entry.get("ignoreCase") is False else re.I
        try:
            compiled.append((name, re.compile(entry["regex"], flags)))
        except re.error as exc:
            broken.append(f"{name}: the regex could not be compiled - {exc}")
    if broken:
        return None, set(), (f"{len(broken)} patterns in {path} are unusable:\n"
                             + "\n".join("      " + b for b in broken)
                             + "\n    A silently dropped pattern removes only leaks of that shape from the check.")
    return compiled, set(cfg.get("allowPaths") or []), None


def added_lines(diff):
    """`(file, added lines)`. Deleted lines are not examined - removing a leak is never blocked."""
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        yield current, line


def emit_note(notes):
    """Leave the fact that it did not judge where Claude can see it.

    The stderr of an exit 0 does not reach Claude. So writing "this repository was not checked" to
    stderr alone makes it a silence indistinguishable from having checked.
    """
    if not notes:
        return
    text = "public-repository guard: " + " / ".join(notes)
    try:
        json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                          "additionalContext": text}},
                  sys.stdout, ensure_ascii=False)
    except Exception:
        pass
    sys.stderr.write(text + "\n")


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    command = (payload.get("tool_input") or {}).get("command", "")
    parts = git_parts(command)
    if not parts:
        return 0

    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    project_top, project_why = toplevel(root)
    company = ignored_company_dirs(root)
    problems, blockers, notes, diffs = [], [], [], []

    for sub, cdir, stages_worktree in parts:
        repo = os.path.expanduser(cdir) if cdir else root
        if not os.path.isabs(repo):
            repo = os.path.join(root, repo)
        top, why = toplevel(repo)
        if top is None:
            # **Block when it is unclear which repository is touched.** That repository might be
            # this public one, and letting it through then sends something unchecked out in the
            # same shape as a pass. A `-C` value that is a shell variable arrives at the hook
            # unexpanded, so this is the only point that notices it.
            if cdir:
                blockers.append(
                    f"could not determine the repository `-C {cdir}` of git {sub} points at"
                    f": {why}\n"
                    "    A shell variable arrives at the hook unexpanded - "
                    "write the absolute path as a literal.")
            else:
                blockers.append(f"`{root}` could not be checked: {project_why or why}")
            continue
        if project_top and top != project_top:
            notes.append(f"git {sub} targets another repository (`{top}`), so this public "
                         "repository's guard did not judge it")
            continue
        if not project_top:
            notes.append(f"the target `{top}` of git {sub} is not this project (`{root}`), "
                         "so it was not judged")
            continue

        scopes, cannot = scopes_for(top, sub, stages_worktree)
        blockers += cannot
        for label, name_args, diff_args in scopes:
            code, out, err = run_git(top, *name_args)
            if code != 0:
                blockers.append(f"could not obtain the {label} list for git {sub}: "
                                f"{(err or out).strip()[:200]}")
                continue
            for path in [p for p in out.splitlines() if p]:
                for d, anchored in company:
                    if under(path, d, anchored):
                        problems.append(f"  [{label}] company path: {path}  "
                                        f"(under gitignored {d}/)")
            code, diff, err = run_git(top, *diff_args)
            if code != 0:
                blockers.append(f"could not obtain the {label} changes for git {sub}: "
                                f"{(err or diff).strip()[:200]}")
                continue
            diffs.append((label, diff))

    # The content check. Missing or broken config blocks - the path check already ran above.
    if diffs:
        patterns, allow, cfg_problem = load_redaction(root)
        if cfg_problem:
            blockers.append(cfg_problem)
        else:
            for label, diff in diffs:
                for current_file, line in added_lines(diff):
                    if current_file in allow:
                        continue
                    for name, rx in patterns:
                        hit = rx.search(line)
                        if hit:
                            problems.append(
                                f"  [{label}] {current_file}: {name} "
                                f"-> {hit.group(0)!r}")
                            break

    if not problems and not blockers:
        emit_note(notes)
        return 0

    seen, unique = set(), []
    for p in problems:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    if unique:
        sys.stderr.write(
            "This repository is public. Company content is about to enter a tracked file:\n\n"
            + "\n".join(unique[:20])
            + ("\n  ... (and %d more)" % (len(unique) - 20) if len(unique) > 20 else "")
            + "\n\naction: move the values into .claude/config/workspace.json (gitignored) and\n"
            "leave only generic names in the skills and documents. The command was stopped.\n")
    if blockers:
        sys.stderr.write(
            ("\n" if unique else "")
            + "the public-repository guard did not finish checking - that is not a pass:\n\n"
            + "\n".join("  " + b for b in dict.fromkeys(blockers))
            + "\n\nThe command was stopped so that something unchecked is not sent out as a pass.\n")
    for n in notes:
        sys.stderr.write("  note: " + n + "\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
