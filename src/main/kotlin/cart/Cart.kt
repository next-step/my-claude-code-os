package cart

class Cart(private val catalog: ProductCatalog? = null) {

    private val items: MutableMap<String, CartItem> = LinkedHashMap()

    fun addItem(product: Product, quantity: Int) {
        if (quantity <= 0) {
            throw InvalidQuantityException("quantity must be greater than 0")
        }
        if (catalog != null && catalog.getAll().none { it.productId == product.productId }) {
            throw ProductNotFoundException("product ${product.productId} not found in catalog")
        }

        val existing = items[product.productId]
        if (existing == null) {
            items[product.productId] = CartItem(product, quantity)
        } else {
            items[product.productId] = existing.copy(quantity = existing.quantity + quantity)
        }
    }

    fun updateQuantity(productId: String, quantity: Int) {
        if (quantity <= 0) {
            throw InvalidQuantityException("quantity must be greater than 0")
        }
        val existing = items[productId]
            ?: throw ProductNotFoundException("product $productId not found in cart")
        items[productId] = existing.copy(quantity = quantity)
    }

    fun removeItem(productId: String) {
        if (!items.containsKey(productId)) {
            throw ProductNotFoundException("product $productId not found in cart")
        }
        items.remove(productId)
    }

    fun getItems(): CartView {
        val itemList = items.values.toList()
        val total = itemList.sumOf { it.subtotal }
        return CartView(items = itemList, totalPrice = total)
    }

    fun applyDiscount(discountRate: Int): DiscountResult {
        if (discountRate < 0 || discountRate > 100) {
            throw InvalidDiscountRateException("discountRate must be between 0 and 100")
        }
        val total = getItems().totalPrice
        val discountAmount = total * discountRate / 100
        return DiscountResult(discountAmount = discountAmount, finalPrice = total - discountAmount)
    }
}
