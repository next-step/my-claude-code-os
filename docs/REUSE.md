# REUSE — 재사용 자산 카탈로그

이 문서는 저장소에 **이미 존재하는 재사용 가능한 자산**의 재고 목록이다.
OS 1원칙 **"재사용 우선"** 을 말이 아니라 **배선**으로 만들기 위한 파일 — 새 코드를 짜기 전에 여기부터 뒤진다.

> **CONVENTIONS.md와의 차이**: `CONVENTIONS.md`는 *규칙*("어떻게 짜라")이고,
> 이 문서는 *재고*("이미 있는 것, 갖다 써라")다. 규칙은 스타일을, 카탈로그는 부품을 다룬다.

## 소유권 · 수명 (계약)
- **쓰기(소유): `os-mapper`(1단계)만.** 매 1단계 스캔에서 코드베이스를 훑어 **전체 갱신**한다(overwrite). 손으로 편집하지 않는다 — 다음 스캔에 덮어써진다.
- **읽기: `os-developer`(2단계 재사용 우선 설계)**, 오케스트레이터(위임 시 경로 포인터).
- **작업 간 학습**: 작업 N에서 새로 만든 일반화 자산은 코드에 실재하므로, 작업 N+1의 1단계 스캔이 **자동으로 편입**한다. 즉 이 카탈로그는 프로젝트가 자랄수록 함께 자란다.
- 형식: `자산 — 경로 — 용도 — 재사용 방법/주의`. 카테고리별로 묶는다.

> 스캔 일자: 2026-07-15. 다음 예정 작업 `ai.genesislab.money.MoneyMath`(BigDecimal 금액 계산 정적 유틸)가
> 소비할 자산을 각 카테고리에 표시(→ MoneyMath)했다.

---

## 1. 공통 유틸 · 골격
- **정적 유틸 클래스 골격** — `src/main/java/ai/genesislab/calculator/Calculator.java`, `src/main/java/ai/genesislab/crypto/AesGcmCipher.java`, `src/main/java/ai/genesislab/sudoku/SudokuSolver.java` — 외부 의존성 없는 순수 로직 유틸의 표준 형태 — `final` 클래스 + `private` 생성자(내부에서 `throw new AssertionError("No <FQCN> instances for you!")`)로 인스턴스화 차단. **→ MoneyMath**: `Calculator`가 가장 닮은 최소 골격(정적 산술 메서드 모음). 이 골격을 복제해 시작.
- **공개 메시지 상수 패턴** — `calculator/Calculator.java`, `crypto/*.java`, `sudoku/*.java` 공통 — 에러 메시지를 `public static final String ...MESSAGE`로 노출 — 테스트가 문자열 하드코딩 없이 상수를 대조할 수 있게 함(CONVENTIONS §4·§5). **→ MoneyMath**: `NULL_ARGUMENT_MESSAGE`, `NON_POSITIVE_COUNT_MESSAGE` 등을 리터럴 대신 이 패턴으로 노출.

## 2. 에러 처리
- **표준 예외 던지기 규약** — `DECISIONS.md §A` 정책 + `calculator/Calculator.java`(ArithmeticException), `sudoku/SudokuValidator.java`(IllegalArgumentException) — 형식·인자 오류는 `IllegalArgumentException`, 산술 위반은 `ArithmeticException` — **→ MoneyMath**: null 인자·`n<=0`은 `IllegalArgumentException`. 음수 금액 정책은 게이트①에서 확정될 사안.
- **모듈 전용 비검사 예외** — `src/main/java/ai/genesislab/crypto/CryptoException.java`, `src/main/java/ai/genesislab/sudoku/SudokuException.java` — 도메인 실패를 표준 예외와 구분해 던지는 모듈 경계 예외(`XxxException extends RuntimeException`, 생성자 2종 + cause 보존) — **→ MoneyMath**: allocate/multiply의 실패는 대부분 *인자 오류*라 표준 예외로 충분. 전용 `MoneyException`은 도메인 고유 운영 실패가 생길 때만 이 패턴으로 추가(불필요하면 만들지 않는다).

## 3. 테스트 헬퍼
- **`assertNotInstantiable`** — `src/test/java/ai/genesislab/testutil/UtilityClasses.java` — 유틸 클래스가 `private` 생성자로 인스턴스화를 막는지 리플렉션으로 검증하는 공통 단언 — **→ MoneyMath**: `MoneyMathTest`에서 `assertNotInstantiable(MoneyMath.class)` 한 줄로 골격 불변식 검증(중복 리플렉션 코드 금지).

## 4. 테스트 템플릿 (구조 패턴)
- **단위 테스트 템플릿** — `src/test/java/ai/genesislab/{calculator,crypto,sudoku}/*Test.java` — JUnit 5 기반 표준 단위 테스트 골격 — `@Nested` 그룹 + 한글 `@DisplayName` + `assertThrows`로 예외·상수 대조 + `@ParameterizedTest`(`@CsvSource`) 표 기반 검증 — **→ MoneyMath**: `CalculatorTest`가 가장 가까운 참조(정상/경계/예외 산술). allocate의 다분배·유실0은 `@ParameterizedTest`로.
- **통합 테스트 템플릿** — `src/test/java/ai/genesislab/{calculator,crypto,sudoku}/*IntegrationTest.java` — 한 모듈 출력이 다음 입력으로 흐르는 라운드트립/합성 시나리오 검증 — **→ MoneyMath**: add/subtract/multiply/allocate를 엮은 합성 시나리오(예: 총액 → allocate 분배 → 재합산 = 원금, 유실 0)로 통합 검증.
- **전용 예외 단위 테스트 템플릿** — `src/test/java/ai/genesislab/sudoku/SudokuExceptionTest.java` — 모듈 전용 예외의 두 생성자·메시지·cause 보존을 검증 — **→ MoneyMath**: 전용 예외를 도입하는 경우에만 이 템플릿을 복제.

## 5. 빌드 · 의존성 배선
- **`build.gradle.kts` 의존성 블록** — `/build.gradle.kts` — java-library 스코프 규칙(`api`/`implementation`/`testImplementation`) + JUnit BOM 패턴 — **→ MoneyMath**: BigDecimal은 JDK 표준이라 **신규 의존성 0**. 빌드 파일 수정 불필요(`DECISIONS.md §C` 의존성 최소화 정책 준수).
- **jacoco 커버리지 리포트 배선** — `/build.gradle.kts`(`jacocoTestReport`, CSV/HTML) — 랄프 루프·검증이 소비하는 커버리지 측정 소스 — 새 모듈은 추가 설정 없이 자동 편입.

## 6. 도메인 모듈 (참조 구현)
> 새 모듈을 짤 때 "가장 닮은 것"을 골라 구조를 본뜬다.
- **Calculator** — `src/main/java/ai/genesislab/calculator/Calculator.java` — 단순 산술 로직 모듈의 최소 참조. **MoneyMath의 1순위 본보기**(정적 산술 + 상수 메시지 + 0-나누기류 예외).
- **AesGcmCipher / PasswordHasher** — `src/main/java/ai/genesislab/crypto/` — 상태 없는 정적 유틸 + 전용 예외 + 상수 메시지 + 외부 의존성(BCrypt) 도입 사례의 완성형 참조.
- **SudokuValidator / SudokuSolver** — `src/main/java/ai/genesislab/sudoku/` — 입력 검증(형식·모순 분리) + 백트래킹 + 원본 불변(새 배열 반환) 로직의 참조. **MoneyMath.allocate**가 `BigDecimal[]`을 새 배열로 반환(원본 불변, `DECISIONS.md §A`)할 때 배열 반환·불변 패턴 참고.

---

> 자산을 재사용했거나 **재사용 불가 사유**가 분명하면, 2단계 보고와 리뷰 게이트에서 그 근거를 남긴다(OS 2단계 DoD (c)).
