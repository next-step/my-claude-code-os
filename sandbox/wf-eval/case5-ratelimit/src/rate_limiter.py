"""사용자별 API 요청 제한기 (spec.md P-001-1 ~ P-001-7).

고정 1분 윈도우 안에서 사용자당 최대 `limit`회 요청을 허용하고, 초과 시
`base_block_seconds` 동안 차단한다. 차단 중 재요청은 차단 시간을 2배로
연장한다(P-001-3). 차단이 풀리거나(P-001-4) 차단 이력 없이 윈도우가
자연 경과하면(P-001-7) 새 윈도우로 취급해 카운트를 리셋한다.

모든 판정은 인메모리 상태만으로 즉시 반환하며(P-001-5), 판정마다 구조화된
로그 1건을 남긴다(P-001-6).
"""
import logging

_logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 10
DEFAULT_WINDOW_SECONDS = 60
DEFAULT_BASE_BLOCK_SECONDS = 60

REASON_WITHIN_LIMIT = "within_limit"
REASON_LIMIT_EXCEEDED = "limit_exceeded"
REASON_BLOCKED = "blocked"
REASON_WINDOW_RESET = "window_reset"

PENALTY_MULTIPLIER = 2


class RateLimiter:
    def __init__(
        self,
        limit: int = DEFAULT_LIMIT,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        base_block_seconds: float = DEFAULT_BASE_BLOCK_SECONDS,
    ):
        self.limit = limit
        self.window_seconds = window_seconds
        self.base_block_seconds = base_block_seconds
        self._state: dict[str, dict] = {}

    def allow(self, user_id: str, now: float) -> bool:
        state = self._state.get(user_id)
        if state is None:
            state = self._new_state(now)
            self._state[user_id] = state

        if self._is_blocked(state, now):
            self._extend_block(state, now)  # P-001-3
            self._log(user_id, "deny", REASON_BLOCKED, state["count"], now)
            return False

        did_reset = self._reset_window_if_elapsed(state, now)  # P-001-4 / P-001-7
        state["count"] += 1

        if state["count"] <= self.limit:  # P-001-1
            reason = REASON_WINDOW_RESET if did_reset else REASON_WITHIN_LIMIT
            self._log(user_id, "allow", reason, state["count"], now)
            return True

        self._start_block(state, now)  # P-001-2
        self._log(user_id, "deny", REASON_LIMIT_EXCEEDED, state["count"], now)
        return False

    @staticmethod
    def _new_state(now: float) -> dict:
        return {"window_start": now, "count": 0, "block_until": None, "block_duration": None}

    @staticmethod
    def _is_blocked(state: dict, now: float) -> bool:
        return state["block_until"] is not None and now < state["block_until"]

    @staticmethod
    def _extend_block(state: dict, now: float) -> None:
        state["block_duration"] *= PENALTY_MULTIPLIER
        state["block_until"] = now + state["block_duration"]

    def _reset_window_if_elapsed(self, state: dict, now: float) -> bool:
        # allow()가 여기 도달하는 시점엔 이미 _is_blocked(state, now)가 False였다 —
        # 즉 block_until이 있다면 반드시 이미 만료된 상태(now >= block_until)다.
        had_pending_block = state["block_until"] is not None
        window_elapsed = (now - state["window_start"]) >= self.window_seconds
        if not (had_pending_block or window_elapsed):
            return False
        state["window_start"] = now
        state["count"] = 0
        state["block_until"] = None
        state["block_duration"] = None
        return True

    def _start_block(self, state: dict, now: float) -> None:
        state["block_duration"] = self.base_block_seconds
        state["block_until"] = now + self.base_block_seconds

    def _log(self, user_id: str, decision: str, reason: str, request_count: int, now: float) -> None:
        _logger.info(
            "user_id=%s decision=%s reason=%s request_count=%s now=%s",
            user_id,
            decision,
            reason,
            request_count,
            now,
        )
