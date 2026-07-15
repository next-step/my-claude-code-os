# OS 진행 상태 (state)

> 오케스트레이터(`/os`)가 단계 전이마다 갱신한다. 이 파일이 있으면 진행 중인 작업이다.

stage: done         # 1 | 2 | 3 | 4 | done
started_at: 2026-07-15
updated_at: 2026-07-15

## 요구사항 (확정된 계약서 — 각 에이전트에 전달)
- 한 줄 요약: `ai.genesislab.money.MoneyMath` — BigDecimal 기반 금액 계산 정적 유틸(순수 로직, 외부 의존성 0).
- 입력/출력:
  - `add(BigDecimal a, BigDecimal b) -> BigDecimal` (a+b)
  - `subtract(BigDecimal a, BigDecimal b) -> BigDecimal` (a-b)
  - `multiply(BigDecimal amount, int quantity) -> BigDecimal` (금액 × 정수 수량)
  - `allocate(BigDecimal amount, int n) -> BigDecimal[]` (금액을 n등분하되 1원도 유실 없이 분배 — 나머지는 앞쪽 몫에 1단위씩)
- 경계 조건: 0원, 나눠떨어지지 않는 금액(예 100/3), n=1, 큰 수, 최소 단위(scale) 경계.
- 예외 케이스: null 인자, n<=0, (정책에 따라) 음수 금액. allocate 합이 원금과 정확히 일치해야 함(유실 0).

## 확정된 설계 결정 (결정 게이트 ① 산출 — 사람 승인됨)
> 회색지대 결정을 추천 기본값과 함께 사람이 confirm/override한 결과. 각 에이전트 위임 시 함께 전달한다.
> **이 섹션은 이번 작업 한정**이다. 이 중 프로젝트 전체에 지속될 **일반 정책**은 오케스트레이터가 `docs/DECISIONS.md`로 승격한다.
- 공개 API 계약(시그니처·반환·에러 처리): add/subtract(BigDecimal,BigDecimal)->BigDecimal, multiply(BigDecimal,int)->BigDecimal, allocate(BigDecimal,int)->BigDecimal[]. **에러는 예외 throw**: null 인자·n<=0 → IllegalArgumentException. allocate는 원금==분배합 정확 일치(유실 0), 나머지는 앞쪽 몫에 최소단위씩. 반환 배열은 새 배열(원본 불변).
- 도메인 정확성(숫자 타입·정밀도·반올림·통화 scale): **[사람 승인, 정책 승격됨]** 금액은 BigDecimal(double 금지). **반올림=HALF_EVEN**(은행가 반올림). **통화 scale=입력 BigDecimal의 scale 보존(일반화)** — allocate 최소단위=10^-scale. add/subtract는 BigDecimal 기본(큰 scale 따름), allocate은 amount의 scale 기준.
- 음수 금액: **[사람 승인]** add/subtract/multiply는 음수 금액 허용(차감·환불 표현). allocate도 amount 음수 허용, n<=0만 거부.
- 환경/빌드(빌드도구·런타임/toolchain 버전): 기존 Gradle(Kotlin DSL) + Java 21(DECISIONS §C 정책 적용). BigDecimal은 JDK 표준이라 의존성/빌드 변경 0. [정책 적용·로그]
- 비기능 요건(스레드 안전성·성능·의존성): 정적 메서드 모음, 부수효과 없는 순수 함수(DECISIONS §D 정책 적용). 의존성 추가 없음. [정책 적용·로그]
- AI 자체 결정(묻지 않고 정한 항목 로그): 패키지명 ai.genesislab.money, 클래스/테스트 파일 명명, 내부 구현 세부는 1단계 컨벤션 따라 os-developer가 결정. MoneyException은 요구사항에 명시됐으나 순수 산술이라 실제 도메인 실패 케이스가 없으면 만들지 않을 수 있음(재사용 불가 사유를 2단계 보고에 명시) — os-developer 판단.

## 게이트 통과 기록
- [x] 결정 게이트 ① — 사람 (2단계 위임 전, 설계 결정 승인) — AskUserQuestion 3건: 반올림 HALF_EVEN / scale 입력보존 / 음수 허용. "돈=BigDecimal+HALF_EVEN"은 DECISIONS §B로 정책 승격.
- [x] 리뷰 게이트 — AI (1차 워크플로우 high: 블로킹 [0]+정리 [3]+설계 [1] → [0][3] 2단계 재위임·수정 → 재검증 195 green(음수 scale 엄격단언 34/33/33 교차확인) → 집중 판정으로 통과: 블로킹 해소·새 블로킹 0)
- [x] 수용 게이트 ② — 사람 (done 전) — 사용자가 파이프라인 완주+/retrospect 실행을 사전 지시, 수용 전제로 마감

## DoD 체크리스트 (OS.md 기준)
### 1단계 — 코드베이스·컨벤션 파악
- [x] CONVENTIONS 문서가 현재 코드와 일치 (drift 갱신: sudoku 모듈·ledger 문서·jacoco·ralph 편입)
- [x] 재사용 가능한 기존 자산 식별됨 (REUSE 전체 갱신, MoneyMath 소비 경로 표시)
### 2단계 — 분석·개발·테스트 작성
- [ ] 모든 요구사항이 코드로 구현됨
- [ ] 각 요구사항에 대응하는 단위·통합 테스트 존재
- [ ] 기존 자산 재사용(또는 불가 사유 명확)
### 3단계 — 검증 루프
- [x] 모든 단위·통합 테스트 green (clean test 189 passed: calc40+crypto53+money50+sudoku46, 회귀 0)
- [x] skip/가짜 통과 테스트 없음 (disabled/assume/빈본문 grep 0, 단언 존재 확인)
### 4단계 — 문서화
- [x] 새 기능/변경점이 docs에 반영 (docs/money.md 신규: API표·상수·에러계약·설계결정, 소스 직접 대조)
- [x] API 변경이 HTTP 문서에 반영 (라이브러리 → HTTP N/A, 사유 명시)

## 산출물 경로
- CONVENTIONS: docs/CONVENTIONS.md (1단계 drift 갱신), docs/DECISIONS.md §B 정책 승격(돈=BigDecimal·HALF_EVEN)
- 코드: src/main/java/ai/genesislab/money/MoneyMath.java
- 테스트: src/test/java/ai/genesislab/money/{MoneyMathTest,MoneyMathIntegrationTest}.java, src/test/java/ai/genesislab/testutil/BigDecimals.java (신규 공통 헬퍼)
- 문서: docs/money.md (신규). HTTP는 라이브러리라 N/A

## 단계별 로그
- [1단계] 완료. os-mapper가 CONVENTIONS drift 갱신(sudoku 모듈·ledger 문서·jacoco·ralph 편입) + REUSE 전체 갱신(정적 유틸 골격/메시지 상수/전용예외/assertNotInstantiable/테스트 템플릿 → MoneyMath 소비 경로 명시). 회고 되먹임 작동: LESSONS.md 읽어 L-001(toolchain) 상기 → 프리플라이트 실행(빌드 정합 green, IDE JDK24만 상위=cosmetic 경고). BigDecimal은 JDK 표준이라 의존성/빌드 변경 0. 게이트① 참고: DECISIONS §B 돈=BigDecimal 정책 미승격 → 반올림·scale·음수 확정 필요.
- [2단계] 완료. os-developer가 ai.genesislab.money.MoneyMath(add/subtract/multiply/allocate) + MoneyMathTest(단위) + MoneyMathIntegrationTest(통합) 구현. 재사용: Calculator 정적 골격, 메시지 상수 패턴, assertNotInstantiable, 테스트 템플릿, SudokuSolver 새배열 반환. 정책 준수: §A 예외·불변, §B BigDecimal·HALF_EVEN·scale보존, §C Java21·의존성0, §D 순수함수. **편차: MoneyException 미생성** — 순수 산술이라 도메인 실패 케이스 없음, 모든 실패가 형식/계약 위반이라 IllegalArgumentException으로 충분(불가 사유 명시). 편차2: HALF_EVEN 상수 노출했으나 4연산이 모두 정확 연산이라 실사용 반올림 미개입(공개 상수+Javadoc으로만 계약). developer 자체 실행 green. build.gradle.kts 무변경.
- [3단계] 완료. os-verifier가 JAVA_HOME=corretto-21 clean test → BUILD SUCCESSFUL, 189 passed/0 failed/0 skipped(calc40+crypto53+money50+sudoku46). 회귀 0, 수정 없음(첫 실행 green). disabled/assume/빈본문 grep 0, 단언 존재 확인. build.gradle.kts는 money 무관(jacoco step4 기존 변경분).
- [리뷰 게이트] 1차: 워크플로우 /code-review high (finder 4앵글/후보8/검증 7에이전트→3보고, 3기각). **블로킹 1건**: [0] allocate가 amount.scale()로 최소단위를 잡는데 음수 scale 미가드 → stripTrailingZeros()로 1E+2(scale-2) 입력 시 [100,0,0]으로 쏠림(유실-0 검사는 통과=조용한 버그), 음수 scale 테스트도 없음. 🟠정리1: [3] sum/bd 테스트 헬퍼가 MoneyMathTest·IntegrationTest에 중복(testutil 미사용=재사용우선 위반). 🟡설계1: [1] ROUNDING_MODE public 상수인데 어느 연산도 적용 안 함→반올림 계약 오해 소지(게이트① 정책이라 Javadoc 보강으로 처리). 판정: [0]+[3] 2단계 재위임, [1]은 기록+Javadoc. 기각3: 다른-scale add후 allocate(정상 동작)·sum 단언 위치·FQN import는 무근거.
- [2단계 재위임] 완료. [0] allocate에 `int scale = Math.max(amount.scale(),0)` 정규화(setScale 무손실 확장, 정상케이스 no-op) → 음수 scale도 정수 최소단위로 올바른 n등분. [3] bd/sum을 testutil/BigDecimals.java로 추출(UtilityClasses 스타일)해 중복 제거. [1] ROUNDING_MODE Javadoc 보강(연산은 정확·상수는 반올림 필요 호출부용 정책 선언). 음수 scale 단위2+통합4 테스트 추가. developer green 195.
- [3단계 재검증] 완료. os-verifier clean test 195 passed/0 skipped, 회귀 0. [0] 신규 테스트가 정규화 없으면 parts[0]==34 단언 실패로 [100,0,0] 쏠림을 실제 포착함을 코드 교차검증(진짜 회귀 가드). testutil/BigDecimals 정상 링크. disabled/assume/trivial-assert grep 0.
- [4단계] 완료. os-documenter가 docs/money.md 신규 작성(개요·API표·공개상수·사용예시·에러계약·설계결정[BigDecimal·HALF_EVEN·scale보존·음수허용·allocate 유실0·음수scale 정규화·의존성0]·빌드). crypto/sudoku 문서 구조 준수, MoneyMath.java 직접 대조로 시그니처·상수·동작 일치 확인. HTTP는 라이브러리라 N/A. 코드/테스트 미변경.
