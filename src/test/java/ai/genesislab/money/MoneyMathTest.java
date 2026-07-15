package ai.genesislab.money;

import static ai.genesislab.testutil.BigDecimals.bd;
import static ai.genesislab.testutil.BigDecimals.sum;
import static ai.genesislab.testutil.UtilityClasses.assertNotInstantiable;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.math.BigDecimal;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;

/**
 * {@link MoneyMath} 단위 테스트.
 *
 * <p>각 연산의 정상·경계(0원·안 떨어지는 분배·n=1·음수·scale 경계)·예외(널 인자·{@code n<=0})
 * 케이스를 검증한다. 금액 비교는 값 동등성을 위해 {@link BigDecimal#compareTo}를 사용한다.</p>
 */
@DisplayName("MoneyMath 단위 테스트")
class MoneyMathTest {

    @Nested
    @DisplayName("add(a, b) — 금액 덧셈")
    class Add {

        @Test
        @DisplayName("정상: 두 금액을 더한다(scale 보존)")
        void add_twoAmounts_returnsSum() {
            assertEquals(0, bd("30.75").compareTo(MoneyMath.add(bd("10.25"), bd("20.50"))));
        }

        @ParameterizedTest(name = "add({0}, {1}) = {2}")
        @DisplayName("경계: 0원·음수·환불 조합")
        @CsvSource({
                "0.00, 0.00, 0.00",
                "100.00, -40.00, 60.00",
                "-10.00, -5.00, -15.00",
                "-50.00, 50.00, 0.00"
        })
        void add_boundaries_returnsSum(String a, String b, String expected) {
            assertEquals(0, bd(expected).compareTo(MoneyMath.add(bd(a), bd(b))));
        }

        @Test
        @DisplayName("경계: scale이 다르면 큰 scale을 따른다")
        void add_differentScales_followsLargerScale() {
            BigDecimal sum = MoneyMath.add(bd("1.5"), bd("2.25"));
            assertEquals(0, bd("3.75").compareTo(sum));
            assertEquals(2, sum.scale());
        }

        @Test
        @DisplayName("예외: 널 인자는 IllegalArgumentException")
        void add_nullArgument_throwsIae() {
            IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
                    () -> MoneyMath.add(null, bd("1.00")));
            assertEquals(MoneyMath.NULL_ARGUMENT_MESSAGE, ex.getMessage());
            assertThrows(IllegalArgumentException.class, () -> MoneyMath.add(bd("1.00"), null));
        }
    }

    @Nested
    @DisplayName("subtract(a, b) — 금액 뺄셈")
    class Subtract {

        @Test
        @DisplayName("정상: 차감 결과를 반환")
        void subtract_twoAmounts_returnsDifference() {
            assertEquals(0, bd("70.00").compareTo(MoneyMath.subtract(bd("100.00"), bd("30.00"))));
        }

        @Test
        @DisplayName("경계: 결과가 음수(환불/초과 차감)")
        void subtract_resultNegative_allowed() {
            assertEquals(0, bd("-30.00").compareTo(MoneyMath.subtract(bd("20.00"), bd("50.00"))));
        }

        @Test
        @DisplayName("예외: 널 인자는 IllegalArgumentException")
        void subtract_nullArgument_throwsIae() {
            assertThrows(IllegalArgumentException.class, () -> MoneyMath.subtract(null, bd("1.00")));
            assertThrows(IllegalArgumentException.class, () -> MoneyMath.subtract(bd("1.00"), null));
        }
    }

    @Nested
    @DisplayName("multiply(amount, quantity) — 단가 × 수량")
    class Multiply {

        @Test
        @DisplayName("정상: 단가에 수량을 곱한다(scale 보존)")
        void multiply_priceByQuantity_returnsProduct() {
            BigDecimal total = MoneyMath.multiply(bd("19.99"), 3);
            assertEquals(0, bd("59.97").compareTo(total));
            assertEquals(2, total.scale());
        }

        @ParameterizedTest(name = "multiply({0}, {1}) = {2}")
        @DisplayName("경계: 0·음수 수량·음수 단가")
        @CsvSource({
                "10.00, 0, 0.00",
                "10.00, -2, -20.00",
                "-10.00, 3, -30.00",
                "-10.00, -3, 30.00"
        })
        void multiply_boundaries_returnsProduct(String amount, int quantity, String expected) {
            assertEquals(0, bd(expected).compareTo(MoneyMath.multiply(bd(amount), quantity)));
        }

        @Test
        @DisplayName("예외: 널 금액은 IllegalArgumentException")
        void multiply_nullAmount_throwsIae() {
            IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
                    () -> MoneyMath.multiply(null, 3));
            assertEquals(MoneyMath.NULL_ARGUMENT_MESSAGE, ex.getMessage());
        }
    }

    @Nested
    @DisplayName("allocate(amount, n) — 유실 없는 n등분")
    class Allocate {

        @Test
        @DisplayName("정상: 나눠떨어지면 균등 분배")
        void allocate_evenlyDivisible_returnsEqualParts() {
            BigDecimal[] parts = MoneyMath.allocate(bd("90.00"), 3);
            assertEquals(3, parts.length);
            for (BigDecimal part : parts) {
                assertEquals(0, bd("30.00").compareTo(part));
            }
        }

        @Test
        @DisplayName("경계: 안 떨어지는 분배(100/3)는 나머지를 앞쪽에 1단위씩")
        void allocate_notDivisible_distributesRemainderToFront() {
            BigDecimal[] parts = MoneyMath.allocate(bd("100.00"), 3);
            assertEquals(0, bd("33.34").compareTo(parts[0]));
            assertEquals(0, bd("33.33").compareTo(parts[1]));
            assertEquals(0, bd("33.33").compareTo(parts[2]));
            assertEquals(0, bd("100.00").compareTo(sum(parts)));
        }

        @Test
        @DisplayName("경계: scale 0(원 단위) 10원을 3등분")
        void allocate_scaleZero_distributesInteger() {
            BigDecimal[] parts = MoneyMath.allocate(bd("10"), 3);
            assertEquals(0, bd("4").compareTo(parts[0]));
            assertEquals(0, bd("3").compareTo(parts[1]));
            assertEquals(0, bd("3").compareTo(parts[2]));
            assertEquals(0, bd("10").compareTo(sum(parts)));
            assertEquals(0, parts[0].scale());
        }

        @Test
        @DisplayName("경계: n=1이면 전액 한 조각")
        void allocate_nIsOne_returnsWholeAmount() {
            BigDecimal[] parts = MoneyMath.allocate(bd("100.00"), 1);
            assertEquals(1, parts.length);
            assertEquals(0, bd("100.00").compareTo(parts[0]));
        }

        @Test
        @DisplayName("경계: 0원 분배는 모두 0")
        void allocate_zeroAmount_returnsZeros() {
            BigDecimal[] parts = MoneyMath.allocate(bd("0.00"), 4);
            for (BigDecimal part : parts) {
                assertEquals(0, BigDecimal.ZERO.compareTo(part));
            }
            assertEquals(0, BigDecimal.ZERO.compareTo(sum(parts)));
        }

        @Test
        @DisplayName("경계: 음수 금액(-1.00)은 앞쪽 조각의 절댓값을 키운다")
        void allocate_negativeAmount_distributesToFront() {
            BigDecimal[] parts = MoneyMath.allocate(bd("-1.00"), 3);
            assertEquals(0, bd("-0.34").compareTo(parts[0]));
            assertEquals(0, bd("-0.33").compareTo(parts[1]));
            assertEquals(0, bd("-0.33").compareTo(parts[2]));
            assertEquals(0, bd("-1.00").compareTo(sum(parts)));
        }

        @Test
        @DisplayName("경계: n이 조각 수보다 많아도(0.05를 10등분) 합이 원금과 일치")
        void allocate_morePartsThanUnits_stillExact() {
            BigDecimal[] parts = MoneyMath.allocate(bd("0.05"), 10);
            assertEquals(10, parts.length);
            assertEquals(0, bd("0.05").compareTo(sum(parts)));
            // 앞쪽 5조각은 0.01, 뒤쪽 5조각은 0.00.
            assertEquals(0, bd("0.01").compareTo(parts[0]));
            assertEquals(0, BigDecimal.ZERO.compareTo(parts[9]));
        }

        @ParameterizedTest(name = "n={0}일 때 조각 합 == 원금")
        @DisplayName("경계: 여러 n에서 합 == 원금(유실 0)")
        @ValueSource(ints = {1, 2, 3, 4, 7, 11, 100})
        void allocate_variousN_sumEqualsAmount(int n) {
            BigDecimal amount = bd("100.00");
            assertEquals(0, amount.compareTo(sum(MoneyMath.allocate(amount, n))));
        }

        @Test
        @DisplayName("경계: 음수 scale 입력(1E+2, scale -2)도 정수 최소단위로 균등 분배")
        void allocate_negativeScale_distributesEvenly() {
            // 1E+2 == 100 이지만 scale이 -2다. 정규화(max(scale,0)=0) 없이는 unscaled 1을
            // 3으로 나눠 [100, 0, 0]처럼 쏠렸다(유실-0 검사는 통과하던 조용한 버그).
            BigDecimal amount = bd("1E+2");
            assertEquals(-2, amount.scale(), "전제: 입력 scale이 음수여야 회귀를 잡는다");

            BigDecimal[] parts = MoneyMath.allocate(amount, 3);

            // (a) 분배가 균등에 가깝다: 최댓값-최솟값 <= 최소단위(1).
            assertEquals(0, bd("34").compareTo(parts[0]));
            assertEquals(0, bd("33").compareTo(parts[1]));
            assertEquals(0, bd("33").compareTo(parts[2]));
            // (b) 재합산 == 원금(유실 0).
            assertEquals(0, amount.compareTo(sum(parts)));
        }

        @Test
        @DisplayName("경계: stripTrailingZeros()로 음수 scale이 된 금액도 유실 0")
        void allocate_stripTrailingZeros_stillExact() {
            BigDecimal amount = bd("100.00").stripTrailingZeros(); // 1E+2, scale -2
            assertTrue(amount.scale() < 0, "전제: stripTrailingZeros 결과 scale이 음수");

            BigDecimal[] parts = MoneyMath.allocate(amount, 3);

            assertEquals(0, bd("34").compareTo(parts[0]));
            assertEquals(0, bd("33").compareTo(parts[1]));
            assertEquals(0, bd("33").compareTo(parts[2]));
            assertEquals(0, amount.compareTo(sum(parts)));
        }

        @Test
        @DisplayName("불변: 매 호출마다 새 배열을 반환")
        void allocate_returnsNewArrayEachCall() {
            BigDecimal amount = bd("10.00");
            assertNotSame(MoneyMath.allocate(amount, 3), MoneyMath.allocate(amount, 3));
        }

        @ParameterizedTest(name = "n={0} → IllegalArgumentException")
        @DisplayName("예외: n<=0은 IllegalArgumentException")
        @ValueSource(ints = {0, -1, -100})
        void allocate_nonPositiveN_throwsIae(int n) {
            IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
                    () -> MoneyMath.allocate(bd("100.00"), n));
            assertEquals(MoneyMath.NON_POSITIVE_COUNT_MESSAGE, ex.getMessage());
        }

        @Test
        @DisplayName("예외: 널 금액은 IllegalArgumentException")
        void allocate_nullAmount_throwsIae() {
            IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
                    () -> MoneyMath.allocate(null, 3));
            assertEquals(MoneyMath.NULL_ARGUMENT_MESSAGE, ex.getMessage());
        }
    }

    @Nested
    @DisplayName("설계 불변식")
    class DesignInvariants {

        @Test
        @DisplayName("정책: 모듈 기본 반올림은 HALF_EVEN(DECISIONS §B)")
        void roundingMode_isHalfEven() {
            assertEquals(java.math.RoundingMode.HALF_EVEN, MoneyMath.ROUNDING_MODE);
        }

        @Test
        @DisplayName("유틸리티 클래스는 인스턴스화할 수 없다")
        void moneyMath_cannotBeInstantiated() throws Exception {
            assertNotInstantiable(MoneyMath.class);
        }
    }
}
