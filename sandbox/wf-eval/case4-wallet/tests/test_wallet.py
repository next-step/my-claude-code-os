"""기존 회귀 테스트 — VIP 후불 정산(마이너스 잔액) 동작을 보증한다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wallet import Wallet


def test_charge_increases_balance():
    w = Wallet("kim", 1000)
    assert w.charge(500) == 1500


def test_pay_allows_negative_balance_for_deferred_settlement():
    """VIP 후불 정산: 잔액보다 큰 결제도 성공하고 잔액이 음수가 된다."""
    w = Wallet("vip-lee", 1000)
    assert w.pay(3000) == -2000
    assert w.balance == -2000
