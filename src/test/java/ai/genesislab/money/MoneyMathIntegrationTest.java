package ai.genesislab.money;

import static ai.genesislab.testutil.BigDecimals.bd;
import static ai.genesislab.testutil.BigDecimals.sum;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.math.BigDecimal;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

/**
 * {@link MoneyMath} 통합 테스트 — 연산 조합 흐름.
 *
 * <p>단일 연산이 아니라 여러 연산을 엮은 실제 금액 처리 시나리오를 검증한다.
 * 핵심 계약은 <b>"총액 → allocate → 재합산 == 원금(유실 0)"</b>이며, 여러 scale·n에서 성립함을 확인한다.</p>
 */
@DisplayName("MoneyMath 통합 테스트 — 금액 처리 흐름")
class MoneyMathIntegrationTest {

    @ParameterizedTest(name = "총액 {0}을 {1}등분 → 재합산 == 원금")
    @DisplayName("핵심: 총액 → allocate → 재합산 == 원금 (여러 scale·n)")
    @CsvSource({
            "100.00, 3",
            "100.00, 7",
            "0.10, 3",
            "0.05, 10",
            "1000, 3",
            "1234.5, 6",
            "9999.99, 13",
            "-100.00, 3",
            "0.00, 5",
            "1E+2, 3",
            "1E+3, 7",
            "-1E+2, 3"
    })
    void allocateThenResum_equalsOriginal(String amount, int n) {
        BigDecimal original = bd(amount);
        BigDecimal[] parts = MoneyMath.allocate(original, n);
        assertEquals(0, original.compareTo(sum(parts)),
                "분배 합이 원금과 정확히 일치해야 한다(유실 0)");
    }

    @Test
    @DisplayName("장바구니 흐름: (단가×수량) 합산 → 인원수로 더치페이 → 재합산 == 총액")
    void cart_multiplyAdd_thenSplit_flow() {
        BigDecimal itemA = MoneyMath.multiply(bd("19.99"), 2); // 39.98
        BigDecimal itemB = MoneyMath.multiply(bd("5.50"), 3);  // 16.50
        BigDecimal total = MoneyMath.add(itemA, itemB);        // 56.48

        assertEquals(0, bd("56.48").compareTo(total));

        BigDecimal[] perPerson = MoneyMath.allocate(total, 3);
        assertEquals(0, total.compareTo(sum(perPerson)));       // 유실 0
        // 나머지 2전은 앞쪽 두 명에게: 18.83 / 18.83 / 18.82
        assertEquals(0, bd("18.83").compareTo(perPerson[0]));
        assertEquals(0, bd("18.83").compareTo(perPerson[1]));
        assertEquals(0, bd("18.82").compareTo(perPerson[2]));
    }

    @Test
    @DisplayName("환불 흐름: 결제액에서 부분 환불(subtract, 음수 경유) 후 잔액 분배")
    void refund_subtract_thenAllocate_flow() {
        BigDecimal paid = bd("100.00");
        BigDecimal refund = bd("30.00");
        BigDecimal remaining = MoneyMath.subtract(paid, refund); // 70.00

        assertEquals(0, bd("70.00").compareTo(remaining));

        BigDecimal[] parts = MoneyMath.allocate(remaining, 3);
        assertEquals(0, remaining.compareTo(sum(parts)));         // 유실 0
    }

    @Test
    @DisplayName("이중 분배 흐름: allocate 결과의 한 조각을 다시 allocate 해도 총합 보존")
    void nestedAllocate_flow() {
        BigDecimal budget = bd("100.00");
        BigDecimal[] teams = MoneyMath.allocate(budget, 3); // 33.34 / 33.33 / 33.33

        BigDecimal grandTotal = BigDecimal.ZERO;
        for (BigDecimal team : teams) {
            BigDecimal[] members = MoneyMath.allocate(team, 2);
            assertEquals(0, team.compareTo(sum(members))); // 각 팀 내부도 유실 0
            grandTotal = grandTotal.add(sum(members));
        }
        assertEquals(0, budget.compareTo(grandTotal)); // 전체도 유실 0
    }

    @Test
    @DisplayName("정규화 흐름: 곱셈 결과를 stripTrailingZeros(음수 scale)한 뒤 분배해도 균등·유실 0")
    void multiply_stripTrailingZeros_thenAllocate_flow() {
        BigDecimal total = MoneyMath.multiply(bd("50.00"), 2).stripTrailingZeros(); // 1E+2, scale -2
        assertTrue(total.scale() < 0, "전제: stripTrailingZeros로 음수 scale이 됐다");

        BigDecimal[] parts = MoneyMath.allocate(total, 3);
        assertEquals(0, total.compareTo(sum(parts)));                 // 유실 0
        // 정규화(최소단위 1) 덕분에 한쪽 쏠림 없이 34 / 33 / 33.
        assertEquals(0, bd("34").compareTo(parts[0]));
        assertEquals(0, bd("33").compareTo(parts[1]));
        assertEquals(0, bd("33").compareTo(parts[2]));
    }

    @Test
    @DisplayName("환불 상쇄 흐름: 음수 금액을 add로 상쇄하면 0")
    void negativeAmount_addBack_flow() {
        BigDecimal charge = bd("59.97");
        BigDecimal refund = MoneyMath.multiply(bd("19.99"), -3); // -59.97
        assertEquals(0, BigDecimal.ZERO.compareTo(MoneyMath.add(charge, refund)));
    }
}
