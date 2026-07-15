# CONVENTIONS

이 문서는 저장소의 구조·네이밍·테스트·빌드·코드 스타일 규칙을 고정한다.
OS.md의 [1단계] 산출물이며, 코드와 어긋나면 이 문서를 현실에 맞게 갱신한다.

> 상태(2026-07-15 갱신): 계산기 모듈(`ai.genesislab.calculator`), 암호화 모듈
> (`ai.genesislab.crypto` — `AesGcmCipher`/`PasswordHasher`/`CryptoException`), 스도쿠 모듈
> (`ai.genesislab.sudoku` — `SudokuValidator`/`SudokuSolver`/`SudokuException`)이 실제로 구현되어
> Gradle 빌드·JUnit 5 테스트가 동작한다(`./gradlew test` BUILD SUCCESSFUL 확인).
> 공통 테스트 헬퍼(`ai.genesislab.testutil.UtilityClasses`)도 도입됐다.
> 따라서 본 문서는 더 이상 "제안"이 아니라 **현재 코드에서 관측된 사실**을 기준으로 한다.
> 다음 예정 모듈(`ai.genesislab.money.MoneyMath` — BigDecimal 금액 계산)은 아래 컨벤션을 그대로 따른다.

---

## 1. 현재 저장소 구조 (사실)

```
my-claude-code-os/
├── .claude/                 # Claude OS 런타임 (에이전트·스킬·훅·상태)
│   ├── agents/              # os-mapper / os-developer / os-verifier / os-documenter
│   ├── hooks/               # count-requests.sh 등
│   ├── os/                  # state.md, state.template.md
│   ├── ralph/               # 랄프 지표 루프 자산(measure-coverage.sh, loop.template.md)
│   └── skills/              # commit, os, os-scan, os-status, skill-stat, retrospect, ralph …
├── .idea/                   # IntelliJ 설정 (languageLevel JDK_23, project SDK corretto-24, gradleJvm corretto-21)
├── CLAUDE.md                # 프로젝트 지침
├── OS.md                    # 개발 파이프라인(1~4단계) 표준 문서
├── README.md                # 미션 안내
├── settings.gradle.kts      # rootProject.name = "calculator"
├── build.gradle.kts         # java-library 플러그인, JUnit 5, jacoco, toolchain JDK 21, bcrypt 의존성
├── gradlew / gradlew.bat    # Gradle Wrapper 실행 스크립트
├── gradle/wrapper/          # gradle-wrapper.jar, gradle-wrapper.properties (Gradle 8.10.2)
├── src/
│   ├── main/java/ai/genesislab/
│   │   ├── calculator/Calculator.java
│   │   ├── crypto/                       # 암호화 모듈
│   │   │   ├── AesGcmCipher.java         # 양방향(AES-256/GCM) 대칭 암호화 유틸
│   │   │   ├── PasswordHasher.java       # 단방향(BCrypt) 해싱 유틸
│   │   │   └── CryptoException.java       # 모듈 전용 비검사 예외
│   │   └── sudoku/                        # 스도쿠 모듈
│   │       ├── SudokuValidator.java       # 입력 검증(형식·값 범위)
│   │       ├── SudokuSolver.java          # 백트래킹 풀이 + 유일해/한계 검증
│   │       └── SudokuException.java       # 모듈 전용 비검사 예외(도메인 실패)
│   └── test/java/ai/genesislab/
│       ├── calculator/
│       │   ├── CalculatorTest.java             # 단위 테스트
│       │   └── CalculatorIntegrationTest.java  # 통합 테스트
│       ├── crypto/
│       │   ├── AesGcmCipherTest.java
│       │   ├── AesGcmCipherIntegrationTest.java
│       │   ├── PasswordHasherTest.java
│       │   └── PasswordHasherIntegrationTest.java
│       ├── sudoku/
│       │   ├── SudokuValidatorTest.java        # 단위 테스트
│       │   ├── SudokuSolverTest.java           # 단위 테스트
│       │   ├── SudokuExceptionTest.java        # 전용 예외 단위 테스트(생성자·cause 보존)
│       │   └── SudokuIntegrationTest.java      # 통합 테스트(validate→solve 흐름)
│       └── testutil/
│           └── UtilityClasses.java         # 공통 테스트 헬퍼(assertNotInstantiable)
└── docs/
    ├── CONVENTIONS.md       # (본 문서) 구조·컨벤션 규칙
    ├── REUSE.md             # 재사용 자산 카탈로그(os-mapper 소유)
    ├── DECISIONS.md         # 결정 원장·회색지대 정책(오케스트레이터 소유)
    ├── LESSONS.md           # 교훈 원장(/retrospect 소유)
    ├── CONTEXT-MAP.md       # 컨텍스트 계층 지도
    ├── CORE-LOOP.md / core-loop.html  # 핵심 루프 설명
    ├── calculator.md        # 계산기 모듈 문서
    ├── crypto.md            # 암호화 모듈 문서
    └── sudoku.md            # 스도쿠 모듈 문서
```

- 빌드 도구: **Gradle (Kotlin DSL)** — `build.gradle.kts`, `settings.gradle.kts`, Wrapper 포함.
- Java 소스/테스트 디렉토리: 표준 레이아웃 존재(`src/main/java`, `src/test/java`).
- 테스트 프레임워크: **JUnit 5 (Jupiter)** 구성 완료.
- 모듈은 **도메인별 패키지**로 추가된다(`ai.genesislab.<도메인>`). 현재 `calculator`, `crypto`, `sudoku` 세 도메인 존재(다음 예정: `money`).
- 테스트 전용 공통 코드는 `src/test/java/ai/genesislab/testutil/`에 둔다(프로덕션 코드 아님).

---

## 2. 빌드 도구 (사실)

- **Gradle Kotlin DSL** (`build.gradle.kts`). 적용 플러그인: `` `java-library` ``, `jacoco`.
- 좌표: `group = "ai.genesislab"`, `version = "0.1.0"`. `settings.gradle.kts`의 `rootProject.name = "calculator"`.
- **Gradle Wrapper 버전: 8.10.2** (`gradle/wrapper/gradle-wrapper.properties`). 항상 `./gradlew`로 실행한다(로컬 Gradle 직접 호출 금지).
- 저장소: `mavenCentral()`.
- **Java toolchain: JDK 21** (`languageVersion = JavaLanguageVersion.of(21)`). `DECISIONS.md §C`에서 전역 정책으로 고정됨.
  - 빌드 스크립트 주석에 근거가 명시돼 있음: CONVENTIONS는 JDK 23+를 타깃으로 제안했으나, 재현 가능한 LTS 빌드를 위해 21을 선택. toolchain 값만 바꾸면 다른 버전으로 전환 가능.
- 테스트 태스크: `useJUnitPlatform()`, `testLogging`에 `passed/skipped/failed` 이벤트 출력. 테스트 후 `jacocoTestReport`가 `finalizedBy`로 자동 실행되어 CSV/HTML 커버리지 리포트를 생성한다(랄프 루프의 "측정" 소스).

### 2-1. 외부 의존성 추가 위치 (재사용 핵심)

`build.gradle.kts`의 `dependencies { }` 블록에 추가한다. 현재 내용:

```kotlin
dependencies {
    // 단방향 비밀번호 해싱(BCrypt). 내부 구현에만 사용하므로 implementation 스코프로 추가
    // (java-library: public API 시그니처에 BCrypt 타입을 노출하지 않음).
    implementation("at.favre.lib:bcrypt:0.10.2")

    testImplementation(platform("org.junit:junit-bom:5.11.3"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
```

- **런타임/구현 의존성**(라이브러리 사용자에게 노출): `api(...)` 또는 `implementation(...)`.
  - `java-library` 플러그인을 쓰므로, 의존성이 public API 시그니처에 노출되면 `api`, 내부 구현에만 쓰이면 `implementation`을 쓴다. 실제 사례: BCrypt는 public 시그니처에 노출되지 않아 `implementation`을 선택했다.
- **테스트 전용 의존성**: `testImplementation(...)`.
- JUnit은 **BOM(platform)** 으로 버전을 한 곳에서 관리하고 개별 아티팩트는 버전 없이 선언한다. 같은 패턴을 신규 의존성에도 권장.
- **순수 로직 모듈은 의존성 0을 유지한다**(JDK 표준 라이브러리만). 외부 라이브러리는 그것이 본질적으로 필요할 때만 추가한다(crypto의 BCrypt가 유일한 사례). 예: 예정된 `money` 모듈은 `java.math.BigDecimal`(JDK 표준)만 쓰므로 신규 의존성이 필요 없다.

---

## 3. 디렉토리 레이아웃 (사실 — 표준 Gradle/Maven 레이아웃)

```
src/
├── main/java/<package>/...        # 기능(라이브러리) 코드
└── test/java/<package>/...        # 테스트 코드 (main과 동일 패키지 미러링) + testutil 공통 헬퍼
```

- 단위·통합 테스트 모두 `src/test/java`의 **동일 패키지**에 둔다. 단위/통합 구분은 별도 source set이 아니라 **클래스 명명**으로 한다(5절).
- 여러 모듈이 공유하는 테스트 헬퍼는 `src/test/java/ai/genesislab/testutil/`에 둔다(예: `UtilityClasses`).
- 규모가 커지면 Gradle source set 분리(`src/integrationTest/java`)를 고려할 수 있으나, 현재 범위에서는 사용하지 않음.

---

## 4. 네이밍 · 패키지 · 레이어 규칙 (사실)

- **루트 패키지**: 역방향 도메인 표기 `ai.genesislab.<module>`. 현재 구현: `ai.genesislab.calculator`, `ai.genesislab.crypto`, `ai.genesislab.sudoku`. 신규 모듈은 도메인 단위로 `ai.genesislab.<module>`을 새로 만든다(예: 금액 계산 모듈 → `ai.genesislab.money`).
- **클래스**: PascalCase. 순수 함수/상태 없는 모음은 `final class` + private 생성자(인스턴스화 방지)로 구현한다. private 생성자는 `throw new AssertionError("No <FQCN> instances for you!")` 형태로 통일한다. 예: `Calculator`, `AesGcmCipher`, `SudokuValidator`, `SudokuSolver` 모두 이 패턴.
- **메서드/변수**: camelCase. 요구사항 용어를 그대로 메서드명에 사용(`add`, `encrypt`, `decrypt`, `hash`, `matches`, `solve`).
- **상수**: UPPER_SNAKE_CASE. 사용자가 검증할 수 있는 **예외 메시지는 `public static final String` 상수로 노출**한다(테스트가 `getMessage()`를 이 상수와 대조). 예: `DIVIDE_BY_ZERO_MESSAGE`, `NULL_PLAINTEXT_MESSAGE`, `NULL_BOARD_MESSAGE`, `NO_SOLUTION_MESSAGE`. 매직 넘버도 의미 있는 상수로 노출(`KEY_SIZE_BITS`, `IV_LENGTH_BYTES`).
- **레이어 구분**: CLI/HTTP 없는 **순수 함수 라이브러리** 단일 레이어. 외부 I/O·가변 상태를 두지 않는다.
- **예외 처리 패턴(재사용 후보)**:
  - **입력 검증 실패(형식·계약 위반)는 표준 예외**를 던진다: null/형식 오류 → `IllegalArgumentException`, 산술 위반(0 나누기) → `ArithmeticException`. 메시지는 위 상수를 사용한다.
  - **모듈 고유의 "운영/도메인 실패"는 모듈 전용 비검사 예외**를 정의해 일관되게 래핑한다. 사례: `CryptoException extends RuntimeException`, `SudokuException extends RuntimeException` — 생성자 2종(`(String message)`, `(String message, Throwable cause)`)을 두고, JDK 검사 예외를 래핑할 때 **원인(cause)을 항상 보존**한다. 같은 패턴으로 도메인별 전용 예외를 만든다.
  - 메서드는 부수효과 없는 결정적 출력(난수·시간 등 본질적 비결정 요소 제외).

---

## 5. 테스트 위치 · 명명 (사실)

- **위치**: `src/test/java`, 대상 클래스와 동일 패키지로 미러링.
- **프레임워크**: **JUnit 5 (Jupiter)**, BOM `org.junit:junit-bom:5.11.3`. (AssertJ 등 보조 라이브러리는 현재 미사용.)
- **명명**(현재 구현 기준):
  - 단위 테스트 클래스: `<대상>Test` (예: `CalculatorTest`, `AesGcmCipherTest`, `SudokuSolverTest`, `SudokuExceptionTest`).
  - 통합 테스트 클래스: `<대상>IntegrationTest` (예: `CalculatorIntegrationTest`, `AesGcmCipherIntegrationTest`, `SudokuIntegrationTest`).
  - 테스트 메서드: 동작 설명형 `대상_상황_기대결과` (예: `divide_byZero_throwsArithmeticException`, `encrypt_producesBase64WithIvPrefix`).
- **공통 테스트 헬퍼(재사용 자산)**:
  - `ai.genesislab.testutil.UtilityClasses.assertNotInstantiable(Class<?>)` — 정적 유틸 클래스의 private 생성자가 `AssertionError`를 던지는지 리플렉션으로 검증한다. 인스턴스화 불가 불변식을 가진 새 유틸 클래스 테스트는 이 헬퍼를 호출한다(6줄 복붙 금지). crypto·sudoku 테스트들이 이미 사용 중.
- **관측된 테스트 작성 패턴(재사용 후보)**:
  - 한글 `@DisplayName`을 클래스·메서드에 병행.
  - 기능 그룹별 `@Nested` 클래스로 구조화(`GenerateKey`, `Encrypt`, `Decrypt` 등).
  - 다중 입력은 `@ParameterizedTest` + `@CsvSource`/`@ValueSource`로 표 기반 검증.
  - 실수 비교는 `private static final double DELTA = 1e-9` 허용 오차 사용.
  - 예외 검증은 `assertThrows`로 타입과 `getMessage()`(상수 대조)까지 확인. 래핑 예외는 `getCause()` 타입까지 확인(예: `AEADBadTagException`). 전용 예외는 두 생성자·cause 보존까지 검증(`SudokuExceptionTest` 참조).
  - 통합 테스트는 한 모듈의 출력이 다음 입력으로 흐르는 라운드트립 시나리오를 검증(예: encrypt→decrypt, hash→matches, validate→solve).

---

## 6. 코드 스타일 (사실)

- 들여쓰기 4 스페이스, 한 줄 120자 내.
- 순수 함수 지향: 입력에 대한 결정적 출력, 부수효과·가변 상태 지양.
- public API에는 Javadoc(파라미터 `@param`·반환 `@return`·예외 `@throws`) 작성. 현재 `Calculator`, `AesGcmCipher`, `PasswordHasher`, `SudokuSolver`, `SudokuValidator`가 이 수준을 충족.
- import 와일드카드(`*`) 지양, 명시적·정적 import 사용.
- 포매터: IDE 기본(IntelliJ). Spotless 등 강제 포매터는 현 시점 미구성.

---

## 7. 산출물 위치 규약 (OS.md 준수)

| 종류 | 위치 |
|---|---|
| 구조·컨벤션 문서 | `docs/CONVENTIONS.md` |
| 재사용 카탈로그 | `docs/REUSE.md` |
| 결정 원장 / 교훈 원장 | `docs/DECISIONS.md` / `docs/LESSONS.md` |
| 일반 문서 | `docs/` (예: `docs/calculator.md`, `docs/crypto.md`, `docs/sudoku.md`) |
| HTTP/API 문서 | `docs/http/` (현재 모듈들은 HTTP 없음 → 미사용) |
| 테스트 | `src/test/java` (본 문서 5절), 공통 헬퍼는 `.../testutil/` |
