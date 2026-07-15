#!/usr/bin/env python3
"""
UserPromptSubmit 훅 — 프롬프트를 JSONL에 기록하고 prompt-ID를 공유 파일에 저장.

log-work.py가 이 ID(pid)를 읽어 작업 항목과 프롬프트를 매핑한다.
출력: .claude/logs/prompts/YYYY-MM-DD.jsonl
공유: .claude/logs/.current_pid
"""
import json, os, sys
from datetime import datetime

# 스크립트 위치 기준 절대경로 — CWD에 무관하게 항상 같은 위치에 로그를 쓴다
HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))   # .claude/hooks/
CLAUDE_DIR = os.path.dirname(HOOKS_DIR)                  # .claude/
LOGS_DIR = os.path.join(CLAUDE_DIR, "logs")              # .claude/logs/

try:
    p = json.load(sys.stdin)
except Exception:
    sys.exit(0)

import re

text = p.get("prompt", "").strip()
if not text or text.startswith("/"):
    sys.exit(0)

# 시스템 태그로 시작하는 노이즈 프롬프트 스킵
if re.match(r"^<(task-notification|command-name|local-command|system-reminder)", text):
    sys.exit(0)

now = datetime.now()
pid = now.strftime("%H%M%S")  # 당일 고유 ID (예: "163045")

# pid를 공유 파일에 저장 → log-work.py가 읽음
pid_file = os.path.join(LOGS_DIR, ".current_pid")
os.makedirs(os.path.dirname(pid_file), exist_ok=True)
with open(pid_file, "w") as f:
    f.write(pid)

# 프롬프트 로그 기록
log_path = os.path.join(LOGS_DIR, "prompts", f"{now.strftime('%Y-%m-%d')}.jsonl")
os.makedirs(os.path.dirname(log_path), exist_ok=True)
entry = {"id": pid, "t": now.strftime("%H:%M"), "p": text[:200]}
with open(log_path, "a", encoding="utf-8") as f:
    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
