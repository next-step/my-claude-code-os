#!/usr/bin/env python3
"""
Skill usage logging hook (PostToolUse / matcher: Skill)

Claude Code invokes a skill through the `Skill` tool.
This script runs right after that tool call and appends one JSON line to
`.claude/skill-usage.jsonl` recording which skill was used in what context.

Key fields of the hook payload (JSON) arriving on stdin:
  session_id      : the session identifier
  transcript_path : this session's transcript (JSONL) path -> used to extract the "context"
  cwd             : the working directory when the hook ran
  tool_name       : "Skill"
  tool_input      : {"skill": "<name>", "args": "<args>"}

Principle: a hook must never interrupt the session.
      Whatever the exception, exit 0 quietly.
"""

import json
import os
import re
import sys
from datetime import datetime

MAX_PROMPT = 160   # maximum length of the context snippet
MAX_ARGS = 120
TAIL_BYTES = 512 * 1024  # read only the last 512KB of the transcript (for long sessions)


def clean(text: str) -> str:
    """Strip system-injected blocks and newlines and make it one line."""
    text = re.sub(r"<system-reminder>.*?</system-reminder>", " ", text, flags=re.S)
    text = re.sub(r"<local-command-stdout>.*?</local-command-stdout>", " ", text, flags=re.S)
    text = re.sub(r"<command-message>.*?</command-message>", " ", text, flags=re.S)
    text = re.sub(r"<command-args>(.*?)</command-args>", r" \1", text, flags=re.S)
    text = re.sub(r"</?command-name>", "", text)
    return " ".join(text.split())


def last_user_message(transcript_path: str) -> str:
    """Find the most recent message a person actually wrote, from the transcript.

    A tool result (tool_result) is also recorded as role=user, so it has to be filtered out.
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return ""
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - TAIL_BYTES))
            chunk = f.read().decode("utf-8", "replace")
    except OSError:
        return ""

    for line in reversed(chunk.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") != "user":
            continue
        content = (entry.get("message") or {}).get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            # A turn holding only a tool_result is not a person speaking
            texts = [b.get("text", "") for b in content
                     if isinstance(b, dict) and b.get("type") == "text"]
            if not texts:
                continue
            text = "\n".join(texts)
        else:
            continue
        text = clean(text)
        if text:
            return text
    return ""


def main() -> None:
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input") or {}

    skill = (tool_input.get("skill") or "").strip()
    if not skill:
        return  # with no skill name there is nothing to record

    args = clean(str(tool_input.get("args") or ""))[:MAX_ARGS]
    prompt = last_user_message(payload.get("transcript_path", ""))

    # Tell apart the user calling /skillname directly from the model choosing it.
    short = skill.split(":")[-1]
    trigger = "user" if re.search(r"(^|\s)/(%s|%s)\b" % (re.escape(skill), re.escape(short)),
                                  prompt) else "auto"

    record = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "skill": skill,
        "trigger": trigger,
        "args": args,
        "context": prompt[:MAX_PROMPT],
        "session": payload.get("session_id", ""),
        "cwd": payload.get("cwd", ""),
    }

    project = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    log_dir = os.path.join(project, ".claude")
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, "skill-usage.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # always exit quietly so a hook failure never blocks the session
    sys.exit(0)
