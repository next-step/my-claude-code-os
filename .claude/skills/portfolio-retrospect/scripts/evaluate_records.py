#!/usr/bin/env python3
"""회고 1단계 — 과거 분석 기록을 현재가와 대조해 status·실제수익률을 *결정론적으로* 확정한다.

설계(OS.md 회고 스킬):
- "목표 도달/손절 닿음" 같은 사실 판정은 토론(서브에이전트)이 아니라 *계산*이다.
  현재가 vs 진입/목표/손절을 비교하는 산수라, 정성 해석과 분리해 여기서 못 박는다.
  (OS 철학: 정성 해석=서브에이전트, 정밀 수치=결정론적 스크립트.)
- 현재가는 analyze-company의 quote.py 를 *재사용*한다(진실원천 한 곳, 드리프트 방지).
- 이 스크립트는 read-only다. status를 파일에 쓰는 건 update_status.py 의 몫(관심사 분리).
- 출력(stdout) JSON 을 토론 전문가들에게 '사실표'로 넘긴다.

status 판정 규칙:
- 터미널 상태(hit_target|stopped)는 **sticky**다 — 한 번 도달/손절이면 되돌리지 않는다.
  *왜:* 예측의 성패는 한 번 일어난 '사건'이다. 목표 찍고 다시 내려와도 "그땐 맞았다"가 진실.
  (주1회 스냅샷이라 실행 사이의 장중 돌파는 놓칠 수 있다 — 알려진 한계, 주기를 좁히면 줄어듦.)
- open/watching 만 재평가: 현재가 ≥ 목표 → hit_target / 현재가 ≤ 손절 → stopped / 그 사이 → watching.
- 진입·목표·손절이 "산출 불가"였던 기록은 평가 불가 → status 그대로, 사유 표기.

수익률 — '미체결 진입갭'과 '체결가정 수익'을 분리한다(회의론자 회고 피드백 2026-06-30):
- entry_gap_pct = (분석시점가 − 진입가)/진입가 — *구조적·고정값*. "진입가를 현재가보다 얼마나 아래(+)
  /위(−)에 뒀나"(눌림목 대기 폭). 경과일과 무관하며 성과가 아니다. (예전 actual_return_pct 가 0일차에
  실제로 잰 게 이것 — 성과로 오독되던 값을 이 이름으로 정직하게 박는다.)
- return_if_filled_pct = (현재가 − 진입가)/진입가 — *체결을 가정한* 수익. entry_filled 가 참일 때만 의미.
- entry_filled = 분석일 이후 일중 저가가 진입가 이하로 내려와 '체결 가정'이 성립했나(ohlcv 경과구간).
- mfe_pct / mae_pct = 체결 이후 최대 유리/불리 폭(휩쏘에 털렸는지 사후 판정). 미체결이면 null.
- atr_pct_at_analysis = 진입 시점 변동성 스냅샷(분석 frontmatter atr_pct). 손절폭/ATR 사후 재현용.

사용:  python3 evaluate_records.py                 # data/analyses 전체 평가
       python3 evaluate_records.py --no-fetch      # 현재가·ohlcv 조회 생략(오프라인 — status 미판정)
       python3 evaluate_records.py --no-ohlcv      # 현재가만 조회, 경과구간 ohlcv(체결/MFE/MAE) 생략
출력:  {"as_of","evaluated":[...],"excluded_context":[...],"summary":{...},"errors":[...]} JSON
  - summary.by_context 로 standalone(개별 분석)과 recommend-stocks(추천 바스켓)를 분리 집계한다
    (선정 논리가 다른 표본을 한 통계로 섞으면 배점 예측력 검증이 왜곡된다 — 펀더멘털 회고 피드백).
"""
from __future__ import annotations
import argparse
import datetime
import glob
import importlib.util
import json
import os
import re
import sys

ANALYSES_DIR = os.path.join(os.getcwd(), "data", "analyses")
REC_DIR = os.path.join(os.getcwd(), "data", "recommendations")

# analyze-company 의 quote.py / ohlcv.py 를 재사용(수치의 단일 진실원천). 경로는 이 파일 기준 상대.
_AC_SCRIPTS = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "analyze-company", "scripts"))
_QUOTE = os.path.join(_AC_SCRIPTS, "quote.py")
_OHLCV = os.path.join(_AC_SCRIPTS, "ohlcv.py")


def _load_module(path: str, name: str):
    """analyze-company 스크립트를 모듈로 로드해 함수를 빌려 쓴다. 실패하면 None(그 기능만 비활성)."""
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    except Exception:
        return None


def _load_quote():
    """quote.py 모듈(fetch_quote/resolve_code). 실패하면 None."""
    return _load_module(_QUOTE, "quote")


def _load_ohlcv():
    """ohlcv.py 모듈(fetch_ohlcv). 실패하면 None — 체결/MFE/MAE 만 비활성, status 판정은 유지."""
    return _load_module(_OHLCV, "ohlcv")


def _excursion(ohlcv_mod, code, analysis_date, as_of, entry, cache: dict) -> dict:
    """경과 구간 [analysis_date..as_of] 의 일별 OHLCV로 진입 체결 여부·MFE/MAE를 결정론적으로 산출.

    - entry_filled: 분석일 이후 어느 거래일이든 저가 ≤ 진입가면 '체결 가정' 성립(True).
    - mfe_pct/mae_pct: 체결일 이후 (최고가/최저가 − 진입가)/진입가 — 휩쏘에 털렸는지 사후 판정용.
    조회 실패·데이터 없음·진입가 없음이면 모두 None(판정 보류, 크래시 금지)."""
    res = {"entry_filled": None, "mfe_pct": None, "mae_pct": None}
    if ohlcv_mod is None or not code or entry is None:
        return res
    bars = cache.get(code)
    if bars is None:
        elapsed = (as_of - analysis_date).days if analysis_date else 0
        # 경과 달력일 → 거래일 여유분(+주말분)으로 넉넉히, 최소 12거래일.
        want = max(int((elapsed or 0) * 5 / 7) + 6, 12)
        try:
            bars = ohlcv_mod.fetch_ohlcv(code, days=want) or []
        except Exception:
            bars = []
        cache[code] = bars
    if not bars:
        return res
    start = analysis_date.isoformat() if analysis_date else None
    win = [b for b in bars if start is None or b["date"].replace(".", "-") >= start]
    if not win:
        return res
    fill_idx = next((i for i, b in enumerate(win) if b.get("low") is not None and b["low"] <= entry), None)
    res["entry_filled"] = fill_idx is not None
    if fill_idx is None:
        return res
    post = win[fill_idx:]
    hi = max(b["high"] for b in post)
    lo = min(b["low"] for b in post)
    res["mfe_pct"] = round((hi - entry) / entry * 100, 1)
    res["mae_pct"] = round((lo - entry) / entry * 100, 1)
    return res


def _parse_frontmatter(text: str) -> dict:
    """save_analysis.py 가 쓴 frontmatter(평평한 key: value)를 dict 로. (save_run 의 파서와 동일 방식)"""
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z_0-9]+):\s*(.*)$", line)
        if mm:
            fm[mm.group(1)] = mm.group(2).strip().strip('"')
    return fm


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _judge(prev_status: str, cur: float | None,
           target: float | None, stop: float | None) -> tuple[str, str]:
    """(새 status, 사유). 터미널 상태는 sticky."""
    if prev_status in ("hit_target", "stopped"):
        return prev_status, "이미 확정된 사건(sticky) — 되돌리지 않음"
    if cur is None:
        return prev_status or "open", "현재가 미조회 — 판정 보류"
    if target is None and stop is None:
        return prev_status or "open", "진입/목표/손절 산출 불가 — 평가 불가"
    if target is not None and cur >= target:
        return "hit_target", f"현재가 {cur:g} ≥ 목표 {target:g}"
    if stop is not None and cur <= stop:
        return "stopped", f"현재가 {cur:g} ≤ 손절 {stop:g}"
    lo = f"{stop:g}" if stop is not None else "?"
    hi = f"{target:g}" if target is not None else "?"
    return "watching", f"현재가 {cur:g} (손절 {lo}~목표 {hi} 사이)"


def _days(date_str: str, as_of: datetime.date) -> int | None:
    try:
        d = datetime.date.fromisoformat(date_str)
        return (as_of - d).days
    except (ValueError, TypeError):
        return None


def evaluate(quote_mod, ohlcv_mod, as_of: datetime.date, fetch: bool) -> dict:
    out = {"as_of": as_of.isoformat(), "evaluated": [],
           "excluded_context": [], "errors": []}
    ohlcv_cache: dict = {}                    # 종목별 OHLCV 1회만 조회

    files = sorted(glob.glob(os.path.join(ANALYSES_DIR, "*.md")))
    if not files:
        out["errors"].append(f"분석 기록이 없다: {ANALYSES_DIR} (먼저 analyze-company 를 돌려 기록을 쌓아야 회고할 게 생긴다)")

    seen_codes: dict[str, dict] = {}  # 종목별 현재가 캐시(같은 종목 여러 기록이면 1회만 조회)

    def current_price(code, name):
        if not fetch or quote_mod is None:
            return None
        key = code or name
        if key in seen_codes:
            return seen_codes[key].get("price")
        q = None
        try:
            c = code or quote_mod.resolve_code(name)
            q = quote_mod.fetch_quote(c) if c else None
        except Exception as e:  # 네트워크/파싱 실패는 그 종목만 건너뛴다
            out["errors"].append(f"현재가 조회 실패({name or code}): {e}")
        seen_codes[key] = q or {}
        return (q or {}).get("price")

    for path in files:
        text = open(path, encoding="utf-8").read()
        fm = _parse_frontmatter(text)
        ref = os.path.relpath(path, os.getcwd())
        name, code = fm.get("name", ""), fm.get("code", "")
        entry = _num(fm.get("entry"))
        target = _num(fm.get("target"))
        stop = _num(fm.get("stop"))
        price0 = _num(fm.get("price"))           # 분석 당시 현재가(수익률 폴백 기준)
        prev = fm.get("status", "open")

        cur = current_price(code, name)
        new_status, reason = _judge(prev, cur, target, stop)

        try:
            analysis_date = datetime.date.fromisoformat(fm.get("date", ""))
        except (ValueError, TypeError):
            analysis_date = None

        # 진입갭(구조적·고정) vs 체결가정 수익(현재가 의존)을 분리해 성과 오독을 막는다.
        entry_gap_pct = None
        if entry and price0 is not None:
            entry_gap_pct = round((price0 - entry) / entry * 100, 1)
        return_if_filled_pct = None
        if entry and cur is not None:
            return_if_filled_pct = round((cur - entry) / entry * 100, 1)

        # 경과 구간 OHLCV로 진입 체결·MFE/MAE 산출(ohlcv_mod None 이면 전부 null — self-guard).
        exc = _excursion(ohlcv_mod, code, analysis_date, as_of, entry, ohlcv_cache)

        out["evaluated"].append({
            "file": ref, "date": fm.get("date", ""), "name": name, "code": code,
            "context": fm.get("context", ""),
            "entry": entry, "target": target, "stop": stop,
            "expected_return_pct": _num(fm.get("expected_return_pct")),
            "atr_pct_at_analysis": _num(fm.get("atr_pct")),
            "price_at_analysis": price0, "current_price": cur,
            "prev_status": prev, "new_status": new_status, "status_changed": new_status != prev,
            "judge_reason": reason,
            "entry_gap_pct": entry_gap_pct,
            "entry_filled": exc["entry_filled"],
            "return_if_filled_pct": return_if_filled_pct,
            "mfe_pct": exc["mfe_pct"], "mae_pct": exc["mae_pct"],
            "days_elapsed": _days(fm.get("date", ""), as_of),
        })

    # 추천 탈락 표본: 회고에서 "빠뜨린 종목이 올랐나" 점검용 맥락. 단 탈락 당시 가격이 기록에
    # 없어 정량 수익률은 못 낸다(현재가만 제공). → 전문가가 정성으로 판단한다(알려진 한계).
    for rpath in sorted(glob.glob(os.path.join(REC_DIR, "*.md"))):
        rtext = open(rpath, encoding="utf-8").read()
        for name, why in re.findall(r"^-\s*([^:]+):\s*(.+)$", rtext, re.M):
            nm = name.strip()
            if nm and len(nm) <= 20:  # 본문 '탈락 표본' 불릿만 대략 추림
                cur = current_price(None, nm)
                out["excluded_context"].append({
                    "name": nm, "exclude_reason": why.strip(),
                    "current_price": cur, "run_file": os.path.relpath(rpath, os.getcwd()),
                    "note": "탈락 당시 가격 미기록 → 등락 정량비교 불가(정성 점검)",
                })

    # 집계 요약(전문가·리포트가 바로 쓰도록).
    ev = out["evaluated"]
    out["summary"] = {
        **_track_summary(ev),
        "status_changes": [e for e in ev if e["status_changed"]],
        # standalone(개별)과 recommend-stocks(바스켓)는 선정 논리가 달라 분리 집계한다.
        "by_context": {ctx: _track_summary(rows)
                       for ctx, rows in sorted(_group_by_context(ev).items())},
    }
    return out


def _group_by_context(rows: list[dict]) -> dict:
    g: dict[str, list] = {}
    for e in rows:
        g.setdefault(e.get("context") or "uncategorized", []).append(e)
    return g


def _avg(vals: list[float]):
    return round(sum(vals) / len(vals), 1) if vals else None


def _track_summary(rows: list[dict]) -> dict:
    """한 묶음의 status 분포 + '진입갭(구조)'·'체결가정 수익(체결분만)'을 분리 집계.
    평균 진입갭은 성과가 아니라 '진입가를 얼마나 아래 뒀나'이고, 평균 체결수익은 entry_filled 분만 센다."""
    gaps = [e["entry_gap_pct"] for e in rows if e.get("entry_gap_pct") is not None]
    filled = [e["return_if_filled_pct"] for e in rows
              if e.get("entry_filled") and e.get("return_if_filled_pct") is not None]
    return {
        "total": len(rows),
        "hit_target": sum(1 for e in rows if e["new_status"] == "hit_target"),
        "stopped": sum(1 for e in rows if e["new_status"] == "stopped"),
        "watching": sum(1 for e in rows if e["new_status"] == "watching"),
        "open_or_unrated": sum(1 for e in rows if e["new_status"] == "open"),
        "entry_filled_count": sum(1 for e in rows if e.get("entry_filled")),
        "avg_entry_gap_pct": _avg(gaps),               # 구조적 — 성과 아님
        "avg_return_if_filled_pct": _avg(filled),      # 체결 가정 수익(체결분만)
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="회고 1단계: 분석 기록 vs 현재가 사실 판정")
    ap.add_argument("--no-fetch", action="store_true", help="현재가·ohlcv 조회 생략(오프라인/테스트)")
    ap.add_argument("--no-ohlcv", action="store_true",
                    help="현재가는 조회하되 경과구간 ohlcv(체결/MFE/MAE)는 생략(빠른 실행)")
    ap.add_argument("--as-of", help="기준일 YYYY-MM-DD (생략 시 오늘)")
    args = ap.parse_args()

    as_of = datetime.date.fromisoformat(args.as_of) if args.as_of else datetime.date.today()
    quote_mod = None if args.no_fetch else _load_quote()
    if not args.no_fetch and quote_mod is None:
        # quote.py 를 못 불러오면 현재가 없이라도 기록 목록은 내보낸다(판정만 보류).
        print(json.dumps({"warning": f"quote.py 로드 실패: {_QUOTE} — 현재가 없이 진행"},
                         ensure_ascii=False), file=sys.stderr)
    # ohlcv 는 현재가가 있을 때만(=온라인) 의미. --no-ohlcv 면 체결/MFE/MAE 만 끈다.
    ohlcv_mod = None if (args.no_fetch or args.no_ohlcv) else _load_ohlcv()
    result = evaluate(quote_mod, ohlcv_mod, as_of, fetch=not args.no_fetch and quote_mod is not None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
