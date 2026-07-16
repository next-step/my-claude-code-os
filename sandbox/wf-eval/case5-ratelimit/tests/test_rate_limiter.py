"""P-001-1 ~ P-001-7 (spec.md) 정책별 테스트.

로그 형식(P-001-6) 관련 참고: spec.md는 로그에 포함될 필드 목록만 규정하고
정확한 문자열 포맷은 규정하지 않는다. 이 테스트는 `logging` 모듈을 통해
`key=value` 공백 구분 형식(예: "user_id=u1 decision=allow reason=within_limit
request_count=1 now=0")으로 기록된다고 가정한다 — 이는 /test 단계에서 내린
해석으로, 구현이 이 포맷을 따르지 않으면 impl 단계에서 조정이 필요할 수 있다.
"""
import inspect
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rate_limiter import RateLimiter


# ---------------------------------------------------------------------------
# P-001-1: 윈도우 내 허용 한도
# ---------------------------------------------------------------------------

def test_P001_1_example_ten_requests_within_window_allowed():
    rl = RateLimiter(limit=10, window_seconds=60, base_block_seconds=60)
    for now in range(10):
        assert rl.allow("u1", now) is True


def test_P001_1_normal_single_request_allowed():
    rl = RateLimiter()
    assert rl.allow("solo-user", 0) is True


def test_P001_1_edge_exactly_at_limit_allowed():
    rl = RateLimiter(limit=10, window_seconds=60, base_block_seconds=60)
    for now in range(9):
        rl.allow("u1", now)
    # 10번째 요청(누적 카운트가 한도와 정확히 같아지는 경계)도 허용되어야 한다.
    assert rl.allow("u1", 9) is True


def test_P001_1_edge_different_users_have_independent_counters():
    rl = RateLimiter(limit=1, window_seconds=60, base_block_seconds=60)
    assert rl.allow("alice", 0) is True
    # alice가 한도를 채웠어도 bob은 독립적으로 자신의 첫 요청이 허용되어야 한다.
    assert rl.allow("bob", 0) is True


# ---------------------------------------------------------------------------
# P-001-2: 한도 초과 시 거부와 차단 시작 (기본값)
# ---------------------------------------------------------------------------

def test_P001_2_example_eleventh_request_denied_and_blocked():
    rl = RateLimiter(limit=10, window_seconds=60, base_block_seconds=60)
    for now in range(10):
        assert rl.allow("u1", now) is True
    assert rl.allow("u1", 10) is False


def test_P001_2_normal_exceeding_smaller_limit_denied():
    rl = RateLimiter(limit=3, window_seconds=60, base_block_seconds=30)
    assert rl.allow("u2", 0) is True
    assert rl.allow("u2", 1) is True
    assert rl.allow("u2", 2) is True
    assert rl.allow("u2", 3) is False  # 4번째 요청이 한도(3)를 초과


def test_P001_2_edge_block_persists_immediately_after_violation():
    rl = RateLimiter(limit=10, window_seconds=60, base_block_seconds=60)
    for now in range(10):
        rl.allow("u1", now)
    rl.allow("u1", 10)  # 차단 시작: duration=60, end=70
    # 위반 직후(같은 순간에 가까운 시점)에도 차단이 유지되어야 한다.
    assert rl.allow("u1", 11) is False


# ---------------------------------------------------------------------------
# P-001-3: 차단 중 재요청 시 페널티 연장 (기본값)
# ---------------------------------------------------------------------------

def test_P001_3_example_penalty_doubles_on_reattempt_during_block():
    rl = RateLimiter(limit=10, window_seconds=60, base_block_seconds=60)
    for now in range(10):
        assert rl.allow("u1", now) is True
    assert rl.allow("u1", 10) is False   # 차단 시작: duration=60, end=70
    assert rl.allow("u1", 15) is False   # 재요청: duration 60*2=120, end=15+120=135
    assert rl.allow("u1", 135) is True   # 135에 차단 완전 해제 (P-001-4)


def test_P001_3_normal_repeated_reattempts_double_each_time():
    rl = RateLimiter(limit=2, window_seconds=60, base_block_seconds=10)
    assert rl.allow("u3", 0) is True
    assert rl.allow("u3", 1) is True
    assert rl.allow("u3", 2) is False   # 차단 시작: duration=10, end=12
    assert rl.allow("u3", 5) is False   # 재요청(5<12): duration=20, end=25
    assert rl.allow("u3", 20) is False  # 재요청(20<25): duration=40, end=60
    assert rl.allow("u3", 60) is True   # 60>=60, 차단 해제


def test_P001_3_edge_one_tick_before_extended_block_end_still_denied():
    rl = RateLimiter(limit=10, window_seconds=60, base_block_seconds=60)
    for now in range(10):
        rl.allow("u1", now)
    rl.allow("u1", 10)   # duration=60, end=70
    rl.allow("u1", 15)   # 연장: duration=120, end=135
    assert rl.allow("u1", 134) is False  # 연장된 종료 시각 1틱 전에도 여전히 차단


# ---------------------------------------------------------------------------
# P-001-4: 차단 해제 후 윈도우 리셋
# ---------------------------------------------------------------------------

def test_P001_4_example_allowed_after_block_expires_and_window_resets():
    rl = RateLimiter(limit=10, window_seconds=60, base_block_seconds=60)
    for now in range(10):
        rl.allow("u1", now)
    rl.allow("u1", 10)
    rl.allow("u1", 15)
    assert rl.allow("u1", 140) is True


def test_P001_4_normal_full_new_window_allowance_after_release():
    rl = RateLimiter(limit=3, window_seconds=60, base_block_seconds=10)
    rl.allow("u5", 0)
    rl.allow("u5", 1)
    rl.allow("u5", 2)
    assert rl.allow("u5", 3) is False   # 초과: duration=10, end=13
    assert rl.allow("u5", 13) is True   # 새 윈도우 첫 요청
    assert rl.allow("u5", 14) is True   # 두 번째
    assert rl.allow("u5", 15) is True   # 세 번째 (한도=3)
    assert rl.allow("u5", 16) is False  # 네 번째는 다시 초과


def test_P001_4_edge_exact_block_end_timestamp_is_allowed():
    rl = RateLimiter(limit=1, window_seconds=60, base_block_seconds=5)
    rl.allow("u6", 0)                   # 카운트=1, 허용
    assert rl.allow("u6", 1) is False   # 초과: duration=5, end=6
    assert rl.allow("u6", 6) is True    # 차단 종료 시각과 정확히 같은 순간 -> 해제


# ---------------------------------------------------------------------------
# P-001-5: 무지연 인메모리 판정 (기본값)
# ---------------------------------------------------------------------------

def test_P001_5_example_thousand_users_immediate_no_delay():
    rl = RateLimiter()
    start = time.perf_counter()
    for i in range(1000):
        rl.allow(f"user-{i}", 0)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0


def test_P001_5_normal_repeated_calls_single_user_immediate():
    rl = RateLimiter()
    start = time.perf_counter()
    for now in range(100):
        rl.allow("solo", now)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.5


def test_P001_5_edge_source_has_no_blocking_io_or_sleep_calls():
    import rate_limiter as rl_module

    source = inspect.getsource(rl_module)
    forbidden = ["time.sleep(", "socket.", "requests.", "open(", "urllib", "subprocess"]
    for token in forbidden:
        assert token not in source, f"blocking/IO 호출 감지: {token}"


# ---------------------------------------------------------------------------
# P-001-6: 구조화된 판정 로그 (기본값)
# ---------------------------------------------------------------------------

def test_P001_6_example_first_request_logs_all_fields(caplog):
    rl = RateLimiter()
    with caplog.at_level(logging.INFO):
        rl.allow("u1", 0)
    assert len(caplog.records) == 1
    msg = caplog.records[0].getMessage()
    assert "user_id=u1" in msg
    assert "decision=allow" in msg
    assert "reason=within_limit" in msg
    assert "request_count=1" in msg
    assert "now=0" in msg


def test_P001_6_normal_denied_request_logs_limit_exceeded_reason(caplog):
    rl = RateLimiter(limit=1, window_seconds=60, base_block_seconds=10)
    rl.allow("u7", 0)
    with caplog.at_level(logging.INFO):
        rl.allow("u7", 1)
    assert len(caplog.records) == 1
    msg = caplog.records[0].getMessage()
    assert "decision=deny" in msg
    assert "reason=limit_exceeded" in msg


def test_P001_6_edge_exactly_one_record_per_call(caplog):
    rl = RateLimiter()
    with caplog.at_level(logging.INFO):
        rl.allow("u8", 0)
        rl.allow("u8", 1)
        rl.allow("u8", 2)
    assert len(caplog.records) == 3


def test_P001_6_edge_blocked_reattempt_request_count_frozen(caplog):
    rl = RateLimiter(limit=1, window_seconds=60, base_block_seconds=10)
    rl.allow("u9", 0)          # request_count=1, allow
    rl.allow("u9", 1)          # request_count=2, deny (limit_exceeded), 차단 시작
    with caplog.at_level(logging.INFO):
        rl.allow("u9", 2)      # 차단 중 재요청 (blocked) -> request_count는 증가하지 않음
    assert len(caplog.records) == 1
    msg = caplog.records[0].getMessage()
    assert "decision=deny" in msg
    assert "reason=blocked" in msg
    assert "request_count=2" in msg  # 차단을 유발한 시점 값(2)에서 고정


# ---------------------------------------------------------------------------
# P-001-7: 차단 이력 없이 자연 경과한 윈도우의 리셋 (기본값)
# ---------------------------------------------------------------------------

def test_P001_7_example_natural_window_reset_without_prior_block():
    rl = RateLimiter(limit=10, window_seconds=60, base_block_seconds=60)
    for now in range(0, 50, 5):  # 0,5,10,...,45 (10회)
        assert rl.allow("u2", now) is True
    assert rl.allow("u2", 65) is True


def test_P001_7_normal_low_volume_user_window_resets_repeatedly():
    rl = RateLimiter(limit=2, window_seconds=10, base_block_seconds=5)
    assert rl.allow("u10", 0) is True
    assert rl.allow("u10", 20) is True   # 윈도우 자연 경과 -> 리셋, 카운트=1
    assert rl.allow("u10", 21) is True   # 카운트=2 (한도=2 이내)
    assert rl.allow("u10", 22) is False  # 카운트=3, 한도 초과 -> 거부


def test_P001_7_edge_exact_window_boundary_resets():
    rl = RateLimiter(limit=1, window_seconds=10, base_block_seconds=5)
    assert rl.allow("u11", 0) is True    # 카운트=1, 윈도우 시작=0
    assert rl.allow("u11", 10) is True   # 정확히 10초 경과 -> 윈도우 리셋, 카운트=1로 다시 허용
