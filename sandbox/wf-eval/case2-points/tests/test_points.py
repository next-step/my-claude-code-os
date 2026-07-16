"""
spec.md (tasks/001-earn-points)의 정책(P-001-1 ~ P-001-8)을 검증하는 테스트.

대상 함수: src.points.calculate_earned_points(grade, payment_amount, is_event_period=False)
- grade: "실버" | "골드" | "VIP" (그 외 값/None이면 ValueError)
- payment_amount: 쿠폰 할인만 반영한 실 결제 금액 (원)
- is_event_period: 이벤트 기간 여부 (기본 False)
- 반환값: floor(payment_amount * 등급 기본율 * 이벤트 배수)를 상한 10,000과
  최소 결제금액 1,000원 미만 제외 규칙까지 적용한 최종 적립 포인트(int)

계산 검산 (전부 spec.md 예시와 동일):
- P-001-1: 50000*0.01=500 / 20000*0.01=200 / 1999*0.01=19.99→19
- P-001-2: 50000*0.02=1000 / 30000*0.02=600 / 1999*0.02=39.98→39
- P-001-3: 50000*0.04=2000 / 10000*0.04=400 / 1999*0.04=79.96→79
- P-001-4: 25000*0.02=500 / 5000*0.01=50 / 1000*0.01=10
- P-001-5: 50000*0.01*2=1000 / 20000*0.02*2=800 / 1060*0.01*2=21.2→21(최종 1회 버림)
- P-001-6: 1000000*0.04*2=80000→상한 10000 / 50000*0.04*2=4000(상한 미만) / 250000*0.04*1=10000(경계, 축소 안 됨)
- P-001-7: 999원 미만 대상 제외→0 / 5000*0.01=50 / 1000*0.01=10(경계 포함) / 0원→0
- P-001-8: 정의되지 않은 등급이면 ValueError
"""

import pytest

from src.points import calculate_earned_points


# ── P-001-1: 실버 등급 기본 적립률 1% ──────────────────────────────

def test_P001_1_example_silver_50000():
    assert calculate_earned_points("실버", 50000, False) == 500


def test_P001_1_normal_silver_20000():
    assert calculate_earned_points("실버", 20000, False) == 200


def test_P001_1_edge_silver_floor_rounding():
    # 1999 * 0.01 = 19.99 -> 버림 19
    assert calculate_earned_points("실버", 1999, False) == 19


# ── P-001-2: 골드 등급 기본 적립률 2% ──────────────────────────────

def test_P001_2_example_gold_50000():
    assert calculate_earned_points("골드", 50000, False) == 1000


def test_P001_2_normal_gold_30000():
    assert calculate_earned_points("골드", 30000, False) == 600


def test_P001_2_edge_gold_floor_rounding():
    # 1999 * 0.02 = 39.98 -> 버림 39
    assert calculate_earned_points("골드", 1999, False) == 39


# ── P-001-3: VIP 등급 기본 적립률 4% ───────────────────────────────

def test_P001_3_example_vip_50000():
    assert calculate_earned_points("VIP", 50000, False) == 2000


def test_P001_3_normal_vip_10000():
    assert calculate_earned_points("VIP", 10000, False) == 400


def test_P001_3_edge_vip_floor_rounding():
    # 1999 * 0.04 = 79.96 -> 버림 79
    assert calculate_earned_points("VIP", 1999, False) == 79


# ── P-001-4: 쿠폰 할인 주문의 적립 대상 포함과 기준 금액 ──────────────

def test_P001_4_example_discounted_order_25000():
    # 정가 30,000원, 쿠폰 5,000원 할인 → 실 결제 금액 25,000원, 골드
    # (할인 전 30,000원 기준이면 600이 되어야 하므로 25,000원 기준임을 검증)
    assert calculate_earned_points("골드", 25000, False) == 500


def test_P001_4_normal_discounted_order_still_earns():
    # 쿠폰 할인이 반영된 소액 실 결제 금액도 적립 대상에서 제외되지 않는다
    assert calculate_earned_points("실버", 5000, False) == 50


def test_P001_4_edge_discounted_amount_at_minimum_threshold():
    # 쿠폰 할인 결과 실 결제 금액이 최소 기준(1,000원)에 정확히 걸리는 경우
    assert calculate_earned_points("실버", 1000, False) == 10


# ── P-001-5: 이벤트 기간 적립률 2배 ────────────────────────────────

def test_P001_5_example_event_double_silver():
    assert calculate_earned_points("실버", 50000, True) == 1000


def test_P001_5_normal_event_double_gold():
    assert calculate_earned_points("골드", 20000, True) == 800


def test_P001_5_edge_floor_applied_once_not_per_step():
    # 1060 * 0.01 * 2 = 21.2 -> 최종 1회 버림 = 21
    # 등급율 단계에서 먼저 버림하면 floor(1060*0.01)=10, 10*2=20이 되어
    # spec 정책충돌 2의 "최종 곱셈 1회 버림" 규칙 위반을 잡아낸다.
    assert calculate_earned_points("실버", 1060, True) == 21


# ── P-001-6: 결제당 최대 적립 포인트 상한 10,000 ────────────────────

def test_P001_6_example_cap_applied_vip_event():
    # 1,000,000 * 0.04 * 2 = 80,000 -> 상한 적용 10,000
    assert calculate_earned_points("VIP", 1000000, True) == 10000


def test_P001_6_normal_below_cap_not_reduced():
    # 50,000 * 0.04 * 2 = 4,000 (상한 미만이므로 그대로)
    assert calculate_earned_points("VIP", 50000, True) == 4000


def test_P001_6_edge_exact_cap_boundary_not_reduced():
    # 250,000 * 0.04 * 1 = 10,000 (상한과 정확히 같음 -> 축소되지 않고 그대로 10,000)
    assert calculate_earned_points("VIP", 250000, False) == 10000


# ── P-001-7: 최소 결제 금액 미만 적립 제외 (1,000원 미만) ────────────

def test_P001_7_example_below_minimum_excluded():
    assert calculate_earned_points("실버", 999, False) == 0


def test_P001_7_normal_above_minimum():
    assert calculate_earned_points("실버", 5000, False) == 50


def test_P001_7_edge_exact_minimum_boundary_included():
    # 1,000원은 "미만"이 아니므로 적립 대상에 포함된다
    assert calculate_earned_points("실버", 1000, False) == 10


def test_P001_7_edge_zero_amount_excluded():
    assert calculate_earned_points("실버", 0, False) == 0


# ── P-001-8: 정의되지 않은 등급 처리 ───────────────────────────────

def test_P001_8_example_invalid_grade_raises():
    with pytest.raises(ValueError):
        calculate_earned_points("브론즈", 50000, False)


def test_P001_8_normal_invalid_grade_empty_string_raises():
    with pytest.raises(ValueError):
        calculate_earned_points("", 50000, False)


def test_P001_8_edge_invalid_grade_none_raises():
    with pytest.raises(ValueError):
        calculate_earned_points(None, 50000, False)
