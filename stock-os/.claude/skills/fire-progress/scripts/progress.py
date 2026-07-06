#!/usr/bin/env python3
"""
파이어 진척도 계산기 — fire-progress 스킬의 결정론적 계산 엔진.

하는 일:
  1) portfolio.private.md → 보유수량 + 예수금
  2) 야후 파이낸스 라이브 현재가 → 순자산(평가액 합 + 예수금) 계산
  3) portfolio.md → 목표금액 · 연 저축(예측용) · 연 수익률 가정 · 목표 시점
  4) 지금 진척률(순자산/목표) + 목표 시점까지 시나리오별 예상 자산/도달 여부 출력

값을 저장하지 않는다(현재가·평가액은 매일 변함). 실행할 때마다 최신으로 계산.
투자 권유가 아니라 사실·계산 전달이다. 예측은 가정(수익률·저축)에 따른 추정일 뿐.

사용:  python3 .claude/skills/fire-progress/scripts/progress.py
"""
import datetime
import json
import re
import ssl
import sys
import urllib.request
from pathlib import Path

try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL = ssl.create_default_context()

ROOT = Path(__file__).resolve().parents[4]
PORTFOLIO = ROOT / "portfolio.md"
PRIVATE = ROOT / "portfolio.private.md"


def _num(s):
    s = re.sub(r"[₩,%\s원]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def _rows(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue
        yield cells


def parse_holdings():
    """private.md → (holdings{code:(name,qty)}, 예수금)."""
    holdings, cash = {}, 0.0
    for cells in _rows(PRIVATE):
        if "예수금" in " ".join(cells):
            for c in reversed(cells):
                v = _num(c)
                if v is not None:
                    cash = v
                    break
            continue
        for i, c in enumerate(cells):
            if re.fullmatch(r"\d{6}", c):
                name = cells[i - 1] if i > 0 else c
                qty = _num(cells[i + 1]) if i + 1 < len(cells) else None
                if qty is not None:
                    holdings[c] = (name, qty)
                break
    return holdings, cash


def parse_fire_params():
    """portfolio.md → (목표금액, 연저축, [수익률%...], 목표연도)."""
    text = PORTFOLIO.read_text(encoding="utf-8")

    def big_num(label):
        for line in text.splitlines():
            if label in line:
                m = re.search(r"[\d,]{4,}", line)
                if m:
                    return float(m.group(0).replace(",", ""))
        return None

    target = big_num("목표 금액")
    savings = big_num("연 저축")
    rates, year = [], None
    for line in text.splitlines():
        if "연 수익률" in line and not rates:
            rates = [int(x) for x in re.findall(r"(\d+)\s*%", line)]
        if "목표 시점" in line and year is None:
            m = re.search(r"(20\d\d)", line)
            if m:
                year = int(m.group(1))
    return target, savings, rates, year


def fetch_price(code):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{code}.KS?interval=1d&range=1d")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15, context=_SSL) as r:
        data = json.load(r)
    return float(data["chart"]["result"][0]["meta"]["regularMarketPrice"])


def won(x):
    """1,000,000,000 → '10.0억' 처럼 읽기 쉽게."""
    if x >= 1e8:
        return f"{x/1e8:,.2f}억"
    return f"{x/1e4:,.0f}만"


def main():
    holdings, cash = parse_holdings()
    target, savings, rates, target_year = parse_fire_params()
    if not holdings:
        sys.exit("보유 종목을 못 읽었다. portfolio.private.md 확인.")
    if not (target and savings and rates and target_year):
        sys.exit("파이어 파라미터를 못 읽었다. portfolio.md의 목표 금액/연 저축/연 수익률/목표 시점 확인.")

    errors = []
    net = cash
    for code, (name, qty) in holdings.items():
        try:
            net += fetch_price(code) * qty
        except Exception as e:  # noqa: BLE001
            errors.append((code, str(e)))

    now_year = datetime.date.today().year
    n = target_year - now_year
    progress = net / target * 100

    print(f"\n=== 파이어 진척도 ===")
    print(f"현재 순자산   : {net:>15,.0f}원  ({won(net)})")
    print(f"목표 금액     : {target:>15,.0f}원  ({won(target)})")
    print(f"진척률        : {progress:>6.1f}%   (목표까지 {won(max(target-net,0))} 남음)")
    print(f"남은 기간     : {n}년  ({now_year} → {target_year})")
    print(f"예측 가정     : 매년 {won(savings)} 저축(연말 납입) + 아래 수익률 복리\n")

    print(f"{'수익률':>6} {'예상 자산('+str(target_year)+')':>18} {'목표 대비':>9}  판정")
    print("-" * 52)
    for pct in rates:
        r = pct / 100
        fv = net * (1 + r) ** n + savings * (((1 + r) ** n - 1) / r)
        ratio = fv / target * 100
        verdict = "도달 ✅" if fv >= target else "부족 ⚠️"
        print(f"{pct:>5}% {won(fv):>18} {ratio:>8.0f}%  {verdict}")

    print("\n※ 예측은 가정(수익률·저축)에 따른 추정일 뿐, 보장 아님. 투자 권유 아님.")
    if errors:
        print("\n[현재가 조회 실패] 사용자에게 현재가를 물어 보완 필요:")
        for code, msg in errors:
            print(f"  - {code}: {msg}")


if __name__ == "__main__":
    main()
