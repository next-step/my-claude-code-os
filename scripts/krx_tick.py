#!/usr/bin/env python3
"""KRX 가격대별 최소 호가단위(틱) 산출기 — 모의 체결의 '한 틱 관통' 판정의 진실원천.

왜 필요한가(daily-trading-loop Q23):
- 모의 시뮬 엔진은 지정가 주문을 '한 틱 관통'(매수 -1틱, 매도 +1틱)으로 체결 판정한다.
  그 '한 틱'이 가격대마다 달라(KRX 규칙), 결정론적으로 코드화해야 한다.
- KRX 호가단위는 웹검색 값이 아니라 규칙이라, 이 스크립트가 진실원천이다
  (market-glossary "KRX 호가단위표"와 정합 — 표와 이 상수가 어긋나면 스크립트가 이긴다).

호가단위표(코스피 종목, market-glossary 항목 4):
  가격 < 2,000        → 1
  2,000 ~ 5,000       → 5
  5,000 ~ 20,000      → 10
  20,000 ~ 50,000     → 50
  50,000 ~ 200,000    → 100
  200,000 ~ 500,000   → 500
  500,000 ~           → 1,000

경계값 처리(glossary가 스크립트에 위임):
- 구간 경계는 **위쪽(비싼) 구간에 속한다** — 즉 하한 이상(>=)이면 그 구간이다.
  예) 정확히 2,000원 → 틱 5,  정확히 20,000원 → 틱 50,  정확히 500,000원 → 틱 1,000.
  이는 실제 KRX 규칙(각 구간은 하한 포함·상한 미포함)과 일치한다.

사용:  python3 krx_tick.py 19990        # 틱만 출력 → 10
       python3 krx_tick.py 19990 --json # {"price":19990.0,"tick":10}
import:  from krx_tick import tick_size; tick_size(19990) -> 10
"""
from __future__ import annotations
import argparse
import json
import sys

# (상한(미포함), 틱). 가격이 이 상한보다 작으면 그 틱. 경계값은 위 구간으로 넘어간다(>= 하한).
# 마지막 구간은 상한 없음(무한대) → 1,000원.
_BANDS: list[tuple[float, int]] = [
    (2_000, 1),
    (5_000, 5),
    (20_000, 10),
    (50_000, 50),
    (200_000, 100),
    (500_000, 500),
    (float("inf"), 1_000),
]


def tick_size(price: float) -> int:
    """가격대에 해당하는 최소 호가단위(원). 경계값은 위쪽(비싼) 구간에 속한다(>= 하한)."""
    if price < 0:
        raise ValueError(f"가격은 음수일 수 없다: {price}")
    for upper, tick in _BANDS:
        if price < upper:
            return tick
    return 1_000  # 도달 불가(마지막 구간이 inf)지만 방어적으로.


def main() -> int:
    ap = argparse.ArgumentParser(description="KRX 가격대별 호가단위(틱) 산출")
    ap.add_argument("price", type=float, help="가격(원)")
    ap.add_argument("--json", action="store_true", help="JSON 한 줄로 출력")
    args = ap.parse_args()
    tick = tick_size(args.price)
    if args.json:
        print(json.dumps({"price": args.price, "tick": tick}, ensure_ascii=False))
    else:
        print(tick)
    return 0


if __name__ == "__main__":
    sys.exit(main())
