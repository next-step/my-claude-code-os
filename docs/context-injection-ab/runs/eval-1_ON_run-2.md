# 회원가입 아이디 중복 실패 처리 스케치

- **언어/스택**: Python (FastAPI + Pydantic + SQLAlchemy)
- **판정 레이어**: `service` (도메인 규칙). controller는 HTTP 변환만, repository는 DB 접근만.
- **실패 표현**: 도메인 예외 `AppError` — 팩토리 `duplicate_username_error()`
- **응답 바디**: `{ "errorCode": ..., "message": ... }` (errors 핸들러가 변환)
- **상태코드**: `409 DUPLICATE_USERNAME`
- **이중 방어**: 1차 조회 + 2차 DB UNIQUE 제약(`IntegrityError`) 정규화

```python
# app/errors.py — 실패는 AppError로만 던지고, 핸들러가 바디를 통일한다
class AppError(Exception):
    """도메인 실패를 표현: error_code·status_code·message를 담는다."""
    def __init__(self, error_code: str, status_code: int, message: str):
        self.error_code, self.status_code, self.message = error_code, status_code, message

def duplicate_username_error() -> AppError:
    """아이디 중복: 이미 사용 중인 username."""
    return AppError("DUPLICATE_USERNAME", 409, "이미 사용 중인 아이디입니다.")

async def app_error_handler(_req, exc: AppError):  # 전역 등록
    # 모든 실패 응답 바디를 { errorCode, message } 로 통일
    return JSONResponse(status_code=exc.status_code,
                        content={"errorCode": exc.error_code, "message": exc.message})


# app/services/auth_service.py — 도메인 규칙 판정 지점 (프레임워크/HTTP 모름)
class AuthService:
    def __init__(self, users: UserRepository, security: Security):
        self.users, self.security = users, security

    def sign_up(self, data: SignUpIn) -> User:
        """회원가입: 아이디 중복을 막고 비밀번호를 해싱해 생성한다."""
        # 1차 방어: 사전 조회로 중복이면 도메인 예외
        if self.users.get_by_username(data.username) is not None:
            raise duplicate_username_error()
        pw_hash = self.security.hash_password(data.password)
        try:
            return self.users.create(username=data.username, password_hash=pw_hash)
        except IntegrityError:
            # 2차(최종) 방어: 동시 요청으로 UNIQUE 위반 → rollback 후 정규화
            self.users.rollback()
            raise duplicate_username_error()


# app/controllers/auth_controller.py — HTTP 변환만, 규칙은 service에 위임
@router.post("/signup", status_code=201)
def signup(body: SignUpIn, svc: AuthService = Depends(get_auth_service)):
    """POST /signup: 요청→service 위임→응답. 실패는 AppError가 핸들러로."""
    user = svc.sign_up(body)          # 중복이면 여기서 AppError(409) 전파
    return {"id": user.id, "username": user.username}


# tests/test_signup.py — 새 동작엔 테스트를 나란히
def test_signup_duplicate_returns_409(client, existing_user):
    res = client.post("/signup", json={"username": existing_user.username, "password": "pw123456"})
    assert res.status_code == 409
    assert res.json() == {"errorCode": "DUPLICATE_USERNAME",
                          "message": "이미 사용 중인 아이디입니다."}
```
