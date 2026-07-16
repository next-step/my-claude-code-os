"""P-001 (잔액 부족 결제 차단) 정책 테스트.

spec: tasks/001-insufficient-balance/spec.md
기존 회귀 테스트(test_wallet.py)는 수정하지 않는다.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import wallet
from wallet import Wallet


# ── P-001-1: 잔액 부족 결제 거부 ──────────────────────────────

def test_P001_1_example_pay_exceeds_balance_raises():
    """예시: Wallet(1000, allow_overdraft=False).pay(1500) → InsufficientBalanceError, 잔액 1000 유지."""
    w = Wallet("kim", 1000, allow_overdraft=False)
    with pytest.raises(wallet.InsufficientBalanceError) as exc_info:
        w.pay(1500)
    assert w.balance == 1000
    assert not isinstance(exc_info.value, ValueError)


def test_P001_1_normal_reject_with_different_amounts():
    """정상 경로: 다른 숫자 조합에서도 초과 결제는 거부된다."""
    w = Wallet("kim", 500, allow_overdraft=False)
    with pytest.raises(wallet.InsufficientBalanceError):
        w.pay(600)
    assert w.balance == 500


def test_P001_1_edge_amount_one_over_balance():
    """엣지: 잔액보다 딱 1 큰 결제도 거부된다 (경계값)."""
    w = Wallet("kim", 100, allow_overdraft=False)
    with pytest.raises(wallet.InsufficientBalanceError):
        w.pay(101)
    assert w.balance == 100


def test_P001_1_edge_amount_zero_raises_valueerror_not_insufficient():
    """엣지: amount<=0은 기존 ValueError 가드가 우선 적용되고 InsufficientBalanceError는 발생하지 않는다."""
    w = Wallet("kim", 0, allow_overdraft=False)
    with pytest.raises(ValueError) as exc_info:
        w.pay(0)
    assert not isinstance(exc_info.value, wallet.InsufficientBalanceError)


# ── P-001-2: 거절된 결제는 history에 남지 않는다 ──────────────────

def test_P001_2_example_rejected_payment_history_empty():
    """예시: 거절된 결제 후 history는 비어 있다."""
    w = Wallet("kim", 1000, allow_overdraft=False)
    with pytest.raises(wallet.InsufficientBalanceError):
        w.pay(1500)
    assert w.history == []


def test_P001_2_normal_history_unchanged_after_rejection():
    """정상 경로: 이전 history가 있는 상태에서 거절된 결제는 history를 변경하지 않는다 (통째로 비우는 구현을 배제)."""
    w = Wallet("kim", 1000, allow_overdraft=False)
    w.charge(200)
    before = list(w.history)
    with pytest.raises(wallet.InsufficientBalanceError):
        w.pay(5000)
    assert w.history == before


def test_P001_2_edge_repeated_rejections_do_not_accumulate():
    """엣지: 거절이 반복돼도 history에는 아무것도 쌓이지 않는다."""
    w = Wallet("kim", 100, allow_overdraft=False)
    for _ in range(3):
        with pytest.raises(wallet.InsufficientBalanceError):
            w.pay(999)
    assert w.history == []


# ── P-001-3: 잔액과 결제 금액이 같으면 성공, 잔액 0 ──────────────────

def test_P001_3_example_pay_equals_balance_succeeds():
    """예시: Wallet(1000, allow_overdraft=False).pay(1000) == 0, 잔액 0."""
    w = Wallet("kim", 1000, allow_overdraft=False)
    assert w.pay(1000) == 0
    assert w.balance == 0


def test_P001_3_normal_pay_equals_balance_different_amount():
    """정상 경로: 다른 숫자 조합에서도 동일 금액 결제는 성공하고 잔액 0이 된다."""
    w = Wallet("kim", 250, allow_overdraft=False)
    assert w.pay(250) == 0
    assert w.balance == 0


def test_P001_3_edge_smallest_balance_equals_amount():
    """엣지: 최소 단위(1)에서도 동일 금액 결제가 성공하며, 성공한 결제는 history에 기록된다."""
    w = Wallet("kim", 1, allow_overdraft=False)
    assert w.pay(1) == 0
    assert w.balance == 0
    assert w.history == [("pay", 1)]


# ── P-001-4: allow_overdraft 미지정 시 기존 동작 보존 ──────────────

def test_P001_4_example_default_allows_negative_balance():
    """예시: 기존 회귀 테스트와 동일한 입출력 — allow_overdraft 미지정 시 초과 결제도 성공하고 잔액이 음수가 된다."""
    w = Wallet("vip-lee", 1000)
    assert w.pay(3000) == -2000
    assert w.balance == -2000


def test_P001_4_normal_default_negative_balance_different_amount():
    """정상 경로: 다른 숫자 조합에서도 미지정 시 초과 결제가 성공한다."""
    w = Wallet("lee", 500)
    assert w.pay(700) == -200
    assert w.balance == -200


def test_P001_4_edge_explicit_allow_overdraft_true_matches_default():
    """엣지: allow_overdraft=True를 명시해도 미지정과 동일하게 초과 결제가 성공한다."""
    w = Wallet("kim", 1000, allow_overdraft=True)
    assert w.pay(3000) == -2000
    assert w.balance == -2000


# ── P-001-5: 잔액 충분 시 정상 결제 성공 ──────────────────────────

def test_P001_5_example_pay_less_than_balance_succeeds():
    """예시: Wallet(1000, allow_overdraft=False).pay(400) == 600, 잔액 600, history에 기록됨."""
    w = Wallet("kim", 1000, allow_overdraft=False)
    assert w.pay(400) == 600
    assert w.balance == 600
    assert w.history == [("pay", 400)]


def test_P001_5_normal_pay_less_than_balance_different_amount():
    """정상 경로: 다른 숫자 조합에서도 잔액 충분 시 결제가 성공한다."""
    w = Wallet("kim", 300, allow_overdraft=False)
    assert w.pay(150) == 150
    assert w.balance == 150


def test_P001_5_edge_pay_one_unit_below_balance():
    """엣지: 잔액보다 딱 1 작은 결제도 성공한다 (경계값)."""
    w = Wallet("kim", 100, allow_overdraft=False)
    assert w.pay(99) == 1
    assert w.balance == 1
