#!/usr/bin/env python3
"""
Stop 훅 — 어제까지의 미회고 세션 로그를 분석해 lessons.md에 누적.
건강도 지표(에이전트 활용률 + 작업 집중도)를 계산해 추세를 추적한다.
"""
import json
import re
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
METRICS_FILE = LOGS_DIR / "retrospect-metrics.jsonl"


def get_last_retrospected() -> date:
    if MARKER_FILE.exists():
        try:
            return date.fromisoformat(MARKER_FILE.read_text().strip())
        except Exception:
            pass
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

    total = sum(ops.values())
    agent_rate = ops.get("agent", 0) / total if total > 0 else 0.0
    work_rate = (ops.get("edit", 0) + ops.get("write", 0)) / total if total > 0 else 0.0
    health = (agent_rate + work_rate) / 2
    grade = "A" if health > 0.25 else "B" if health >= 0.15 else "C"

    files = sorted(files_modified)
    return {
        "total": total,
        "ops": dict(ops),
        "files": files[:10],
        "files_total": len(files),
        "agents": agents[:3],
        "prompts": prompts[:4],
        "agent_rate": agent_rate,
        "work_rate": work_rate,
        "health": health,
        "grade": grade,
        "metrics_valid": total >= 10,  # 10건 미만은 지표 신뢰 불가
    }


def format_entry(target: date, s: dict) -> str:
    lines = [f"\n## {target} 회고\n"]

    if s["total"] == 0:
        lines.append("*(로그 없음 — 작업 없음)*\n---")
        return "\n".join(lines)

    ops_str = ", ".join(f"{k}: {v}" for k, v in sorted(s["ops"].items()))
    lines.append(f"**도구 호출** {s['total']}건 ({ops_str})")

    if s["files"]:
        file_str = ", ".join(s["files"])
        suffix = f" 외 {s['files_total'] - 10}개" if s["files_total"] > 10 else ""
        lines.append(f"**수정 파일** {file_str}{suffix}")

    if s["agents"]:
        lines.append(f"**에이전트** {'; '.join(s['agents'])}")

    if s["prompts"]:
        lines.append("**작업 내용**")
        for p in s["prompts"]:
            lines.append(f"- {p}")

    if s["metrics_valid"]:
        lines.append(
            f"**건강도** `{s['health']:.2f}` Grade **{s['grade']}**"
            f"  (에이전트 {s['agent_rate']:.1%} · 집중도 {s['work_rate']:.1%})"
        )
    else:
        lines.append(f"**건강도** 측정 불가 (호출 {s['total']}건 — 기준 미달)")
    lines.append("\n---")
    return "\n".join(lines)


def append_metrics(target: date, s: dict) -> None:
    entry = {
        "date": str(target),
        "total": s["total"],
        "agent": s["ops"].get("agent", 0),
        "edit": s["ops"].get("edit", 0),
        "write": s["ops"].get("write", 0),
        "bash": s["ops"].get("bash", 0),
        "agent_rate": round(s["agent_rate"], 4),
        "work_rate": round(s["work_rate"], 4),
        "health": round(s["health"], 4),
        "grade": s["grade"],
    }
    with METRICS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def update_trend_summary() -> None:
    if not METRICS_FILE.exists():
        return

    metrics = []
    for line in METRICS_FILE.read_text(encoding="utf-8").splitlines():
        try:
            metrics.append(json.loads(line))
        except Exception:
            pass

    if not metrics:
        return

    rows = []
    for m in metrics[-10:]:
        rows.append(
            f"| {m['date']} | {m['total']} | {m['agent_rate']:.1%} | "
            f"{m['work_rate']:.1%} | {m['health']:.2f} | {m['grade']} |"
        )

    recent = [m["health"] for m in metrics[-3:]]
    if len(recent) >= 2:
        trend = "↑ 상승" if recent[-1] > recent[-2] else "↓ 하락" if recent[-1] < recent[-2] else "→ 유지"
    else:
        trend = "데이터 부족"
    avg = sum(recent) / len(recent) if recent else 0.0

    summary = (
        "<!-- METRICS_START -->\n"
        "## 📊 추세 요약\n\n"
        "> **건강도** = (에이전트 활용률 + 작업 집중도) / 2\n"
        "> Grade: **A** > 0.25 · **B** 0.15 ~ 0.25 · **C** < 0.15\n\n"
        "| 날짜 | 총 호출 | 에이전트율 | 집중도 | 건강도 | Grade |\n"
        "|------|---------|-----------|--------|--------|-------|\n"
        + "\n".join(rows)
        + f"\n\n최근 추세: **{trend}** (최근 {len(recent)}회 평균 `{avg:.2f}`)\n"
        "<!-- METRICS_END -->"
    )

    content = LESSONS_FILE.read_text(encoding="utf-8")
    if "<!-- METRICS_START -->" in content:
        content = re.sub(
            r"<!-- METRICS_START -->.*?<!-- METRICS_END -->",
            summary,
            content,
            flags=re.DOTALL,
        )
    else:
        content = content.rstrip() + "\n\n" + summary + "\n"

    LESSONS_FILE.write_text(content, encoding="utf-8")


def seed_historical_metrics() -> None:
    """metrics.jsonl이 없을 때 기존 세션 로그로 소급 계산한다."""
    if METRICS_FILE.exists():
        return

    last = get_last_retrospected()
    seen: set = set()

    for f in sorted(SESSIONS_DIR.glob("*.jsonl")):
        try:
            d = date.fromisoformat(f.stem)
        except Exception:
            continue
        if d > last or d in seen:
            continue
        seen.add(d)
        s = analyze(d)
        if s["total"] > 0 and s["metrics_valid"]:
            append_metrics(d, s)

    for f in sorted(PROMPTS_DIR.glob("*.jsonl")):
        try:
            d = date.fromisoformat(f.stem)
        except Exception:
            continue
        if d > last or d in seen:
            continue
        seen.add(d)
        s = analyze(d)
        if s["total"] > 0 and s["metrics_valid"]:
            append_metrics(d, s)


# ── 메인 ──────────────────────────────────────────────────────────────────────

seed_historical_metrics()

yesterday = date.today() - timedelta(days=1)
last = get_last_retrospected()

if last >= yesterday:
    update_trend_summary()
    sys.exit(0)

pending = []
cursor = last + timedelta(days=1)
while cursor <= yesterday:
    pending.append(cursor)
    cursor += timedelta(days=1)

if not pending:
    update_trend_summary()
    sys.exit(0)

if not LESSONS_FILE.exists():
    LESSONS_FILE.write_text(
        "# Lessons Learned\n\n> 매 세션 첫 Stop 훅에서 어제 회고가 자동 누적됩니다.\n",
        encoding="utf-8",
    )

for d in pending:
    if not (SESSIONS_DIR / f"{d}.jsonl").exists() and not (PROMPTS_DIR / f"{d}.jsonl").exists():
        continue
    s = analyze(d)
    entry = format_entry(d, s)
    with LESSONS_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")
    if s["total"] > 0 and s["metrics_valid"]:
        append_metrics(d, s)

MARKER_FILE.write_text(str(yesterday), encoding="utf-8")
update_trend_summary()
