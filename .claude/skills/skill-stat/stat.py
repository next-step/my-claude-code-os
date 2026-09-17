#!/usr/bin/env python3
"""
Read .claude/skill-usage.jsonl and print skill usage statistics.

Usage:
  python3 .claude/skills/skill-stat/stat.py                # everything
  python3 .claude/skills/skill-stat/stat.py --since 7d     # the last 7 days
  python3 .claude/skills/skill-stat/stat.py --since 2026-08-01
  python3 .claude/skills/skill-stat/stat.py --skill git-commit   # one skill only
  python3 .claude/skills/skill-stat/stat.py --recent 10    # recent calls, with their context
  python3 .claude/skills/skill-stat/stat.py --json         # machine-readable output
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta

DEFAULT_LOG = os.path.join(
    os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()), ".claude", "skill-usage.jsonl"
)


def parse_since(value):
    """Turn '7d' / '12h' / '2026-08-01' into an aware datetime."""
    if not value:
        return None
    now = datetime.now().astimezone()
    m = re.fullmatch(r"(\d+)([dhw])", value.strip().lower())
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {"d": timedelta(days=n), "h": timedelta(hours=n), "w": timedelta(weeks=n)}[unit]
        return now - delta
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        sys.exit("bad --since format: %r (e.g. 7d, 12h, 2w, 2026-08-01)" % value)
    return dt if dt.tzinfo else dt.replace(tzinfo=now.tzinfo)


def load(path, since=None, skill=None, session=None):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue  # skip a broken line (a practical defence for an append-only log)
            try:
                r["_ts"] = datetime.fromisoformat(r["ts"])
            except (KeyError, ValueError):
                continue
            if since and r["_ts"] < since:
                continue
            if skill and skill not in r.get("skill", ""):
                continue
            if session and r.get("session", "") != session:
                continue
            rows.append(r)
    rows.sort(key=lambda r: r["_ts"])
    return rows


def width_of(text):
    """Terminal display width. Korean and emoji take two columns, so len() misaligns the table."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def pad(text, w, align="<"):
    """Cut to the display width and pad."""
    while width_of(text) > w:
        text = text[:-1]
    space = " " * (w - width_of(text))
    return space + text if align == ">" else text + space


def bar(count, top, width=24):
    if top <= 0:
        return ""
    filled = max(1, round(count / top * width))
    return "█" * filled


def human(dt):
    return dt.strftime("%Y-%m-%d %H:%M")


def report(rows, recent):
    if not rows:
        print("no skill call has been recorded.")
        print("(the log fills only after a skill is called at least once in a new session, with the hook registered)")
        return

    counts = Counter(r["skill"] for r in rows)
    triggers = defaultdict(Counter)
    last_used = {}
    for r in rows:
        triggers[r["skill"]][r.get("trigger", "auto")] += 1
        last_used[r["skill"]] = r["_ts"]

    total = len(rows)
    span = "%s ~ %s" % (human(rows[0]["_ts"]), human(rows[-1]["_ts"]))
    sessions = len({r.get("session", "") for r in rows})

    print("Skill usage")
    print("─" * 64)
    print("period    : %s" % span)
    print("total     : %d calls   |   distinct skills: %d   |   sessions: %d"
          % (total, len(counts), sessions))
    print()

    top = counts.most_common(1)[0][1]
    name_w = min(max(max(width_of(s) for s in counts), 12), 34)
    row = "%s %s %s  %s %s"
    print(row % (pad("skill", name_w), pad("calls", 5, ">"), pad("share", 5, ">"),
                 pad("", 24), "last used"))
    print("─" * 64)
    for skill, n in counts.most_common():
        print(row % (pad(skill, name_w), pad(str(n), 5, ">"),
                     pad("%.0f%%" % (n / total * 100), 5, ">"),
                     pad(bar(n, top), 24), human(last_used[skill])))
    print()

    # Called directly (/skillname) versus chosen by the model - this is the indicator of
    # whether the skill's description is doing its job.
    user_n = sum(t["user"] for t in triggers.values())
    print("call path : %d by the user directly / %d chosen by the model" % (user_n, total - user_n))

    if recent:
        print()
        print("%d recent calls" % min(recent, total))
        print("─" * 64)
        for r in rows[-recent:][::-1]:
            print("%s  %s (%s)" % (human(r["_ts"]), r["skill"], r.get("trigger", "auto")))
            ctx = r.get("context") or "(no context)"
            print("    ↳ %s" % ctx)


def main():
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--log", default=DEFAULT_LOG)
    p.add_argument("--since")
    p.add_argument("--skill")
    p.add_argument("--session")
    p.add_argument("--recent", type=int, default=5)
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    rows = load(a.log, parse_since(a.since), a.skill, a.session)

    if a.json:
        counts = Counter(r["skill"] for r in rows)
        print(json.dumps({
            "total": len(rows),
            "skills": [{"skill": s, "count": n} for s, n in counts.most_common()],
            "entries": [{k: v for k, v in r.items() if k != "_ts"} for r in rows],
        }, ensure_ascii=False, indent=2))
        return

    report(rows, a.recent)


if __name__ == "__main__":
    main()
