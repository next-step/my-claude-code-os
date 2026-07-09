#!/usr/bin/env python3
"""국면 지표(정량) 산출기 — 지수(코스피/코스닥)·개별 종목의 3축 국면을 결정론으로.

왜 필요한가(OS.md·daily-trading-loop Q12~Q15 보강):
- 위원회 국면 토론(항목 7)이 딛을 결정론적 '사실판'이 없었다. 이 스크립트가 국면을
  정량 3축으로만 산출하면, 위원회가 그 위에 서술 라벨('상승장 후반부' 등)을 붙인다.
  → 스크립트는 지표까지, 라벨은 위원회(하이브리드 역할, C1). "정밀 수치는 스크립트,
    해석은 토론"과 정합.

국면 3축(market-glossary "시장 국면 — 표준 3축"과 정합):
- ① 추세: 이동평균 배열(정배열/역배열)과 기울기(%). "방향이 위/아래인가, 얼마나 가파른가".
- ② 사이클 위치: 52주 고저 대비 현재가 위치(%)와 신고가/신저가 여부. "사이클 어느 단계인가".
- ③ 변동성: ATR%·연율 변동성(realized_vol_pct). ohlcv.py `compute_volatility` 재사용.

대상(C2):
- 지수(코스피/코스닥) = 배경 국면. 지수는 종목코드가 없어 ohlcv.py per-종목 fetch로는 못 읽어,
  네이버 지수 전용 소스(api.finance.naver.com/siseJson.naver, 지수 OHLC JSON)에서 읽는다.
- 보유·관심 종목 = 각 종목 국면. ohlcv.py `fetch_ohlcv`(네이버 sise_day) 재사용.

산출 스키마(C3): 정량 필드만. 서술 라벨은 붙이지 않는다. 회고가 과거 국면을 정량 비교할 앵커.

사용:
  python3 market_regime.py --index KOSPI KOSDAQ
  python3 market_regime.py --code 005930 000660
  python3 market_regime.py --index KOSPI --code 005930 --days 250
출력: 대상 1개면 객체, 여러 개면 배열(JSON, 한 줄).
"""
from __future__ import annotations
import argparse
import datetime as _dt
import json
import os
import re
import sys
import urllib.request

# ── ohlcv.py(.claude/lib) 재사용: 종목 fetch·변동성 계산은 복붙하지 않고 import ─────────
_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    ".claude", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
import ohlcv  # noqa: E402  (fetch_ohlcv, compute_volatility)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
# 지수 일별 OHLC(JSON). 종목 sise_day와 달리 지수는 이 소스가 시·고·저·종을 다 준다.
INDEX_JSON = ("https://api.finance.naver.com/siseJson.naver"
              "?symbol={symbol}&requestType=1&startTime={start}&endTime={end}&timeframe=day")
INDEX_SYMBOLS = {"KOSPI": "KOSPI", "KOSDAQ": "KOSDAQ"}


# ── 지수 소스 ────────────────────────────────────────────────────────────────────
def parse_index_json(text: str) -> list[dict]:
    """siseJson 응답(엄격 JSON 아님 — 헤더 행 + 데이터 행)에서 OHLC 행만 정규식으로 뽑는다.

    한 데이터 행: ["YYYYMMDD", 시가, 고가, 저가, 종가, 거래량, 외국인소진율]
    날짜·수치는 인코딩과 무관하게 ASCII라, ohlcv.py 스타일(정규식 파싱)로 결정론 처리한다.
    """
    rows: list[dict] = []
    for m in re.finditer(
            r'\["(\d{8})",\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*(\d+)', text):
        d, o, h, l, c, v = m.groups()
        rows.append(dict(date=f"{d[:4]}.{d[4:6]}.{d[6:]}", open=float(o), high=float(h),
                         low=float(l), close=float(c), volume=float(v)))
    return rows


def fetch_index(symbol: str, days: int = 250) -> list[dict]:
    """지수 최근 `days` 거래일 OHLC를 과거→현재 순으로. 네트워크 실패 시 빈 리스트."""
    end = _dt.date.today()
    start = end - _dt.timedelta(days=int(days * 1.9) + 30)  # 휴장 감안 넉넉히
    url = INDEX_JSON.format(symbol=INDEX_SYMBOLS[symbol],
                            start=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            text = r.read().decode("euc-kr", errors="replace")
    except Exception:
        return []
    rows = parse_index_json(text)
    return rows[-days:]


# ── 3축 국면 지표(지수·종목 공통 — 둘 다 OHLC 리스트를 받는다) ──────────────────────────
def _sma(vals: list[float], n: int) -> float | None:
    return round(sum(vals[-n:]) / n, 2) if len(vals) >= n else None


def compute_trend(rows: list[dict], mas=(20, 60, 120), slope_win: int = 20) -> dict:
    """① 추세: 이동평균 배열(정배열/역배열/혼조)과 MA20 기울기(%). 방향·강도를 정량으로."""
    closes = [r["close"] for r in rows]
    last = closes[-1]
    ma = {n: _sma(closes, n) for n in mas}
    short, mid, long = (ma[n] for n in mas)
    arrangement = None
    if None not in (short, mid, long):
        if short > mid > long:
            arrangement = "정배열"
        elif short < mid < long:
            arrangement = "역배열"
        else:
            arrangement = "혼조"
    # MA20 기울기: slope_win 거래일 전 MA20 대비 현재 MA20 변화율(%).
    slope_pct = None
    n0 = mas[0]
    if len(closes) >= n0 + slope_win:
        ma_now = sum(closes[-n0:]) / n0
        ma_prev = sum(closes[-n0 - slope_win:-slope_win]) / n0
        if ma_prev:
            slope_pct = round((ma_now - ma_prev) / ma_prev * 100, 2)
    return dict(
        ma={f"ma{n}": ma[n] for n in mas},
        arrangement=arrangement,
        price_vs_ma_short_pct=(round((last - short) / short * 100, 2) if short else None),
        ma_short_slope_pct=slope_pct,
    )


def compute_cycle(rows: list[dict]) -> dict:
    """② 사이클 위치: 52주(=창 전체) 고저 대비 현재가 위치(%)와 신고가/신저가."""
    highs = [r["high"] for r in rows]
    lows = [r["low"] for r in rows]
    closes = [r["close"] for r in rows]
    last = closes[-1]
    hi, lo = max(highs), min(lows)
    position_pct = round((last - lo) / (hi - lo) * 100, 1) if hi > lo else None
    return dict(
        period_high=hi,
        period_low=lo,
        position_pct=position_pct,           # 0=저점권, 100=고점권
        new_high=bool(last >= max(closes)),  # 창 안 최고 종가 갱신
        new_low=bool(last <= min(closes)),   # 창 안 최저 종가 갱신
    )


def compute_regime(rows: list[dict]) -> dict:
    """3축(추세·사이클·변동성)을 한 번에. 변동성은 ohlcv.py compute_volatility 재사용."""
    return dict(
        last_close=rows[-1]["close"],
        asof=rows[-1]["date"],
        trend=compute_trend(rows),
        cycle=compute_cycle(rows),
        volatility=ohlcv.compute_volatility(rows),
    )


# ── 대상별 분석 ──────────────────────────────────────────────────────────────────
def analyze_index(symbol: str, days: int = 250) -> dict:
    rows = fetch_index(symbol, days)
    base = dict(target=symbol, kind="index",
                source="네이버 지수 시세(api.finance.naver.com/siseJson, 지수 OHLC)")
    if not rows:
        return {**base, "error": f"지수 시세를 읽지 못함: {symbol}"}
    return {**base, "days": len(rows), **compute_regime(rows)}


def analyze_stock(code: str, days: int = 250) -> dict:
    rows = ohlcv.fetch_ohlcv(code, days)
    base = dict(target=code, kind="stock",
                source="네이버 일별 시세(ohlcv.py, sise_day)")
    if not rows:
        return {**base, "error": f"OHLCV를 읽지 못함: {code}"}
    return {**base, "days": len(rows), **compute_regime(rows)}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="지수·종목 국면 지표(정량 3축: 추세·사이클 위치·변동성) 산출")
    ap.add_argument("--index", nargs="*", default=[], choices=sorted(INDEX_SYMBOLS),
                    help="지수 심볼(KOSPI/KOSDAQ), 여러 개 가능")
    ap.add_argument("--code", nargs="*", default=[], help="6자리 종목코드, 여러 개 가능")
    ap.add_argument("--days", type=int, default=250, help="거래일 수(기본 250≈52주)")
    args = ap.parse_args()
    if not args.index and not args.code:
        ap.error("--index 또는 --code 중 하나는 지정해야 합니다.")

    results = [analyze_index(s, args.days) for s in args.index]
    results += [analyze_stock(c, args.days) for c in args.code]
    out = results[0] if len(results) == 1 else results
    print(json.dumps(out, ensure_ascii=False))
    return 0 if any("error" not in r for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
