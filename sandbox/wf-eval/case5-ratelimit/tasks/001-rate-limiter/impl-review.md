---
reviewed: 2026-07-16
applied: 2
deferred: 0
---

## 요약

`src/rate_limiter.py`(`RateLimiter` 클래스, P-001-1~7 구현)를 새 컨텍스트의 general-purpose 서브에이전트에게 정확성·단순화·견고성 세 관점으로 검토하도록 위임했다. 검토자는 상태 불변식, 차단 우선순위, `request_count` 동결 로직, 윈도우 리셋과 차단 해제의 상호작용, 로그 필드를 경계값·중복 실행 시나리오로 수동 추적했으나 정책 위반이나 크래시로 이어지는 결함은 찾지 못했다("결함 없음"). 개선 지적 2건(죽은 조건 단순화, 핫패스에서의 불필요한 딕셔너리 할당)을 찾아냈고, 둘 다 동작을 바꾸지 않는 것으로 판단해 이 세션이 직접 적용했다. 적용 후 테스트는 여전히 23/23 통과한다.

## 검증

- 실행 명령: `uv run --no-project --with pytest -- pytest tests/ -v` (프로젝트 루트: `sandbox/wf-eval/case5-ratelimit`)
- 적용 전: 23/23
- 적용 후: 23/23

## 적용한 변경

1. **분류:** 개선 · **관련 정책:** 일반 (P-001-5 무지연 판정의 취지) · **근거:** `src/rate_limiter.py:40`(적용 전) — `self._state.setdefault(user_id, self._new_state(now))`는 Python이 인자를 먼저 평가하므로 기존 사용자가 반복 요청하는 핫패스에서도 매 호출마다 버려지는 딕셔너리를 할당하고 있었다. **변경:** `self._state.get(user_id)`로 조회 후 `None`일 때만 `_new_state(now)`를 생성해 저장하도록 바꿔, 기존 사용자 경로에서 불필요한 할당을 없앴다.
2. **분류:** 개선 · **관련 정책:** P-001-4 / P-001-7 (로직 단순화) · **근거:** `src/rate_limiter.py:73`(적용 전) — `_reset_window_if_elapsed`는 `allow()`에서 `_is_blocked(state, now)`가 이미 `False`를 반환한 뒤에만 호출되므로, 이 시점에 `block_until is not None`이면 `now >= block_until`은 항상 참인 죽은 조건이었다. **변경:** `block_just_released = ... and now >= state["block_until"]`를 `had_pending_block = state["block_until"] is not None`로 단순화하고, 이 불변식을 설명하는 주석을 추가했다. 변수명도 "방금 풀림"이 아니라 "만료된 차단 이력이 있었음"이라는 실제 의미에 맞게 바꿨다.

## 보류한 지적

없음 — 서브에이전트가 제시한 지적은 개선 2건뿐이었고 둘 다 적용했다. 결함(정확성) 지적은 없었다.
