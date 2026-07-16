---
created: 2026-07-16
policies: 8
tests: 25
---

| 정책 ID | 테스트 이름 | 종류 | 시작 상태 |
|---------|------------|------|----------|
| P-001-1 | test_P001_1_example_three_days | 예시 | red |
| P-001-1 | test_P001_1_normal_one_day | 정상 | red |
| P-001-1 | test_P001_1_edge_zero_days | 엣지 | red |
| P-001-1 | test_P001_1_edge_day_six_boundary_continuity | 엣지 | red |
| P-001-2 | test_P001_2_example_ten_days | 예시 | red |
| P-001-2 | test_P001_2_normal_exactly_seven_days | 정상 | red |
| P-001-2 | test_P001_2_edge_day_eight_after_week | 엣지 | red |
| P-001-3 | test_P001_3_example_popular_three_days | 예시 | red |
| P-001-3 | test_P001_3_normal_popular_one_day | 정상 | red |
| P-001-3 | test_P001_3_edge_popular_with_weekly_discount | 엣지 | red |
| P-001-4 | test_P001_4_example_price_cap_reduces_surcharge | 예시 | red |
| P-001-4 | test_P001_4_normal_floor_guarantee_nonpopular_cheap_book | 정상 | red |
| P-001-4 | test_P001_4_edge_floor_overrides_multiplier_when_price_below_base | 엣지 | red |
| P-001-5 | test_P001_5_example_capped_at_ten_thousand | 예시 | red |
| P-001-5 | test_P001_5_normal_capped_with_different_inputs | 정상 | red |
| P-001-5 | test_P001_5_edge_exactly_at_cap_boundary | 엣지 | red |
| P-001-6 | test_P001_6_example_reimbursement_floored_by_day30_fee | 예시 | red |
| P-001-6 | test_P001_6_normal_expensive_book_reimburses_price | 정상 | red |
| P-001-6 | test_P001_6_edge_day30_not_lost_and_no_regression_at_day31 | 엣지 | red |
| P-001-7 | test_P001_7_example_accrued_after_loss | 예시 | red |
| P-001-7 | test_P001_7_normal_accrued_just_after_loss_threshold | 정상 | red |
| P-001-7 | test_P001_7_edge_accrued_differs_from_fee_before_loss | 엣지 | red |
| P-001-8 | test_P001_8_example_negative_days_raises | 예시 | red |
| P-001-8 | test_P001_8_normal_zero_days_is_valid | 정상 | red |
| P-001-8 | test_P001_8_edge_non_integer_days_raises | 엣지 | red |

비고: 25개 테스트 전부 `src/late_fee.py`가 아직 존재하지 않아 `ModuleNotFoundError`로 인한 컬렉션 에러로 실패했다(`uv run --no-project --with pytest -- pytest tests/ -v` 실행 결과: `1 error during collection`). 테스트 파일 자체의 문법/설정 오류가 아니라 미구현 대상 모듈 호출로 인한 실패이므로 정상 red 상태로 간주한다.
