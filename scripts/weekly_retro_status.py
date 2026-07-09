#!/usr/bin/env python3
"""주간 회고 status — 한 주 루프 기록물을 결정론으로 집계하는 '사실판'.

왜 필요한가(OS.md F·daily-trading-loop Q28~Q30):
- 주간 회고(F)의 축약 위원회가 딛을 결정론적 사실판이 없으면, 페르소나가 '한 주 무슨 일이
  있었나'를 기억에 의존해 지어낼 위험이 있다. 이 스크립트가 회의록·계획·체결·포트폴리오를
  날짜 창(기본 7일)으로 집계해 **정량 사실**만 뽑아 주면, 위원회는 그 위에 해석(실력 vs 시장
  휩쓸림)만 얹는다. → 스크립트는 집계까지, 판단은 토론(investment-committee의 하이브리드
  역할과 정합, record-conventions의 "회고가 되짚을 원본"과 정합).

무결성(trading-principles 1·3):
- 값을 지어내지 않는다. 못 구한 값·없는 파일은 "확인 불가"/null로 표기하고 note에 남긴다.
- 주간 수익률은 포트폴리오(상태 파일, 이력 없음)만으로는 산출 불가라 "확인 불가"로 둔다
  (시작~종료 시점 평가액 이력이 없기 때문 — 체결 로그가 사건 원천).

집계 대상(record-conventions 기록물 5종 중 루프 산출물):
- 회의록  data/minutes/YYYY-MM-DD.md   (사건 로그) — 국면 합의·계획 결정·긴급 여부
- 체결    data/fills/YYYY-MM-DD.md      (사건 로그) — 체결 이벤트 수(휴리스틱)
- 브리핑  data/briefings/YYYY-MM-DD.md  (사건 로그) — 존재 인벤토리
- 계획서  data/investment-plan.md       (상태)     — 종목별 상태 라벨 집계
- 포트폴리오 data/portfolio.md           (상태)     — 현재 보유·현금·평가손익(라벨 추출)

사용:
  python3 weekly_retro_status.py                 # 오늘 기준 최근 7일
  python3 weekly_retro_status.py --end 2026-07-11 --days 7
출력: JSON 한 줄(회고 위원회 입력용 사실판).
"""
from __future__ import annotations
import argparse
import datetime as _dt
import json
import os
import re
from pathlib import Path

# 저장소 루트: CLAUDE_PROJECT_DIR 우선, 없으면 스크립트 위치 기준.
ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", "")) if os.environ.get(
    "CLAUDE_PROJECT_DIR") else Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})(?:-\d+)?\.md$")


def _in_window(name: str, start: _dt.date, end: _dt.date):
    """파일명에서 YYYY-MM-DD를 뽑아 창 [start, end] 안이면 그 날짜를 돌려준다(아니면 None)."""
    m = DATE_RE.search(name)
    if not m:
        return None
    try:
        d = _dt.date.fromisoformat(m.group(1))
    except ValueError:
        return None
    return d if start <= d <= end else None


def collect_logs(subdir: str, start: _dt.date, end: _dt.date) -> dict:
    """사건 로그 디렉터리(브리핑/회의록/체결)의 창 안 파일을 날짜순 인벤토리로."""
    d = DATA / subdir
    files = []
    if d.is_dir():
        for p in sorted(d.iterdir()):
            day = _in_window(p.name, start, end)
            if day is not None:
                files.append((day, p))
    return {
        "present_dir": d.is_dir(),
        "count": len(files),
        "dates": sorted({day.isoformat() for day, _ in files}),
        "files": [str(p.relative_to(ROOT)) for _, p in files],
        "_paths": files,
    }


def digest_minutes(start: _dt.date, end: _dt.date) -> dict:
    """회의록: 창 안 파일별로 긴급 여부와 '국면 합의' 섹션을 결정론 추출(국면 판정 앵커)."""
    base = collect_logs("minutes", start, end)
    entries = []
    emergency = 0
    for day, p in base["_paths"]:
        text = p.read_text(encoding="utf-8", errors="replace")
        is_emg = ("긴급" in text) or ("긴급" in p.name)
        emergency += 1 if is_emg else 0
        entries.append({
            "date": day.isoformat(),
            "path": str(p.relative_to(ROOT)),
            "emergency": is_emg,
            "regime_section": _section(text, "국면 합의"),
            "plan_section": _section(text, "계획 결정"),
        })
    return {
        "present_dir": base["present_dir"],
        "count": base["count"],
        "dates": base["dates"],
        "emergency_count": emergency,
        "entries": entries,
    }


def _section(text: str, header: str):
    """'## <header>' 다음부터 다음 '## '(또는 EOF)까지를 그대로 잘라낸다. 없으면 None."""
    m = re.search(rf"^##\s*{re.escape(header)}\s*$", text, re.MULTILINE)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^##\s", rest, re.MULTILINE)
    body = rest[: nxt.start()] if nxt else rest
    return body.strip() or None


def digest_fills(start: _dt.date, end: _dt.date) -> dict:
    """체결 로그: 파일 인벤토리 + 체결 이벤트 수(휴리스틱 — 표 행/불릿 줄)."""
    base = collect_logs("fills", start, end)
    event_lines = 0
    for _, p in base["_paths"]:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            # 표 데이터 행(| … |, 구분선/헤더 제외) 또는 '- ' 불릿을 이벤트 후보로 셈.
            if s.startswith("|") and s.endswith("|") and not re.match(r"^\|[\s:|-]+\|$", s):
                if not re.search(r"종목|수량|체결가|시각", s):  # 헤더 행 제외
                    event_lines += 1
            elif s.startswith("- "):
                event_lines += 1
    return {
        "present_dir": base["present_dir"],
        "count": base["count"],
        "dates": base["dates"],
        "files": base["files"],
        "event_lines_heuristic": event_lines,
    }


def digest_plan() -> dict:
    """투자계획서(상태): 종목별 상태 라벨(대기/진행중/완료)을 표에서 집계."""
    p = DATA / "investment-plan.md"
    if not p.is_file():
        return {"present": False}
    text = p.read_text(encoding="utf-8", errors="replace")
    positions = []
    counts = {"대기": 0, "진행중": 0, "완료": 0, "기타": 0}
    for line in text.splitlines():
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if re.match(r"^[\s:|-]+$", s.replace("|", " ")):  # 구분선
            continue
        if any(h in cells[0] for h in ("종목",)) and len(cells) > 1:  # 헤더 행
            continue
        label = next((c for c in cells if c in ("대기", "진행중", "완료")), None)
        if label is None:
            continue
        counts[label] += 1
        positions.append({"종목": cells[0], "상태": label})
    return {
        "present": True,
        "path": str(p.relative_to(ROOT)),
        "position_count": len(positions),
        "status_counts": counts,
        "positions": positions,
    }


def digest_portfolio() -> dict:
    """포트폴리오(상태): 현금·평가손익·총평가액 라벨을 있으면 추출(없으면 확인 불가)."""
    p = DATA / "portfolio.md"
    if not p.is_file():
        return {"present": False}
    text = p.read_text(encoding="utf-8", errors="replace")
    extracted = {}
    for key, pat in (("현금", r"현금"), ("평가손익", r"평가\s*손익|평가손익"),
                     ("총평가액", r"총\s*평가|평가\s*금액|총자산")):
        m = re.search(rf"(?:{pat})[^0-9\-]*(-?[\d,]+(?:\.\d+)?)", text)
        extracted[key] = m.group(1).replace(",", "") if m else None
    return {
        "present": True,
        "path": str(p.relative_to(ROOT)),
        "extracted": extracted,
        "raw": text.strip(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="주간 회고용 루프 기록물 집계(결정론 사실판)")
    ap.add_argument("--end", help="창 종료일 YYYY-MM-DD(기본 오늘)")
    ap.add_argument("--days", type=int, default=7, help="창 길이(일, 기본 7)")
    args = ap.parse_args()

    end = _dt.date.fromisoformat(args.end) if args.end else _dt.date.today()
    start = end - _dt.timedelta(days=args.days - 1)

    minutes = digest_minutes(start, end)
    fills = digest_fills(start, end)
    briefings = collect_logs("briefings", start, end)
    plan = digest_plan()
    portfolio = digest_portfolio()

    notes = []
    if not minutes["count"]:
        notes.append("확인 불가: 창 안 회의록 없음 — 위원회 판단 이력 부재(초기 상태이거나 미수집)")
    if not fills["count"]:
        notes.append("확인 불가: 창 안 체결 로그 없음 — 체결 결과 집계 불가")
    if not plan.get("present"):
        notes.append("확인 불가: 투자계획서 없음 — 계획 상태 집계 불가")
    if not portfolio.get("present"):
        notes.append("확인 불가: 포트폴리오 없음 — 현재 손익 집계 불가")
    # 주간 수익률은 상태 파일만으로 산출 불가(이력 없음). 무결성 1: 지어내지 않는다.
    notes.append(
        "주간 수익률: 확인 불가 — 포트폴리오는 상태(이력 없음)라 시작·종료 평가액 차를 "
        "결정론으로 못 구한다. 위원회가 체결 로그·회의록으로 정성 판단한다(수치 날조 금지).")

    out = {
        "window": {"start": start.isoformat(), "end": end.isoformat(), "days": args.days},
        "root": str(ROOT),
        "data_present": DATA.is_dir(),
        "briefings": {k: briefings[k] for k in ("present_dir", "count", "dates", "files")},
        "minutes": minutes,
        "fills": fills,
        "investment_plan": plan,
        "portfolio": portfolio,
        "weekly_return": None,  # 결정론 산출 불가(위 note 참조)
        "notes": notes,
    }
    print(json.dumps(out, ensure_ascii=False))
    # 회의록·체결이 하나도 없으면(되짚을 사건 부재) exit 1로 신호.
    return 0 if (minutes["count"] or fills["count"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
