#!/usr/bin/env python3
"""권위 있는 현재 시세 fetcher — 진입가/손절가의 '앵커'를 결정론적으로 제공한다.

왜 필요한가:
- analyze-company의 웹검색 리서처는 현재가를 출처마다 다르게 물어와(예: 170,200 vs 140,600)
  엉뚱한 값을 단독 채택하는 사고가 있었다(2026-06-30 기아 검증에서 실증).
- 진입/손절은 '지금 실제 시세'에 붙어야 의미가 있으므로, 현재가·52주 고저는
  웹검색 내러티브가 아니라 네이버 금융 개별 종목 페이지에서 직접 읽어 확정한다.
- 컨센서스 목표주가·뉴스·거시 같은 '정성' 정보는 여전히 웹검색(서브에이전트)의 몫.

사용:  python3 quote.py --code 000270        # 코드로 (권장, 가장 안정적)
       python3 quote.py --name 기아          # 이름으로 (best-effort 코드 변환)
출력:  {"code","name","price","week52_high","week52_low","volume"} JSON
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
ITEM = "https://finance.naver.com/item/main.nhn?code={code}"
AUTOCOMPLETE = "https://m.stock.naver.com/front-api/search/autoComplete?query={q}&target=stock"


def _get(url: str, encoding: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode(encoding, errors="replace")


def _num(s):
    if not s:
        return None
    s = str(s).replace(",", "").strip()
    return float(s) if re.fullmatch(r"\d+(\.\d+)?", s) else None


def _find(pattern: str, text: str):
    m = re.search(pattern, text)
    return _num(m.group(1)) if m else None


def resolve_code(name: str) -> str | None:
    """이름 → 6자리 코드. 네이버 모바일 autoComplete에서 국내(KOSPI/KOSDAQ) 첫 종목. best-effort."""
    try:
        data = json.loads(_get(AUTOCOMPLETE.format(q=urllib.parse.quote(name)), "utf-8"))
    except Exception:
        return None
    items = (data.get("result") or {}).get("items") or []
    domestic = [it for it in items if it.get("typeCode") in ("KOSPI", "KOSDAQ")]
    exact = [it for it in domestic if it.get("name") == name]
    pick = (exact or domestic or None)
    return pick[0]["code"] if pick else None


def fetch_quote(code: str) -> dict | None:
    html = _get(ITEM.format(code=code), "utf-8")          # 개별 페이지는 UTF-8
    flat = re.sub(r"<[^>]+>", " ", html)                  # 52주 고저는 태그 사이에 걸쳐 있어 평문화 후 매칭
    price = _find(r"현재가[^0-9]*([\d,]{3,})", html)
    name = (re.search(r"<title>([^:<]+)", html) or [None, ""])[1].strip() or None
    hi = _find(r"52주\s*최고\s*[:：]?\s*([\d,]+)", flat)
    lo = _find(r"52주\s*최저\s*[:：]?\s*([\d,]+)", flat)
    vol = _find(r"거래량[^0-9]*([\d,]{3,})", html)
    if price is None:
        return None
    return dict(code=code, name=name, price=price,
                week52_high=hi, week52_low=lo, volume=vol)


def main() -> int:
    ap = argparse.ArgumentParser(description="네이버 권위 시세 (현재가·52주 고저)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--code", help="6자리 종목코드 (권장)")
    g.add_argument("--name", help="종목명 (best-effort 코드 변환)")
    args = ap.parse_args()

    code = args.code or resolve_code(args.name)
    if not code:
        print(json.dumps({"error": f"코드를 찾지 못함: {args.name}"}, ensure_ascii=False))
        return 1
    q = fetch_quote(code)
    if not q:
        print(json.dumps({"error": f"시세를 읽지 못함: {code}"}, ensure_ascii=False))
        return 1
    print(json.dumps(q, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
