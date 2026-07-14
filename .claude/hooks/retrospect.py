#!/usr/bin/env python3
"""
Stop 훅 — 어제까지의 미회고 세션 로그를 분석해 lessons.md에 누적.
하루 첫 Stop 이벤트에서만 실행되며, 마지막 회고 날짜를 파일로 추적한다.
"""
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

HOOKS_DIR = Path(__file__).parent
CLAUDE_DIR = HOOKS_DIR.parent
LOGS_DIR = CLAUDE_DIR / "logs"
SESSIONS_DIR = LOGS_DIR / "sessions"
PROMPTS_DIR = LOGS_DIR / "prompts"
MARKER_FILE = LOGS_DIR / ".last-retrospected-through"
LESSONS_FILE = CLAUDE_DIR / "lessons.md"


def get_last_retrospected() -> date:
    if MARKER_FILE.exists():
        try:
            return date.fromisoformat(MARKER_FILE.read_text().strip())
        except Exception:
            pass
    # 마커 없으면 30일 전부터 시작
    return date.today() - timedelta(days=30)


def analyze(target: date) -> dict:
    ops: Counter = Counter()
    files_modified: set = set()
    agents: list = []

    session_file = SESSIONS_DIR / f"{target}.jsonl"
    if session_file.exists():
        for line in session_file.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                ops[e.get("op", "?")] += 1
                if e["op"] in ("write", "edit") and e.get("path"):
                    files_modified.add(Path(e["path"]).name)
                if e["op"] == "agent" and e.get("desc"):
                    agents.append(e["desc"][:60])
            except Exception:
                pass

    prompts: list = []
    prompt_file = PROMPTS_DIR / f"{target}.jsonl"
    if prompt_file.exists():
        for line in prompt_file.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                if e.get("p"):
                    prompts.append(e["p"][:100])
            except Exception:
                pass

    return {
        "total": sum(ops.values()),
        "ops": dict(ops),
        "files": sorted(files_modified),
        "agents": agents[:3],
        "prompts": prompts[:4],
    }


def format_entry(target: date, s: dict) -> str:
    lines = [f"\n## {target} 회고\n"]

    if s["total"] == 0:
        lines.append("*(로그 없음 — 작업 없음)*\n---")
        return "\n".join(lines)

    ops_str = ", ".join(f"{k}: {v}" for k, v in sorted(s["ops"].items()))
    lines.append(f"**도구 호출** {s['total']}건 ({ops_str})")

    if s["files"]:
        lines.append(f"**수정 파일** {', '.join(s['files'])}")

    if s["agents"]:
        lines.append(f"**에이전트** {'; '.join(s['agents'])}")

    if s["prompts"]:
        lines.append("**작업 내용**")
        for p in s["prompts"]:
            lines.append(f"- {p}")

    lines.append("\n---")
    return "\n".join(lines)


# ── 메인 ──────────────────────────────────────────────────────────────────────

yesterday = date.today() - timedelta(days=1)
last = get_last_retrospected()

if last >= yesterday:
    sys.exit(0)

pending = []
cursor = last + timedelta(days=1)
while cursor <= yesterday:
    pending.append(cursor)
    cursor += timedelta(days=1)

if not pending:
    sys.exit(0)

if not LESSONS_FILE.exists():
    LESSONS_FILE.write_text(
        "# Lessons Learned\n\n> 매 세션 첫 Stop 훅에서 어제 회고가 자동 누적됩니다.\n",
        encoding="utf-8",
    )

for d in pending:
    # 세션/프롬프트 파일이 없는 날은 기록하지 않음
    if not (SESSIONS_DIR / f"{d}.jsonl").exists() and not (PROMPTS_DIR / f"{d}.jsonl").exists():
        continue
    summary = analyze(d)
    entry = format_entry(d, summary)
    with LESSONS_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")

MARKER_FILE.write_text(str(yesterday), encoding="utf-8")
