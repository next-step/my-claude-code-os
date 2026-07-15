---
name: scaffold
description: 설계 스프린트 산출물(domain-model.md)을 읽어 DDD 계층 구조의 코드 스켈레톤을 생성합니다. Shared Kernel, Aggregate/Entity/ValueObject, Repository 인터페이스, UseCase 스텁, 테스트 스텁을 인터페이스 우선 원칙으로 생성합니다.
---

# scaffold

`/design-sprint` 산출물을 실제 코드 스켈레톤으로 변환하는 오케스트레이터.
인터페이스를 먼저 정의하고 구현은 스텁으로 남겨, 이후 `/implement`가 채워나갈 수 있는 골격을 만든다.

## 실행 방법

```
/scaffold <프로젝트 폴더>
```

예시: `/scaffold sandbox/subscription-tracker`

---

## 준비: 컨텍스트 수집

### 1. $PROJECT 결정

인수가 주어지면 그대로 사용한다. 없으면 `sandbox/` 안의 디렉토리를 나열하고 `AskUserQuestion`으로 선택받는다.

### 2. 설계 문서 확인

아래 파일의 존재 여부를 확인한다:

| 파일 | 필수 여부 |
|------|----------|
| `$PROJECT/docs/design/domain-model.md` | **필수** |
| `$PROJECT/docs/design/events.md` | 권장 (UseCase 생성에 사용) |
| `$PROJECT/docs/design/prd.md` | 선택 |

`domain-model.md`가 없으면 `/design-sprint $PROJECT`를 먼저 실행하라고 안내하고 종료한다.

### 3. 언어 감지

`$PROJECT` 루트의 파일을 아래 순서로 확인해 언어를 결정한다. `$SRC`, `$TEST`는 `$PROJECT` 기준 상대 경로다 (예: `$PROJECT/src/`):

| 감지 파일 | 언어 | 소스 루트 | 테스트 루트 |
|----------|------|----------|------------|
| `tsconfig.json` + `package.json` | TypeScript | `src/` | `src/` (`.spec.ts` 인접) |
| `package.json` (tsconfig 없음) | JavaScript | `src/` | `src/` (`.spec.js` 인접) |
| `build.gradle.kts` 또는 `build.gradle` | Kotlin | `src/main/kotlin/` | `src/test/kotlin/` |
| `pom.xml` | Java | `src/main/java/` | `src/test/java/` |
| `Cargo.toml` | Rust | `src/` | 인라인 `#[cfg(test)]` |
| `go.mod` | Go | (모듈 루트) | 인접 `_test.go` |
| `pyproject.toml` 또는 `requirements.txt` | Python | `src/` | `tests/` |

감지 실패 시(신규 프로젝트라 마커 파일이 없는 경우 포함) `AskUserQuestion`으로 언어를 선택받고, `$SRC`는 `$PROJECT/src/`로 한다.

이후 내부 변수로 저장한다:
- `$LANG` — 감지된 언어
- `$SRC` — 소스 루트 경로
- `$TEST` — 테스트 루트 경로
- `$EXT` — 파일 확장자 (예: `.ts`, `.kt`, `.go`)

---

## Step 1 — 설계 문서 분석 [Auto]

Agent tool로 서브 에이전트를 실행한다.

**서브 에이전트 프롬프트:**
```
아래 DDD 설계 문서를 분석해 코드 구조를 추출하라.

=== domain-model.md ===
{domain-model.md 전체 내용}

=== events.md (있을 경우) ===
{events.md 전체 내용}

아래 JSON 형식으로만 출력하라. JSON 외 텍스트는 출력하지 마라.

{
  "boundedContexts": [
    {
      "name": "PascalCase BC 이름",
      "dirName": "kebab-case 디렉토리명",
      "aggregates": [
        {
          "name": "PascalCase",
          "responsibility": "한 줄 책임 설명",
          "entities": ["PascalCase 이름 목록"],
          "valueObjects": ["PascalCase 이름 목록"],
          "businessRules": ["비즈니스 규칙 목록 (위반 시 throw 필요한 것)"]
        }
      ],
      "domainServices": ["PascalCase 서비스명"],
      "domainEvents": ["PascalCase 이벤트명 (과거형)"],
      "commands": ["동사+명사 형태의 커맨드명 (UseCase로 변환될 것)"]
    }
  ],
  "sharedKernelNeeded": true
}
```

출력을 파싱해 `$STRUCTURE`로 저장한다. JSON 파싱 실패 시 domain-model.md를 직접 읽어 수동으로 구조를 파악한다.

---

## Step 2 — 구조 제안 Gate 🧑

`$STRUCTURE`를 바탕으로 생성될 파일 트리를 사용자에게 보여준다.

**출력 형식 예시 (TypeScript, subscription BC 기준):**

```
생성될 파일 구조:

$SRC
├── shared/domain/
│   ├── AggregateRoot.ts       ← 기반 클래스
│   ├── Entity.ts
│   ├── ValueObject.ts
│   └── DomainEvent.ts
│
└── subscription/              ← Bounded Context
    ├── domain/
    │   ├── subscription/
    │   │   ├── Subscription.ts        ← Aggregate Root
    │   │   ├── PaymentHistory.ts      ← Entity
    │   │   └── Price.ts               ← Value Object
    │   ├── ISubscriptionRepository.ts ← Repository 인터페이스 (포트)
    │   └── events/
    │       └── SubscriptionRenewed.ts ← 도메인 이벤트
    ├── application/
    │   ├── AddSubscriptionUseCase.ts  ← UseCase 스텁
    │   └── CancelSubscriptionUseCase.ts
    ├── infrastructure/
    │   └── SubscriptionRepositoryImpl.ts ← 구현 스텁 (빈 껍데기)
    └── __tests__/
        ├── Subscription.spec.ts       ← 테스트 스텁
        └── Price.spec.ts

총 {n}개 파일 생성 예정
```

**AskUserQuestion으로 확인한다:**
- [y] 이 구조로 생성 시작
- [n] 취소
- [e] 소스 루트 경로 변경 후 진행

[e] 선택 시 경로를 입력받아 `$SRC`, `$TEST`를 업데이트하고 트리를 다시 보여준다.
[n] 선택 시 아무것도 하지 않고 종료한다.

---

## Step 3 — Shared Kernel 생성 [Auto]

`$STRUCTURE.sharedKernelNeeded`가 true이면 `$SRC/shared/domain/` 아래에 기반 클래스를 생성한다.

언어별 구현 가이드를 따른다. 서브 에이전트를 쓰지 않고 직접 Write 도구로 파일을 작성한다.

### TypeScript 기반 클래스

**`DomainEvent.ts`**
```typescript
export interface DomainEvent {
  readonly eventName: string;
  readonly occurredAt: Date;
}
```

**`ValueObject.ts`**
```typescript
export abstract class ValueObject<T extends Record<string, unknown>> {
  protected readonly props: Readonly<T>;

  constructor(props: T) {
    this.props = Object.freeze({ ...props });
  }

  equals(other?: ValueObject<T>): boolean {
    if (!other) return false;
    return JSON.stringify(this.props) === JSON.stringify(other.props);
  }
}
```

**`Entity.ts`**
```typescript
export abstract class Entity<TId> {
  protected readonly _id: TId;

  constructor(id: TId) {
    this._id = id;
  }

  get id(): TId {
    return this._id;
  }

  equals(other?: Entity<TId>): boolean {
    if (!other) return false;
    return this._id === other._id;
  }
}
```

**`AggregateRoot.ts`**
```typescript
import { Entity } from './Entity';
import { DomainEvent } from './DomainEvent';

export abstract class AggregateRoot<TId> extends Entity<TId> {
  private _domainEvents: DomainEvent[] = [];

  get domainEvents(): ReadonlyArray<DomainEvent> {
    return [...this._domainEvents];
  }

  protected addDomainEvent(event: DomainEvent): void {
    this._domainEvents.push(event);
  }

  clearDomainEvents(): void {
    this._domainEvents = [];
  }
}
```

### Kotlin 기반 클래스

**`DomainEvent.kt`**
```kotlin
interface DomainEvent {
    val eventName: String
    val occurredAt: java.time.Instant get() = java.time.Instant.now()
}
```

**`ValueObject.kt`**
```kotlin
abstract class ValueObject<T : ValueObject<T>> {
    abstract override fun equals(other: Any?): Boolean
    abstract override fun hashCode(): Int
}
```

**`Entity.kt`**
```kotlin
abstract class Entity<TId>(val id: TId) {
    override fun equals(other: Any?): Boolean {
        if (other !is Entity<*>) return false
        return id == other.id
    }
    override fun hashCode(): Int = id.hashCode()
}
```

**`AggregateRoot.kt`**
```kotlin
abstract class AggregateRoot<TId>(id: TId) : Entity<TId>(id) {
    private val _domainEvents = mutableListOf<DomainEvent>()
    val domainEvents: List<DomainEvent> get() = _domainEvents.toList()

    protected fun addDomainEvent(event: DomainEvent) { _domainEvents.add(event) }
    fun clearDomainEvents() { _domainEvents.clear() }
}
```

Python, Java, Go, Rust는 각 언어의 관용구에 맞게 동등한 패턴을 생성한다. (Python: `dataclass` + `__eq__` 오버라이드, Go: `interface` 기반, Rust: `trait` 기반)

---

## Step 4 — 도메인 계층 생성 [Auto, BC별 병렬]

`$STRUCTURE.boundedContexts`의 각 항목에 대해 **Agent tool로 서브 에이전트를 병렬 실행**한다.
BC가 3개 이상이면 한 번에 병렬 실행하고, 1-2개면 순차 실행해도 무방하다.

**각 BC별 서브 에이전트 프롬프트:**
```
아래 Bounded Context의 도메인 계층 코드를 $LANG으로 작성하라.

BC 정보:
{bc 항목 JSON}

기반 클래스 위치: $SRC/shared/domain/
출력 루트: $SRC/{bc.dirName}/domain/

반드시 따를 규칙:
1. Aggregate Root는 AggregateRoot<TId>를 상속한다
2. Entity는 Entity<TId>를 상속한다
3. ValueObject는 ValueObject<T>를 상속하며 불변(immutable)이다
4. Repository는 인터페이스(포트)만 작성한다. 구현 클래스는 만들지 않는다
5. Domain Event는 DomainEvent 인터페이스를 구현하며 불변이다
6. businessRules에 명시된 규칙은 해당 메서드 안에 throw 스텁으로 표현한다
   예시: if (amount <= 0) throw new Error('금액은 0보다 커야 합니다');
7. 모든 생성자에 타입을 명시한다
8. 비즈니스 메서드 본체는 // TODO: implement 한 줄로만 남긴다

각 파일을 아래 형식으로 출력하라:
### FILE: {정확한 경로}
```$LANG
{코드}
```
```

서브 에이전트 출력에서 `### FILE:` 블록을 파싱해 경로와 내용을 추출한 뒤 Write 도구로 저장한다.

---

## Step 5 — 애플리케이션 계층 생성 [Auto, BC별 병렬]

Step 4와 동시에 애플리케이션 계층 에이전트도 병렬로 실행한다.

**서브 에이전트 프롬프트:**
```
아래 커맨드 목록을 UseCase 클래스로 변환하라. $LANG으로 작성한다.

BC 이름: {bc.name}
커맨드 목록: {bc.commands}
관련 Aggregate: {bc.aggregates[].name}
Repository 인터페이스 위치: $SRC/{bc.dirName}/domain/
출력 위치: $SRC/{bc.dirName}/application/

규칙:
1. UseCase마다 파일 1개, 클래스 1개
2. 단일 public execute(command: XxxCommand): XxxResult 메서드만 갖는다
3. Command DTO와 Result DTO를 같은 파일 안에 정의한다
4. Repository는 생성자 주입으로 받는다 (의존성 역전)
5. execute 본문은 아래 순서의 주석 스텁으로 채운다:
   // 1. 입력 검증
   // 2. Repository에서 Aggregate 로드
   // 3. 도메인 메서드 호출
   // 4. Repository에 저장
   // 5. 도메인 이벤트 발행 (TODO)
   // 6. Result 반환
6. TODO 주석을 남기되 실제 구현은 하지 않는다

### FILE: {경로}
```$LANG
{코드}
```
```

---

## Step 6 — 인프라 스텁 + 테스트 스텁 생성 [Auto, 병렬]

두 에이전트를 동시에 실행한다.

### 인프라 에이전트

```
아래 Repository 인터페이스의 In-Memory 구현 스텁을 $LANG으로 생성하라.

인터페이스 파일 경로: $SRC/{bc.dirName}/domain/I{Aggregate}Repository$EXT
출력 위치: $SRC/{bc.dirName}/infrastructure/

규칙:
1. 클래스명: {Aggregate}RepositoryImpl
2. 내부에 Map(또는 언어별 동등 자료구조)으로 인메모리 저장소를 갖는다
3. 모든 메서드는 throw new Error('Not implemented') 한 줄만 작성한다
4. 클래스 상단에 // TODO: 실제 영속성 구현으로 교체 주석을 남긴다

### FILE: {경로}
```$LANG
{코드}
```
```

### 테스트 에이전트

```
아래 도메인 클래스에 대한 테스트 스텁을 $LANG의 기본 테스트 프레임워크로 작성하라.
(TypeScript: Jest / Kotlin: JUnit5 / Python: pytest / Go: testing 패키지 / Java: JUnit5)

대상 클래스 목록:
{bc별 Aggregate, Entity, ValueObject 목록}

출력 위치: $TEST/{bc.dirName}/__tests__/ (TypeScript) 또는 언어별 관례

각 클래스에 대해:
1. describe/class 블록 1개
2. "생성 - 유효한 입력으로 생성된다" 케이스 (빈 스텁)
3. businessRules 수만큼 "검증 - {규칙} 위반 시 에러를 던진다" 케이스 (빈 스텁)
4. 구현은 전부 비운다 (TypeScript: it.todo('...'), 기타: 빈 메서드 + // TODO)

### FILE: {경로}
```$LANG
{코드}
```
```

---

## 완료

모든 파일을 Write 도구로 저장한 뒤 아래를 안내한다.

```
스캐폴딩 완료.

생성 파일 요약:
  shared/domain/          기반 클래스 4개
  {bc}/domain/            Aggregate {n}개 · Entity {n}개 · VO {n}개 · Repository 인터페이스 {n}개
  {bc}/application/       UseCase 스텁 {n}개
  {bc}/infrastructure/    Repository 구현 스텁 {n}개
  {bc}/__tests__/         테스트 스텁 {n}개
  ─────────────────────────────────────
  합계: {총 n}개

TODO 항목: 각 파일의 // TODO 주석이 다음 구현 단계의 작업 목록입니다.

다음 단계:
  $PROJECT/tasks/001-<작업명>/request.md 작성 → /spec → /spec-review → 승인 → /test → /impl 로 TODO를 채워나갑니다
  /git-commit           → 스캐폴드 커밋
```
