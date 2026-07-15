# Money 모듈 사용 문서

이 문서는 금액 계산 라이브러리 모듈의 사용법·API·설계 제약을 설명한다.
OS.md의 [4단계] 산출물이며, 코드와 어긋나면 본 문서를 현실에 맞게 갱신한다.

> 상태(2026-07-15): 단위/통합 테스트 195/195 통과(green) 기준으로 작성됨(리뷰 게이트 통과 후).
>
> **HTTP API 없음(N/A)**: 본 모듈은 순수 라이브러리(JVM 메서드 호출)이므로 엔드포인트가 없다.
> 따라서 `docs/http/` 문서는 작성하지 않는다(crypto·sudoku 모듈 선례와 동일).

---

## 1. 개요

- **역할**: 이진 부동소수 오차 없이 정확한 금액 계산을 제공하는 부수효과 없는 순수 함수형 라이브러리.
  - **정확 산술(`add`·`subtract`·`multiply`)**: 손실 없는 덧셈·뺄셈·정수 수량 곱.
  - **정확 분배(`allocate`)**: 금액을 `n`등분하되 최소 단위 1개도 유실 없이 분배한다(원금 == 분배 합).
- **패키지**: `ai.genesislab.money`
- **위치**: `src/main/java/ai/genesislab/money/MoneyMath.java`
- **특성**: CLI/HTTP 없는 순수 라이브러리 레이어. 상태가 없는 정적 메서드 모음(`final` + private 생성자, 인스턴스화 시 `AssertionError`). 모든 금액은 `BigDecimal`로 표현한다(`double`/`float` 금지). 반환 배열은 항상 새 배열이며 입력을 변형하지 않는다(원본 불변). **외부 의존성 0**(순수 JDK).

---

## 2. 공개 API

모든 메서드는 정적 메서드다.

| 메서드 | 시그니처 | 반환 | 예외 |
|---|---|---|---|
| `add` | `static BigDecimal add(BigDecimal a, BigDecimal b)` | `a + b`(정확 연산, 결과 scale은 두 입력 중 큰 scale) | `IllegalArgumentException`(a 또는 b가 null) |
| `subtract` | `static BigDecimal subtract(BigDecimal a, BigDecimal b)` | `a - b`(정확 연산, 결과 scale은 두 입력 중 큰 scale) | `IllegalArgumentException`(a 또는 b가 null) |
| `multiply` | `static BigDecimal multiply(BigDecimal amount, int quantity)` | `amount * quantity`(정확 연산, 결과 scale은 `amount`의 scale 보존) | `IllegalArgumentException`(amount가 null) |
| `allocate` | `static BigDecimal[] allocate(BigDecimal amount, int n)` | 길이 `n`의 **새 배열**. 각 원소의 합은 `amount`와 정확히 일치(유실 0) | `IllegalArgumentException`(amount가 null 또는 `n <= 0`) |

- `add`/`subtract`는 `BigDecimal`의 기본 동작을 따르므로 결과 scale은 두 피연산자 중 **큰 scale**을 따른다.
- `multiply`의 `quantity`는 `int`다. **`0`·음수 수량도 허용**한다(음수는 차감/환불 표현). 결과 scale은 `amount`의 scale을 보존한다.
- `allocate`의 최소 분배 단위는 `10`<sup>-scale</sup>이며, 여기서 `scale`은 `Math.max(amount.scale(), 0)`로 정규화한 유효 scale이다(음수 scale 처리는 4·5절 참고). 나눠떨어지지 않아 생기는 나머지는 **앞쪽 조각부터** 최소 단위씩 흡수하며, 부호는 원금을 따른다. 따라서 반환된 모든 조각의 합은 원금과 정확히 일치한다.

### 공개 상수

| 상수 | 값 | 의미 |
|---|---|---|
| `ROUNDING_MODE` | `RoundingMode.HALF_EVEN` | 모듈 표준 반올림 정책(은행가 반올림). **정책 선언 상수** — 4개 연산 자체에는 적용되지 않는다(아래 주의 참고). |
| `NULL_ARGUMENT_MESSAGE` | `"Money amount arguments must not be null."` | 널 금액 인자 예외 메시지 |
| `NON_POSITIVE_COUNT_MESSAGE` | `"The number of parts (n) must be a positive integer."` | 분배 개수 `n <= 0` 예외 메시지 |

> **`ROUNDING_MODE`는 연산 결과에 적용되지 않는다.** 이 클래스의 4개 연산(`add`·`subtract`·`multiply`·`allocate`)은 모두 **정확 연산**이라 내부에서 실제 반올림이 개입하지 않는다(`allocate`조차 정수 단위 나머지 분배로 유실이 0이다). `ROUNDING_MODE`는 연산 결과에 적용되는 값이 아니라, **반올림이 필요한 호출부**(예: 세율·이자 계산으로 scale을 줄여야 하는 경우)가 모듈 표준 정책으로 참조하도록 노출하는 정책 선언 상수다.

---

## 3. 사용 예시 (Java)

### 정확 산술 (add / subtract / multiply)

```java
import ai.genesislab.money.MoneyMath;
import java.math.BigDecimal;

BigDecimal a = new BigDecimal("0.10");
BigDecimal b = new BigDecimal("0.20");

BigDecimal sum  = MoneyMath.add(a, b);                 // 0.30 (double의 0.30000000000000004 오차 없음)
BigDecimal diff = MoneyMath.subtract(a, b);            // -0.10 (음수 허용: 차감/환불)

BigDecimal price = new BigDecimal("19.99");
BigDecimal total = MoneyMath.multiply(price, 3);       // 59.97 (scale 2 보존)
BigDecimal refund = MoneyMath.multiply(price, -1);     // -19.99 (음수 수량 허용)
```

### 정확 분배 (allocate, 유실 0)

```java
import ai.genesislab.money.MoneyMath;
import java.math.BigDecimal;

BigDecimal[] parts = MoneyMath.allocate(new BigDecimal("100.00"), 3);
// [33.34, 33.33, 33.33] — 앞쪽 조각이 최소 단위(0.01)를 하나 더 받는다.
// 합계 = 100.00 (원금과 정확히 일치, 유실 0)

BigDecimal[] neg = MoneyMath.allocate(new BigDecimal("-100.00"), 3);
// [-33.34, -33.33, -33.33] — 음수도 앞쪽 조각의 절댓값을 키우는 방향으로 분배, 합 = -100.00
```

### 예외 처리

```java
import ai.genesislab.money.MoneyMath;

try {
    MoneyMath.allocate(amount, 0);
} catch (IllegalArgumentException e) {
    // e.getMessage()를 공개 상수와 대조해 분기할 수 있다:
    if (MoneyMath.NON_POSITIVE_COUNT_MESSAGE.equals(e.getMessage())) {
        // 분배 개수가 양수가 아님
    } else if (MoneyMath.NULL_ARGUMENT_MESSAGE.equals(e.getMessage())) {
        // 널 금액 인자
    }
}
```

---

## 4. 에러 계약 (중요)

Money 모듈의 모든 실패는 **형식·계약 위반**이며 표준 `IllegalArgumentException`으로 거부한다(순수 산술이라 별도 도메인 예외 타입은 두지 않는다 — 5절 설계 결정 참고). 호출자는 공개 상수 메시지에 의존해 분기할 수 있다.

| 입력 상황 | 대상 메서드 | 결과 |
|---|---|---|
| `a` 또는 `b`가 null | `add`, `subtract` | `IllegalArgumentException` + `NULL_ARGUMENT_MESSAGE` |
| `amount`가 null | `multiply`, `allocate` | `IllegalArgumentException` + `NULL_ARGUMENT_MESSAGE` |
| `n <= 0` | `allocate` | `IllegalArgumentException` + `NON_POSITIVE_COUNT_MESSAGE` |

- **음수 금액은 예외가 아니다.** `add`/`subtract`/`multiply`/`allocate` 모두 음수 금액을 허용한다(차감·환불 표현). `multiply`의 `quantity`도 `0`·음수를 허용한다. `allocate`는 `amount`의 음수를 허용하며 `n <= 0`만 거부한다.
- `allocate`의 검증 순서는 **null → n<=0**이다. `amount`가 null이면 `n` 값과 무관하게 `NULL_ARGUMENT_MESSAGE`가 먼저 던져진다.

> **`allocate`의 유실-0 계약과 음수 scale 안전성**: `allocate`는 원금을 정수 최소 단위로 환산해(`amount.setScale(scale).unscaledValue()`) `divideAndRemainder`로 나눈 뒤, 나머지 절댓값만큼 앞쪽 조각에 최소 단위를 하나씩 더한다. 여기서 유효 scale은 `Math.max(amount.scale(), 0)`로 **정규화**한다. `stripTrailingZeros()` 등으로 음수 scale이 된 금액(예: `1E+2`, scale `-2`)을 정규화 없이 처리하면 최소 단위가 원금의 10<sup>|scale|</sup>배로 커져 `[100, 0, 0]`처럼 한쪽에 쏠린다(합은 일치해 "유실-0 검사는 통과하는 조용한 버그"). 정규화로 음수 scale도 정수 최소 단위(scale 0) 기준으로 올바르게 n등분되어, 조각 쏠림 없이 합도 정확히 일치한다.

---

## 5. 주요 설계 결정 · 제약

- **금액 타입은 `BigDecimal`(`double`/`float` 금지)**: 이진 부동소수는 `0.1 + 0.2 != 0.3`처럼 십진 금액을 정확히 표현하지 못한다. 모든 금액을 `BigDecimal`로 다뤄 반올림 오차를 배제한다(`DECISIONS.md §B` 정책 승격).
- **반올림 = `HALF_EVEN`(은행가 반올림), 단 연산에는 미개입**: 모듈 표준 반올림 정책을 `ROUNDING_MODE` 상수로 노출한다. 그러나 4개 연산은 모두 **정확 연산**이라 실제 반올림이 일어나지 않는다. `ROUNDING_MODE`는 향후 확장·**반올림이 필요한 호출부**(세율·이자 등 scale 축소 시)가 참조하는 정책 선언 상수이지, 연산 결과에 적용되는 값이 아니다.
- **통화 scale 강제 없이 입력 scale 보존(일반화)**: 특정 통화의 소수 자릿수를 강제하지 않고 입력 `BigDecimal`의 scale을 보존한다. `add`/`subtract`는 두 입력 중 큰 scale, `multiply`는 `amount`의 scale, `allocate`는 `Math.max(amount.scale(), 0)`을 따른다. `allocate`의 최소 분배 단위는 `10`<sup>-scale</sup>이다.
- **음수 금액 허용**: 차감·환불을 표현하기 위해 음수 금액을 허용한다. `multiply`의 `quantity`도 `0`·음수를 허용한다. `allocate`의 음수 금액은 나머지를 앞쪽 조각의 **절댓값을 키우는 방향**으로 분배한다(부호는 원금을 따름).
- **`allocate`의 유실-0 정확 분배**: 정수 단위 `divideAndRemainder`로 나눈 뒤 나머지를 앞쪽 조각에 최소 단위씩 흡수시켜, 반환된 모든 조각의 합이 원금과 **1단위도 유실 없이 정확히 일치**한다. 반올림이 아니라 정수 나머지 분배이므로 손실이 원천적으로 없다.
- **음수 scale 정규화**: 유효 scale을 `Math.max(amount.scale(), 0)`로 정규화해, `stripTrailingZeros()` 등으로 음수 scale이 된 금액도 정수 최소 단위 기준으로 올바르게 분배한다(4절 조용한 버그 방지). `setScale(scale)`로의 확장은 scale 증가 방향이라 항상 손실 없는 정확 연산이다. 정규화 결과 음수 scale 입력의 조각 scale은 0이 된다.
- **전용 예외 타입 없음(`IllegalArgumentException`으로 충분)**: 순수 산술이라 "해 없음" 같은 도메인 실패 케이스가 없고, 모든 실패가 형식·계약 위반(널 인자, `n <= 0`)이다. 따라서 `CryptoException`/`SudokuException`에 대응하는 `MoneyException`은 두지 않는다(재사용 불가 사유가 명확).
- **원본 불변 / 부수효과 없음**: `allocate`는 항상 새 배열을 반환하며 입력을 변형하지 않는다. `BigDecimal`은 불변 타입이라 산술 메서드도 입력을 바꾸지 않는다(`DECISIONS.md §A`).
- **정적 유틸 클래스**: 상태가 없으므로 `final` + private 생성자로 인스턴스화를 금지한다(인스턴스화 시 `AssertionError`).
- **의존성 0(순수 JDK)**: `BigDecimal`/`BigInteger`는 JDK 표준이라 외부 라이브러리·빌드 설정 변경이 없다(`DECISIONS.md §C·§D`).

---

## 6. 빌드 · 의존성 · 테스트 실행

- 빌드 도구: **Gradle (Kotlin DSL)**, 플러그인 `java-library`, **JDK 21 toolchain**.
- 의존성: JDK 표준 라이브러리만 사용 — **외부 의존성 0**(BigDecimal은 JDK 내장).
- 테스트 프레임워크: **JUnit 5 (Jupiter)**.
- 테스트 위치: `src/test/java/ai/genesislab/money/`
  - 단위: `MoneyMathTest`
  - 통합: `MoneyMathIntegrationTest`
  - 공통 테스트 헬퍼: `src/test/java/ai/genesislab/testutil/BigDecimals.java`(중복 제거를 위한 `bd`/`sum` 유틸)

### 실행

```bash
./gradlew test
```

### JAVA_HOME 주의사항

- 빌드는 Gradle **toolchain으로 Java 21(Corretto 21, LTS)** 을 타깃한다(`build.gradle.kts`). 로컬 `JAVA_HOME`은 Corretto 21 이상을 권장한다(상세는 `docs/calculator.md` 4절 참고).

---

## 7. 관련 문서

- 저장소 구조·네이밍·테스트·빌드 규칙: [`docs/CONVENTIONS.md`](./CONVENTIONS.md)
- 설계 결정·정책 원장: [`docs/DECISIONS.md`](./DECISIONS.md)
- 암호화 모듈 문서(동일 스타일): [`docs/crypto.md`](./crypto.md)
- 스도쿠 모듈 문서(동일 스타일): [`docs/sudoku.md`](./sudoku.md)
- 계산기 모듈 문서(동일 스타일): [`docs/calculator.md`](./calculator.md)
- 개발 파이프라인 표준: [`OS.md`](../OS.md)
