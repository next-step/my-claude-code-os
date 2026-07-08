#!/usr/bin/env python3
"""stock-os 결정적 수익률 계산기 (return-calculator).

수익률·실질(세후) 손익·손절/목표가 도달 여부·월 손실한도 잔여액 계산은
LLM이 암산하지 않고 이 스크립트가 결정적으로 수행한다.
portfolio-analyst가 Bash로 실행해 결과 JSON만 사용한다.

사용법:
  python3 .claude/scripts/return-calculator.py --json '{...}'
  echo '{...}' | python3 .claude/scripts/return-calculator.py
  python3 .claude/scripts/return-calculator.py --self-test

입력 JSON 스키마:
{
  "fx_usdkrw": 1380.0,               // US 포지션이 있으면 필수
  "monthly_pnl_krw": -300000,        // 이번 달 단타 누적손익(원). 기본 0
  "monthly_loss_limit_krw": -1500000,// 월 손실한도(원). 기본 -1,500,000 (-15%)
  "us_realized_gain_krw_ytd": 0,     // 올해 해외주식 기실현 양도차익(원). 250만원 공제 소진 계산용
  "positions": [
    {
      "name": "종목명", "market": "KR" | "US",
      "qty": 10, "entry": 50000, "current": 52000,
      "stop": 47500, "target": 60000,   // 없으면 null 허용 (원칙상 빈칸은 위반)
      "fee_rate_pct": 0.015             // 편도 매매수수료 %. 기본 0
    }
  ]
}

세율 근거: 05_reference/tax-and-fees.md (2026년 기준)
- 국내 매도세(거래세+농특세): 매도금액의 0.20%
- 미국 양도세: 연 250만원 공제 초과분의 22% (지방세 포함)
"""
import json
import sys

KR_SELL_TAX_PCT = 0.20          # 매도금액 대비 %
US_CGT_RATE = 0.22              # 공제 초과 양도차익에 대한 세율
US_ANNUAL_DEDUCTION_KRW = 2_500_000
DEFAULT_MONTHLY_LOSS_LIMIT_KRW = -1_500_000


def calc_position(p, fx_usdkrw, us_deduction_left_krw):
    name = p.get("name") or "(이름 없음)"
    market = (p.get("market") or "").upper()
    qty = float(p["qty"])
    entry = float(p["entry"])
    current = float(p["current"])
    stop = p.get("stop")
    target = p.get("target")
    fee_rate = float(p.get("fee_rate_pct") or 0.0)

    if market not in ("KR", "US"):
        raise ValueError(f"{name}: market은 KR 또는 US여야 함 (받은 값: {market!r})")
    if qty <= 0 or entry <= 0 or current <= 0:
        raise ValueError(f"{name}: qty/entry/current는 양수여야 함")
    if market == "US" and not fx_usdkrw:
        raise ValueError(f"{name}: US 포지션에는 fx_usdkrw가 필요함")

    buy_amt = entry * qty
    sell_amt = current * qty
    gross_pnl = sell_amt - buy_amt
    gross_ret_pct = (current / entry - 1.0) * 100.0
    fees = (buy_amt + sell_amt) * fee_rate / 100.0

    if market == "KR":
        sell_tax = sell_amt * KR_SELL_TAX_PCT / 100.0
        est_tax_krw = sell_tax
        net_pnl_krw = gross_pnl - fees - sell_tax
        cost_basis_krw = buy_amt
    else:
        gross_pnl_krw = gross_pnl * fx_usdkrw
        fees_krw = fees * fx_usdkrw
        taxable = max(0.0, gross_pnl_krw - fees_krw - us_deduction_left_krw)
        est_tax_krw = taxable * US_CGT_RATE
        net_pnl_krw = gross_pnl_krw - fees_krw - est_tax_krw
        cost_basis_krw = buy_amt * fx_usdkrw

    net_ret_pct = net_pnl_krw / cost_basis_krw * 100.0 if cost_basis_krw else 0.0

    result = {
        "name": name,
        "market": market,
        "gross_return_pct": round(gross_ret_pct, 2),
        "gross_pnl_local": round(gross_pnl, 2),
        "est_fees_local": round(fees, 2),
        "est_tax_krw": round(est_tax_krw),
        "net_pnl_krw": round(net_pnl_krw),
        "net_return_pct": round(net_ret_pct, 2),
        "stop_hit": (stop is not None and current <= float(stop)),
        "target_hit": (target is not None and current >= float(target)),
        "dist_to_stop_pct": round((current - float(stop)) / current * 100.0, 2) if stop is not None else None,
        "dist_to_target_pct": round((float(target) - current) / current * 100.0, 2) if target is not None else None,
        "missing_stop_or_target": stop is None or target is None,  # 원칙 위반 플래그
    }
    return result


def calc(data):
    fx = data.get("fx_usdkrw")
    monthly_pnl = float(data.get("monthly_pnl_krw") or 0)
    limit = float(data.get("monthly_loss_limit_krw") or DEFAULT_MONTHLY_LOSS_LIMIT_KRW)
    if limit >= 0:
        raise ValueError("monthly_loss_limit_krw는 음수(손실 한도)여야 함")
    us_ytd = float(data.get("us_realized_gain_krw_ytd") or 0)
    us_deduction_left = max(0.0, US_ANNUAL_DEDUCTION_KRW - us_ytd)

    positions = [calc_position(p, fx, us_deduction_left) for p in data.get("positions") or []]

    remaining = monthly_pnl - limit  # 예: -30만 - (-150만) = 120만원 남음
    monthly = {
        "limit_krw": round(limit),
        "cumulative_pnl_krw": round(monthly_pnl),
        "remaining_loss_capacity_krw": round(remaining),
        "limit_used_pct": round(min(monthly_pnl, 0.0) / limit * 100.0, 1),
        "limit_breached": monthly_pnl <= limit,
    }

    return {
        "positions": positions,
        "monthly_limit": monthly,
        "assumptions": [
            f"국내 매도세 {KR_SELL_TAX_PCT}% (거래세+농특세, 2026)",
            f"미국 양도세 {US_CGT_RATE*100:.0f}%, 연 공제 {US_ANNUAL_DEDUCTION_KRW:,}원 중 잔여 {us_deduction_left:,.0f}원 반영",
            "수수료는 입력된 fee_rate_pct 기준(미입력 시 0) — 증권사 실제 수수료 확인 필요",
            "미국 양도세는 '지금 전량 매도 시' 추정치 (환율은 입력된 fx_usdkrw 고정)",
        ],
    }


def self_test():
    # KR: 진입 50,000 × 10주 → 현재 52,000. 수수료 0.015%/편도
    out = calc({
        "monthly_pnl_krw": -300000,
        "positions": [{
            "name": "테스트KR", "market": "KR", "qty": 10,
            "entry": 50000, "current": 52000, "stop": 47500, "target": 60000,
            "fee_rate_pct": 0.015,
        }],
    })
    p = out["positions"][0]
    assert p["gross_return_pct"] == 4.0, p
    assert p["gross_pnl_local"] == 20000.0, p
    # 매도세 520,000*0.002=1,040 / 수수료 (500,000+520,000)*0.00015=153
    assert p["est_tax_krw"] == 1040, p
    assert p["net_pnl_krw"] == 18807, p
    assert p["stop_hit"] is False and p["target_hit"] is False, p
    m = out["monthly_limit"]
    assert m["remaining_loss_capacity_krw"] == 1200000, m
    assert m["limit_used_pct"] == 20.0, m

    # US: 진입 $100 × 5주 → 현재 $130, 환율 1,300. 차익 195,000원 → 공제 내 → 세금 0
    out = calc({
        "fx_usdkrw": 1300,
        "positions": [{
            "name": "테스트US", "market": "US", "qty": 5,
            "entry": 100, "current": 130, "stop": 95, "target": 125,
        }],
    })
    p = out["positions"][0]
    assert p["gross_return_pct"] == 30.0, p
    assert p["est_tax_krw"] == 0, p
    assert p["net_pnl_krw"] == 195000, p
    assert p["target_hit"] is True, p

    # US 공제 소진: 올해 기실현 250만 → 공제 잔여 0 → 차익 전액 22% 과세
    out = calc({
        "fx_usdkrw": 1300,
        "us_realized_gain_krw_ytd": 2_500_000,
        "positions": [{
            "name": "테스트US2", "market": "US", "qty": 5,
            "entry": 100, "current": 130, "stop": None, "target": None,
        }],
    })
    p = out["positions"][0]
    assert p["est_tax_krw"] == 42900, p  # 195,000 * 0.22
    assert p["missing_stop_or_target"] is True, p

    # 손절 도달
    out = calc({"positions": [{
        "name": "손절", "market": "KR", "qty": 1,
        "entry": 10000, "current": 9400, "stop": 9500, "target": 12000,
    }]})
    assert out["positions"][0]["stop_hit"] is True

    print("self-test OK")


def main(argv):
    if "--self-test" in argv:
        self_test()
        return 0
    try:
        if "--json" in argv:
            raw = argv[argv.index("--json") + 1]
        else:
            raw = sys.stdin.read()
        data = json.loads(raw)
        print(json.dumps(calc(data), ensure_ascii=False, indent=2))
        return 0
    except (KeyError, IndexError, ValueError, TypeError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
