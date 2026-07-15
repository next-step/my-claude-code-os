package ai.genesislab.money;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;

/**
 * 부수효과 없는 순수 함수형 금액 계산 라이브러리.
 *
 * <p>모든 금액은 이진 부동소수의 반올림 오차를 피하기 위해 {@link BigDecimal}로 표현한다
 * ({@code double}/{@code float} 금지 — {@code DECISIONS.md §B}). 반올림이 필요한 경우의
 * 모듈 기본은 {@link RoundingMode#HALF_EVEN}(은행가 반올림)이며 {@link #ROUNDING_MODE}로 노출한다.
 * 통화 scale은 별도로 강제하지 않고 <b>입력 {@code BigDecimal}의 scale을 보존</b>한다
 * (일반화). {@link #allocate}의 최소 분배 단위는 {@code 10}<sup>-scale</sup>이다.</p>
 *
 * <p>{@link #add}·{@link #subtract}·{@link #multiply}는 손실 없는 정확 연산이며,
 * {@link #allocate}는 정수 단위 나머지 분배로 <b>원금과 분배 합이 1단위도 유실 없이 정확히 일치</b>한다.
 * 따라서 이 네 연산 자체에는 실제 반올림이 개입하지 않는다({@link #ROUNDING_MODE}는 향후 확장·호출부
 * 계약 명시를 위한 모듈 정책 상수).</p>
 *
 * <p>음수 금액은 차감·환불 표현을 위해 허용한다. 형식·계약 위반(널 인자, {@code n <= 0})은
 * {@link IllegalArgumentException}으로 던진다({@code DECISIONS.md §A}). 반환 배열은 항상 새 배열이며
 * 입력을 변형하지 않는다(원본 불변, {@code DECISIONS.md §A}).</p>
 *
 * <p>본 클래스는 상태가 없으므로 인스턴스화하지 않는다(정적 메서드 모음).</p>
 */
public final class MoneyMath {

    /**
     * 금액을 다루는 모듈 기본 반올림 방식(은행가 반올림). {@code DECISIONS.md §B}.
     *
     * <p><b>주의:</b> 이 클래스의 4개 연산({@link #add}·{@link #subtract}·{@link #multiply}·{@link #allocate})은
     * 모두 <b>정확 연산</b>이라 내부에서 실제 반올림이 개입하지 않는다({@code allocate}조차 정수 단위 나머지
     * 분배로 유실이 0이다). 이 상수는 연산 결과에 적용되는 값이 아니라, <b>반올림이 필요한 호출부</b>
     * (예: 세율·이자 계산으로 scale을 줄여야 하는 경우)가 모듈 표준 정책으로 참조하도록 노출하는
     * <b>정책 선언 상수</b>다.</p>
     */
    public static final RoundingMode ROUNDING_MODE = RoundingMode.HALF_EVEN;

    /** 널 금액 인자가 전달됐을 때 사용하는 예외 메시지. */
    public static final String NULL_ARGUMENT_MESSAGE = "Money amount arguments must not be null.";

    /** 분배 개수 {@code n}이 양수가 아닐 때 사용하는 예외 메시지. */
    public static final String NON_POSITIVE_COUNT_MESSAGE =
            "The number of parts (n) must be a positive integer.";

    private MoneyMath() {
        // 유틸리티 클래스: 인스턴스화 방지.
        throw new AssertionError("No ai.genesislab.money.MoneyMath instances for you!");
    }

    /**
     * 두 금액을 더한다. 결과 scale은 두 입력 중 큰 scale을 따른다(정확 연산).
     *
     * @param a 피연산자(음수 허용)
     * @param b 피연산자(음수 허용)
     * @return {@code a + b}
     * @throws IllegalArgumentException {@code a} 또는 {@code b}가 {@code null}인 경우
     */
    public static BigDecimal add(BigDecimal a, BigDecimal b) {
        requireNonNull(a);
        requireNonNull(b);
        return a.add(b);
    }

    /**
     * 첫 번째 금액에서 두 번째 금액을 뺀다. 결과 scale은 두 입력 중 큰 scale을 따른다(정확 연산).
     *
     * @param a 피감수(음수 허용)
     * @param b 감수(음수 허용)
     * @return {@code a - b}
     * @throws IllegalArgumentException {@code a} 또는 {@code b}가 {@code null}인 경우
     */
    public static BigDecimal subtract(BigDecimal a, BigDecimal b) {
        requireNonNull(a);
        requireNonNull(b);
        return a.subtract(b);
    }

    /**
     * 금액에 정수 수량을 곱한다. 결과 scale은 {@code amount}의 scale을 보존한다(정확 연산).
     *
     * @param amount   단가(음수 허용)
     * @param quantity 정수 수량(0·음수 허용 — 음수는 차감/환불 표현)
     * @return {@code amount * quantity}
     * @throws IllegalArgumentException {@code amount}가 {@code null}인 경우
     */
    public static BigDecimal multiply(BigDecimal amount, int quantity) {
        requireNonNull(amount);
        return amount.multiply(BigDecimal.valueOf(quantity));
    }

    /**
     * 금액을 {@code n}등분하되 <b>1단위(최소 분배 단위 {@code 10}<sup>-scale</sup>)도 유실 없이</b> 분배한다.
     *
     * <p>몫이 나눠떨어지지 않아 생기는 나머지는 <b>앞쪽 몫부터</b> 최소 단위씩 더해 흡수한다.
     * 따라서 반환된 모든 조각의 합은 원금 {@code amount}와 정확히 일치한다(scale 보존).
     * 음수 금액도 허용하며, 이 경우 나머지는 앞쪽 몫의 절댓값을 키우는 방향으로 분배된다.</p>
     *
     * <p>최소 분배 단위의 유효 scale은 {@code Math.max(amount.scale(), 0)}으로 정규화한다.
     * {@code stripTrailingZeros()} 등으로 <b>음수 scale</b>이 된 금액(예: {@code 1E+2}, scale {@code -2})도
     * 정수 최소단위(1) 기준으로 올바르게 n등분되어, 조각이 한쪽에 쏠리지 않고 합 유실도 없다.</p>
     *
     * @param amount 분배할 총액(음수 허용). 조각의 최소 단위는 {@code max(amount.scale(), 0)}을 따른다.
     * @param n      분배 개수(양수)
     * @return 길이 {@code n}의 <b>새 배열</b>. 각 원소의 합은 {@code amount}와 정확히 일치한다.
     * @throws IllegalArgumentException {@code amount}가 {@code null}이거나 {@code n <= 0}인 경우
     */
    public static BigDecimal[] allocate(BigDecimal amount, int n) {
        requireNonNull(amount);
        if (n <= 0) {
            throw new IllegalArgumentException(NON_POSITIVE_COUNT_MESSAGE);
        }

        // 최소 분배 단위의 유효 scale. 음수 scale(예: 1E+2 → scale -2)이면 정수 최소단위(scale 0)로
        // 정규화한다. 정규화하지 않으면 unscaledValue가 원금의 10^|scale|배 축소된 값이라(1E+2 → 1),
        // 그 1을 n등분해 [원금, 0, 0]처럼 한쪽에 쏠린다(유실-0 검사는 통과하는 조용한 버그).
        int scale = Math.max(amount.scale(), 0);
        // setScale로 유효 scale에 맞춰 확장(scale 증가는 항상 손실 없는 정확 연산).
        BigInteger totalUnits = amount.setScale(scale).unscaledValue();  // amount * 10^scale (정수 단위)
        BigInteger[] quotientAndRemainder =
                totalUnits.divideAndRemainder(BigInteger.valueOf(n));
        BigInteger baseUnits = quotientAndRemainder[0];
        BigInteger remainder = quotientAndRemainder[1];

        // 나머지 절댓값만큼의 앞쪽 조각이 최소 단위 하나씩을 더 받는다(부호는 원금을 따른다).
        int partsWithExtra = remainder.abs().intValueExact();
        BigInteger extraUnit = remainder.signum() < 0 ? BigInteger.valueOf(-1) : BigInteger.ONE;

        BigDecimal[] result = new BigDecimal[n];
        for (int i = 0; i < n; i++) {
            BigInteger partUnits = i < partsWithExtra ? baseUnits.add(extraUnit) : baseUnits;
            result[i] = new BigDecimal(partUnits, scale);
        }
        return result;
    }

    private static void requireNonNull(BigDecimal amount) {
        if (amount == null) {
            throw new IllegalArgumentException(NULL_ARGUMENT_MESSAGE);
        }
    }
}
