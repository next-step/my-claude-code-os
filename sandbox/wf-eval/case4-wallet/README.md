# 선불 지갑 (case4-wallet)

선불 충전 지갑의 잔액 관리 모듈. 워크플로우 평가용 케이스 4 — 기존 코드와 기존 테스트가 있는 상태에서 작업을 추가한다.

- 언어: Python (테스트는 `uv run --no-project --with pytest -- pytest` 로 실행)
- 코드: `src/`, 테스트: `tests/`
- `src/wallet.py`는 운영 중인 코드다. 마이너스 잔액(후불 정산)은 VIP 고객 대상으로 이미 서비스 중인 기능이다.
