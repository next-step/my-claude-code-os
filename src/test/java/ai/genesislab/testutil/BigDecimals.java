package ai.genesislab.testutil;

import java.math.BigDecimal;

/**
 * {@link BigDecimal} 금액 테스트를 위한 공통 헬퍼(정적 메서드 모음).
 *
 * <p>{@code MoneyMathTest}와 {@code MoneyMathIntegrationTest}에 동일하게 복붙되어 있던
 * {@code bd(String)}(문자열 → {@code BigDecimal} 축약 팩토리)와 {@code sum(BigDecimal[])}(조각 재합산)을
 * 여기로 공통화한다. {@link UtilityClasses}와 동일한 {@code testutil} 위치·스타일
 * ({@code final class} + private 생성자에서 {@link AssertionError})을 따른다.</p>
 */
public final class BigDecimals {

    private BigDecimals() {
        throw new AssertionError("No ai.genesislab.testutil.BigDecimals instances for you!");
    }

    /**
     * 문자열을 {@link BigDecimal}로 만드는 축약 팩토리. 입력 표기의 scale을 그대로 보존한다
     * (예: {@code "1E+2"} → scale {@code -2}).
     *
     * @param value {@link BigDecimal} 생성자가 받는 십진 문자열
     * @return 해당 문자열로 만든 {@link BigDecimal}
     */
    public static BigDecimal bd(String value) {
        return new BigDecimal(value);
    }

    /**
     * 조각 배열을 재합산한다. 시작값의 scale 영향을 없애기 위해 {@link BigDecimal#ZERO}부터 누적한다.
     *
     * @param parts 합산할 {@link BigDecimal} 배열
     * @return 모든 원소의 합(빈 배열이면 {@link BigDecimal#ZERO})
     */
    public static BigDecimal sum(BigDecimal[] parts) {
        BigDecimal total = BigDecimal.ZERO;
        for (BigDecimal part : parts) {
            total = total.add(part);
        }
        return total;
    }
}
