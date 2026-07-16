---
created: 2026-07-16
policies: 8
tests: 25
---

| 정책 ID | 테스트 이름 | 종류 | 시작 상태 |
|---------|------------|------|----------|
| P-001-1 | test_P001_1_example_silver_50000 | 예시 | red |
| P-001-1 | test_P001_1_normal_silver_20000 | 정상 | red |
| P-001-1 | test_P001_1_edge_silver_floor_rounding | 엣지 | red |
| P-001-2 | test_P001_2_example_gold_50000 | 예시 | red |
| P-001-2 | test_P001_2_normal_gold_30000 | 정상 | red |
| P-001-2 | test_P001_2_edge_gold_floor_rounding | 엣지 | red |
| P-001-3 | test_P001_3_example_vip_50000 | 예시 | red |
| P-001-3 | test_P001_3_normal_vip_10000 | 정상 | red |
| P-001-3 | test_P001_3_edge_vip_floor_rounding | 엣지 | red |
| P-001-4 | test_P001_4_example_discounted_order_25000 | 예시 | red |
| P-001-4 | test_P001_4_normal_discounted_order_still_earns | 정상 | red |
| P-001-4 | test_P001_4_edge_discounted_amount_at_minimum_threshold | 엣지 | red |
| P-001-5 | test_P001_5_example_event_double_silver | 예시 | red |
| P-001-5 | test_P001_5_normal_event_double_gold | 정상 | red |
| P-001-5 | test_P001_5_edge_floor_applied_once_not_per_step | 엣지 | red |
| P-001-6 | test_P001_6_example_cap_applied_vip_event | 예시 | red |
| P-001-6 | test_P001_6_normal_below_cap_not_reduced | 정상 | red |
| P-001-6 | test_P001_6_edge_exact_cap_boundary_not_reduced | 엣지 | red |
| P-001-7 | test_P001_7_example_below_minimum_excluded | 예시 | red |
| P-001-7 | test_P001_7_normal_above_minimum | 정상 | red |
| P-001-7 | test_P001_7_edge_exact_minimum_boundary_included | 엣지 | red |
| P-001-7 | test_P001_7_edge_zero_amount_excluded | 엣지 | red |
| P-001-8 | test_P001_8_example_invalid_grade_raises | 예시 | red |
| P-001-8 | test_P001_8_normal_invalid_grade_empty_string_raises | 정상 | red |
| P-001-8 | test_P001_8_edge_invalid_grade_none_raises | 엣지 | red |
