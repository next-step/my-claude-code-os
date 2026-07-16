"""
spec.md (sandbox/wf-eval/case3-latefee/tasks/001-late-fee/spec.md)의 정책(P-001-1 ~ P-001-8)을
검증하는 테스트. src/late_fee.py의 calculate_late_fee(overdue_days, price, is_popular=False)를
호출해 다음 형태의 dict를 기대한다:

    {
        "fee": int,               # 실제 청구액 (연체료 또는 분실 배상액)
        "is_lost": bool,          # 연체 30일 초과(31일째부터) 여부
        "accrued_late_fee": int,  # 할인/할증/상한 없이 연체일수 * 500원으로 누적되는 참고 수치
    }

overdue_days가 0 이상의 정수가 아니면 ValueError를 발생시킨다 (P-001-8).
"""

import pytest

from src.late_fee import calculate_late_fee


# ---------------------------------------------------------------------------
# P-001-1: 기본 연체료(7일 미만) — 연체일수 * 500원
# ---------------------------------------------------------------------------

def test_P001_1_example_three_days():
    # 예시: 연체 3일 -> 3 * 500 = 1,500원
    result = calculate_late_fee(overdue_days=3, price=5000, is_popular=False)
    assert result["fee"] == 1500


def test_P001_1_normal_one_day():
    # 정상: 연체 1일 -> 500원
    result = calculate_late_fee(overdue_days=1, price=5000, is_popular=False)
    assert result["fee"] == 500


def test_P001_1_edge_zero_days():
    # 엣지: 연체 0일(경계값) -> 0원
    result = calculate_late_fee(overdue_days=0, price=5000, is_popular=False)
    assert result["fee"] == 0


def test_P001_1_edge_day_six_boundary_continuity():
    # 엣지: 7일 미만 구간의 마지막 날(6일) -> 6 * 500 = 3,000원
    # (P-001-2의 7일차 정액 3,000원과 값이 우연히 같아 구간 경계 연속성을 확인한다)
    result = calculate_late_fee(overdue_days=6, price=5000, is_popular=False)
    assert result["fee"] == 3000


# ---------------------------------------------------------------------------
# P-001-2: 주간 할인 구간(7일 이상) — 3,000원 + (연체일수-7) * 500원
# ---------------------------------------------------------------------------

def test_P001_2_example_ten_days():
    # 예시: 연체 10일 -> 3,000 + (10-7)*500 = 4,500원
    result = calculate_late_fee(overdue_days=10, price=10000, is_popular=False)
    assert result["fee"] == 4500


def test_P001_2_normal_exactly_seven_days():
    # 정상: 연체 정확히 7일 -> 3,000 + 0*500 = 3,000원 (하루당 500원이면 3,500원이어야 하지만
    # 주간 할인으로 3,000원)
    result = calculate_late_fee(overdue_days=7, price=10000, is_popular=False)
    assert result["fee"] == 3000


def test_P001_2_edge_day_eight_after_week():
    # 엣지: 주간 할인 구간 진입 직후(8일) -> 3,000 + 1*500 = 3,500원
    # (naive 8*500=4,000원이 아님을 확인)
    result = calculate_late_fee(overdue_days=8, price=10000, is_popular=False)
    assert result["fee"] == 3500


# ---------------------------------------------------------------------------
# P-001-3: 인기 도서 2배 할증 (기본 연체료 * 2)
# ---------------------------------------------------------------------------

def test_P001_3_example_popular_three_days():
    # 예시: 인기 도서, 연체 3일(기본 연체료 1,500원) -> 1,500 * 2 = 3,000원
    # 정가(5000)를 기본 연체료*2(3000)보다 높게 잡아 P-001-4 상한이 개입하지 않게 한다.
    result = calculate_late_fee(overdue_days=3, price=5000, is_popular=True)
    assert result["fee"] == 3000


def test_P001_3_normal_popular_one_day():
    # 정상: 인기 도서, 연체 1일(기본 연체료 500원) -> 500 * 2 = 1,000원
    result = calculate_late_fee(overdue_days=1, price=5000, is_popular=True)
    assert result["fee"] == 1000


def test_P001_3_edge_popular_with_weekly_discount():
    # 엣지: 인기 도서 + 주간 할인 구간(7일, 기본 연체료 3,000원) -> 3,000 * 2 = 6,000원
    result = calculate_late_fee(overdue_days=7, price=10000, is_popular=True)
    assert result["fee"] == 6000


# ---------------------------------------------------------------------------
# P-001-4: 정가 상한과 기본 연체료 하한
#   fee = max(min(할증적용액, 정가), 기본연체료)
# ---------------------------------------------------------------------------

def test_P001_4_example_price_cap_reduces_surcharge():
    # 예시: 정가 2,000원, 인기 도서, 연체 3일
    # 기본 연체료 1,500원, 할증액 3,000원 -> min(3000,2000)=2000, max(2000,1500)=2,000원
    result = calculate_late_fee(overdue_days=3, price=2000, is_popular=True)
    assert result["fee"] == 2000


def test_P001_4_normal_floor_guarantee_nonpopular_cheap_book():
    # 정상: 정가 500원(기본 연체료보다 낮음), 비인기 도서, 연체 3일
    # 기본 연체료 1,500원 -> min(1500,500)=500, max(500,1500)=1,500원 (정가보다 낮아지지 않는다)
    result = calculate_late_fee(overdue_days=3, price=500, is_popular=False)
    assert result["fee"] == 1500


def test_P001_4_edge_floor_overrides_multiplier_when_price_below_base():
    # 엣지(경계 사례): 정가 1,000원(기본 연체료보다 낮음), 인기 도서, 연체 3일
    # 기본 연체료 1,500원, 할증액 3,000원 -> min(3000,1000)=1000, max(1000,1500)=1,500원
    # 정가가 기본 연체료보다 낮으면 인기 도서 할증이 최종 금액에 반영되지 않는다(spec-review 확정 동작).
    result = calculate_late_fee(overdue_days=3, price=1000, is_popular=True)
    assert result["fee"] == 1500


# ---------------------------------------------------------------------------
# P-001-5: 10,000원 절대 상한
# ---------------------------------------------------------------------------

def test_P001_5_example_capped_at_ten_thousand():
    # 예시: 정가 50,000원, 인기 도서, 연체 20일
    # 기본 연체료 9,500원, 할증액 19,000원, 정가상한 미적용(19000<50000) -> 10,000원 상한 적용
    result = calculate_late_fee(overdue_days=20, price=50000, is_popular=True)
    assert result["fee"] == 10000


def test_P001_5_normal_capped_with_different_inputs():
    # 정상: 정가 100,000원, 인기 도서, 연체 29일 -> 기본연체료 14,000원, 할증 28,000원
    # 정가상한 미적용 -> 10,000원 상한 적용
    result = calculate_late_fee(overdue_days=29, price=100000, is_popular=True)
    assert result["fee"] == 10000


def test_P001_5_edge_exactly_at_cap_boundary():
    # 엣지: 정가 20,000원, 비인기 도서, 연체 21일 -> 기본연체료 정확히 10,000원
    # (3,000 + (21-7)*500 = 10,000) -> 상한이 더 깎지 않고 정확히 10,000원 유지
    result = calculate_late_fee(overdue_days=21, price=20000, is_popular=False)
    assert result["fee"] == 10000


# ---------------------------------------------------------------------------
# P-001-6: 30일 초과 분실 처리 (단조성 보정: max(정가, 30일째 상한적용 연체료))
# ---------------------------------------------------------------------------

def test_P001_6_example_reimbursement_floored_by_day30_fee():
    # 예시: 정가 8,000원, 비인기 도서, 연체 31일
    # 30일째 기준 연체료 = 3,000+23*500=14,500원 -> 10,000원 상한 -> max(8000,10000)=10,000원
    result = calculate_late_fee(overdue_days=31, price=8000, is_popular=False)
    assert result["fee"] == 10000
    assert result["is_lost"] is True


def test_P001_6_normal_expensive_book_reimburses_price():
    # 정상: 정가 50,000원, 비인기 도서, 연체 40일
    # 30일째 기준 연체료는 10,000원 상한에 걸리지만 정가(50,000)가 더 크므로 정가를 배상
    result = calculate_late_fee(overdue_days=40, price=50000, is_popular=False)
    assert result["fee"] == 50000
    assert result["is_lost"] is True


def test_P001_6_edge_day30_not_lost_and_no_regression_at_day31():
    # 엣지: 정가 8,000원, 비인기 도서 — 30일(아직 분실 아님) vs 31일(분실) 청구액 비교
    day30 = calculate_late_fee(overdue_days=30, price=8000, is_popular=False)
    day31 = calculate_late_fee(overdue_days=31, price=8000, is_popular=False)
    assert day30["is_lost"] is False
    assert day30["fee"] == 10000
    assert day31["is_lost"] is True
    assert day31["fee"] == 10000
    # 연체가 하루 늘었다고 청구액이 줄어들면 안 된다 (단조성).
    assert day31["fee"] >= day30["fee"]


# ---------------------------------------------------------------------------
# P-001-7: 분실 후에도 계속 누적되는 참고용 연체료(accrued_late_fee)
# ---------------------------------------------------------------------------

def test_P001_7_example_accrued_after_loss():
    # 예시: 정가 8,000원, 연체 35일 -> 청구액 10,000원(P-001-6), 참고 누적 연체료 = 35*500=17,500원
    result = calculate_late_fee(overdue_days=35, price=8000, is_popular=False)
    assert result["fee"] == 10000
    assert result["accrued_late_fee"] == 17500


def test_P001_7_normal_accrued_just_after_loss_threshold():
    # 정상: 정가 8,000원, 연체 31일 -> 참고 누적 연체료 = 31*500=15,500원
    result = calculate_late_fee(overdue_days=31, price=8000, is_popular=False)
    assert result["accrued_late_fee"] == 15500


def test_P001_7_edge_accrued_differs_from_fee_before_loss():
    # 엣지: 정가 5,000원, 연체 7일(분실 아님) -> 연체료(fee)는 주간 할인 적용된 3,000원이지만
    # 참고 누적치(accrued_late_fee)는 할인 미적용 원값 7*500=3,500원으로 서로 달라야 한다.
    result = calculate_late_fee(overdue_days=7, price=5000, is_popular=False)
    assert result["fee"] == 3000
    assert result["accrued_late_fee"] == 3500


# ---------------------------------------------------------------------------
# P-001-8: 입력 유효성 (0 이상의 정수만 유효)
# ---------------------------------------------------------------------------

def test_P001_8_example_negative_days_raises():
    # 예시: 연체일수 = -1 -> 오류(ValueError) 발생
    with pytest.raises(ValueError):
        calculate_late_fee(overdue_days=-1, price=5000, is_popular=False)


def test_P001_8_normal_zero_days_is_valid():
    # 정상: 연체일수 = 0 -> 정상 처리, 연체료 0원 (오류 없음)
    result = calculate_late_fee(overdue_days=0, price=5000, is_popular=False)
    assert result["fee"] == 0


def test_P001_8_edge_non_integer_days_raises():
    # 엣지: 연체일수 = 0.5(정수가 아님) -> 오류(ValueError) 발생
    with pytest.raises(ValueError):
        calculate_late_fee(overdue_days=0.5, price=5000, is_popular=False)
