"""배송비 계산 (spec: tasks/001-shipping-fee/spec.md, 정책 P-001-1 ~ P-001-8)."""

BASE_FEE = 3000  # P-001-1
FREE_SHIPPING_THRESHOLD = 50000  # P-001-2
EXPRESS_FEE = 2000  # P-001-5

# P-001-3, P-001-4: region별 추가비. "일반"은 추가비 없음(0).
REGION_SURCHARGES = {
    "제주": 3000,
    "도서산간": 5000,
}
VALID_REGIONS = {"일반", *REGION_SURCHARGES.keys()}  # P-001-7 검증에 사용


def calculate_shipping(order):
    """주문(order)을 받아 배송비를 계산한다.

    order는 subtotal(정수 원), region(문자열), is_express(bool) 키를 모두 가져야
    한다 — 키가 없으면 KeyError가 그대로 전파된다 (P-001-8).
    """
    subtotal = order["subtotal"]
    region = order["region"]
    is_express = order["is_express"]

    if subtotal <= 0 or region not in VALID_REGIONS:  # P-001-6, P-001-7
        raise ValueError(
            f"invalid order: subtotal={subtotal!r}, region={region!r} "
            f"(subtotal must be > 0 and region must be one of {sorted(VALID_REGIONS)})"
        )

    base_fee = 0 if subtotal >= FREE_SHIPPING_THRESHOLD else BASE_FEE  # P-001-1, P-001-2
    region_surcharge = REGION_SURCHARGES.get(region, 0)  # P-001-3, P-001-4
    express_fee = EXPRESS_FEE if is_express is True else 0  # P-001-5

    return base_fee + region_surcharge + express_fee
