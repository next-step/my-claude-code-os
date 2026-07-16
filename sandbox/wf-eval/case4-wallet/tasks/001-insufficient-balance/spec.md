---
status: approved
---

## 요약

지갑(`Wallet`)의 결제(`pay`)에 잔액 부족 시 결제를 거부하는 정책을 추가한다. 결제 금액이 잔액보다 크면 `InsufficientBalanceError`를 발생시키고 거래 내역(history)을 남기지 않으며, 잔액과 결제 금액이 정확히 같거나 잔액보다 작으면 결제는 성공한다. 이 정책은 기존에 운영 중인 VIP 후불 정산(마이너스 잔액 허용) 기능과 정면으로 충돌하므로, 신규 정책은 새 파라미터 `allow_overdraft`(기본값 `True`)를 통해 명시적으로 활성화(`allow_overdraft=False`)하는 형태로 도입한다(근거는 아래 정책 충돌 참고). 신규 잔액 검증은 기존 `amount<=0` 검증을 항상 통과한 뒤에만 수행되며, 신규 예외 `InsufficientBalanceError`는 기존 `ValueError`와 별도 계층이다.

## 정책 충돌

- `sandbox/wf-eval/case4-wallet/src/wallet.py` 1~4행(모듈 docstring): "마이너스 잔액 허용은 VIP 후불 정산 기능으로, 운영 중인 동작이다." — 잔액 부족 결제를 정상 동작으로 명시하고 있다.
- `sandbox/wf-eval/case4-wallet/src/wallet.py` 21~30행(`pay` 메서드): "잔액이 부족해도 결제는 성공하며 잔액이 음수가 된다 (VIP 후불 정산)." 코드상으로도 잔액 검증 없이 무조건 차감·기록한다.
- `sandbox/wf-eval/case4-wallet/tests/test_wallet.py` 15~19행: `test_pay_allows_negative_balance_for_deferred_settlement`가 `Wallet("vip-lee", 1000).pay(3000) == -2000`을 회귀 테스트로 고정하고 있다.
- 이 프로젝트에는 다른 작업 폴더(`tasks/*/spec.md`)나 `docs/design/`이 없어 기존 승인 spec과의 충돌은 없음(확인 완료, 없음).

request.md의 "잔액 부족 시 결제 거부"를 문자 그대로 모든 지갑에 적용하면 위 VIP 후불 정산 동작 및 회귀 테스트와 직접 모순된다. 두 선택지:

- **옵션 A — 전체 지갑에 무조건 적용**: request 문구를 그대로 구현. 결과: `test_pay_allows_negative_balance_for_deferred_settlement`가 깨지고, 파이프라인 원칙(`/impl`은 기존 테스트 파일을 수정할 수 없음)상 이 테스트를 건드리지 않고는 구현이 성립하지 않는다 — 구현 단계가 항상 실패 원장(failures.md)행이 된다.
- **옵션 B — 옵트인 파라미터로 신규 정책 도입 (기본값)**: `Wallet`에 `allow_overdraft` 파라미터(기본값 `True`)를 추가한다. 파라미터를 지정하지 않으면 기존 동작(잔액 부족해도 결제 성공, 마이너스 허용)이 100% 그대로 유지되어 기존 코드·회귀 테스트가 전혀 바뀌지 않는다. 신규 정책(잔액 부족 시 거부)은 `allow_overdraft=False`로 명시한 호출에만 적용된다.

옵션 B를 기본값으로 채택한다 — 기존에 운영 중인 기능과 회귀 테스트를 파괴하지 않으면서 request의 요구를 실제로 구현 가능한 형태로 만드는 유일한 선택지이기 때문이다. 이 기본값 선택에 따라 아래 정책 전부에 `(기본값)`을 표기한다.

추가로 확인된 두 가지 충돌·미정 지점과 그 해소(spec-review 반영):

- `src/wallet.py` 26~27행의 기존 가드 `if amount <= 0: raise ValueError("결제 금액은 양수여야 합니다")`는 `allow_overdraft` 값과 무관하게 그대로 유지되며 신규 잔액 검증보다 **항상 먼저** 실행된다. 즉 `amount<=0`이면 잔액·`allow_overdraft` 상태와 무관하게 기존과 동일하게 `ValueError`가 발생하고, 신규 정책(P-001-1, P-001-3, P-001-5)은 이 가드를 통과한 `amount>0` 입력에만 적용된다 (기본값). 이로써 `balance=0, amount=0` 같은 입력에서 신규 잔액 검증(P-001-3)과 기존 금액 검증이 동시에 발동해 우선순위가 불명확해지는 문제를 해소한다.
- `InsufficientBalanceError`는 `Exception`을 직접 상속하며 `ValueError`를 상속하지 않는다 (기본값) — 기존 금액 검증(`ValueError`)과 신규 잔액 검증을 호출자가 `except` 절로 구분해 처리할 수 있게 하기 위함이다.

## 변경 범위

- `src/wallet.py` — `InsufficientBalanceError(Exception)` 예외 클래스 추가, `Wallet.__init__`에 `allow_overdraft: bool = True` 파라미터 추가, `pay()`에 잔액 검증 로직 추가. 신규 잔액 검증은 기존 `amount<=0` 검증(26~27행) 통과 후에만 수행한다 — 검증 순서를 바꾸지 않는다.
- `tests/` — `/test`가 정책별 신규 테스트를 추가한다 (기존 `tests/test_wallet.py`의 기존 테스트 함수는 수정하지 않는다). P-001-4는 기존 회귀 테스트와 동일한 입출력을 검증하므로, `/test`는 이를 신규 테스트가 아니라 기존 테스트를 근거로 한 "기존충족"으로 표시할 수 있다.

## 정책

### P-001-1: 잔액 부족 결제 거부 (기본값)
- 규칙: `allow_overdraft=False`로 생성된 지갑에서 `amount>0`이고 `amount`가 `balance`보다 크면, `pay(amount)`는 `InsufficientBalanceError`를 발생시키고 `balance`는 변경되지 않는다. (`amount<=0`은 이 정책과 무관하게 기존 `ValueError` 가드가 그대로 적용된다 — 정책충돌 참고)
- 예시: `Wallet("kim", 1000, allow_overdraft=False).pay(1500)`은 `InsufficientBalanceError`를 발생시키고, 발생 직후 `wallet.balance == 1000`이다.

### P-001-2: 거절된 결제는 history에 남지 않는다 (기본값)
- 규칙: `allow_overdraft=False`인 지갑에서 `InsufficientBalanceError`가 발생한 `pay` 호출은 `history`에 항목을 추가하지 않는다.
- 예시: `w = Wallet("kim", 1000, allow_overdraft=False)`; `w.pay(1500)`이 예외를 발생시킨 뒤 `w.history == []`이다.

### P-001-3: 잔액과 결제 금액이 같으면 결제 성공, 잔액 0 (기본값)
- 규칙: `allow_overdraft=False`인 지갑에서 `amount>0`이고 `amount == balance`이면 `pay(amount)`는 예외 없이 성공하고 반환값과 `balance`가 모두 `0`이 된다. (`amount<=0`인 경우는 P-001-1과 동일하게 이 정책 대상이 아니다)
- 예시: `Wallet("kim", 1000, allow_overdraft=False).pay(1000) == 0`이고 호출 후 `wallet.balance == 0`이다.

### P-001-4: allow_overdraft 미지정 시 기존 동작 보존 (기본값)
- 규칙: `allow_overdraft` 파라미터를 지정하지 않고 생성한 지갑(기본값 `True`)은 잔액 부족 여부와 무관하게 `pay(amount)`가 항상 성공하고 잔액이 음수가 될 수 있다 (기존 VIP 후불 정산 동작과 동일).
- 예시: `Wallet("vip-lee", 1000).pay(3000) == -2000`이고 호출 후 `wallet.balance == -2000`이다 (`tests/test_wallet.py`의 기존 회귀 테스트와 동일한 입출력).

### P-001-5: 잔액 충분 시 정상 결제 성공 (기본값)
- 규칙: `allow_overdraft=False`인 지갑에서 `0 < amount < balance`이면 `pay(amount)`는 예외 없이 성공하고 반환값과 `balance`가 모두 `balance - amount`가 된다.
- 예시: `Wallet("kim", 1000, allow_overdraft=False).pay(400) == 600`이고 호출 후 `wallet.balance == 600`.
