---
created: 2026-07-16
policies: 7
tests: 23
---

| 정책 ID | 테스트 이름 | 종류 | 시작 상태 |
|---------|------------|------|----------|
| P-001-1 | test_P001_1_example_ten_requests_within_window_allowed | 예시 | red |
| P-001-1 | test_P001_1_normal_single_request_allowed | 정상 | red |
| P-001-1 | test_P001_1_edge_exactly_at_limit_allowed | 엣지 | red |
| P-001-1 | test_P001_1_edge_different_users_have_independent_counters | 엣지 | red |
| P-001-2 | test_P001_2_example_eleventh_request_denied_and_blocked | 예시 | red |
| P-001-2 | test_P001_2_normal_exceeding_smaller_limit_denied | 정상 | red |
| P-001-2 | test_P001_2_edge_block_persists_immediately_after_violation | 엣지 | red |
| P-001-3 | test_P001_3_example_penalty_doubles_on_reattempt_during_block | 예시 | red |
| P-001-3 | test_P001_3_normal_repeated_reattempts_double_each_time | 정상 | red |
| P-001-3 | test_P001_3_edge_one_tick_before_extended_block_end_still_denied | 엣지 | red |
| P-001-4 | test_P001_4_example_allowed_after_block_expires_and_window_resets | 예시 | red |
| P-001-4 | test_P001_4_normal_full_new_window_allowance_after_release | 정상 | red |
| P-001-4 | test_P001_4_edge_exact_block_end_timestamp_is_allowed | 엣지 | red |
| P-001-5 | test_P001_5_example_thousand_users_immediate_no_delay | 예시 | red |
| P-001-5 | test_P001_5_normal_repeated_calls_single_user_immediate | 정상 | red |
| P-001-5 | test_P001_5_edge_source_has_no_blocking_io_or_sleep_calls | 엣지 | red |
| P-001-6 | test_P001_6_example_first_request_logs_all_fields | 예시 | red |
| P-001-6 | test_P001_6_normal_denied_request_logs_limit_exceeded_reason | 정상 | red |
| P-001-6 | test_P001_6_edge_exactly_one_record_per_call | 엣지 | red |
| P-001-6 | test_P001_6_edge_blocked_reattempt_request_count_frozen | 엣지 | red |
| P-001-7 | test_P001_7_example_natural_window_reset_without_prior_block | 예시 | red |
| P-001-7 | test_P001_7_normal_low_volume_user_window_resets_repeatedly | 정상 | red |
| P-001-7 | test_P001_7_edge_exact_window_boundary_resets | 엣지 | red |

비고: 23개 테스트 전부 `src/rate_limiter.py`(RateLimiter 클래스)가 아직 존재하지 않아 `ModuleNotFoundError`로 인한 수집 단계 오류(빨강)로 확인됨. 이는 스킬 지시문의 "미구현 기능 호출로 인한 실패는 정상 red"에 해당한다.
