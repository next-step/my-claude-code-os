#!/usr/bin/env python3
"""
리밸런싱 계산기 — stock-os의 리밸런싱 단계에서 쓰는 결정론적 계산 도구.

하는 일:
  1) portfolio.md         → 종목별 목표비중(%)
  2) portfolio.private.md → 종목별 보유수량 + 예수금 + 총 투자원금
  3) 야후 파이낸스에서 각 종목 현재가 조회 (한국 종목은 티커.KS)
  4) 평가액·현재비중·목표대비 갭·리밸런싱 수량을 계산해 표로 출력

값을 파일에 저장하지 않는다(현재가는 매일 변하는 파생값). 실행할 때마다 최신으로 계산해 보여줄 뿐.
실제 매매는 사용자가 한다. 이 출력은 투자 권유가 아니라 사실·계산 전달이다.

사용:  python3 .claude/scripts/rebalance.py
"""
import json
import math
import re
import ssl
import sys
import urllib.request
from pathlib import Path

try:  # macOS Python.org 빌드는 시스템 인증서를 못 찾을 때가 있어 certifi로 우회
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL = ssl.create_default_context()

ROOT = Path(__file__).resolve().parents[4]  # scripts→rebalance→skills→.claude→프로젝트루트
PORTFOLIO = ROOT / "portfolio.md"
PRIVATE = ROOT / "portfolio.private.md"


def num(s: str):
    """'₩24,286,525' / '26,310' / '+13.52%' → float. 실패하면 None."""
    if s is None:
        return None
    s = re.sub(r"[₩,%\s+]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def table_rows(path: Path):
    """마크다운 표의 데이터 행을 셀 리스트로 돌려준다(구분선·헤더 제외)."""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):  # |---|---| 구분선
            continue
        yield cells


def parse_targets():
    """portfolio.md → {code: 목표비중%}. 행 형식: 종목 | 코드 | 목표비중 | 자산군"""
    out = {}
    for cells in table_rows(PORTFOLIO):
        for i, c in enumerate(cells):
            if re.fullmatch(r"\d{6}", c):
                t = num(cells[i + 1]) if i + 1 < len(cells) else None
                if t is not None:
                    out[c] = t
                break
    return out


def parse_holdings():
    """portfolio.private.md → (holdings{code:(name,qty)}, 예수금, 총원금)."""
    holdings, cash, principal = {}, 0.0, None
    for line in PRIVATE.read_text(encoding="utf-8").splitlines():
        m = re.search(r"총\s*투자원금.*?([\d,]+)", line)
        if m:
            principal = num(m.group(1))
    for cells in table_rows(PRIVATE):
        joined = " ".join(cells)
        if "예수금" in joined:
            for c in reversed(cells):
                v = num(c)
                if v is not None:
                    cash = v
                    break
            continue
        for i, c in enumerate(cells):
            if re.fullmatch(r"\d{6}", c):
                name = cells[i - 1] if i > 0 else c
                qty = num(cells[i + 1]) if i + 1 < len(cells) else None
                if qty is not None:
                    holdings[c] = (name, qty)
                break
    return holdings, cash, principal


def fetch_price(code: str):
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{code}.KS?interval=1d&range=1d"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15, context=_SSL) as r:
        data = json.load(r)
    return float(data["chart"]["result"][0]["meta"]["regularMarketPrice"])


def main():
    targets = parse_targets()
    holdings, cash, principal = parse_holdings()
    if not holdings:
        sys.exit("보유 종목을 못 읽었다. portfolio.private.md 형식을 확인하라.")

    prices, errors = {}, []
    for code in holdings:
        try:
            prices[code] = fetch_price(code)
        except Exception as e:  # noqa: BLE001
            errors.append((code, str(e)))

    values = {c: prices[c] * holdings[c][1] for c in prices}
    total = sum(values.values()) + cash

    rows = []
    for code, (name, qty) in holdings.items():
        if code not in prices:
            continue
        val = values[code]
        cur_w = val / total * 100
        tgt_w = targets.get(code, 0.0)
        tgt_val = tgt_w * total / 100
        gap = cur_w - tgt_w
        delta_shares = math.floor((tgt_val - val) / prices[code])  # 시트 컨벤션: 내림
        rows.append((name, code, prices[code], int(qty), val, cur_w, tgt_w, gap, delta_shares))

    w = max(len(r[0]) for r in rows)
    print(f"\n{'종목':<{w}}  {'현재가':>9} {'수량':>4} {'평가액':>12} "
          f"{'현재%':>6} {'목표%':>6} {'갭%p':>6} {'매매':>5}")
    print("-" * (w + 60))
    for name, code, price, qty, val, cw, tw, gap, ds in rows:
        sign = f"{ds:+d}" if ds != 0 else "0"
        print(f"{name:<{w}}  {price:>9,.0f} {qty:>4} {val:>12,.0f} "
              f"{cw:>6.2f} {tw:>6.2f} {gap:>+6.2f} {sign:>5}")
    print("-" * (w + 60))
    print(f"{'예수금(현금)':<{w}}  {'':>9} {'':>4} {cash:>12,.0f}")
    print(f"{'합계(평가액)':<{w}}  {'':>9} {'':>4} {total:>12,.0f}")
    if principal:
        pnl = total - principal
        ret = pnl / principal * 100
        print(f"\n투자원금 {principal:>14,.0f}  |  평가손익 {pnl:>+13,.0f}  "
              f"|  수익률 {ret:>+6.2f}%")

    if errors:
        print("\n[현재가 조회 실패] — 아래는 사용자에게 앱 현재가를 물어 채워야 함:")
        for code, msg in errors:
            print(f"  - {code}: {msg}")
    print("\n※ 투자 권유 아님. 실제 매매는 직접. 매매 = 목표비중까지 맞추기 위한 수량(+매수/−매도).")


if __name__ == "__main__":
    main()
