---
status: approved
---

## 요약

주문 정보(`order`: `subtotal`, `region`, `is_express`)를 받아 배송비를 계산하는 순수 함수 `calculate_shipping(order)`를 추가한다. 기본 배송비에 무료배송 조건을 적용한 뒤, 지역 추가비와 특급 추가비를 무료배송 여부와 무관하게 더하고, `subtotal`이 0 이하이거나 `region`이 허용된 세 값이 아니면 `ValueError`를 발생시킨다.

## 정책 충돌

기존 코드/문서 조사 결과: 이 프로젝트(`sandbox/wf-eval/case1-shipping`)에는 `README.md`와 `request.md`만 존재하고 `src/`, `tests/`, 기존 `spec.md`가 전혀 없다(확인: 프로젝트 루트 파일 목록). 따라서 기존 승인 정책과의 충돌은 **없음**.

다만 request.md 자체의 해석이 갈리는 지점이 있어 기본값을 선택한다:

1. **`order`에 필요한 키가 없는 경우의 처리** — request는 `order`가 `subtotal`/`region`/`is_express`를 항상 포함한다고 전제하고, 키 누락 시 동작을 명시하지 않는다. (spec-review 차단 지적: 서술로만 남아 있어 검증 불가능했음 → P-001-8로 정책화)
   - 선택지 A: 누락 키를 별도로 검사해 `ValueError`(또는 `KeyError`)를 명시적으로 발생시킨다.
   - 선택지 B (기본값): 명세 범위를 "세 키가 모두 존재하는 `order`"로 한정하고, 키 누락 시 별도 방어 코드(예: `.get()`으로 기본값 치환) 없이 자연스러운 `KeyError`가 그대로 전파되어야 한다.
   - 근거: request가 명시적으로 요구하지 않은 방어 로직을 추가하면 정책 5(값 검증)의 범위를 벗어난다. 다만 "누락 키를 조용히 기본값으로 채우는" 구현이 다른 정책을 위반하지 않고도 가능했으므로, 이를 막기 위해 P-001-8로 명문화한다.

2. **`subtotal`의 타입 검증 여부** — request는 "정수 원"이라고 설명하지만, 타입이 `int`가 아닌 경우(예: `float`, `str`)의 동작은 명시하지 않는다.
   - 선택지 A: `int`가 아니면 `TypeError`/`ValueError`를 발생시킨다.
   - 선택지 B (기본값): 타입 검증은 하지 않고 값 비교(`subtotal <= 0`, `subtotal >= 50000`)만 수행한다. 비교 연산이 불가능한 타입(예: `str`)이 들어와 파이썬이 자체적으로 `TypeError` 등을 발생시키는 것은 **정책 위반이 아니며 테스트 대상도 아니다** — 명세 범위 밖이다.
   - 근거: request의 규칙 5는 "0 이하"라는 값 조건만 명시하며 타입 조건을 언급하지 않는다.

3. **`is_express`의 진위 판정 기준** — P-001-5는 "`is_express`가 `True`이면"이라고만 규정해, `bool`이 아닌 값(예: 문자열 `"False"`)이 들어왔을 때 엄격 식별(`is True`)과 truthy 판정(`if is_express:`) 중 어느 쪽인지 불명확했다. (spec-review 차단 지적, 아래 반영 참고 — P-001-5 규칙 문구를 수정함)
   - 선택지 A (기본값): `is_express is True`(정확히 `bool` 타입의 `True`)인 경우에만 특급비를 부과한다. `bool`이 아닌 값이 들어온 경우의 동작은 정의하지 않는다(명세 범위 밖).
   - 선택지 B: truthy 판정(`if is_express:`)을 사용해 문자열/숫자 등도 특급비 부과 여부에 영향을 준다.
   - 근거: request는 `is_express`를 `bool`로 명시했으므로, `bool`이 아닌 입력에 대해서는 타입 계약 위반으로 보고 엄격 식별을 기본값으로 삼는 것이 타입 계약과 일치한다.

4. **`ValueError` 메시지 내용** — request는 예외 종류만 명시하고 메시지 문구는 규정하지 않는다.
   - 선택지 A: 특정 문구를 표준으로 고정한다.
   - 선택지 B (기본값): 원인을 식별 가능한 메시지를 포함하되 문구 자체는 테스트 대상으로 삼지 않는다(예외 타입만 검증).
   - 근거: request에 문구 요구사항이 없고, 문구를 고정하면 불필요한 결합이 생긴다.

## 변경 범위

- `src/shipping.py` (신규) — `calculate_shipping(order)` 함수 구현
- `tests/test_shipping.py` (신규, `/test` 단계에서 생성)

## 정책

### P-001-1: 기본 배송비
- 규칙: `subtotal`이 50,000원 미만이면 기본 배송비는 3,000원이다.
- 예시: `subtotal=10000, region="일반", is_express=False` → 3,000원 (기본 3,000 + 지역 0 + 특급 0).

### P-001-2: 무료 배송 임계값
- 규칙: `subtotal`이 50,000원 이상이면 기본 배송비는 0원이다.
- 예시: `subtotal=50000, region="일반", is_express=False` → 0원 (기본 0 + 지역 0 + 특급 0).

### P-001-3: 제주 지역 추가비
- 규칙: `region`이 "제주"이면 무료배송 여부와 무관하게 3,000원의 지역 추가비가 항상 부과된다.
- 예시: `subtotal=60000, region="제주", is_express=False` → 3,000원 (기본 0 + 지역 3,000 + 특급 0).

### P-001-4: 도서산간 지역 추가비
- 규칙: `region`이 "도서산간"이면 무료배송 여부와 무관하게 5,000원의 지역 추가비가 항상 부과된다.
- 예시: `subtotal=60000, region="도서산간", is_express=False` → 5,000원 (기본 0 + 지역 5,000 + 특급 0).

### P-001-5: 특급 배송비 (기본값)
- 규칙: `is_express is True`(정확히 `bool` 타입의 `True`)이면 무료배송 여부와 무관하게 2,000원의 특급비가 항상 부과된다. `bool`이 아닌 값(예: 문자열 `"False"`, 숫자 `1`)이 들어온 경우의 동작은 정의하지 않는다.
- 예시: `subtotal=60000, region="일반", is_express=True` → 2,000원 (기본 0 + 지역 0 + 특급 2,000).

### P-001-6: subtotal 값 검증 (기본값)
- 규칙: `subtotal`이 0 이하이면 `ValueError`가 발생한다.
- 예시: `subtotal=0, region="일반", is_express=False` → `ValueError`.

### P-001-7: region 값 검증 (기본값)
- 규칙: `region`이 "일반", "제주", "도서산간" 중 하나가 아니면 `ValueError`가 발생한다.
- 예시: `subtotal=10000, region="서울", is_express=False` → `ValueError`.

### P-001-8: 누락된 키의 처리 (기본값)
- 규칙: `order`에 `subtotal`, `region`, `is_express` 중 하나라도 키가 없으면, 이를 기본값으로 조용히 치환하지 않고 `KeyError`가 그대로 전파되어야 한다.
- 예시: `order={"subtotal": 10000, "region": "일반"}` (`is_express` 키 없음) → `KeyError`.
