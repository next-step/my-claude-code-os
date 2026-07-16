"""
도서 연체료 계산 (spec: tasks/001-late-fee/spec.md, 정책 P-001-1 ~ P-001-8).

calculate_late_fee(overdue_days, price, is_popular=False)를 호출하면
{"fee": int, "is_lost": bool, "accrued_late_fee": int} 를 반환한다.
"""

DAILY_RATE = 500  # P-001-1: 하루당 기본 연체료
WEEKLY_DISCOUNT_THRESHOLD_DAYS = 7  # P-001-2: 이 일수 이상부터 주간 할인 구간
WEEKLY_FLAT_FEE = 3000  # P-001-2: 7일째까지의 정액 연체료
POPULAR_SURCHARGE_MULTIPLIER = 2  # P-001-3: 인기 도서 할증 배수
ABSOLUTE_FEE_CAP = 10000  # P-001-5: 어떤 경우에도 넘지 않는 절대 상한
LOST_AFTER_DAYS = 30  # P-001-6: 이 일수를 초과하면(31일째부터) 분실 처리


def _validate_overdue_days(overdue_days):
    """P-001-8: 연체일수는 0 이상의 정수만 유효하다."""
    is_integer = isinstance(overdue_days, int) and not isinstance(overdue_days, bool)
    if not is_integer or overdue_days < 0:
        raise ValueError(
            f"overdue_days는 0 이상의 정수여야 합니다: {overdue_days!r}"
        )


def _validate_price(price):
    """정가는 0 이상의 정수(원)여야 한다 — P-001-1~7 전 계산이 전제하는 통화 단위.

    impl-review에서 발견: price가 None/문자열이면 TypeError로 크래시했고,
    price가 float이면 결과 fee에 소수 원이 새어나갔다. overdue_days(P-001-8)와
    동일한 수준으로 검증해 명확한 ValueError로 거부한다.
    """
    is_integer = isinstance(price, int) and not isinstance(price, bool)
    if not is_integer or price < 0:
        raise ValueError(f"price는 0 이상의 정수여야 합니다: {price!r}")


def _base_fee(overdue_days):
    """P-001-1 / P-001-2: 할증 전 기본 연체료."""
    if overdue_days < WEEKLY_DISCOUNT_THRESHOLD_DAYS:
        return overdue_days * DAILY_RATE
    extra_days = overdue_days - WEEKLY_DISCOUNT_THRESHOLD_DAYS
    return WEEKLY_FLAT_FEE + extra_days * DAILY_RATE


def _surcharged_fee(base_fee, is_popular):
    """P-001-3: 인기 도서 2배 할증."""
    multiplier = POPULAR_SURCHARGE_MULTIPLIER if is_popular else 1
    return base_fee * multiplier


def _apply_price_cap_and_floor(base_fee, surcharged_fee, price):
    """P-001-4: 정가 상한(할증액을 정가로 캡) 후 기본 연체료 하한 보장."""
    price_capped = min(surcharged_fee, price)
    return max(price_capped, base_fee)


def _apply_absolute_cap(fee):
    """P-001-5: 10,000원 절대 상한."""
    return min(fee, ABSOLUTE_FEE_CAP)


def _fee_before_loss(overdue_days, price, is_popular):
    """P-001-1~5를 순서대로 적용한, 분실 처리 이전의 연체료."""
    base_fee = _base_fee(overdue_days)
    surcharged_fee = _surcharged_fee(base_fee, is_popular)
    capped_fee = _apply_price_cap_and_floor(base_fee, surcharged_fee, price)
    return _apply_absolute_cap(capped_fee)


def _accrued_late_fee(overdue_days):
    """P-001-7: 할인·할증·상한 없이 계속 누적되는 참고용 연체료."""
    return overdue_days * DAILY_RATE


def calculate_late_fee(overdue_days, price, is_popular=False):
    _validate_overdue_days(overdue_days)
    _validate_price(price)

    is_lost = overdue_days > LOST_AFTER_DAYS
    if is_lost:
        # P-001-6: 정가 배상과 30일째 상한적용 연체료 중 큰 값 (단조성 보정).
        day30_fee = _fee_before_loss(LOST_AFTER_DAYS, price, is_popular)
        fee = max(price, day30_fee)
    else:
        fee = _fee_before_loss(overdue_days, price, is_popular)

    return {
        "fee": fee,
        "is_lost": is_lost,
        "accrued_late_fee": _accrued_late_fee(overdue_days),
    }
