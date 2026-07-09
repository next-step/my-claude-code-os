package cart

import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class CartTest {

    private lateinit var cart: Cart

    @BeforeEach
    fun setUp() {
        cart = Cart()
    }

    // covers S01
    @Test
    fun s01_빈장바구니에상품추가() {
        // Given: 비어 있는 장바구니 (setUp에서 생성)
        val product = Product(productId = "P1", name = "상품1", price = 1000)

        // When: productId=P1, 수량 2인 상품을 추가한다
        cart.addItem(product, 2)

        // Then: 장바구니에 P1 항목이 수량 2로 존재한다
        val view = cart.getItems()
        assertEquals(1, view.items.size)
        val item = view.items.first()
        assertEquals("P1", item.product.productId)
        assertEquals(2, item.quantity)
    }

    // covers S02
    @Test
    fun s02_서로다른상품여러개추가() {
        // Given: 비어 있는 장바구니 (setUp에서 생성)
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        val p2 = Product(productId = "P2", name = "상품2", price = 500)

        // When: P1(수량 1), P2(수량 3)을 순서대로 추가한다
        cart.addItem(p1, 1)
        cart.addItem(p2, 3)

        // Then: 장바구니에 P1(수량 1), P2(수량 3) 두 항목이 존재한다
        val view = cart.getItems()
        assertEquals(2, view.items.size)
        val p1Item = view.items.first { it.product.productId == "P1" }
        val p2Item = view.items.first { it.product.productId == "P2" }
        assertEquals(1, p1Item.quantity)
        assertEquals(3, p2Item.quantity)
    }

    // covers S03
    @Test
    fun s03_이미담긴상품재추가시수량병합() {
        // Given: P1이 수량 2로 담긴 장바구니
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        cart.addItem(p1, 2)

        // When: 동일한 P1을 수량 3으로 추가한다
        cart.addItem(p1, 3)

        // Then: 항목은 여전히 하나이며 P1의 수량은 5가 된다
        val view = cart.getItems()
        assertEquals(1, view.items.size)
        assertEquals(5, view.items.first().quantity)
    }

    // covers S04
    @Test
    fun s04_수량0으로추가시InvalidQuantityException() {
        // Given: 비어 있는 장바구니 (setUp에서 생성)
        val product = Product(productId = "P1", name = "상품1", price = 1000)

        // When: P1을 수량 0으로 추가한다
        // Then: 추가가 거부되고 InvalidQuantityException이 발생하며, 장바구니는 비어 있는 상태로 유지된다
        assertThrows<InvalidQuantityException> {
            cart.addItem(product, 0)
        }
        assertTrue(cart.getItems().items.isEmpty())
    }

    // covers S04 (음수 케이스)
    @Test
    fun s04_음수수량으로추가시InvalidQuantityException() {
        // Given: 비어 있는 장바구니 (setUp에서 생성)
        val product = Product(productId = "P1", name = "상품1", price = 1000)

        // When: P1을 수량 -1로 추가한다
        // Then: 추가가 거부되고 InvalidQuantityException이 발생하며, 장바구니는 비어 있는 상태로 유지된다
        assertThrows<InvalidQuantityException> {
            cart.addItem(product, -1)
        }
        assertTrue(cart.getItems().items.isEmpty())
    }

    // covers S05
    @Test
    fun s05_담긴목록조회시항목과합계반환() {
        // Given: P1(수량 2, 단가 1000), P2(수량 1, 단가 500)이 담긴 장바구니
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        val p2 = Product(productId = "P2", name = "상품2", price = 500)
        cart.addItem(p1, 2)
        cart.addItem(p2, 1)

        // When: 목록을 조회한다
        val view = cart.getItems()

        // Then: P1(수량 2), P2(수량 1) 두 항목과 합계 금액 2500이 반환된다
        assertEquals(2, view.items.size)
        val p1Item = view.items.first { it.product.productId == "P1" }
        val p2Item = view.items.first { it.product.productId == "P2" }
        assertEquals(2, p1Item.quantity)
        assertEquals(1, p2Item.quantity)
        assertEquals(2500, view.totalPrice)
    }

    // covers S06
    @Test
    fun s06_빈장바구니조회시빈목록과합계0() {
        // Given: 비어 있는 장바구니 (setUp에서 생성)

        // When: 목록을 조회한다
        val view = cart.getItems()

        // Then: 빈 목록과 합계 0이 반환된다
        assertTrue(view.items.isEmpty())
        assertEquals(0, view.totalPrice)
    }

    // covers S07
    @Test
    fun s07_수량변경절대값지정() {
        // Given: P1이 수량 2로 담긴 장바구니
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        cart.addItem(p1, 2)

        // When: P1의 수량을 5로 변경한다
        cart.updateQuantity("P1", 5)

        // Then: P1의 수량은 5가 된다
        val view = cart.getItems()
        assertEquals(5, view.items.first { it.product.productId == "P1" }.quantity)
    }

    // covers S08
    @Test
    fun s08_수량0으로변경시InvalidQuantityException() {
        // Given: P1이 수량 2로 담긴 장바구니
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        cart.addItem(p1, 2)

        // When: P1의 수량을 0으로 변경한다
        // Then: 변경이 거부되고 InvalidQuantityException이 발생하며, P1의 수량은 2로 유지된다
        assertThrows<InvalidQuantityException> {
            cart.updateQuantity("P1", 0)
        }
        assertEquals(2, cart.getItems().items.first { it.product.productId == "P1" }.quantity)
    }

    // covers S08 (음수 케이스)
    @Test
    fun s08_음수수량으로변경시InvalidQuantityException() {
        // Given: P1이 수량 2로 담긴 장바구니
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        cart.addItem(p1, 2)

        // When: P1의 수량을 -3으로 변경한다
        // Then: 변경이 거부되고 InvalidQuantityException이 발생하며, P1의 수량은 2로 유지된다
        assertThrows<InvalidQuantityException> {
            cart.updateQuantity("P1", -3)
        }
        assertEquals(2, cart.getItems().items.first { it.product.productId == "P1" }.quantity)
    }

    // covers S09
    @Test
    fun s09_없는상품수량변경시ProductNotFoundException() {
        // Given: P1만 담긴 장바구니
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        cart.addItem(p1, 2)

        // When: 담긴 적 없는 P9의 수량을 3으로 변경한다
        // Then: 조작이 거부되고 ProductNotFoundException이 발생하며, 장바구니 상태는 변하지 않는다
        assertThrows<ProductNotFoundException> {
            cart.updateQuantity("P9", 3)
        }
        val view = cart.getItems()
        assertEquals(1, view.items.size)
        assertEquals("P1", view.items.first().product.productId)
    }

    // covers S10
    @Test
    fun s10_상품삭제후나머지항목만남음() {
        // Given: P1(수량 2), P2(수량 1)이 담긴 장바구니
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        val p2 = Product(productId = "P2", name = "상품2", price = 500)
        cart.addItem(p1, 2)
        cart.addItem(p2, 1)

        // When: P1을 삭제한다
        cart.removeItem("P1")

        // Then: 장바구니에는 P2(수량 1)만 남는다
        val view = cart.getItems()
        assertEquals(1, view.items.size)
        assertEquals("P2", view.items.first().product.productId)
        assertEquals(1, view.items.first().quantity)
    }

    // covers S11
    @Test
    fun s11_없는상품삭제시ProductNotFoundException() {
        // Given: P1만 담긴 장바구니
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        cart.addItem(p1, 2)

        // When: 담긴 적 없는 P9를 삭제한다
        // Then: 조작이 거부되고 ProductNotFoundException이 발생하며, 장바구니 상태는 변하지 않는다
        assertThrows<ProductNotFoundException> {
            cart.removeItem("P9")
        }
        val view = cart.getItems()
        assertEquals(1, view.items.size)
        assertEquals("P1", view.items.first().product.productId)
    }

    // covers S12
    @Test
    fun s12_마지막상품삭제로빈장바구니복귀() {
        // Given: P1만 담긴 장바구니
        val p1 = Product(productId = "P1", name = "상품1", price = 1000)
        cart.addItem(p1, 2)

        // When: P1을 삭제한다
        cart.removeItem("P1")

        // Then: 장바구니는 비어 있고, 조회 시 빈 목록과 합계 0이 반환된다
        val view = cart.getItems()
        assertTrue(view.items.isEmpty())
        assertEquals(0, view.totalPrice)
    }
}
