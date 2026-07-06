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

---

## 1. 공통 유틸 · 골격
- **정적 유틸 클래스 골격** — `src/main/java/ai/genesislab/crypto/AesGcmCipher.java` — 외부 의존성 없는 순수 로직 유틸의 표준 형태 — `final` 클래스 + `private` 생성자(내부에서 `AssertionError` throw)로 인스턴스화 차단. 새 순수-로직 모듈(예: 검증기/변환기)은 이 골격을 복제.
- **공개 메시지 상수 패턴** — `crypto/*.java`, `sudoku/*.java` 공통 — 에러 메시지를 `public static final String ...MESSAGE`로 노출 — 테스트가 문자열 하드코딩 없이 상수를 대조할 수 있게 함(CONVENTIONS §5). 새 예외 메시지는 리터럴 대신 이 상수 패턴으로.

## 2. 에러 처리
- **모듈 전용 비검사 예외** — `src/main/java/ai/genesislab/crypto/CryptoException.java`, `src/main/java/ai/genesislab/sudoku/SudokuException.java` — 도메인 실패를 표준 예외와 구분해 던지는 모듈 경계 예외 — 새 모듈은 `XxxException extends RuntimeException` 형태로 이 패턴 복제(형식·인자 오류는 `IllegalArgumentException`, 도메인 실패만 전용 예외 — `DECISIONS.md` 정책 참조).

## 3. 테스트 헬퍼
- **`assertNotInstantiable`** — `src/test/java/ai/genesislab/testutil/UtilityClasses.java` — 유틸 클래스가 `private` 생성자로 인스턴스화를 막는지 검증하는 공통 단언 — 새 정적 유틸의 단위 테스트에서 그대로 호출(중복 리플렉션 코드 금지).

## 4. 테스트 템플릿 (구조 패턴)
- **단위/통합 테스트 템플릿** — `src/test/java/ai/genesislab/{calculator,crypto,sudoku}/*Test.java` / `*IntegrationTest.java` — JUnit 5 기반 표준 테스트 골격 — `@Nested` 그룹 + 한글 `@DisplayName` + `assertThrows`로 예외·상수 대조. 새 모듈 테스트는 가장 가까운 기존 모듈의 테스트를 복제해 시작.

## 5. 도메인 모듈 (참조 구현)
> 새 모듈을 짤 때 "가장 닮은 것"을 골라 구조를 본뜬다.
- **Calculator** — `src/main/java/ai/genesislab/calculator/Calculator.java` — 단순 산술 로직 모듈의 최소 참조.
- **AesGcmCipher / PasswordHasher** — `src/main/java/ai/genesislab/crypto/` — 상태 없는 정적 유틸 + 전용 예외 + 상수 메시지의 완성형 참조.
- **SudokuValidator / SudokuSolver** — `src/main/java/ai/genesislab/sudoku/` — 입력 검증(형식·모순 분리) + 백트래킹 + 원본 불변(새 배열 반환) 로직의 참조. `validateFormat` 공통화 방식 참고.

---

> 자산을 재사용했거나 **재사용 불가 사유**가 분명하면, 2단계 보고와 리뷰 게이트에서 그 근거를 남긴다(OS 2단계 DoD (c)).
