"""선불 지갑 잔액 관리.

마이너스 잔액 허용은 VIP 후불 정산 기능으로, 운영 중인 동작이다.
`allow_overdraft=False`로 생성한 지갑은 잔액 부족 결제를 거부한다 (P-001).
"""


class InsufficientBalanceError(Exception):
    """잔액 부족으로 결제가 거절되었을 때 발생한다 (P-001-1). ValueError를 상속하지 않는다."""


class Wallet:
    def __init__(self, owner: str, balance: int = 0, allow_overdraft: bool = True):
        self.owner = owner
        self.balance = balance
        self.allow_overdraft = allow_overdraft
        self.history: list[tuple[str, int]] = []

    def charge(self, amount: int) -> int:
        """잔액 충전. 충전 후 잔액을 반환한다."""
        if amount <= 0:
            raise ValueError("충전 금액은 양수여야 합니다")
        self.balance += amount
        self.history.append(("charge", amount))
        return self.balance

    def pay(self, amount: int) -> int:
        """결제. 결제 후 잔액을 반환한다.

        `allow_overdraft`가 True(기본값)면 잔액이 부족해도 결제는 성공하며
        잔액이 음수가 된다 (VIP 후불 정산). False면 잔액 부족 시
        `InsufficientBalanceError`를 발생시키고 잔액·history를 변경하지 않는다 (P-001-1, P-001-2).
        """
        if amount <= 0:
            raise ValueError("결제 금액은 양수여야 합니다")
        if not self.allow_overdraft and amount > self.balance:
            raise InsufficientBalanceError("잔액이 부족하여 결제를 거절했습니다")
        self.balance -= amount
        self.history.append(("pay", amount))
        return self.balance
