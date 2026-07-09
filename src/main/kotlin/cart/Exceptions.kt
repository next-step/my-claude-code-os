package cart

class InvalidQuantityException(message: String) : RuntimeException(message)

class ProductNotFoundException(message: String) : RuntimeException(message)

class InvalidDiscountRateException(message: String) : RuntimeException(message)
