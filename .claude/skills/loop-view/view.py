#!/usr/bin/env python3
# 훅이 남긴 루프 로그를 읽어 「어떤 흐름이 흘러갔는지」를 보여준다. loop-view 스킬의 렌더러.
#
# 표준 라이브러리만 쓴다 — 로그 한 번 보려고 의존성을 설치하게 만들지 않는다.
#
# 이 스크립트는 「무엇이 기록되었는지」만 보여준다. 잘 돌았는지는 판정하지 않는다.
#   기록 재생 → 이 스크립트 (사람 없이 같은 입력에 같은 그림이 나온다)
#   해석      → SKILL.md 4절 해석 규칙 (사람이 한다)
# 둘을 섞으면 관측 로그가 채점기 행세를 한다. OS.md 2026-08-30 결정 로그 참조.
#
# 입력 : .claude/agent-handoff.jsonl · .claude/human-intervention.jsonl · projects/*/loops/
# 출력 : --list 루프 목록(최신순) / <루프> 그 루프의 흐름. --mermaid, --json 지원.
# 종료 : 0 정상 / 1 루프를 찾지 못함 / 2 로그를 읽을 수 없음

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

# 라벨 → 구간. feature-loop 의 단계 번호(①요구수집 ②PM ③Developer ④Reviewer ⑤배포)를 따른다.
# 순서가 규칙이다 — 「Developer 자문」은 ②에서 벌어지므로 「Developer」보다 먼저 걸러야 한다.
# 규칙에 걸리지 않는 라벨은 「기타」로 두고 라벨을 그대로 보여준다.
#   추측해서 아무 구간에나 넣지 않는다. 훅이 loop 을 못 찾으면 "-" 로 두는 것과 같은 이유다.
STAGE_RULES = [
    ("②", "PM",             r"^\s*(PM|기획자)\b"),
    ("②", "Developer 자문",  r"^\s*(Developer|개발자)\s*[·:]?\s*(자문|문의|협의)"),
    ("③", "Developer",      r"^\s*(Developer|개발자)\b"),
    ("④", "Reviewer",       r"^\s*(Reviewer|리뷰어)\b"),
]

# 라벨이 규칙에 안 걸릴 때의 보조 근거 — 어떤 역할 타입으로 띄웠는가(.claude/agents/).
# 라벨을 먼저 보는 이유: 라벨에는 관점("Reviewer: 회귀")이 담기지만 타입에는 없다.
# 타입은 라벨이 어긋났을 때만 쓴다. 추측이 아니라 훅이 기록한 사실이므로 「기타」로 흘리지 않는다.
AGENT_STAGES = {
    "feature-pm":                ("②", "PM"),
    "feature-developer-advisor": ("②", "Developer 자문"),
    "feature-developer":         ("③", "Developer"),
    "feature-reviewer":          ("④", "Reviewer"),
}

# 서브에이전트가 없는 구간. 로그에 왕복이 안 남는 것이 정상이므로 「없음」을 실패로 읽으면 안 된다.
NO_SUBAGENT = {"①": "요구 수집 (메인이 사람과 직접)", "⑤": "배포 (사람이 방아쇠)"}
STAGE_ORDER = ["①", "②", "③", "④", "⑤"]

# 기본 화면에서 접는 개입. 내용이 없는 진행 알림이라 흐름을 가린다. --full 로 편다.
QUIET_KINDS = {"알림"}

# 사람이 친 것이 아니라 서브에이전트 복귀 알림이 UserPromptSubmit 으로 들어온 줄.
# 훅은 이것도 kind="사람입력" 으로 남긴다(이벤트만 보면 구별이 안 된다).
# kind 를 고쳐 쓰지 않고 auto 플래그만 달아 따로 센다 — 로그를 다시 쓰는 것이 아니라 읽는 쪽에서 가른다.
AUTO_RETURN = re.compile(r"^\s*<task-notification>")

# 세션 안에서 오케스트레이터가 바뀐 지점. 사람이 친 "/스킬명" 이 그 신호다.
#   한 세션에서 feature-loop 를 돌린 뒤 skill-forge 를 이어 돌리면 두 오케스트레이터의 왕복이
#   같은 세션에 섞이고, 세션 이어붙이기(attribute) 가 그것을 한 루프로 몰아넣는다.
# 라벨 모양(「검토자」는 skill-forge 것)으로 가르지 않는다 — 그건 추측이고, 라벨은 언제든 바뀐다.
# 사람이 무엇을 불렀는지가 로그에 남아 있으므로 그 사실로 가른다.
SLASH_CALL = re.compile(r"^\s*/([a-z][a-z0-9-]*)")


def dwidth(text):
    """터미널 표시 폭. 한글·CJK는 두 칸으로 센다."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def pad(text, width):
    return text + " " * max(0, width - dwidth(text))


def clip(text, width):
    if dwidth(text) <= width:
        return text
    out = ""
    for ch in text:
        if dwidth(out) + dwidth(ch) > width - 1:
            break
        out += ch
    return out + "…"


def parse_ts(raw):
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def hm(dt):
    return dt.astimezone(KST).strftime("%H:%M")


def stamp(dt):
    return dt.astimezone(KST).strftime("%m-%d %H:%M")


def human_bytes(n):
    if n is None:
        return "-"
    if n < 1024:
        return f"{n}B"
    return f"{n / 1024:.1f}KB"


def load_jsonl(path):
    """(레코드 목록, 깨진 줄 수). 파일이 없으면 ([], 0) — 훅 설치 전 구간은 비어 있는 게 정상이다."""
    if not os.path.exists(path):
        return [], 0
    rows, broken = [], 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                broken += 1
    return rows, broken


def stage_of(label, agent=None):
    for mark, role, pattern in STAGE_RULES:
        if re.search(pattern, label or "", re.IGNORECASE):
            return mark, role
    if agent in AGENT_STAGES:
        return AGENT_STAGES[agent]
    return "기타", (label or "-").split(":")[0].strip() or "-"


def normalize(root):
    """두 로그를 한 줄씩 같은 모양으로 편다. 시간순 정렬은 호출자가 한다."""
    handoff, b1 = load_jsonl(os.path.join(root, ".claude", "agent-handoff.jsonl"))
    human, b2 = load_jsonl(os.path.join(root, ".claude", "human-intervention.jsonl"))

    events = []
    for r in handoff:
        ts = parse_ts(r.get("ts"))
        if ts is None:
            continue
        mark, role = stage_of(r.get("label", ""), r.get("agent"))
        events.append({
            "ts": ts, "src": "agent", "ev": r.get("ev", "?"),
            "loop": r.get("loop", "-") or "-", "session": r.get("session", ""),
            "stage": mark, "role": role, "label": r.get("label", "-"),
            "agent": r.get("agent", "-"), "summary": r.get("summary", ""),
            "bytes": r.get("bytes"), "dur_s": r.get("dur_s"),
            "iso": r.get("isolation_line"), "key": r.get("key", ""),
            "kind": None, "question": False, "auto": False,
        })
    for r in human:
        ts = parse_ts(r.get("ts"))
        if ts is None:
            continue
        events.append({
            "ts": ts, "src": "human", "ev": r.get("ev", "?"),
            "loop": r.get("loop", "-") or "-", "session": r.get("session", ""),
            "stage": "▣", "role": r.get("kind", "-"), "label": r.get("kind", "-"),
            "agent": "-", "summary": r.get("summary", ""),
            "bytes": r.get("bytes"), "dur_s": r.get("dur_s"),
            "iso": None, "key": "",
            "kind": r.get("kind", "-"), "question": bool(r.get("question")),
            "auto": bool(AUTO_RETURN.match(r.get("summary", "") or "")),
        })
    return events, b1 + b2


def attribute(events):
    """loop=="-" 인 줄을 세션 안에서 이어붙인다.

    훅은 프롬프트에서 루프 경로를 못 찾으면 "-" 로 남긴다(추측해서 쓰면 틀린 데이터가 굳으므로).
    그래서 실제 로그는 대부분 "-" 다. 여기서 세션 단위로만 이어붙이고,
    이어붙인 줄에는 attr="session" 을 달아 화면에서 ~ 로 구분해 보여준다.
    「최근에 고친 루프」 같은 세션 밖 추측은 하지 않는다.
    """
    by_session = {}
    for e in events:
        by_session.setdefault(e["session"], []).append(e)

    for evs in by_session.values():
        evs.sort(key=lambda e: e["ts"])
        carried = None
        for e in evs:
            if e["loop"] != "-":
                carried = e["loop"]
                e["attr"] = "log"
            elif carried:
                e["loop"] = carried
                e["attr"] = "session"
            else:
                e["attr"] = None
        # 세션 앞머리(첫 루프 이름이 찍히기 전 구간)는 뒤에서 끌어와 채운다.
        head = next((e["loop"] for e in evs if e.get("attr") == "log"), None)
        if head:
            for e in evs:
                if e.get("attr") is not None:
                    break
                e["loop"] = head
                e["attr"] = "session"
        for e in evs:
            if e.get("attr") is None:
                e["loop"] = "(미귀속)"
                e["attr"] = "none"
    return events


def mark_orchestrator(events, known_skills):
    """각 줄이 어느 오케스트레이터가 도는 중에 찍혔는지 단다.

    근거는 하나뿐이다 — 사람이 친 "/스킬명". 그 시점부터 다음 "/스킬명" 까지가 그 오케스트레이터의 구간이다.
    첫 "/스킬명" 이전 줄은 None 으로 둔다(모른다). 모르는 것을 앞의 값으로 채우지 않는다.
    """
    by_session = {}
    for e in events:
        by_session.setdefault(e["session"], []).append(e)
    for evs in by_session.values():
        evs.sort(key=lambda e: e["ts"])
        current = None
        for e in evs:
            if (e["src"] == "human" and e["ev"] == "answer" and not e["auto"]):
                m = SLASH_CALL.match(e["summary"] or "")
                if m and m.group(1) in known_skills:
                    current = m.group(1)
                    e["orch_switch"] = current
            e["orch"] = current
    return events


def scan_skills(root):
    d = os.path.join(root, ".claude", "skills")
    if not os.path.isdir(d):
        return set()
    return {n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n))}


def scan_loop_dirs(root):
    """projects/<제품>/loops/NNN-<기능> 을 훑는다. 로그가 없는 옛 루프도 목록에 나와야 한다."""
    found = {}
    base = os.path.join(root, "projects")
    if not os.path.isdir(base):
        return found
    for product in sorted(os.listdir(base)):
        loops_dir = os.path.join(base, product, "loops")
        if not os.path.isdir(loops_dir):
            continue
        for leaf in sorted(os.listdir(loops_dir)):
            if re.match(r"^\d{3}-", leaf) and os.path.isdir(os.path.join(loops_dir, leaf)):
                found[f"{product}/{leaf}"] = os.path.join(loops_dir, leaf)
    return found


def loop_number(name):
    m = re.search(r"(?:^|/)(\d{3})-", name)
    return int(m.group(1)) if m else -1


def collect(root, all_orch=False):
    events, broken = normalize(root)
    attribute(events)
    mark_orchestrator(events, scan_skills(root))
    events.sort(key=lambda e: e["ts"])

    loops = {}
    for name, path in scan_loop_dirs(root).items():
        loops[name] = {"name": name, "path": path, "events": []}
    for e in events:
        loops.setdefault(e["loop"], {"name": e["loop"], "path": None, "events": []})
        loops[e["loop"]]["events"].append(e)

    for lp in loops.values():
        # 루프의 주인 오케스트레이터 = 이 루프의 첫 줄이 찍힐 때 돌던 것.
        # 다른 오케스트레이터가 돈 구간은 기본으로 접는다(--all-orch 로 편다).
        all_evs = lp["events"]
        owner = next((e["orch"] for e in all_evs if e["orch"]), None)
        lp["owner"] = owner
        lp["all_orch"] = all_orch
        if all_orch or owner is None:
            lp["outside"] = []
        else:
            lp["outside"] = [e for e in all_evs if e["orch"] not in (None, owner)]
            lp["events"] = [e for e in all_evs if e["orch"] in (None, owner)]
        lp["outside_orch"] = sorted({e["orch"] for e in lp["outside"] if e["orch"]})
        lp["outside_dispatch"] = sum(1 for e in lp["outside"]
                                     if e["src"] == "agent" and e["ev"] == "dispatch")
        evs = lp["events"]
        agent_evs = [e for e in evs if e["src"] == "agent"]
        dispatches = [e for e in agent_evs if e["ev"] == "dispatch"]
        returns = [e for e in agent_evs if e["ev"] == "return"]
        returned_keys = {e["key"] for e in returns}
        lp["dispatch"] = len(dispatches)
        lp["unreturned"] = [e for e in dispatches if e["key"] not in returned_keys]
        lp["human"] = [e for e in evs if e["src"] == "human" and not e["auto"]]
        lp["auto_return"] = [e for e in evs if e["src"] == "human" and e["auto"]]
        lp["wait_s"] = sum(e["dur_s"] or 0 for e in lp["human"] if e["ev"] == "answer")
        kinds = {}
        for e in lp["human"]:
            kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
        lp["kinds"] = kinds
        lp["stages"] = [m for m in STAGE_ORDER if any(e["stage"] == m for e in dispatches)]
        lp["other"] = [e for e in dispatches if e["stage"] == "기타"]
        lp["first"] = evs[0]["ts"] if evs else None
        lp["last"] = evs[-1]["ts"] if evs else None
        lp["sessions"] = sorted({e["session"] for e in evs if e["session"]})
        lp["inferred"] = sum(1 for e in evs if e.get("attr") == "session")
        lp["confirmed"] = sum(1 for e in evs if e.get("attr") == "log")
        lp["no_isolation"] = [e for e in dispatches if e["iso"] is False]
        lp["empty_return"] = [e for e in returns if not e.get("bytes")]
        lp["number"] = loop_number(lp["name"])

    ordered = sorted(loops.values(), key=lambda l: (l["number"], l["name"]), reverse=True)
    return ordered, broken


# ------------------------------------------------------------------ 목록

def render_list(loops, broken):
    lines = ["루프 목록 · 시간 KST · 최신순(루프 번호 기준)"]
    logged = [l for l in loops if l["events"]]
    if logged:
        lo = min(l["first"] for l in logged)
        hi = max(l["last"] for l in logged)
        lines.append(f"로그 구간 {stamp(lo)} ~ {stamp(hi)}")
    else:
        lines.append("로그 구간 — 기록된 줄이 없다")
    if broken:
        lines.append(f"⚠ 읽지 못한 줄 {broken}개를 건너뛰었다")
    lines.append("")

    rows = []
    for i, l in enumerate(loops, 1):
        if l["events"]:
            stages = "".join(l["stages"]) or "—"
            if l["other"]:
                stages += "+기타"
            rows.append([str(i), l["name"], stages, str(l["dispatch"]),
                         str(len(l["human"])), stamp(l["last"])])
        else:
            rows.append([str(i), l["name"], "— 로그 없음", "-", "-", "-"])

    head = ["#", "루프", "도달 구간", "왕복", "개입", "마지막 기록"]
    widths = [max(dwidth(r[c]) for r in [head] + rows) for c in range(len(head))]
    lines.append("  ".join(pad(head[c], widths[c]) for c in range(len(head))).rstrip())
    for r in rows:
        lines.append("  ".join(pad(r[c], widths[c]) for c in range(len(r))).rstrip())

    lines.append("")
    lines.append("도달 구간 = 서브에이전트 왕복이 로그에 남은 구간. ①·⑤는 서브가 없어 여기 나오지 않는다.")
    lines.append("개입 = 사람이 실제로 답한 줄. 서브 복귀 알림(<task-notification>)은 빼고 셌다.")
    lines.append("로그 없음 = 훅 설치 이전에 돈 루프. 돌지 않은 것이 아니다.")
    folded = [l for l in loops if l.get("outside")]
    if folded:
        lines.append("")
        for l in folded:
            lines.append(f"접음  {l['name']} — 같은 세션의 {'·'.join(l['outside_orch'])} "
                         f"왕복 {l['outside_dispatch']}건은 빼고 셌다 (--all-orch 로 포함)")
    return "\n".join(lines)


# ------------------------------------------------------------------ 상세

def render_loop(lp, full=False):
    lines = [f"루프  {lp['name']}"]
    if lp["path"]:
        lines.append(f"경로  {lp['path']}")

    if not lp["events"]:
        lines += [
            "",
            "이 루프의 로그가 없다. 훅 설치 이전에 돈 루프이거나, 루프 세션 밖에서 진행됐다.",
            "디렉터리의 criteria.md · observation.md 를 직접 읽는 편이 빠르다.",
        ]
        return "\n".join(lines)

    span = int((lp["last"] - lp["first"]).total_seconds() // 60)
    lines.append(f"기록  {stamp(lp['first'])} ~ {stamp(lp['last'])} KST · {span}분 · 세션 {len(lp['sessions'])}개")
    lines.append(f"귀속  로그가 직접 지목 {lp['confirmed']}줄 · 세션으로 이어붙임 {lp['inferred']}줄(~ 표시)")
    if lp["outside"]:
        o_first, o_last = lp["outside"][0]["ts"], lp["outside"][-1]["ts"]
        lines.append(f"범위  {lp['owner']} 구간만. 같은 세션의 "
                     f"{'·'.join(lp['outside_orch'])} 왕복 {lp['outside_dispatch']}건"
                     f"({hm(o_first)}~{hm(o_last)})은 접었다 — --all-orch 로 펼침")
    elif lp["all_orch"]:
        lines.append("범위  전부. 같은 세션의 다른 오케스트레이터 구간까지 포함했다(--all-orch)")
    elif lp["owner"]:
        lines.append(f"범위  {lp['owner']} 구간만. 이 세션에 다른 오케스트레이터는 없었다")

    # ── 구간 도달
    lines += ["", "구간 — 서브에이전트 왕복이 로그에 남은 것"]
    dispatches = [e for e in lp["events"] if e["src"] == "agent" and e["ev"] == "dispatch"]
    for mark in STAGE_ORDER:
        if mark in NO_SUBAGENT:
            lines.append(f"  {mark} {pad(NO_SUBAGENT[mark], 28)}  서브에이전트 없음 — 로그로 판정하지 않는다")
            continue
        hits = [e for e in dispatches if e["stage"] == mark]
        title = {"②": "PM", "③": "Developer", "④": "Reviewer"}[mark]
        if not hits:
            lines.append(f"  {mark} {pad(title, 28)}  왕복 없음")
            continue
        roles = {}
        for e in hits:
            roles[e["role"]] = roles.get(e["role"], 0) + 1
        detail = " · ".join(f"{k} {v}" for k, v in roles.items())
        guess = sum(1 for e in hits if e.get("attr") == "session")
        tag = f" · 그중 ~{guess}" if guess else ""
        lines.append(f"  {mark} {pad(title, 28)}  왕복 {len(hits)} ({detail}{tag})  "
                     f"{hm(hits[0]['ts'])}~{hm(hits[-1]['ts'])}")
    if lp["other"]:
        first, last = lp["other"][0], lp["other"][-1]
        labels = ", ".join(sorted({clip(e["label"], 24) for e in lp["other"]})[:4])
        guess = sum(1 for e in lp["other"] if e.get("attr") == "session")
        tag = f" · 그중 ~{guess}" if guess else ""
        lines.append(f"  기타 {pad('구간 규칙 밖', 27)}  왕복 {len(lp['other'])}{tag}  "
                     f"{hm(first['ts'])}~{hm(last['ts'])}")
        lines.append(f"       {labels}")

    # ── 사람 개입
    if lp["kinds"]:
        lines += ["", "사람 개입 — 훅이 남긴 kind 그대로. 원칙 6의 네 단계로 분류하지 않는다"]
        for k, v in sorted(lp["kinds"].items(), key=lambda kv: -kv[1]):
            lines.append(f"  {pad(k, 10)} {v}회")
        if lp["wait_s"]:
            lines.append(f"  {pad('붙잡힌 시간', 10)} {lp['wait_s'] // 60}분 {lp['wait_s'] % 60}초 "
                         f"(사람이 답하기까지. 서브 복귀 대기는 뺐다)")
        if lp["auto_return"]:
            lines.append(f"  {pad('(자동)', 10)} {len(lp['auto_return'])}회 — 서브 복귀 알림. "
                         f"훅은 사람입력으로 남기지만 사람이 친 것이 아니다")

    # ── 흐름
    lines += ["", "흐름   ─▶ 내보냄 · ◀─ 돌아옴 · ▣ 사람 · ? 사람에게 물은 것 · ~ 세션으로 이어붙인 줄"]
    shown, hidden = [], 0
    for e in lp["events"]:
        if not full and e["src"] == "human" and (e["kind"] in QUIET_KINDS
                                                 or (e["kind"] == "턴종료" and not e["question"])):
            hidden += 1
            continue
        shown.append(e)

    W = 46
    for e in shown:
        tick = "~" if e.get("attr") == "session" else " "
        when = hm(e["ts"])
        arrow = "─▶" if e["ev"] in ("dispatch", "ask") else "◀─"
        if e["src"] == "agent":
            lane = pad(e["stage"], 5)
            body = clip(e["label"], W)
            if e["ev"] == "dispatch":
                tail = f"{human_bytes(e['bytes']):>7}  {'격리✓' if e['iso'] else '격리✗'}  {e['agent']}"
            else:
                dur = f"{e['dur_s']}s" if e["dur_s"] is not None else "-"
                tail = f"{human_bytes(e['bytes']):>7}  {dur}" + ("  ⚠ 빈 응답" if not e["bytes"] else "")
        else:
            lane = pad("▣" + ("?" if e["question"] else ""), 5)
            tag = "자동" if e["auto"] else e["kind"]
            body = clip(f"{pad(tag, 8)} {e['summary']}", W)
            dur = f"{e['dur_s']}s" if e["dur_s"] is not None else "-"
            tail = f"{human_bytes(e['bytes']):>7}  {dur}"
        lines.append(f"{tick}{when}  {lane}{arrow} {pad(body, W)}  {tail}".rstrip())
    if hidden:
        lines.append(f"        … 내용 없는 진행 알림 {hidden}줄을 접었다 (--full 로 펼침)")

    # ── 관측 메모
    notes = []
    if lp["no_isolation"]:
        labels = ", ".join(clip(e["label"], 24) for e in lp["no_isolation"][:4])
        notes.append(f"격리 없이 나간 호출 {len(lp['no_isolation'])}건 — {labels} "
                     f"(프롬프트에도 역할 타입에도 읽는 범위 제한이 없었다 · OS.md 4절 규칙 3)")
    if lp["empty_return"]:
        notes.append(f"빈 응답 {len(lp['empty_return'])}건 — 서브가 배경으로 돌아 return 이 즉시 찍혔다. "
                     f"dur_s 를 작업 시간으로 읽으면 안 된다")
    if lp["unreturned"]:
        labels = ", ".join(clip(e["label"], 24) for e in lp["unreturned"][:4])
        notes.append(f"return 이 없는 호출 {len(lp['unreturned'])}건 — {labels}")
    if notes:
        lines += ["", "관측"]
        lines += [f"  · {n}" for n in notes]

    lines += ["", f"요약: {lp['name']} 왕복 {lp['dispatch']} 개입 {len(lp['human'])} "
                  f"구간 {''.join(lp['stages']) or '—'}"]
    return "\n".join(lines)


# ------------------------------------------------------------------ mermaid

def render_mermaid(lp):
    if not lp["events"]:
        return f'flowchart TD\n  n0["{lp["name"]}<br/>로그 없음"]'

    def esc(s):
        return re.sub(r'[\"<>|]', "", (s or "").replace("⏎", " ")).strip()

    nodes, edges = [], []
    prev = None
    run = None  # 연속된 같은 구간의 dispatch 를 한 노드로 묶는다
    for e in lp["events"]:
        if e["src"] == "agent" and e["ev"] == "dispatch":
            if run and run["stage"] == e["stage"]:
                run["n"] += 1
                run["last"] = e["ts"]
                continue
            run = {"stage": e["stage"], "role": e["role"], "n": 1,
                   "first": e["ts"], "last": e["ts"], "kind": "stage"}
            nodes.append(run)
        elif e["src"] == "human" and e["kind"] in ("의사결정", "승인요청") and e["ev"] == "ask":
            run = None
            nodes.append({"kind": "human", "text": esc(e["summary"])[:70],
                          "label": e["kind"], "first": e["ts"]})
        elif e["src"] == "human" and e["kind"] == "사람입력" and not nodes:
            nodes.append({"kind": "start", "text": esc(e["summary"])[:70], "first": e["ts"]})

    out = ["flowchart TD"]
    for i, n in enumerate(nodes[:40]):
        nid = f"n{i}"
        if n["kind"] == "stage":
            out.append(f'  {nid}["{n["stage"]} {esc(n["role"])}<br/>왕복 {n["n"]} · '
                       f'{hm(n["first"])}"]')
        elif n["kind"] == "human":
            out.append(f'  {nid}{{{{"▣ {n["label"]} {hm(n["first"])}<br/>{n["text"]}"}}}}')
        else:
            out.append(f'  {nid}(["▣ 시작 {hm(n["first"])}<br/>{n["text"]}"])')
        if prev is not None:
            edges.append(f"  {prev} --> {nid}")
        prev = nid
    out += edges
    out.append(f'  %% {lp["name"]} · 로그에 남은 것만. 관문 되돌림은 기록되지 않아 이 그림에 없다.')
    return "\n".join(out)


# ------------------------------------------------------------------ 진입점

def find_loop(loops, query):
    """003 · 003-delete-note · review-scheduler/003-delete-note 를 모두 받는다."""
    q = query.strip().strip("/")
    exact = [l for l in loops if l["name"] == q or l["name"].split("/")[-1] == q]
    if exact:
        return exact[0], []
    if re.fullmatch(r"\d{1,3}", q):
        num = int(q)
        hit = [l for l in loops if l["number"] == num]
        if len(hit) == 1:
            return hit[0], []
        if hit:
            return None, hit
    part = [l for l in loops if q.lower() in l["name"].lower()]
    if len(part) == 1:
        return part[0], []
    return None, part


def as_json(lp):
    return {
        "loop": lp["name"], "path": lp["path"], "orchestrator": lp["owner"],
        "folded_orchestrators": lp["outside_orch"], "folded_dispatch": lp["outside_dispatch"],
        "first": lp["first"].isoformat() if lp["first"] else None,
        "last": lp["last"].isoformat() if lp["last"] else None,
        "sessions": lp["sessions"], "dispatch": lp["dispatch"],
        "human": len(lp["human"]), "auto_return": len(lp["auto_return"]),
        "human_wait_s": lp["wait_s"], "human_kinds": lp["kinds"], "stages": lp["stages"],
        "attribution": {"log": lp["confirmed"], "session": lp["inferred"]},
        "no_isolation": [e["label"] for e in lp["no_isolation"]],
        "empty_return": len(lp["empty_return"]),
        "unreturned": [e["label"] for e in lp["unreturned"]],
        "events": [{
            "ts": e["ts"].isoformat(), "src": e["src"], "ev": e["ev"],
            "stage": e["stage"], "label": e["label"], "kind": e["kind"],
            "summary": e["summary"], "bytes": e["bytes"], "dur_s": e["dur_s"],
            "isolation_line": e["iso"], "attribution": e.get("attr"), "auto": e["auto"],
        } for e in lp["events"]],
    }


def main():
    ap = argparse.ArgumentParser(description="루프 로그를 목록·흐름으로 보여준다.")
    ap.add_argument("loop", nargs="?", help="루프 이름 (003 · 003-delete-note · 제품/003-...)")
    ap.add_argument("--list", action="store_true", help="루프 목록만 (기본)")
    ap.add_argument("--full", action="store_true", help="접은 진행 알림까지 모두 보이기")
    ap.add_argument("--mermaid", action="store_true", help="흐름을 mermaid flowchart 로")
    ap.add_argument("--all-orch", action="store_true",
                    help="같은 세션에서 다른 오케스트레이터가 돈 구간까지 포함")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    ap.add_argument("--root", default=os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()),
                    help="저장소 루트")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(os.path.join(root, ".claude")):
        print(f"저장소 루트가 아니다: {root} (.claude 가 없다)", file=sys.stderr)
        return 2

    loops, broken = collect(root, all_orch=args.all_orch)

    if args.loop and not args.list:
        lp, candidates = find_loop(loops, args.loop)
        if lp is None:
            print(f"'{args.loop}' 에 맞는 루프를 찾지 못했다.", file=sys.stderr)
            if candidates:
                print("후보: " + ", ".join(l["name"] for l in candidates), file=sys.stderr)
            else:
                print("있는 루프: " + ", ".join(l["name"] for l in loops), file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(as_json(lp), ensure_ascii=False, indent=2))
        elif args.mermaid:
            print(render_mermaid(lp))
        else:
            print(render_loop(lp, full=args.full))
        return 0

    if args.json:
        print(json.dumps([{
            "loop": l["name"], "logged": bool(l["events"]), "stages": l["stages"],
            "orchestrator": l["owner"], "folded_dispatch": l["outside_dispatch"],
            "dispatch": l["dispatch"], "human": len(l["human"]),
            "last": l["last"].isoformat() if l["last"] else None,
        } for l in loops], ensure_ascii=False, indent=2))
    else:
        print(render_list(loops, broken))
    return 0


if __name__ == "__main__":
    sys.exit(main())
