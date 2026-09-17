#!/usr/bin/env python3
"""Injection budget check - no consumer exceeds 90% of MAX_INJECT_BYTES.

Growth rule 4 of the design document is this check. It measures bytes rather than lines because
the machine cuts by bytes, and it sits at 90% so it stops **before a file that grew is silently
truncated**. A truncation arriving in the same shape as a pass is the defect this OS has fixed
again and again.

It reads the frontmatter directly here. Importing the hook's parser would make this check fall
silent in the same round the hook breaks, and then two checks disappear at once.

It runs with no arguments and requires no company tree.
"""
import glob
import os
import re
import sys

BUDGET_FRACTION = 0.90
LINE_SMELL = {"context": 40, "agent": 60, "skill": 150}

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


def max_inject_bytes(root):
    """Read the budget the hook declares from the hook source. If unreadable, say so and stop."""
    p = os.path.join(root, ".claude", "hooks", "context-inject.py")
    if not os.path.isfile(p):
        return None, f"{p} is missing - the budget cannot be known"
    src = open(p, encoding="utf-8").read()
    m = re.search(r"^MAX_INJECT_BYTES\s*=\s*(.+)$", src, re.M)
    if not m:
        return None, "could not find MAX_INJECT_BYTES in context-inject.py"
    try:
        return int(eval(m.group(1), {"__builtins__": {}}, {})), None
    except Exception as exc:
        return None, f"could not parse the MAX_INJECT_BYTES value: {exc}"


def body_of(text):
    parts = text.split("---\n", 2)
    return parts[2] if len(parts) == 3 else text


def context_items(root):
    """A list of (name, agents, skills, rendered_bytes, body_lines)."""
    out = []
    d = os.path.join(root, ".claude", "context")
    for f in sorted(glob.glob(os.path.join(d, "*.md"))):
        s = open(f, encoding="utf-8").read()
        parts = s.split("---\n", 2)
        if len(parts) != 3:
            out.append((os.path.basename(f), [], [], 0, 0, "the frontmatter could not be read"))
            continue
        fm, body = parts[1], parts[2]

        def lst(key):
            m = re.search(rf"^  {key}: \[(.*?)\]$", fm, re.M)
            return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []

        def val(key):
            m = re.search(rf"^{key}: (.+)$", fm, re.M)
            return m.group(1).strip() if m else ""

        name = val("name")
        # Count in the same shape as the block the hook assembles.
        block = (
            f'\n<context name="{name}" kind="{val("kind")}" token="{val("token")}">\n'
            f"{body.strip()}\n</context>"
        )
        out.append(
            (name, lst("agents"), lst("skills"), len(block.encode("utf-8")),
             len(body.strip().splitlines()), None)
        )
    return out


def main():
    cap, err = max_inject_bytes(ROOT)
    fails, warns = [], []

    print("## injection budget")
    if err:
        # Not knowing the budget is not a pass.
        print(f"  FAIL  {err}")
        return 1

    items = context_items(ROOT)
    broken = [n for n, _, _, _, _, e in items if e]
    for n in broken:
        fails.append(f"{n}: the frontmatter could not be read")

    header = 112  # the first line of render()
    limit = int(cap * BUDGET_FRACTION)
    consumers = sorted({c for _, ags, sks, _, _, _ in items for c in ags + sks})
    for c in consumers:
        b = header + sum(
            sz for _, ags, sks, sz, _, e in items if not e and c in ags + sks
        )
        pct = 100.0 * b / cap
        mark = "pass"
        if b > cap:
            mark, _ = "FAIL", fails.append(f"{c}: injects {b}B > budget {cap}B - the file gets truncated")
        elif b > limit:
            mark, _ = "warn", warns.append(f"{c}: injects {b}B > {int(BUDGET_FRACTION*100)}% ({limit}B)")
        print(f"  {mark:4}  {c:32} {b:6}B  {pct:5.1f}%")

    print("\n## line counts (a smell, not a gate)")
    for n, _, _, _, lines, e in items:
        if e:
            continue
        over = " ← over" if lines > LINE_SMELL["context"] else ""
        print(f"        {n:32} {lines:4} lines{over}")
    for kind, pat, key in (
        ("agent", ".claude/agents/*.md", "agent"),
        ("skill", ".claude/skills/*/SKILL.md", "skill"),
    ):
        for f in sorted(glob.glob(os.path.join(ROOT, pat))):
            lines = len(body_of(open(f, encoding="utf-8").read()).strip().splitlines())
            if lines > LINE_SMELL[key]:
                label = os.path.basename(os.path.dirname(f)) if key == "skill" else os.path.basename(f)
                print(f"        {label:32} {lines:4} lines ← {kind} smell limit {LINE_SMELL[key]}")

    if warns:
        print("\nwarnings:")
        for w in warns:
            print(f"  - {w}")
    if fails:
        print("\nFAIL:")
        for f_ in fails:
            print(f"  - {f_}")
        print(f"\n{len(consumers) - len(fails)}/{len(consumers)} pass")
        return 1
    print(f"\nall {len(consumers)} consumers within {int(BUDGET_FRACTION*100)}% of the budget")
    print(f"{len(consumers)}/{len(consumers)} pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
