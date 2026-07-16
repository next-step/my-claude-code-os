---
created: 2026-07-16
policies: 5
tests: 16
---

| 정책 ID | 테스트 이름 | 종류 | 시작 상태 |
|---------|------------|------|----------|
| P-001-1 | test_P001_1_example_pay_exceeds_balance_raises | 예시 | red |
| P-001-1 | test_P001_1_normal_reject_with_different_amounts | 정상 | red |
| P-001-1 | test_P001_1_edge_amount_one_over_balance | 엣지 | red |
| P-001-1 | test_P001_1_edge_amount_zero_raises_valueerror_not_insufficient | 엣지 | red |
| P-001-2 | test_P001_2_example_rejected_payment_history_empty | 예시 | red |
| P-001-2 | test_P001_2_normal_history_unchanged_after_rejection | 정상 | red |
| P-001-2 | test_P001_2_edge_repeated_rejections_do_not_accumulate | 엣지 | red |
| P-001-3 | test_P001_3_example_pay_equals_balance_succeeds | 예시 | red |
| P-001-3 | test_P001_3_normal_pay_equals_balance_different_amount | 정상 | red |
| P-001-3 | test_P001_3_edge_smallest_balance_equals_amount | 엣지 | red |
| P-001-4 | test_P001_4_example_default_allows_negative_balance | 예시 | 기존충족 |
| P-001-4 | test_P001_4_normal_default_negative_balance_different_amount | 정상 | 기존충족 |
| P-001-4 | test_P001_4_edge_explicit_allow_overdraft_true_matches_default | 엣지 | red |
| P-001-5 | test_P001_5_example_pay_less_than_balance_succeeds | 예시 | red |
| P-001-5 | test_P001_5_normal_pay_less_than_balance_different_amount | 정상 | red |
| P-001-5 | test_P001_5_edge_pay_one_unit_below_balance | 엣지 | red |
