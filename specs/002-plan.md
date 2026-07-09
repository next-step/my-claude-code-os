# 002-plan — 상품 카탈로그·소계·할인 계산

선행 스펙: `specs/002-spec.md` (승인됨)

---

## 인터페이스 스케치 (코드 아님, 시그니처만)

```kotlin
// Product — 001 재사용, 변경 없음
data class Product(val productId: String, val name: String, val price: Int)

// 신규 — 고정 카탈로그 (10개, 하드코딩)
object ProductCatalog {
    fun getAll(): List<Product>
}

// Cart — 001 확장. catalog는 선택적 협력 객체 (A03)
class Cart(private val catalog: ProductCatalog? = null) {
    fun addItem(product: Product, quantity: Int)          // 001 유지 + catalog 주입 시 검증 추가
    fun updateQuantity(productId: String, quantity: Int)  // 001 유지, 변경 없음
    fun removeItem(productId: String)                      // 001 유지, 변경 없음
    fun getItems(): CartView                                // 001 유지 + subtotal 노출
    fun applyDiscount(discountRate: Int): DiscountResult    // 신규 (A07~A13)
}

// CartItem — 001 확장, subtotal 파생 프로퍼티 추가 (A04)
data class CartItem(val product: Product, val quantity: Int) {
    val subtotal: Int get() = product.price * quantity
}

// CartView — 001 유지. totalPrice 의미 불변 (A05, 할인 전 합계)
data class CartView(val items: List<CartItem>, val totalPrice: Int)

// 신규 — 할인 계산 결과 (A09, A10)
data class DiscountResult(val discountAmount: Int, val finalPrice: Int)

// 신규 예외
class InvalidDiscountRateException(message: String) : RuntimeException(message)

// 001 기존 예외 재사용 (변경 없음)
class InvalidQuantityException(message: String) : RuntimeException(message)
class ProductNotFoundException(message: String) : RuntimeException(message)
```

### 001과의 관계 (충돌 해소 반영)
- `Cart()` (catalog 미주입) → 001 동작 100% 보존. 기존 `CartTest.kt` 수정 없음.
- `Cart(ProductCatalog)` (catalog 주입) → 002 S03 카탈로그 검증 동작.
- `CartView.totalPrice`는 001 S05/S06과 동일한 의미(할인 전 합계) 유지. 최종 할인가는 `DiscountResult.finalPrice`로 분리.

---

## 태스크 · 시나리오 대응표

| 태스크 | 시나리오 | 대상 인터페이스 |
|---|---|---|
| T1. 고정 카탈로그 조회 | S01, S02 | `ProductCatalog.getAll()` |
| T2. 카탈로그 검증 (선택적 주입) | S03 | `Cart(catalog)`, `addItem` |
| T3. 항목별 소계 | S04, S05 | `CartItem.subtotal` |
| T4. 다항목 소계·합계 일관성 | S06, S07 | `CartItem.subtotal`, `CartView.totalPrice` |
| T5. 할인 계산 — 정상 경로 | S08, S09, S10, S11 | `Cart.applyDiscount()`, `DiscountResult` |
| T6. 할인 계산 — 오류 경로 | S12, S13 | `InvalidDiscountRateException` |
| T7. 할인 계산 — 경계 상태 | S14, S15 | `Cart.applyDiscount()` |

---

## 시나리오 → 테스트 함수 대응표

| 시나리오 | 테스트 함수명 | 파일 |
|---|---|---|
| S01 | `s01_고정카탈로그전체조회` | CartCatalogAndDiscountTest.kt |
| S02 | `s02_카탈로그안정성_두번조회시동일` | CartCatalogAndDiscountTest.kt |
| S03 | `s03_카탈로그에없는상품담기거부` | CartCatalogAndDiscountTest.kt |
| S04 | `s04_단일항목소계계산` | CartCatalogAndDiscountTest.kt |
| S05 | `s05_수량변경후소계갱신` | CartCatalogAndDiscountTest.kt |
| S06 | `s06_다항목소계와합계일관성` | CartCatalogAndDiscountTest.kt |
| S07 | `s07_수량변경이합계에반영` | CartCatalogAndDiscountTest.kt |
| S08 | `s08_유효한할인율적용_정수로떨어지는경우` | CartCatalogAndDiscountTest.kt |
| S09 | `s09_할인금액원단위미만버림` | CartCatalogAndDiscountTest.kt |
| S10 | `s10_할인율0퍼센트경계` | CartCatalogAndDiscountTest.kt |
| S11 | `s11_할인율100퍼센트경계` | CartCatalogAndDiscountTest.kt |
| S12 | `s12_음수할인율거부` | CartCatalogAndDiscountTest.kt |
| S13 | `s13_100초과할인율거부` | CartCatalogAndDiscountTest.kt |
| S14 | `s14_빈장바구니에할인적용` | CartCatalogAndDiscountTest.kt |
| S15 | `s15_수량변경후할인재계산` | CartCatalogAndDiscountTest.kt |

15개 시나리오 모두 1:1 커버됨 (시나리오당 정확히 1개 테스트).

## RED 확인 (H1 — 러너 출력 전문 근거)

명령: `gradle test --console=plain` (sandbox 해제 필요 — 네이티브 라이브러리 접근 제한, 아래 참고)

```
> Task :compileTestKotlin FAILED
e: .../CartCatalogAndDiscountTest.kt:22:24 Unresolved reference: ProductCatalog
e: .../CartCatalogAndDiscountTest.kt:51:20 Unresolved reference: Cart
e: .../CartCatalogAndDiscountTest.kt:56:22 Unresolved reference: ProductNotFoundException
e: .../CartCatalogAndDiscountTest.kt:209:22 Unresolved reference: InvalidDiscountRateException
... (cascade: Product, Cart, CartItem.subtotal, DiscountResult 등 미해결 참조 다수)
e: .../CartTest.kt:11:32 Unresolved reference: Cart   ← 001 기존 테스트도 동일 원인으로 함께 실패 (프로덕션 코드 부재, 정상)

FAILURE: Build failed with an exception.
> Task :compileTestKotlin FAILED
> Execution failed for task ':compileTestKotlin'.
BUILD FAILED in 5s
```

원인 격리: 최초 실행 시 sandbox가 `libnative-platform.dylib` 접근을 막아 Gradle 데몬 시작 자체가 실패했다. sandbox 해제 후 재실행하여 컴파일 단계까지 정상 진행되었고, 위 실패는 sandbox 문제가 아니라 프로덕션 코드 부재로 인한 **의도된 RED**임을 확인했다 (H2 준수 — test-writer는 구현 스텁을 작성하지 않음).

## 게이트 — 대응표 확인 (개입 2/3)
시나리오 S01~S15 모두 테스트에 1:1 커버됨. 001 기존 테스트(CartTest.kt) 미수정 확인됨.
