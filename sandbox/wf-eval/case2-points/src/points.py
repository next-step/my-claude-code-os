"""결제 금액에 대한 회원 등급별 포인트 적립 계산.

정책 출처: tasks/001-earn-points/spec.md (P-001-1 ~ P-001-8)
"""

# P-001-1, P-001-2, P-001-3: 등급별 기본 적립률 (퍼센트 정수)
GRADE_BASE_RATE_PERCENT = {
    "실버": 1,
    "골드": 2,
    "VIP": 4,
}

# P-001-5: 이벤트 기간 배수
EVENT_PERIOD_MULTIPLIER = 2
NON_EVENT_PERIOD_MULTIPLIER = 1

# P-001-6: 결제당 최대 적립 포인트 상한
MAX_EARNED_POINTS = 10000

# P-001-7: 이 금액 미만 결제는 적립 대상이 아니다
MIN_PAYMENT_AMOUNT_FOR_EARNING = 1000

# 퍼센트(%) 정수를 비율로 환산하는 분모 (정책이 아닌 "%" 단위 자체의 정의)
PERCENT_BASE = 100


def calculate_earned_points(grade, payment_amount, is_event_period=False):
    """쿠폰 할인만 반영한 실 결제 금액(payment_amount)과 회원 등급(grade)으로
    적립 포인트를 계산한다.

    포인트 = floor(payment_amount * 등급 기본율 * 이벤트 배수)를 계산한 뒤
    최소 결제금액(P-001-7) 및 상한(P-001-6)을 적용한다. 버림은 등급율과 이벤트
    배수를 모두 곱한 최종 결과에 정수 나눗셈으로 1회만 적용해, 단계별로 나눠
    버림할 때 생기는 결과 불일치를 피한다 (spec.md 정책 충돌 2 참조).

    grade가 정의된 등급(실버/골드/VIP)이 아니면 ValueError를 발생시킨다
    (P-001-8). payment_amount가 숫자가 아니거나 is_event_period가 bool이
    아닌 경우에도 예측 가능한 ValueError를 발생시킨다(임의 예외 타입 누출
    방지, impl-review 결함 지적 반영).
    """
    if not isinstance(grade, str) or grade not in GRADE_BASE_RATE_PERCENT:
        raise ValueError(f"정의되지 않은 회원 등급입니다: {grade!r}")

    if not isinstance(payment_amount, (int, float)):
        raise ValueError(f"결제 금액이 올바르지 않습니다: {payment_amount!r}")

    if not isinstance(is_event_period, bool):
        raise ValueError(f"이벤트 기간 여부는 bool이어야 합니다: {is_event_period!r}")

    if payment_amount < MIN_PAYMENT_AMOUNT_FOR_EARNING:
        return 0

    multiplier = (
        EVENT_PERIOD_MULTIPLIER if is_event_period else NON_EVENT_PERIOD_MULTIPLIER
    )
    effective_rate_percent = GRADE_BASE_RATE_PERCENT[grade] * multiplier

    points = (payment_amount * effective_rate_percent) // PERCENT_BASE

    return min(points, MAX_EARNED_POINTS)
