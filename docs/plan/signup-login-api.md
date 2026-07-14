# Plan — 회원가입·로그인 API (FastAPI)

> 상태: 구현됨 · 2026-07 (스냅샷 — 최신화 안 함)

## 재활용할 기존 코드 (지도 기반)

이 저장소는 애플리케이션 소스 코드가 **0개**인 문서·스킬 기반 "개발 OS"다(`README.md`, `OS.md`, `.claude/skills/*/SKILL.md`, `docs/`). `.py` 파일·`pyproject.toml`·`requirements*.txt`·테스트 러너가 전무하고, FastAPI/JWT/SQLite/DB 관련 코드도 전혀 없다(`find . -name "*.py"` → 0건 확인). 따라서 **재활용할 기존 비즈니스 로직은 없으며, 전부 신규 구현**이다. 재활용 대상은 코드가 아니라 이 OS의 규약·패턴이다.

- **개발 흐름·테스트 필수 원칙 (`OS.md` 원칙 3 / §2.③ / `CLAUDE.md` 규칙 3)**: 구현에 단위/통합 테스트 필수, 사람 검토 게이트 통과 전 구현 금지. 이 Plan은 ② 설계 산출물이며 구현은 범위 밖.
- **개인 데이터·gitignore 패턴 (`.gitignore`, `skill-usage.log`)**: 비밀(JWT 시크릿)과 로컬 DB 파일은 절대 커밋하지 않는다 — `.gitignore`에 `.db`/`.env` 추가로 동일 정책 적용.
- **컨벤션 (`OS.md` §6)**: 한국어 출력/문서, 커밋 접두사(`feat : `), 커밋 서명. 산출물 메시지·docstring·에러 안내를 한국어로.
- **검증된 라이브러리 활용 (PRD 재활용 지도)**: "기존 코드 재활용"이 없으므로 표준 라이브러리를 적극 채택 — `FastAPI 0.111.1`, `pydantic v2`(FastAPI 0.111 동봉), `SQLAlchemy 2.x`(ORM), `python-jose[cryptography]`(JWT/HS256), 표준 라이브러리 `hashlib`(SHA-512)·`secrets`(솔트). 테스트는 `pytest` + FastAPI `TestClient`(httpx 기반).

## 직접 구현이 필요한 부분

전부 신규다.

- **프로젝트 골격**: `pyproject.toml`(의존성·Python 3.12 핀), 패키지 디렉토리, 설정 로딩(환경변수).
- **DB 계층**: SQLAlchemy 엔진/세션, `users` 테이블 모델(SQLite), 테이블 자동 생성.
- **보안 로직**: 솔트 생성(`secrets.token_hex`), SHA-512 해싱·검증(`hashlib`), JWT 발급·만료(HS256, `python-jose`).
- **검증 로직**: username(≤20자·공백불가·trim 후 중복판정), password(소문자+숫자 포함·8자 이상) — Pydantic validator.
- **라우트**: `POST /signup`, `POST /login` + 에러코드 매핑(`DUPLICATE_USERNAME` 409, `INVALID_CREDENTIALS` 401, 검증 400/422).
- **에러 응답 규격**: 모든 실패 응답에 `errorCode` 필드를 싣는 공통 예외 핸들러(422 Pydantic 기본 응답도 `errorCode`로 정규화).

## 확정 사항 (설계 단계에서 정할 것)

**성공 응답 바디 스키마 (확정):**

- `POST /signup` → **201 Created**
  ```json
  { "userId": 1, "username": "alice", "name": "앨리스" }
  ```
  (비밀번호/솔트/해시는 절대 응답하지 않음. `userId`는 DB PK.)

- `POST /login` → **200 OK**
  ```json
  { "accessToken": "<jwt>", "tokenType": "bearer", "expiresIn": 3600 }
  ```
  (`expiresIn`은 초 단위 = 60분 = 3600. JWT payload는 `{ "sub": "<user_id>", "exp": <unix> }` — PRD "payload=user_id만" 준수, `sub`에 user_id 문자열.)

**실패 응답 바디 스키마 (확정, 전 엔드포인트 공통):**
```json
{ "errorCode": "INVALID_CREDENTIALS", "message": "아이디 또는 비밀번호가 올바르지 않습니다." }
```
errorCode 값: `DUPLICATE_USERNAME`(409), `INVALID_CREDENTIALS`(401), `VALIDATION_ERROR`(400/422).

**솔트·해시 저장 형태 (확정):**

- `users` 테이블 컬럼:
  | 컬럼 | 타입 | 비고 |
  |---|---|---|
  | `id` | INTEGER PK AUTOINCREMENT | user_id |
  | `username` | TEXT NOT NULL UNIQUE | trim 후 저장, 대소문자 구분 |
  | `name` | TEXT NOT NULL | |
  | `password_hash` | TEXT NOT NULL | SHA-512 hex digest (128자) |
  | `salt` | TEXT NOT NULL | **별도 컬럼**(PRD 명시) |
  | `created_at` | TEXT NOT NULL | ISO8601 UTC |

- **솔트 길이: 32바이트** = `secrets.token_hex(32)` → **64자 hex 문자열**로 저장(충분한 엔트로피, 가독·이식성 위해 hex).
- **해시 계산**: `hashlib.sha512((salt + password).encode("utf-8")).hexdigest()` → 128자 hex. 검증 시 동일 방식 재계산 후 `secrets.compare_digest`로 상수시간 비교.
- `username` UNIQUE 제약은 DB 레벨 안전망(대소문자 구분이므로 SQLite 기본 BINARY collation과 정합). 애플리케이션 레벨에서 trim 후 조회로 1차 판정.

## 아키텍처 (레이어 구조) — ★개정★

요청 흐름을 레이어로 분리한다. 의존 방향은 위→아래 한 방향(아래 층은 위 층을 모른다):

```
Controller(HTTP)  →  Service(비즈니스 로직)  →  Repository(DB 접근)  →  Model(ORM)
                          ↘ Security(해싱·토큰) · Schema(검증·DTO) 는 보조로 사용
```

- **Controller** (`controllers/auth_controller.py`): 라우터. HTTP 요청/응답만. 요청 스키마로 받아 service 호출, 결과를 응답 스키마로 변환. 비즈니스 로직·DB 접근 없음.
- **Service** (`services/auth_service.py`): 가입/로그인 규칙. repository로 사용자 조회·저장, security로 해싱·토큰. 도메인 예외(AppError) 발생.
- **Repository** (`repositories/user_repository.py`): DB 접근만. username 조회/저장. SQLAlchemy 세션은 여기서만 다룬다.
- **Model** (`models/user.py`): ORM 엔티티.
- **Schema** (`schemas/auth.py`): Pydantic 요청/응답 DTO + validator.
- **Security** (`security/password.py`, `security/token.py`): FastAPI·DB와 무관한 순수 함수(해싱·JWT). 단위 테스트가 쉽다.

원칙: 각 층은 한 가지 책임만(Controller는 HTTP만, Repository는 DB만). 동작이 기준이므로 이 구조 변경은 **기존 23개 테스트를 깨지 않는 리팩터링**이다(테스트가 안전망).

## 손댈 파일 (신규/수정 — 디렉토리 구조 포함)

```
my-claude-code-os/
├── app/
│   ├── __init__.py
│   ├── main.py                      앱 조립(라우터/핸들러 등록, lifespan으로 DB 테이블 생성)
│   ├── config.py                    환경변수 설정(JWT_SECRET, 만료, 알고리즘, DB_URL)
│   ├── database.py                  SQLAlchemy engine/SessionLocal/Base, get_db
│   ├── errors.py                    AppError + errorCode 핸들러(422 정규화)
│   ├── controllers/                 [Controller] HTTP 입출력만
│   │   ├── __init__.py
│   │   └── auth_controller.py       POST /signup, /login — service 호출·응답 변환
│   ├── services/                    [Service] 비즈니스 로직
│   │   ├── __init__.py
│   │   └── auth_service.py          가입/로그인 규칙(repository+security 사용)
│   ├── repositories/                [Repository] DB 접근만
│   │   ├── __init__.py
│   │   └── user_repository.py       User 조회(by username)/저장
│   ├── models/                      [Model] ORM 엔티티
│   │   ├── __init__.py
│   │   └── user.py                  User 테이블
│   ├── schemas/                     [Schema] Pydantic DTO
│   │   ├── __init__.py
│   │   └── auth.py                  Signup/Login 요청·응답·Error + validator
│   └── security/                    [Security] 순수 보안 함수
│       ├── __init__.py
│       ├── password.py              make_salt/hash_password/verify_password
│       └── token.py                 create_access_token(HS256, sub=user_id, 60m)
├── tests/
│   ├── __init__.py                  [신규]
│   ├── conftest.py                  [신규] 임시 SQLite(인메모리/임시파일) + TestClient 픽스처, 테스트용 JWT_SECRET 주입
│   ├── test_security.py             [신규] 단위: 솔트/해시/검증/토큰
│   ├── test_schemas.py              [신규] 단위: username/password validator
│   ├── test_signup.py              [신규] 통합: /signup 성공·중복·검증실패
│   └── test_login.py               [신규] 통합: /login 성공·실패(아이디없음/비번불일치 동일응답)
├── pyproject.toml                   [신규] 의존성·python 3.12·pytest 설정
├── .env.example                     [신규] JWT_SECRET 등 예시(실제 .env는 gitignore)
├── .gitignore                       [수정] *.db, .env 추가
├── docs/plan/signup-login-api.md    [신규] 이 Plan 문서
└── OS.md                            [수정] §4 도구/예시 표에 "이 OS 흐름으로 만든 첫 백엔드 기능" 한 줄 추가(원칙 5: 청사진과 어긋나면 함께 갱신)
```

레이어 분리·의존 방향은 위 "아키텍처 (레이어 구조)" 절 참조. 단방향 의존이라 각 층을 독립적으로 테스트·교체할 수 있다. 기존 평면 구조(models.py/schemas.py/security.py/routers/auth.py)에 있던 로직을 controller/service/repository로 재배치하는 **리팩터링**이며, 기존 테스트는 import 경로만 갱신하고 동작 단언은 그대로 둔다.

## 구현 단계 (순서대로)

1. **골격·의존성**: `pyproject.toml`(fastapi==0.111.1, sqlalchemy, python-jose[cryptography], uvicorn, pytest, httpx), `.gitignore` 수정, `.env.example` 작성, `app/config.py`로 환경변수 로딩(`JWT_SECRET` 없으면 기동 실패시켜 하드코딩 방지).
2. **DB 계층**: `database.py`(engine·SessionLocal·Base·get_db), `models.py`(User). `main.py` startup에서 `Base.metadata.create_all`.
3. **보안 로직 + 단위 테스트(나란히)**: `security.py`의 `make_salt`(token_hex(32)), `hash_password`, `verify_password`(compare_digest), `create_access_token`(sub=user_id, exp=now+60m). → `test_security.py`.
4. **스키마·검증 + 단위 테스트(나란히)**: `schemas.py` validator(username: trim·≤20·공백불가, password: 소문자+숫자 정규식·≥8). 성공/실패 응답 모델. → `test_schemas.py`.
5. **에러 규격**: `errors.py`에 `AppError(error_code,status,message)` + FastAPI 핸들러, `RequestValidationError` 핸들러를 `errorCode:"VALIDATION_ERROR"` 형태로 정규화.
6. **라우트**: `routers/auth.py`. `/signup`: 검증→trim username 중복조회→있으면 `DUPLICATE_USERNAME`(409), 없으면 salt/hash 생성·저장→201 바디. `/login`: username 조회→없거나 verify 실패면 **동일하게** `INVALID_CREDENTIALS`(401), 성공 시 토큰 200.
7. **앱 조립**: `main.py`에서 라우터·핸들러 등록.
8. **통합 테스트**: `conftest.py`(임시 DB·테스트 시크릿·TestClient), `test_signup.py`/`test_login.py`.
9. **문서/설정 마무리**: `OS.md` 표 갱신, `docs/plan/signup-login-api.md` 반영.
10. **수동 검증**: `uvicorn app.main:app`로 기동, `/signup`→`/login`→토큰 디코드로 payload(sub=user_id)·만료 확인. (검토 게이트 통과 후 구현 진입)

## 테스트 전략 (단위/통합 — 필수)

러너: **pytest** + FastAPI **TestClient**(httpx). DB는 픽스처로 **임시 SQLite**(파일 또는 인메모리 `StaticPool`)를 매 테스트 격리, `JWT_SECRET`은 테스트 전용 값 주입. 실제 `.db`/`.env` 미사용(파일 미변경·격리).

**단위 테스트**

- `test_security.py`:
  - `make_salt()` 매 호출 서로 다름, 길이 64(hex).
  - 같은 (pw, salt) → 동일 해시; 다른 salt → 다른 해시(솔트 효과).
  - `verify_password` 정답 True / 오답 False.
  - `create_access_token(user_id)` 디코드 시 `sub == str(user_id)`, `exp`가 ~60분 후, 잘못된 시크릿으로 디코드 실패.
- `test_schemas.py`:
  - username: 21자 거부, 공백 포함 거부, `" abc "`→`"abc"` trim, `Abc`≠`abc`(대소문자 구분 유지).
  - password: 8자 미만 거부, 소문자 없음 거부, 숫자 없음 거부, `"abcd1234"` 통과.

**통합 테스트**

- `test_signup.py`:
  - 정상 가입 → 201 + `{userId,username,name}`, 비밀번호/솔트 미노출.
  - 동일 username 재가입 → 409 + `errorCode:"DUPLICATE_USERNAME"`.
  - trim 후 동일(`" alice "` vs `"alice"`) → 409.
  - 대소문자 다름(`Alice` vs `alice`) → 둘 다 가입 성공(구분).
  - 비번 규칙 위반·username 21자 → 422(또는 400) + `errorCode:"VALIDATION_ERROR"`.
- `test_login.py`:
  - 가입 후 정상 로그인 → 200 + `accessToken` 디코드 시 `sub`=해당 userId, `expiresIn:3600`.
  - 없는 아이디 → 401 + `INVALID_CREDENTIALS`.
  - 틀린 비번 → 401 + `INVALID_CREDENTIALS` (없는 아이디와 **응답 바디·상태 동일**임을 단언).

## 위험 요소 / 롤백

- **런타임 도입의 정합성**: 지금까지 순수 문서/Bash OS였는데 Python/FastAPI 소스가 처음 들어온다. 완화 — 모든 신규 코드는 `app/`·`tests/`에 격리, OS 흐름(이 Plan→검토→구현)을 그대로 따르고 `OS.md`에 "첫 백엔드 기능 예시"로 명기(원칙 5).
- **시크릿 노출**: `JWT_SECRET`·로컬 `.db` 커밋 사고. 완화 — `.gitignore`에 `.env`/`*.db` **1단계에서 선반영**, `config.py`가 시크릿 없으면 기동 실패(하드코딩 금지 PRD 준수), `.env.example`만 커밋.
- **약한 해시(수용된 잔여 리스크)**: SHA-512는 빠른 해시라 솔트가 있어도 대량 대입에 취약. PRD가 명시 수용. 완화/후속 — security 계층을 함수로 분리해 추후 bcrypt/Argon2 교체 시 `hash_password`/`verify_password`만 교체 가능하게 설계.
- **검증 상태코드 400 vs 422**: Pydantic 기본은 422. PRD가 둘 다 허용하므로 422를 채택하되 핸들러로 `errorCode`를 반드시 싣고, 테스트는 `status in (400,422)`로 유연 단언.
- **로그인 실패 정보 누출**: 아이디없음/비번불일치를 코드 분기상으로도 동일 경로·동일 응답으로 처리(타이밍까지 엄밀히 맞추진 않음 — 범위 밖). 테스트에서 응답 동일성 단언.
- **DB 동시성**: SQLite 단일 파일·학습용이라 동시성 락 미고려(범위 밖). UNIQUE 제약으로 중복 가입 경합만 DB 레벨 방어.
- **롤백**: 전부 신규 파일이라 영향 격리. 되돌리려면 `app/`·`tests/`·`pyproject.toml`·`.env.example` 삭제, `.gitignore`/`OS.md` 추가분만 되돌리면 됨. 기존 스킬·훅·문서에 파괴적 수정 없음.
