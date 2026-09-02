#!/usr/bin/env python3
"""PreToolUse(Bash) — keep company content out of this public repository.

CLAUDE.md forbids moving anything from the gitignored company checkouts into a
tracked file: source, internal domains, issue IDs, people's names. git already
refuses to stage ignored paths, but it cannot see the case that actually bites —
a skill or doc that *quotes* company internals.

So this hook fires on the git commands that would publish, and checks two things:

  1. Path guard   — nothing being staged lives under a gitignored company dir.
  2. Content guard — the staged diff matches none of the redaction patterns.

Both are advisory-by-config: patterns live in .claude/config/redaction.json,
which is itself gitignored because the pattern list names internal systems.
Missing config disables the content guard rather than blocking work.

Exit 2 blocks the tool call and shows stderr to Claude.
"""
import json
import os
import re
import subprocess
import sys

# Commands worth inspecting. `git add` matters as much as `git commit`: once the
# content is staged the next commit may come from anywhere.
GIT_PUBLISHING = re.compile(r"\bgit\s+(add|commit|push)\b")

# Directories the repository declares as company checkouts. Derived from .gitignore
# so the two never drift; anything anchored there must never be staged.
def ignored_company_dirs(root):
    path = os.path.join(root, ".gitignore")
    dirs = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("/") and line.endswith("/"):
                    dirs.append(line.strip("/"))
    except OSError:
        pass
    return dirs


def git(root, *args):
    try:
        out = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=15
        )
        return out.stdout
    except Exception:
        return ""


def load_redaction(root):
    path = os.path.join(root, ".claude", "config", "redaction.json")
    try:
        with open(path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    compiled = []
    for entry in cfg.get("patterns", []):
        # Default to case-insensitive: that is what the first patterns were written
        # against. A pattern whose whole signal is CamelCase must opt out, or `re.I`
        # turns `[A-Z]\w+Service` into a match for the word "microservice" — and a
        # guard that blocks ordinary English is a guard someone switches off.
        flags = 0 if entry.get("ignoreCase") is False else re.I
        try:
            compiled.append((entry.get("name", "?"), re.compile(entry["regex"], flags)))
        except (KeyError, re.error):
            continue
    return compiled, set(cfg.get("allowPaths", []))


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    command = (payload.get("tool_input") or {}).get("command", "")
    if not GIT_PUBLISHING.search(command):
        return 0

    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    problems = []

    # --- 1. path guard -------------------------------------------------------
    staged = [p for p in git(root, "diff", "--cached", "--name-only").splitlines() if p]
    company = ignored_company_dirs(root)
    for path in staged:
        for d in company:
            if path == d or path.startswith(d + "/"):
                problems.append(f"  staged company path: {path}  (under gitignored {d}/)")

    # --- 2. content guard ----------------------------------------------------
    redaction = load_redaction(root)
    if redaction is not None:
        patterns, allow = redaction
        # Read added lines only: removing a leaked string must never be blocked.
        diff = git(root, "diff", "--cached", "--unified=0")
        current_file = None
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[6:]
                continue
            if not line.startswith("+") or line.startswith("+++"):
                continue
            if current_file in allow:
                continue
            for name, rx in patterns:
                hit = rx.search(line)
                if hit:
                    problems.append(
                        f"  {current_file}: {name} -> {hit.group(0)!r}"
                    )
                    break

    if not problems:
        return 0

    seen, unique = set(), []
    for p in problems:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    sys.stderr.write(
        "이 저장소는 공개됩니다. 회사 내용이 추적 파일에 들어가려 합니다:\n\n"
        + "\n".join(unique[:20])
        + ("\n  ... (외 %d건)" % (len(unique) - 20) if len(unique) > 20 else "")
        + "\n\n조치: 값을 .claude/config/workspace.json(gitignored)으로 옮기고\n"
        "스킬·문서에는 일반 명칭만 남기세요. 커밋을 중단했습니다.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
