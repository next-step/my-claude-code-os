# 회원가입 아이디 중복 실패 처리 (스케치)

- **언어/스택**: Python (FastAPI + Pydantic + SQLAlchemy)
- **판정 레이어**: `service` — 도메인 규칙 위반이므로 여기서 `AppError`를 던진다. controller는 HTTP 변환만, repository는 DB 접근만.
- **실패 표현**: 도메인 예외 `AppError(error_code, status_code, message)` — 팩토리 `duplicate_username_error()`.
- **응답 바디**: `{ "errorCode": ..., "message": ... }` (errors 핸들러가 변환).
- **상태코드**: `409 DUPLICATE_USERNAME`.
- **이중 방어**: 1차 조회(`get_by_username`) + 2차 DB UNIQUE 제약(`IntegrityError`) → rollback 후 같은 도메인 예외로 정규화(동시성 최종 방어).

```python
# app/errors.py — 실패의 단일 표현
class AppError(Exception):
    """도메인 실패를 error_code·status·message로 담는 예외."""
    def __init__(self, error_code: str, status_code: int, message: str):
        self.error_code = error_code
        self.status_code = status_code
        self.message = message

def duplicate_username_error() -> AppError:
    """아이디 중복 실패 — 409로 정규화."""
    return AppError("DUPLICATE_USERNAME", 409, "이미 사용 중인 아이디입니다.")


# app/services/auth_service.py — 도메인 규칙(중복 판정)이 사는 곳
class AuthService:
    def __init__(self, repo, hasher):
        self.repo = repo
        self.hasher = hasher

    def sign_up(self, username: str, password: str):
        """회원가입 — 아이디 중복이면 도메인 예외를 던진다(HTTP 무관)."""
        # 1차 방어: 조회로 선제 차단
        if self.repo.get_by_username(username):
            raise duplicate_username_error()

        user = User(
            username=username,
            password_hash=self.hasher.hash(password),  # security 레이어에 위임
            created_at=datetime.now(timezone.utc).isoformat(),  # UTC ISO 8601
        )
        try:
            return self.repo.create(user)
        except IntegrityError:
            # 2차 방어: 동시 요청이 UNIQUE 제약에 걸린 경우 → 같은 실패로 정규화
            self.repo.rollback()
            raise duplicate_username_error()


# app/controllers/auth_controller.py — HTTP 변환만(비즈니스 로직 없음)
@router.post("/signup")
def signup(body: SignUpRequest, service: AuthService = Depends(get_auth_service)):
    """가입 요청을 service에 위임. 성공만 다루고 실패는 AppError 핸들러가 처리."""
    user = service.sign_up(body.username, body.password)
    return {"id": user.id, "username": user.username}


# app/errors.py — 모든 실패 응답을 통일된 바디로 변환
@app.exception_handler(AppError)
def handle_app_error(request, exc: AppError):
    """AppError → { errorCode, message } + status_code 로 정규화."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"errorCode": exc.error_code, "message": exc.message},
    )
```

**중복 시 응답 예**

```
HTTP/1.1 409 Conflict
{ "errorCode": "DUPLICATE_USERNAME", "message": "이미 사용 중인 아이디입니다." }
```

> 테스트(구현의 일부): service 단위 테스트(1차 조회 차단 + IntegrityError 정규화)와 `POST /signup` 통합 테스트(409·바디 형식)를 나란히 둔다.
