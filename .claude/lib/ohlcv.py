#!/usr/bin/env python3
"""일별 OHLCV(시·고·저·종·거래량) fetcher + 지지/저항·변동성 계산기.

왜 필요한가(OS.md 보강):
- 진입/손절의 근거가 그동안 '52주 고저'에만 의존해 약했다. 실제 차트의 지지/저항은
  최근 봉들의 스윙 고/저에서 나오므로, 일별 OHLCV가 있어야 결정론적으로 계산된다.
- 변동성(얼마나 출렁이나)도 일별 수익률에서 나온다 → recommend-stocks 2차 점수의 '변동성 가점'에 재사용.
- 소스 = 네이버 일별 시세(finance.naver.com/item/sise_day, EUC-KR). 정성 정보가 아니라
  '정밀 수치'이므로 웹검색이 아니라 스크립트로 직접 읽는다(quote.py 와 같은 철학).

이 파일은 CLI로도(analyze-company), import 모듈로도(score_stocks의 변동성 가점) 쓴다.

사용:  python3 ohlcv.py --code 000270 --days 250
출력:  {"code","days","last_close","support":[{level,touches}],"resistance":[...],
        "realized_vol_pct","atr_pct","period_high","period_low"}
"""
from __future__ import annotations
import argparse
import json
import math
import re
import sys
import time
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
SISE_DAY = "https://finance.naver.com/item/sise_day.nhn?code={code}&page={page}"


def fetch_ohlcv(code: str, days: int = 250, sleep: float = 0.15) -> list[dict]:
    """최근 `days` 거래일의 OHLCV를 과거→현재 순으로 반환. 1페이지=10거래일."""
    pages = max(1, math.ceil(days / 10))
    out: list[dict] = []
    for page in range(1, pages + 1):
        req = urllib.request.Request(SISE_DAY.format(code=code, page=page),
                                     headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                html = r.read().decode("euc-kr", errors="replace")
        except Exception:
            break
        rows = re.findall(
            r'<td align="center"><span[^>]*>(\d{4}\.\d{2}\.\d{2})</span></td>'
            r'(.*?)(?=<td align="center">|</table>)', html, re.S)
        if not rows:
            break
        for date, blk in rows:
            nums = [n.replace(",", "")
                    for n in re.findall(r'class="tah p11[^"]*">\s*([\d,]+)\s*<', blk)]
            if len(nums) < 6:                      # [종가, 전일비, 시가, 고가, 저가, 거래량]
                continue
            out.append(dict(date=date, close=float(nums[0]), open=float(nums[2]),
                            high=float(nums[3]), low=float(nums[4]), volume=float(nums[5])))
        time.sleep(sleep)
    out.reverse()                                   # 과거 → 현재
    return out[-days:]


def _cluster(vals: list[float], tol: float) -> list[tuple[float, int]]:
    """비슷한 가격대(상대오차 tol 이내)를 하나로 묶어 (대표가, 터치횟수)로. 여러 번 닿은 곳이 강한 레벨."""
    if not vals:
        return []
    vals = sorted(vals)
    groups = [[vals[0]]]
    for v in vals[1:]:
        if abs(v - groups[-1][-1]) / groups[-1][-1] <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [(round(sum(g) / len(g)), len(g)) for g in groups]


def compute_levels(rows: list[dict], k: int = 5, tol: float = 0.02, max_each: int = 3,
                   last_close: float | None = None, recent: int = 20) -> dict:
    """스윙 고/저(국소 극값)를 모아 군집화 → 현재가 위는 저항, 아래는 지지. 가까운 순.

    피벗만으로는 (a)최근 고/저는 앞쪽 k일 확인이 안 돼 빠지고 (b)창 경계의 전체 고/저도 빠진다.
    진입·손절엔 바로 그 '최근 저점/고점'이 제일 중요하므로 전체·최근 구간의 고저를 후보에 보강한다.
    """
    if len(rows) < 2 * k + 1:
        return dict(support=[], resistance=[])
    highs = [r["high"] for r in rows]
    lows = [r["low"] for r in rows]
    piv_hi, piv_lo = [], []
    for i in range(k, len(rows) - k):
        if highs[i] == max(highs[i - k:i + k + 1]):
            piv_hi.append(highs[i])
        if lows[i] == min(lows[i - k:i + k + 1]):
            piv_lo.append(lows[i])
    piv_hi += [max(highs), max(highs[-recent:])]      # 전체 고점 + 최근 구간 고점 보강
    piv_lo += [min(lows), min(lows[-recent:])]        # 전체 저점 + 최근 구간 저점 보강
    last = last_close if last_close is not None else rows[-1]["close"]
    res = [c for c in _cluster(piv_hi, tol) if c[0] > last]
    sup = [c for c in _cluster(piv_lo, tol) if c[0] < last]
    res.sort(key=lambda c: c[0] - last)             # 현재가 바로 위부터
    sup.sort(key=lambda c: last - c[0])             # 현재가 바로 아래부터
    fmt = lambda lst: [dict(level=c[0], touches=c[1]) for c in lst[:max_each]]
    return dict(support=fmt(sup), resistance=fmt(res))


def compute_volatility(rows: list[dict], atr_period: int = 14) -> dict:
    """일별 수익률 표준편차(연율화)와 ATR%(평균진폭). 둘 다 '얼마나 출렁이나'의 척도."""
    if len(rows) < 3:
        return dict(realized_vol_pct=None, atr_pct=None)
    closes = [r["close"] for r in rows]
    rets = [math.log(closes[i] / closes[i - 1])
            for i in range(1, len(closes)) if closes[i - 1] > 0]
    realized = None
    if len(rets) >= 2:
        mean = sum(rets) / len(rets)
        var = sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)
        realized = round(math.sqrt(var) * math.sqrt(252) * 100, 1)   # 연율화 %
    trs = []
    for i in range(1, len(rows)):
        h, l, pc = rows[i]["high"], rows[i]["low"], rows[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr_pct = None
    if trs:
        atr = sum(trs[-atr_period:]) / len(trs[-atr_period:])
        atr_pct = round(atr / closes[-1] * 100, 2)
    return dict(realized_vol_pct=realized, atr_pct=atr_pct)


def analyze(code: str, days: int = 250) -> dict | None:
    rows = fetch_ohlcv(code, days)
    if not rows:
        return None
    last = rows[-1]["close"]
    out = dict(code=code, days=len(rows), last_close=last,
               period_high=max(r["high"] for r in rows),
               period_low=min(r["low"] for r in rows))
    out.update(compute_levels(rows, last_close=last))
    out.update(compute_volatility(rows))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="네이버 일별 OHLCV → 지지/저항·변동성")
    ap.add_argument("--code", required=True, help="6자리 종목코드")
    ap.add_argument("--days", type=int, default=250, help="거래일 수(기본 250≈1년)")
    args = ap.parse_args()
    res = analyze(args.code, args.days)
    if not res:
        print(json.dumps({"error": f"OHLCV를 읽지 못함: {args.code}"}, ensure_ascii=False))
        return 1
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
