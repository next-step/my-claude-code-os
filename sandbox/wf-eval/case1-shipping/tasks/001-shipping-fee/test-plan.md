---
created: 2026-07-16
policies: 8
tests: 24
---

| 정책 ID | 테스트 이름 | 종류 | 시작 상태 |
|---------|------------|------|----------|
| P-001-1 | test_P001_1_example_base_fee | 예시 | red |
| P-001-1 | test_P001_1_normal_base_fee_just_under_threshold | 정상 | red |
| P-001-1 | test_P001_1_edge_smallest_valid_subtotal | 엣지 | red |
| P-001-2 | test_P001_2_example_free_shipping | 예시 | red |
| P-001-2 | test_P001_2_normal_free_shipping_high_subtotal | 정상 | red |
| P-001-2 | test_P001_2_edge_boundary_crossing | 엣지 | red |
| P-001-3 | test_P001_3_example_jeju_fee | 예시 | red |
| P-001-3 | test_P001_3_normal_jeju_fee_with_base_fee | 정상 | red |
| P-001-3 | test_P001_3_edge_jeju_fee_at_free_shipping_boundary | 엣지 | red |
| P-001-4 | test_P001_4_example_remote_island_fee | 예시 | red |
| P-001-4 | test_P001_4_normal_remote_island_fee_with_base_fee | 정상 | red |
| P-001-4 | test_P001_4_edge_remote_island_fee_at_free_shipping_boundary | 엣지 | red |
| P-001-5 | test_P001_5_example_express_fee | 예시 | red |
| P-001-5 | test_P001_5_normal_express_fee_with_base_fee | 정상 | red |
| P-001-5 | test_P001_5_edge_express_fee_at_free_shipping_boundary | 엣지 | red |
| P-001-6 | test_P001_6_example_zero_subtotal_raises | 예시 | red |
| P-001-6 | test_P001_6_normal_negative_subtotal_raises | 정상 | red |
| P-001-6 | test_P001_6_edge_multiple_violations_still_raises_value_error | 엣지 | red |
| P-001-7 | test_P001_7_example_invalid_region_raises | 예시 | red |
| P-001-7 | test_P001_7_normal_empty_region_raises | 정상 | red |
| P-001-7 | test_P001_7_edge_near_miss_region_string_raises | 엣지 | red |
| P-001-8 | test_P001_8_example_missing_is_express_raises_key_error | 예시 | red |
| P-001-8 | test_P001_8_normal_missing_subtotal_raises_key_error | 정상 | red |
| P-001-8 | test_P001_8_edge_empty_order_raises_key_error | 엣지 | red |
