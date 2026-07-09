package cart

import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * 002-spec: 고정 카탈로그 + 할인 기능
 * 이 파일은 002-spec.md 의 S01~S15 시나리오를 다룬다.
 * 001-spec.md 의 CartTest.kt 는 별도로 유지되며 수정하지 않는다.
 */
class CartCatalogAndDiscountTest {

    // covers S01
    @Test
    fun s01_고정카탈로그전체조회() {
        // Given: 시스템 초기화 상태 (별도 준비 불필요, ProductCatalog 는 object)

        // When: 카탈로그 전체를 조회한다
        val products = ProductCatalog.getAll()

        // Then: 정확히 10개 상품이 반환되고, 각 항목은 productId/name/price 를 가진다
        assertEquals(10, products.size)
        products.forEach { product ->
            assertTrue(product.productId.isNotBlank())
            assertTrue(product.name.isNotBlank())
            assertTrue(product.price > 0)
        }
    }

    // covers S02
    @Test
    fun s02_카탈로그안정성_두번조회시동일() {
        // Given: 시스템 초기화 상태

        // When: 카탈로그를 두 번 조회한다
        val first = ProductCatalog.getAll()
        val second = ProductCatalog.getAll()

        // Then: 두 결과의 productId 목록과 price 가 동일하다
        assertEquals(first.map { it.productId }, second.map { it.productId })
        assertEquals(first.map { it.price }, second.map { it.price })
    }

    // covers S03
    @Test
    fun s03_카탈로그에없는상품담기거부() {
        // Given: catalog 가 주입된 비어 있는 Cart
        val cart = Cart(catalog = ProductCatalog)
        val unknownProduct = Product(productId = "P999", name = "존재하지않는상품", price = 100)

        // When: 카탈로그에 없는 상품(P999)을 담으려 시도한다
        // Then: ProductNotFoundException 이 발생하고 장바구니는 비어 있다
        assertThrows<ProductNotFoundException> {
            cart.addItem(unknownProduct, 1)
        }
        assertTrue(cart.getItems().items.isEmpty())
    }

    // covers S04
    @Test
    fun s04_단일항목소계계산() {
        // Given: 단가 1000인 P1이 수량 3으로 담김
        val cart = Cart()
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        cart.addItem(p1, 3)

        // When: 목록을 조회한다
        val view = cart.getItems()

        // Then: P1 의 subtotal 은 3000 이다
        val item = view.items.first { it.product.productId == "P1" }
        assertEquals(3000, item.subtotal)
    }

    // covers S05
    @Test
    fun s05_수량변경후소계갱신() {
        // Given: 단가 1000 P1 수량 3 (subtotal 3000)
        val cart = Cart()
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        cart.addItem(p1, 3)
        assertEquals(3000, cart.getItems().items.first { it.product.productId == "P1" }.subtotal)

        // When: 수량을 5로 변경한 뒤 재조회한다
        cart.updateQuantity("P1", 5)
        val view = cart.getItems()

        // Then: subtotal 은 5000 이다
        assertEquals(5000, view.items.first { it.product.productId == "P1" }.subtotal)
    }

    // covers S06
    @Test
    fun s06_다항목소계와합계일관성() {
        // Given: P1(단가1000,수량2), P2(단가500,수량3)
        val cart = Cart()
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        val p2 = Product(productId = "P2", name = "상품2", price = 500)
        cart.addItem(p1, 2)
        cart.addItem(p2, 3)

        // When: 목록을 조회한다
        val view = cart.getItems()

        // Then: P1 subtotal 2000, P2 subtotal 1500, totalPrice 3500
        assertEquals(2000, view.items.first { it.product.productId == "P1" }.subtotal)
        assertEquals(1500, view.items.first { it.product.productId == "P2" }.subtotal)
        assertEquals(3500, view.totalPrice)
    }

    // covers S07
    @Test
    fun s07_수량변경이합계에반영() {
        // Given: P1(1000×2), P2(500×3), totalPrice 3500
        val cart = Cart()
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        val p2 = Product(productId = "P2", name = "상품2", price = 500)
        cart.addItem(p1, 2)
        cart.addItem(p2, 3)
        assertEquals(3500, cart.getItems().totalPrice)

        // When: P2 수량을 1로 변경한 뒤 재조회한다
        cart.updateQuantity("P2", 1)
        val view = cart.getItems()

        // Then: totalPrice 는 2500 이다
        assertEquals(2500, view.totalPrice)
    }

    // covers S08
    @Test
    fun s08_유효한할인율적용_정수로떨어지는경우() {
        // Given: totalPrice 3000
        val cart = Cart()
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        cart.addItem(p1, 3)
        assertEquals(3000, cart.getItems().totalPrice)

        // When: 할인율 10% 를 적용한다
        val result = cart.applyDiscount(10)

        // Then: discountAmount 300, finalPrice 2700
        assertEquals(300, result.discountAmount)
        assertEquals(2700, result.finalPrice)
    }

    // covers S09
    @Test
    fun s09_할인금액원단위미만버림() {
        // Given: totalPrice 1005
        val cart = Cart()
        val p1 = Product(productId = "P1", name = "상품1", price = 1005)
        cart.addItem(p1, 1)
        assertEquals(1005, cart.getItems().totalPrice)

        // When: 할인율 33% 를 적용한다
        val result = cart.applyDiscount(33)

        // Then: discountAmount 331 (1005*0.33=331.65 -> 버림), finalPrice 674
        assertEquals(331, result.discountAmount)
        assertEquals(674, result.finalPrice)
    }

    // covers S10
    @Test
    fun s10_할인율0퍼센트경계() {
        // Given: totalPrice 3000
        val cart = Cart()
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        cart.addItem(p1, 3)

        // When: 할인율 0% 를 적용한다
        val result = cart.applyDiscount(0)

        // Then: discountAmount 0, finalPrice 3000
        assertEquals(0, result.discountAmount)
        assertEquals(3000, result.finalPrice)
    }

    // covers S11
    @Test
    fun s11_할인율100퍼센트경계() {
        // Given: totalPrice 3000
        val cart = Cart()
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        cart.addItem(p1, 3)

        // When: 할인율 100% 를 적용한다
        val result = cart.applyDiscount(100)

        // Then: discountAmount 3000, finalPrice 0
        assertEquals(3000, result.discountAmount)
        assertEquals(0, result.finalPrice)
    }

    // covers S12
    @Test
    fun s12_음수할인율거부() {
        // Given: totalPrice 3000
        val cart = Cart()
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        cart.addItem(p1, 3)

        // When: 할인율 -1 을 적용 시도한다
        // Then: InvalidDiscountRateException 이 발생한다
        assertThrows<InvalidDiscountRateException> {
            cart.applyDiscount(-1)
        }
    }

    // covers S13
    @Test
    fun s13_100초과할인율거부() {
        // Given: totalPrice 3000
        val cart = Cart()
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        cart.addItem(p1, 3)

        // When: 할인율 101 을 적용 시도한다
        // Then: InvalidDiscountRateException 이 발생한다
        assertThrows<InvalidDiscountRateException> {
            cart.applyDiscount(101)
        }
    }

    // covers S14
    @Test
    fun s14_빈장바구니에할인적용() {
        // Given: 비어 있는 장바구니 (totalPrice 0)
        val cart = Cart()
        assertEquals(0, cart.getItems().totalPrice)

        // When: 할인율 20% 를 적용한다
        val result = cart.applyDiscount(20)

        // Then: discountAmount 0, finalPrice 0 (예외 아님)
        assertEquals(0, result.discountAmount)
        assertEquals(0, result.finalPrice)
    }

    // covers S15
    @Test
    fun s15_수량변경후할인재계산() {
        // Given: totalPrice 3000
        val cart = Cart()
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        cart.addItem(p1, 3)
        assertEquals(3000, cart.getItems().totalPrice)

        // When: 수량을 늘려 totalPrice 4000 을 만든 뒤 할인율 10% 를 적용한다
        cart.updateQuantity("P1", 4)
        assertEquals(4000, cart.getItems().totalPrice)
        val result = cart.applyDiscount(10)

        // Then: discountAmount 400, finalPrice 3600
        assertEquals(400, result.discountAmount)
        assertEquals(3600, result.finalPrice)
    }
}
