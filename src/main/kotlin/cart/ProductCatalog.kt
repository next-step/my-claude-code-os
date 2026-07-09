package cart

object ProductCatalog {
    private val products: List<Product> = listOf(
        Product(productId = "P1", name = "상품1", price = 1000),
        Product(productId = "P2", name = "상품2", price = 2000),
        Product(productId = "P3", name = "상품3", price = 3000),
        Product(productId = "P4", name = "상품4", price = 4000),
        Product(productId = "P5", name = "상품5", price = 5000),
        Product(productId = "P6", name = "상품6", price = 6000),
        Product(productId = "P7", name = "상품7", price = 7000),
        Product(productId = "P8", name = "상품8", price = 8000),
        Product(productId = "P9", name = "상품9", price = 9000),
        Product(productId = "P10", name = "상품10", price = 10000)
    )

    fun getAll(): List<Product> = products
}
