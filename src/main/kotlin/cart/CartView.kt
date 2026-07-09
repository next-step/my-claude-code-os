package cart

data class CartView(
    val items: List<CartItem>,
    val totalPrice: Int
)
