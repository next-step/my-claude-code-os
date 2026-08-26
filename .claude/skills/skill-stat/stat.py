#!/usr/bin/env python3
# 스킬 호출 로그를 읽어 통계로 요약한다.
#
# 표준 라이브러리만 쓴다 — 통계를 보려고 의존성을 설치하게 만들지 않는다.
# 이 스크립트는 "세는 일"만 한다. 해석과 제안은 SKILL.md가 맡는다.
#
# 입력 (우선순위 --source 로 선택)
#   hook       : $ROOT/.claude/skill-usage.jsonl  — PostToolUse(Skill) 훅이 남긴 원본 로그
#   transcript : ~/.claude/projects/<slug>/*.jsonl — 세션 기록에 남은 Skill 툴 호출 (훅 설치 이전 구간)
#   both       : 훅 로그의 첫 기록 시점을 경계로 그 이전은 transcript, 이후는 hook
#
# 출력: 사람이 읽는 표(기본) 또는 --json (기계용)

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

FULL = "█"
EMPTY = "░"


def dwidth(text):
    """터미널 표시 폭. 한글·CJK는 두 칸으로 센다."""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def pad(text, width):
    """표시 폭 기준 왼쪽 정렬."""
    return text + " " * max(0, width - dwidth(text))


# ---------------------------------------------------------------- 시간 유틸

def parse_ts(raw):
    """ISO8601 문자열을 로컬 타임존 datetime으로. 실패하면 None."""
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:                 # 타임존이 없으면 UTC로 본다 (훅이 date -u 로 찍는다)
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()                # 표시·집계는 로컬 시간 기준


def parse_since(spec):
    """--since 값을 로컬 datetime 하한으로. '7d' / '24h' / '2026-08-01' 형식."""
    if not spec:
        return None
    s = spec.strip().lower()
    now = datetime.now().astimezone()
    m = re.fullmatch(r"(\d+)\s*([dhw])", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        delta = {"h": timedelta(hours=n), "d": timedelta(days=n), "w": timedelta(weeks=n)}[unit]
        return now - delta
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        raise SystemExit(f"--since 형식을 알 수 없습니다: {spec!r} (예: 7d, 24h, 2026-08-01)")
    if d.tzinfo is None:
        d = d.replace(tzinfo=now.tzinfo)
    return d


# ---------------------------------------------------------------- 로그 읽기

def read_hook_log(path):
    """훅 로그(JSONL)를 읽는다. 반환: (records, 깨진 줄 수)."""
    records, broken = [], 0
    if not os.path.exists(path):
        return records, broken
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                broken += 1                # 훅이 쓰는 중이었을 수 있다. 세지만 버린다
                continue
            skill = d.get("skill")
            ts = parse_ts(d.get("ts"))
            if not skill or ts is None:
                broken += 1
                continue
            records.append({"skill": skill, "ts": ts, "session": d.get("session") or "", "src": "hook"})
    return records, broken


def project_slug_dir(root):
    """Claude Code가 이 프로젝트의 세션 기록을 두는 디렉터리를 찾는다."""
    base = os.path.expanduser("~/.claude/projects")
    if not os.path.isdir(base):
        return None
    want = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(root))
    exact = os.path.join(base, want)
    if os.path.isdir(exact):
        return exact
    tail = re.sub(r"[^A-Za-z0-9]", "-", os.path.basename(os.path.abspath(root)))
    hits = [p for p in glob.glob(os.path.join(base, "*")) if os.path.isdir(p) and p.endswith(tail)]
    return hits[0] if len(hits) == 1 else None


def read_transcripts(root):
    """세션 기록에서 Skill 툴 호출을 긁는다. 훅 설치 이전 구간을 메우는 용도."""
    records = []
    d = project_slug_dir(root)
    if not d:
        return records, None
    for path in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
        fallback_session = os.path.basename(path)[:-6]
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if '"Skill"' not in line:      # 값싼 사전 필터. 파일이 크다
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = entry.get("message") or {}
                content = msg.get("content")
                if not isinstance(content, list):
                    continue
                ts = parse_ts(entry.get("timestamp"))
                session = entry.get("sessionId") or fallback_session
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use" or block.get("name") != "Skill":
                        continue
                    skill = (block.get("input") or {}).get("skill")
                    if skill and ts is not None:
                        records.append({"skill": skill, "ts": ts, "session": session, "src": "transcript"})
    return records, d


def merge_sources(hook, transcript):
    """훅 로그 시작 시점을 경계로 합친다. 같은 호출을 두 번 세지 않기 위한 규칙."""
    if not hook:
        return transcript, None
    cutover = min(r["ts"] for r in hook)
    return [r for r in transcript if r["ts"] < cutover] + hook, cutover


# ---------------------------------------------------------------- 스킬 목록

def local_skill_dirs(root):
    """파일로 존재하는 스킬 이름 → 위치 라벨. 플러그인·내장 스킬은 여기 없다."""
    found = {}
    for label, pattern in (
        ("project", os.path.join(root, ".claude", "skills", "*", "SKILL.md")),
        ("user", os.path.expanduser("~/.claude/skills/*/SKILL.md")),
    ):
        for path in glob.glob(pattern):
            found.setdefault(os.path.basename(os.path.dirname(path)), label)
    return found


# ---------------------------------------------------------------- 집계

def bar(frac, width=20):
    filled = int(round(frac * width))
    if frac > 0:
        filled = max(1, filled)
    filled = min(width, filled)
    return FULL * filled + EMPTY * (width - filled)


def build_stats(records, skill_files, top, max_days):
    counts = Counter(r["skill"] for r in records)
    last = {}
    for r in records:
        if r["skill"] not in last or r["ts"] > last[r["skill"]]:
            last[r["skill"]] = r["ts"]
    total = sum(counts.values())

    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], -last[kv[0]].timestamp(), kv[0]))
    rows = [{
        "skill": name,
        "count": n,
        "share": n / total if total else 0.0,
        "last": last[name],
        "where": skill_files.get(name, "external"),   # external = 플러그인·내장·삭제됨
    } for name, n in ranked]

    per_day = Counter(r["ts"].date() for r in records)
    days = []
    if per_day:
        cur, end = min(per_day), max(per_day)
        while cur <= end:
            days.append((cur, per_day.get(cur, 0)))
            cur += timedelta(days=1)
    truncated_days = max(0, len(days) - max_days)
    days = days[-max_days:]

    sessions = Counter(r["session"] for r in records if r["session"])
    unused = sorted(n for n in skill_files if n not in counts)

    return {
        "total": total,
        "distinct": len(counts),
        "rows": rows,
        "top_rows": rows[:top],
        "days": days,
        "truncated_days": truncated_days,
        "sessions": sessions,
        "unused": unused,
        "first": min((r["ts"] for r in records), default=None),
        "last": max((r["ts"] for r in records), default=None),
    }


# ---------------------------------------------------------------- 출력

def fmt(dt):
    return dt.strftime("%m-%d %H:%M") if dt else "-"


def render(st, meta):
    out = []
    tz = datetime.now().astimezone().tzname() or "local"
    src = {"hook": "훅 로그", "transcript": "세션 기록", "both": "훅 로그 + 세션 기록"}[meta["source"]]

    if st["total"] == 0:
        out.append(f"기록된 스킬 호출이 없습니다. (출처: {src})")
        out.append(f"  훅 로그: {meta['log']} — {'있음' if os.path.exists(meta['log']) else '없음'}")
        if meta["since"]:
            out.append(f"  --since {meta['since_raw']} 조건을 지웠을 때도 없는지 확인하세요.")
        return "\n".join(out)

    span_days = (st["last"].date() - st["first"].date()).days + 1
    out.append(f"스킬 호출 통계 · 출처 {src} · 시간 {tz}")
    out.append(f"기록 구간 {st['first']:%Y-%m-%d %H:%M} ~ {st['last']:%Y-%m-%d %H:%M} ({span_days}일)")
    line = f"총 {st['total']}회 · 스킬 {st['distinct']}종"
    if st["sessions"]:
        line += f" · 세션 {len(st['sessions'])}개 (세션당 평균 {st['total'] / len(st['sessions']):.1f}회)"
    out.append(line)
    out.append("")

    width = max([dwidth(r["skill"]) for r in st["top_rows"]] + [8])
    # 행 배치: [스킬 width][공백][마커 1][공백][호출 4][공백2][막대 20][공백][비율 5][공백2][최근]
    out.append(pad("스킬", width + 3) + "호출" + "  " + pad("비중", 28) + "최근 호출")
    for r in st["top_rows"]:
        mark = "*" if r["where"] == "external" else " "
        out.append(
            f"{pad(r['skill'], width)} {mark} {r['count']:>4}  "
            f"{bar(r['share'])} {r['share'] * 100:>4.0f}%  {fmt(r['last'])}"
        )
    hidden = len(st["rows"]) - len(st["top_rows"])
    if hidden > 0:
        out.append(f"… 그 외 {hidden}종 (--top 으로 더 보기)")
    if any(r["where"] == "external" for r in st["top_rows"]):
        out.append("* 프로젝트/사용자 스킬 디렉터리에 파일이 없는 스킬 (플러그인·내장 또는 삭제됨)")

    if len(st["days"]) > 1:
        out.append("")
        out.append("일별")
        peak = max(n for _, n in st["days"]) or 1
        for day, n in st["days"]:
            out.append(f"{day:%m-%d}  {FULL * max(1, round(n / peak * 24)) if n else '':<24} {n}")
        if st["truncated_days"]:
            out.append(f"(앞쪽 {st['truncated_days']}일 생략 — --days 로 조정)")

    if st["unused"]:
        out.append("")
        out.append(f"이 구간에 한 번도 호출되지 않은 스킬 ({len(st['unused'])}종)")
        out.append("  " + ", ".join(st["unused"]))

    return "\n".join(out)


def to_json(st, meta):
    return {
        "source": meta["source"],
        "log": meta["log"],
        "since": meta["since_raw"],
        "broken_lines": meta["broken"],
        "cutover": meta["cutover"].isoformat() if meta["cutover"] else None,
        "first": st["first"].isoformat() if st["first"] else None,
        "last": st["last"].isoformat() if st["last"] else None,
        "total": st["total"],
        "distinct_skills": st["distinct"],
        "sessions": len(st["sessions"]),
        "skills": [{
            "skill": r["skill"],
            "count": r["count"],
            "share": round(r["share"], 4),
            "last": r["last"].isoformat(),
            "where": r["where"],
        } for r in st["rows"]],
        "daily": [{"date": d.isoformat(), "count": n} for d, n in st["days"]],
        "never_called": st["unused"],
    }


# ---------------------------------------------------------------- 진입점

def main():
    ap = argparse.ArgumentParser(description="스킬 호출 로그를 통계로 요약한다.")
    ap.add_argument("--root", default=os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd(),
                    help="프로젝트 루트 (기본: CLAUDE_PROJECT_DIR 또는 현재 디렉터리)")
    ap.add_argument("--log", help="훅 로그 경로 (기본: <root>/.claude/skill-usage.jsonl)")
    ap.add_argument("--source", choices=("hook", "transcript", "both"), default="hook")
    ap.add_argument("--since", help="이 시점 이후만 (7d, 24h, 2026-08-01)")
    ap.add_argument("--top", type=int, default=15, help="표에 보일 스킬 수 (기본 15)")
    ap.add_argument("--days", type=int, default=21, help="일별 그래프에 보일 최근 일수 (기본 21)")
    ap.add_argument("--include-self", action="store_true",
                    help="skill-stat 자신의 호출도 집계에 포함 (기본 제외)")
    ap.add_argument("--json", action="store_true", help="JSON으로 출력")
    args = ap.parse_args()

    root = os.path.abspath(os.path.expanduser(args.root))
    log = os.path.abspath(os.path.expanduser(args.log)) if args.log \
        else os.path.join(root, ".claude", "skill-usage.jsonl")

    hook, broken = ([], 0)
    transcript = []
    if args.source in ("hook", "both"):
        hook, broken = read_hook_log(log)
    if args.source in ("transcript", "both"):
        transcript, _ = read_transcripts(root)

    cutover = None
    if args.source == "hook":
        records = hook
    elif args.source == "transcript":
        records = transcript
    else:
        records, cutover = merge_sources(hook, transcript)

    if not args.include_self:
        records = [r for r in records if r["skill"] != "skill-stat"]

    since = parse_since(args.since)
    if since:
        records = [r for r in records if r["ts"] >= since]

    skill_files = local_skill_dirs(root)
    st = build_stats(records, skill_files, max(1, args.top), max(1, args.days))
    meta = {"source": args.source, "log": log, "since": since,
            "since_raw": args.since, "broken": broken, "cutover": cutover}

    if args.json:
        print(json.dumps(to_json(st, meta), ensure_ascii=False, indent=2))
    else:
        print(render(st, meta))
        notes = []
        if broken:
            notes.append(f"읽을 수 없는 로그 줄 {broken}개를 건너뛰었습니다.")
        if cutover:
            notes.append(f"{cutover:%Y-%m-%d %H:%M} 이전은 세션 기록, 이후는 훅 로그에서 셌습니다.")
        if not args.include_self and st["total"]:
            notes.append("skill-stat 자신의 호출은 제외했습니다 (--include-self 로 포함).")
        if notes:
            print("\n" + "\n".join("· " + n for n in notes))


if __name__ == "__main__":
    main()
