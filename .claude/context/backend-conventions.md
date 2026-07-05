# 백엔드 컨벤션 (app/ · tests/)

> 이 파일은 `app/`·`tests/` 코드를 만지는 순간 **자동 주입**되는 규칙 카드다.
> 스킬을 안 돌리고 맨손으로 코드를 고칠 때도, 격리된 서브에이전트가 코드를 볼 때도 이 규칙이 따라온다.
> 규칙은 여기 한 곳에만 둔다(단일 출처). 실제 예시는 `app/` 코드가 원본.

## 레이어 (책임 분리 — 위→아래로만 의존)

```
controller → service → repository → model
                    ↘ security (해싱·토큰)
schema(입출력 검증) · errors(예외·정규화) 는 가로로 공유
```

- **controller** (`app/controllers/`): HTTP 요청/응답 변환만. 비즈니스 로직·DB 접근 금지 → service에 위임.
  라우터 의존성으로 service를 **요청 단위 조립**(`Depends`).
- **service** (`app/services/`): 도메인 규칙 수행. repository·security를 조합하고, 규칙 위반 시 **도메인 예외(`AppError`)** 를 던진다. HTTP·프레임워크 세부를 몰라야 한다.
- **repository** (`app/repositories/`): DB 접근만(`get_by_username`, `create`, `rollback` …). 도메인 규칙 판단 안 함.
- **model** (`app/models/`) · **schema** (`app/schemas/`): ORM 모델 / Pydantic 입출력. 입력 정제(trim 등)는 schema validator에서.
- **security** (`app/security/`): 비밀번호 해싱·salt·토큰 발급. service가 호출.

## 에러 처리 (반드시 지킬 것)

- 실패는 **`AppError(error_code, status_code, message)`** 로 던진다. 팩토리 함수로 생성:
  예) `duplicate_username_error()` → `("DUPLICATE_USERNAME", 409, …)`.
- 모든 실패 응답 바디는 **`{ "errorCode": ..., "message": ... }`** 로 통일(`app/errors.py`의 핸들러가 변환).
- Pydantic 검증 실패(422)도 `errorCode: "VALIDATION_ERROR"` 로 정규화.
- **보안: 실패 원인을 과도하게 구분하지 않는다.** 로그인은 "아이디 없음"과 "비밀번호 불일치"를 **동일하게** `INVALID_CREDENTIALS(401)` 로 처리.

## 관례

- **한국어 docstring** — 모듈·함수 첫 줄에 "무엇을/왜"를 한 줄로.
- **snake_case**, 파일명은 레이어별 디렉토리 아래 도메인 이름(`auth_controller.py`, `user_repository.py`).
- **시각은 UTC ISO 8601** (`datetime.now(timezone.utc).isoformat()`).
- **동시성 최종 방어**: DB UNIQUE 위반(`IntegrityError`)은 rollback 후 도메인 예외로 정규화(1차 조회 + 2차 제약 이중 방어).

## 테스트 (OS 원칙 3 — 구현의 일부)

- 러너: `pytest`. 위치 `tests/`. 새 동작을 넣으면 **테스트를 나란히** 추가한다(테스트 없는 구현 = 미완료).
- 레이어 단위 테스트(`test_security`·`test_schemas`) + 엔드포인트 통합 테스트(`test_signup`·`test_login`)를 함께 둔다. 공용 픽스처는 `conftest.py`.

> 흐름·게이트 등 개발 전반 규칙은 [flow-rules.md](./flow-rules.md) 참조.
