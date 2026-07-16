---
reviewed: 2026-07-16
applied: 2
deferred: 0
---

## 요약

`src/late_fee.py`를 새 컨텍스트의 general-purpose 서브에이전트에게 spec.md·test-plan.md·테스트 파일과 함께 넘겨 정확성·단순화·견고성 세 관점으로 검토시켰다. 정책 로직(P-001-1~8)의 대수적 정합성, 경계값 처리, 코드 구조(정책별 private 함수 분리)에는 문제가 없다고 확인됐지만, `overdue_days`는 P-001-8로 엄격히 검증하면서 동일하게 계산에 개입하는 `price`는 아무 검증이 없다는 결함 2건(입력 크래시, float 유출)을 지적받았다. 두 시나리오 모두 직접 재현해 실제로 발생함을 확인한 뒤, `_validate_price` 함수를 추가해 `price`도 `overdue_days`와 동일한 수준(0 이상의 정수)으로 검증하도록 수정했다. 기존 25개 테스트는 이 변경 후에도 전부 통과한다.

## 검증

- 적용 전: 25/25 통과
- 적용 후: 25/25 통과
- 실행 명령: `uv run --no-project --with pytest -- pytest tests/ -v` (프로젝트 루트 `sandbox/wf-eval/case3-latefee`에서 실행)

## 적용한 변경

1. **분류**: 결함 (크래시 가능) · **관련 정책**: 일반 (P-001-1~7 전 계산이 전제하는 `price` 입력에 대한 방어 부재)
   - **무엇을 왜 바꿨나**: `price=None`, `price="5000"` 등 비정상 입력 시 `min(surcharged_fee, price)`(`src/late_fee.py`의 `_apply_price_cap_and_floor`)에서 `TypeError`가 발생해 함수가 크래시했다. 재현 확인: `calculate_late_fee(overdue_days=3, price=None, is_popular=False)` → `TypeError: '<' not supported between instances of 'NoneType' and 'int'`. `_validate_price` 함수를 추가해 `calculate_late_fee` 진입부에서 `overdue_days`와 동일하게 명확한 `ValueError`로 거부하도록 했다.
   - **근거 파일**: `sandbox/wf-eval/case3-latefee/src/late_fee.py` (`_validate_price` 신설, `calculate_late_fee` 첫 줄에 호출 추가)

2. **분류**: 결함 (정책/계약 위반 가능) · **관련 정책**: 일반 (spec의 모든 예시가 정수 원 단위를 전제, 테스트 독스트링도 `"fee": int` 명시)
   - **무엇을 왜 바꿨나**: `price`가 float(예: `1600.7`)이면 `min`/`max` 연산을 그대로 통과해 결과 `fee`가 `1600.7`처럼 소수 원으로 반환됐다. 재현 확인: `calculate_late_fee(overdue_days=3, price=1600.7, is_popular=True)` → `{'fee': 1600.7, ...}`. `_validate_price`가 `price`의 정수 여부까지 함께 검증하도록 해 float 입력 자체를 거부, 정수 원 계약을 지키도록 했다(결함 1과 동일한 수정으로 함께 해소됨).
   - **근거 파일**: `sandbox/wf-eval/case3-latefee/src/late_fee.py`

## 보류한 지적

없음 — 서브에이전트가 제시한 지적 2건 모두 재현 확인 후 적용했고, 테스트는 변경 전후 모두 25/25로 회귀 없음을 확인했다.
