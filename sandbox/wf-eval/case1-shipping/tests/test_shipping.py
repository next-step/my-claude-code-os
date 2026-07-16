import pytest

from src.shipping import calculate_shipping


# P-001-1: 기본 배송비 (subtotal < 50000 -> 기본 배송비 3000원)

def test_P001_1_example_base_fee():
    # spec 예시: subtotal=10000, region="일반", is_express=False -> 3,000원
    assert calculate_shipping({"subtotal": 10000, "region": "일반", "is_express": False}) == 3000


def test_P001_1_normal_base_fee_just_under_threshold():
    # 무료배송 임계값(50000) 바로 아래 -> 기본 배송비 3000원 그대로 부과
    assert calculate_shipping({"subtotal": 49999, "region": "일반", "is_express": False}) == 3000


def test_P001_1_edge_smallest_valid_subtotal():
    # 유효한 최소 subtotal(1) -> 기본 배송비 3000원
    assert calculate_shipping({"subtotal": 1, "region": "일반", "is_express": False}) == 3000


# P-001-2: 무료 배송 임계값 (subtotal >= 50000 -> 기본 배송비 0원)

def test_P001_2_example_free_shipping():
    # spec 예시: subtotal=50000, region="일반", is_express=False -> 0원
    assert calculate_shipping({"subtotal": 50000, "region": "일반", "is_express": False}) == 0


def test_P001_2_normal_free_shipping_high_subtotal():
    assert calculate_shipping({"subtotal": 100000, "region": "일반", "is_express": False}) == 0


def test_P001_2_edge_boundary_crossing():
    # 임계값을 하나씩 넘나드는 경계: 49999는 유료, 50000은 무료
    assert calculate_shipping({"subtotal": 49999, "region": "일반", "is_express": False}) == 3000
    assert calculate_shipping({"subtotal": 50000, "region": "일반", "is_express": False}) == 0


# P-001-3: 제주 지역 추가비 (무료배송 여부와 무관하게 항상 3000원)

def test_P001_3_example_jeju_fee():
    # spec 예시: subtotal=60000, region="제주", is_express=False -> 3,000원
    assert calculate_shipping({"subtotal": 60000, "region": "제주", "is_express": False}) == 3000


def test_P001_3_normal_jeju_fee_with_base_fee():
    # 기본 배송비(3000) + 제주 추가비(3000)
    assert calculate_shipping({"subtotal": 10000, "region": "제주", "is_express": False}) == 6000


def test_P001_3_edge_jeju_fee_at_free_shipping_boundary():
    # 무료배송 임계값 경계(정확히 50000)에서도 제주 추가비는 그대로 부과
    assert calculate_shipping({"subtotal": 50000, "region": "제주", "is_express": False}) == 3000


# P-001-4: 도서산간 지역 추가비 (무료배송 여부와 무관하게 항상 5000원)

def test_P001_4_example_remote_island_fee():
    # spec 예시(request.md 원본 예시와 동일): subtotal=60000, region="도서산간", is_express=False -> 5,000원
    assert calculate_shipping({"subtotal": 60000, "region": "도서산간", "is_express": False}) == 5000


def test_P001_4_normal_remote_island_fee_with_base_fee():
    # 기본 배송비(3000) + 도서산간 추가비(5000)
    assert calculate_shipping({"subtotal": 10000, "region": "도서산간", "is_express": False}) == 8000


def test_P001_4_edge_remote_island_fee_at_free_shipping_boundary():
    assert calculate_shipping({"subtotal": 50000, "region": "도서산간", "is_express": False}) == 5000


# P-001-5: 특급 배송비 (is_express is True -> 무료배송 여부와 무관하게 항상 2000원)

def test_P001_5_example_express_fee():
    # spec 예시: subtotal=60000, region="일반", is_express=True -> 2,000원
    assert calculate_shipping({"subtotal": 60000, "region": "일반", "is_express": True}) == 2000


def test_P001_5_normal_express_fee_with_base_fee():
    # 기본 배송비(3000) + 특급비(2000)
    assert calculate_shipping({"subtotal": 10000, "region": "일반", "is_express": True}) == 5000


def test_P001_5_edge_express_fee_at_free_shipping_boundary():
    # 무료배송 임계값 경계(정확히 50000)에서도 특급비는 그대로 부과
    assert calculate_shipping({"subtotal": 50000, "region": "일반", "is_express": True}) == 2000


# P-001-6: subtotal 값 검증 (subtotal <= 0 -> ValueError)

def test_P001_6_example_zero_subtotal_raises():
    # spec 예시: subtotal=0, region="일반", is_express=False -> ValueError
    with pytest.raises(ValueError):
        calculate_shipping({"subtotal": 0, "region": "일반", "is_express": False})


def test_P001_6_normal_negative_subtotal_raises():
    with pytest.raises(ValueError):
        calculate_shipping({"subtotal": -100, "region": "일반", "is_express": False})


def test_P001_6_edge_multiple_violations_still_raises_value_error():
    # subtotal(0 이하)과 region(부적합)이 동시에 위반돼도 ValueError 하나만 발생하면 됨 (spec-review 반례 1)
    with pytest.raises(ValueError):
        calculate_shipping({"subtotal": -1000, "region": "부산", "is_express": False})


# P-001-7: region 값 검증 (허용된 세 값이 아니면 -> ValueError)

def test_P001_7_example_invalid_region_raises():
    # spec 예시: subtotal=10000, region="서울", is_express=False -> ValueError
    with pytest.raises(ValueError):
        calculate_shipping({"subtotal": 10000, "region": "서울", "is_express": False})


def test_P001_7_normal_empty_region_raises():
    with pytest.raises(ValueError):
        calculate_shipping({"subtotal": 10000, "region": "", "is_express": False})


def test_P001_7_edge_near_miss_region_string_raises():
    # 허용값과 유사하지만 정확히 일치하지 않는 문자열(공백 포함)도 ValueError
    with pytest.raises(ValueError):
        calculate_shipping({"subtotal": 10000, "region": "제주 ", "is_express": False})


# P-001-8: 누락된 키의 처리 (키가 없으면 KeyError가 그대로 전파되어야 한다)

def test_P001_8_example_missing_is_express_raises_key_error():
    # spec 예시: order={"subtotal": 10000, "region": "일반"} (is_express 키 없음) -> KeyError
    with pytest.raises(KeyError):
        calculate_shipping({"subtotal": 10000, "region": "일반"})


def test_P001_8_normal_missing_subtotal_raises_key_error():
    with pytest.raises(KeyError):
        calculate_shipping({"region": "일반", "is_express": False})


def test_P001_8_edge_empty_order_raises_key_error():
    with pytest.raises(KeyError):
        calculate_shipping({})
