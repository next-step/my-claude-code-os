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
# 주별 무결성 건강도 시계열 원장(런타임 생성 — --append-health-ledger로만 기록).
HEALTH_LEDGER = DATA / "health" / "integrity-health.jsonl"

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})(?:-\d+)?\.md$")

# 빈 셀·자리표시자(값 없음). 무결성 1: 없는 값을 지어내지 않고 '확인 불가'로 남긴다.
EMPTY_TOKENS = {"", "-", "—", "–", "TBD", "미정", "미기재", "N/A", "n/a", "null", "None", "?"}


def _clean_cell(cell):
    """빈 셀·자리표시자는 None, 아니면 원문 텍스트(양끝 공백 제거)."""
    if cell is None:
        return None
    c = cell.strip()
    return None if c in EMPTY_TOKENS else c


def _parse_price(cell):
    """가격 셀에서 숫자를 결정론 추출(콤마·'원' 접미사 허용). 실패·빈 셀은 None.

    정수면 int, 소수면 float로 돌려준다(JSON 가독성).
    """
    c = _clean_cell(cell)
    if c is None:
        return None
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", c)
    if not m:
        return None
    try:
        v = float(m.group(0).replace(",", ""))
    except ValueError:
        return None
    return int(v) if v.is_integer() else v


def _parse_qty(cell):
    """수량 셀 파싱. 미기재→None, 양의 정수→int, 그 밖(기재됐으나 정수 아님)→원문 문자열.

    compute_integrity_health가 `isinstance(int)`로 정합 여부를, `None`으로 미기재(확인 불가)를 가른다.
    """
    c = _clean_cell(cell)
    if c is None:
        return None
    t = re.sub(r"\s*주\s*$", "", c.replace(",", "").strip())
    if re.fullmatch(r"\d+", t) and int(t) > 0:
        return int(t)
    return c  # 기재됐으나 양의 정수 아님 → 원문을 값으로(위반 근거)


def _col_index(headers, *keywords):
    """헤더 셀 목록에서 keyword를 포함하는 첫 열의 인덱스(없으면 None)."""
    for i, h in enumerate(headers):
        if any(kw in h for kw in keywords):
            return i
    return None


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
        # 긴급위 마커는 '긴급' 표기 헤딩(record-conventions)이다. 본문에 단어가 언급됐다고
        # 긴급 회의로 세면 정규 회의록이 오탐된다(긴급위 규약을 논의만 해도 걸린다).
        is_emg = bool(re.search(r"^#{1,3}.*긴급", text, re.MULTILINE)) or ("긴급" in p.name)
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
    """'## <header>' 다음부터 다음 '## '(또는 EOF)까지를 그대로 잘라낸다. 없으면 None.

    회의록 스키마는 헤딩에 괄호 주석을 허용한다("## 국면 합의  (라운드 2에 수렴)").
    """
    m = re.search(rf"^##\s*{re.escape(header)}\s*(?:\(.*\))?\s*$", text, re.MULTILINE)
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


def _fill_position(pos: dict, cells: list, cols: dict) -> None:
    """헤더 열 맵(cols)으로 종목 행의 진입가·목표가·손절가·수량·근거 셀을 pos에 채운다.

    열이 헤더에 아예 없으면 해당 키를 넣지 않고(→ 확인 불가), 열은 있으나 셀이 비면
    None을 넣는다(compute_integrity_health가 '열 부재' vs '셀 빔'을 구분하도록 — 무결성 1).
    """
    def raw_cell(key):
        idx = cols.get(key)
        if idx is None:
            return None
        return cells[idx] if idx < len(cells) else None

    for key in ("진입가", "목표가", "손절가"):
        if cols.get(key) is not None:
            pos[key] = _parse_price(raw_cell(key))
    if cols.get("수량") is not None:
        pos["수량"] = _parse_qty(raw_cell("수량"))
    if cols.get("근거") is not None:
        pos["근거"] = _clean_cell(raw_cell("근거"))


def digest_plan() -> dict:
    """투자계획서(상태+자기정합): 종목별 상태 라벨 집계 + 진입가·목표가·손절가·수량·근거 파싱.

    표 헤더 행(첫 칸에 '종목')에서 열 위치를 매칭해 종목별 셀을 결정론 추출한다(열 순서 변화에 견고).
    파싱 실패·미기재 셀은 None, 헤더에 그 열이 없으면 해당 키를 생략한다(compute_integrity_health가
    '셀 빔'과 '열 부재'를 구분해 확인 불가/위반을 가른다).
    """
    p = DATA / "investment-plan.md"
    if not p.is_file():
        return {"present": False}
    text = p.read_text(encoding="utf-8", errors="replace")
    positions = []
    counts = {"대기": 0, "진행중": 0, "완료": 0, "기타": 0}
    cols = None  # 첫 종목 헤더 행에서 잡은 열 인덱스 맵
    for line in text.splitlines():
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        if re.match(r"^\|[\s:|-]+\|$", s):  # 구분선
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        # 헤더 행: 첫 칸에 '종목'. 가장 먼저 나온 것으로 열 위치 맵을 확정한다.
        if cols is None and cells and "종목" in cells[0] and len(cells) > 1:
            cols = {
                "진입가": _col_index(cells, "진입"),
                "목표가": _col_index(cells, "목표가"),
                "손절가": _col_index(cells, "손절"),
                "수량": _col_index(cells, "수량"),
                "근거": _col_index(cells, "근거"),
            }
            continue
        # 데이터 행: 상태 라벨이 있어야 종목 행으로 인정(기존 휴리스틱 유지).
        label = next((c for c in cells if c in ("대기", "진행중", "완료")), None)
        if label is None:
            continue
        counts[label] += 1
        pos = {"종목": cells[0], "상태": label}
        if cols:
            _fill_position(pos, cells, cols)
        positions.append(pos)
    return {
        "present": True,
        "path": str(p.relative_to(ROOT)),
        "position_count": len(positions),
        "status_counts": counts,
        "positions": positions,
    }


def compute_integrity_health(positions: list) -> dict:
    """계획서 내부 자기정합 점검 4종을 돌려 무결성 건강도를 산출한다(외부 데이터·날조 없음).

    점검(위반 조건):
      ① 근거 유무   — 근거 셀이 빔                 (trading-principles 무결성 2)
      ② 손절가 정합 — 손절가 ≥ 진입가              ("손절가는 진입가 아래")
      ③ 목표가 정합 — 목표가 ≤ 진입가              (롱 진입 논리)
      ④ 수량 정합   — 주문 수량이 양의 정수 아님    (D 스키마: 정수주 확정)

    값이 없어 판정 불가한 셀(열 부재·셀 빔)은 점검·위반 어디에도 세지 않고 '확인 불가'에 남긴다
    (무결성 1). 건강도 = 1 − 위반/점검, 점검=0이면 None.
    """
    checks = 0
    violations = 0
    violation_list = []
    unknown = []

    def add_violation(name, check, value):
        nonlocal violations
        violations += 1
        violation_list.append({"종목": name, "점검": check, "값": value})

    for pos in positions:
        name = pos.get("종목", "?")
        entry = pos.get("진입가")

        # ① 근거 유무: 근거 열이 있어야 판정. 셀이 비면 위반, 열 자체가 없으면 확인 불가.
        if "근거" not in pos:
            unknown.append({"종목": name, "점검": "근거 유무", "사유": "근거 열 없음"})
        else:
            checks += 1
            if pos["근거"] is None:
                add_violation(name, "근거 유무", None)

        # ② 손절가 정합: 진입가·손절가 둘 다 있어야 판정.
        if "손절가" not in pos or "진입가" not in pos or pos.get("손절가") is None or entry is None:
            unknown.append({"종목": name, "점검": "손절가 정합", "사유": "진입가/손절가 미기재"})
        else:
            checks += 1
            if pos["손절가"] >= entry:
                add_violation(name, "손절가 정합", pos["손절가"])

        # ③ 목표가 정합: 진입가·목표가 둘 다 있어야 판정.
        if "목표가" not in pos or "진입가" not in pos or pos.get("목표가") is None or entry is None:
            unknown.append({"종목": name, "점검": "목표가 정합", "사유": "진입가/목표가 미기재"})
        else:
            checks += 1
            if pos["목표가"] <= entry:
                add_violation(name, "목표가 정합", pos["목표가"])

        # ④ 수량 정합: 수량 열·셀이 있어야 판정. 양의 정수면 int, 아니면 원문(위반).
        if "수량" not in pos:
            unknown.append({"종목": name, "점검": "수량 정합", "사유": "수량 열 없음"})
        elif pos["수량"] is None:
            unknown.append({"종목": name, "점검": "수량 정합", "사유": "수량 미기재"})
        else:
            checks += 1
            if not isinstance(pos["수량"], int):
                add_violation(name, "수량 정합", pos["수량"])

    health = None if checks == 0 else round(1 - violations / checks, 4)
    return {
        "점검": checks,
        "위반": violations,
        "건강도": health,
        "위반내역": violation_list,
        "확인불가": unknown,
    }


def append_health_ledger(window_end: str, ih: dict) -> bool:
    """무결성 건강도 한 줄을 창 종료일(window_end) 키로 원장에 멱등 append.

    같은 window_end가 이미 있으면 추가하지 않는다(재실행 안전). 디렉터리가 없으면 만든다.
    돌려주는 값: 실제로 추가했으면 True, 이미 있어 건너뛰면 False.
    """
    HEALTH_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    if HEALTH_LEDGER.is_file():
        for line in HEALTH_LEDGER.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("window_end") == window_end:
                return False  # 멱등: 같은 주 이미 기록됨
    rec = {
        "window_end": window_end,
        "checked": ih["점검"],
        "violations": ih["위반"],
        "health": ih["건강도"],
    }
    with HEALTH_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return True


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
    ap.add_argument("--append-health-ledger", action="store_true",
                    help="무결성 건강도를 data/health/integrity-health.jsonl에 창 종료일 키로 멱등 append")
    args = ap.parse_args()

    end = _dt.date.fromisoformat(args.end) if args.end else _dt.date.today()
    start = end - _dt.timedelta(days=args.days - 1)

    minutes = digest_minutes(start, end)
    fills = digest_fills(start, end)
    briefings = collect_logs("briefings", start, end)
    plan = digest_plan()
    portfolio = digest_portfolio()
    integrity = compute_integrity_health(plan.get("positions", []) if plan.get("present") else [])

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
    if integrity["점검"] == 0:
        notes.append("무결성 건강도: 확인 불가 — 결정론 점검 대상(계획서 종목·정합 셀)이 없음")

    # --append-health-ledger: 무결성 건강도를 창 종료일 키로 주별 원장에 멱등 기록(기본은 순수 출력).
    ledger_status = None
    if args.append_health_ledger:
        appended = append_health_ledger(end.isoformat(), integrity)
        ledger_status = {
            "path": str(HEALTH_LEDGER.relative_to(ROOT)),
            "appended": appended,
        }
        notes.append(
            f"무결성 건강도 원장: {'추가' if appended else '이미 기록됨(멱등 건너뜀)'} "
            f"— {ledger_status['path']} (키=window_end {end.isoformat()})")

    out = {
        "window": {"start": start.isoformat(), "end": end.isoformat(), "days": args.days},
        "root": str(ROOT),
        "data_present": DATA.is_dir(),
        "briefings": {k: briefings[k] for k in ("present_dir", "count", "dates", "files")},
        "minutes": minutes,
        "fills": fills,
        "investment_plan": plan,
        "portfolio": portfolio,
        "integrity_health": integrity,
        "health_ledger": ledger_status,  # --append-health-ledger 없으면 None
        "weekly_return": None,  # 결정론 산출 불가(위 note 참조)
        "notes": notes,
    }
    print(json.dumps(out, ensure_ascii=False))
    # 회의록·체결이 하나도 없으면(되짚을 사건 부재) exit 1로 신호.
    return 0 if (minutes["count"] or fills["count"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
