---
reviewed: 2026-07-16
applied: 3
deferred: 0
---

## 요약

`src/points.py`(`calculate_earned_points`)를 spec.md(P-001-1~8)와 test-plan.md에 매핑된 `tests/test_points.py`를 근거로 general-purpose 서브에이전트가 새 컨텍스트에서 검토했다. 서브에이전트는 결함 2건(이벤트 기간 플래그의 진리값 강제 평가로 인한 P-001-5 위반 가능성, `payment_amount`에 비숫자 값이 들어올 때의 예측 불가능한 크래시)과 개선 1건(등급 값이 해시 불가능한 타입일 때 `ValueError` 계약이 깨지는 문제)을 지적했다. 세 건 모두 실제로 재현해 문제를 확인한 뒤 `calculate_earned_points`에 입력 유효성 검사를 추가해 세 경로 모두 일관되게 `ValueError`를 던지도록 수정했고, 적용 후 25개 테스트 전부 유지됨을 확인했다.

## 검증

- 실행 명령: `uv run --no-project --with pytest -- pytest tests/ -v` (프로젝트 루트 `sandbox/wf-eval/case2-points`에서 실행)
- 전 25/25 (기준선, 2단계) / 후 25/25 (3건 적용 후 재실행)

## 적용한 변경

1. **결함** · 관련 정책: P-001-5 — `is_event_period`가 실제 `bool`이 아니라 문자열 등으로 전달되면 파이썬 진리값(truthy) 평가에 의존해 `calculate_earned_points("실버", 50000, "False")`가 이벤트 배수(2배)를 잘못 적용해 1,000포인트를 반환함을 재현으로 확인(원래 기대는 비이벤트 500포인트 상당). `is_event_period`가 `bool`이 아니면 `ValueError`를 던지도록 검증을 추가했다. 근거 파일: `sandbox/wf-eval/case2-points/src/points.py`.
2. **결함** · 관련 정책: 일반(P-001-7 최소 결제금액 판정 직전 경로) — `calculate_earned_points("실버", None, False)`가 `None < 1000` 비교에서 `TypeError`로 크래시함을 재현으로 확인. `payment_amount`가 `int`/`float`가 아니면 `ValueError`를 던지도록 검증을 추가했다. 근거 파일: `sandbox/wf-eval/case2-points/src/points.py`.
3. **개선** · 관련 정책: 일반(P-001-8 예외 계약 일관성) — `grade`가 리스트 등 해시 불가능한 값이면 `in` 연산 자체가 `TypeError`를 던져 P-001-8이 보장해야 할 `ValueError` 계약이 깨짐을 재현으로 확인. `isinstance(grade, str)` 검사를 딕셔너리 조회 앞에 추가해 항상 `ValueError`로 통일했다. 근거 파일: `sandbox/wf-eval/case2-points/src/points.py`.

## 보류한 지적

없음 — 서브에이전트가 제기한 3건 모두 재현에 성공했고 적용 후에도 25개 테스트가 전부 통과해 전부 반영했다.
