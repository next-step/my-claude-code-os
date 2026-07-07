# 로그인 실패 처리 스케치 (Python)

레이어: `controller → service → repository → security`, 실패는 도메인 예외 `AppError`로 던지고
`app/errors.py` 핸들러가 `{ "errorCode", "message" }` 바디로 정규화한다.

## 보안 관점 핵심

- **아이디 없음 == 비밀번호 불일치**: 원인을 구분하지 않고 **동일하게** `INVALID_CREDENTIALS(401)`.
  → 계정 존재 여부(user enumeration)를 응답으로 노출하지 않는다.
- 사용자 조회 실패여도 **더미 해시로 검증을 한 번 수행**해 타이밍 차이(존재 여부 측정)를 줄인다.
- 실패 응답에 "왜 틀렸는지" 세부(어느 필드가 없다/틀리다)를 담지 않는다.

## errors.py — 실패 표현 (팩토리)

```python
"""도메인 실패를 표준 예외로 표현한다 — 핸들러가 응답 바디로 정규화."""

class AppError(Exception):
    def __init__(self, error_code: str, status_code: int, message: str):
        self.error_code = error_code
        self.status_code = status_code
        self.message = message


def invalid_credentials_error() -> AppError:
    """아이디 없음·비번 불일치를 구분 없이 하나로 — enumeration 방지."""
    return AppError("INVALID_CREDENTIALS", 401, "아이디 또는 비밀번호가 올바르지 않습니다.")
```

## service — 도메인 규칙 (실패 판단)

```python
"""로그인 도메인 규칙 — 조회·검증을 조합하고 실패 시 도메인 예외를 던진다."""

DUMMY_HASH = "$2b$12$0000000000000000000000000000000000000000000000000000"

class AuthService:
    def __init__(self, users: "UserRepository", security: "Security"):
        self.users = users
        self.security = security

    def login(self, username: str, password: str) -> "User":
        user = self.users.get_by_username(username)  # 없으면 None
        # 타이밍 방어: 유저가 없어도 해시 검증을 동일하게 한 번 수행
        stored_hash = user.password_hash if user else DUMMY_HASH
        ok = self.security.verify_password(password, stored_hash)
        if user is None or not ok:
            raise invalid_credentials_error()  # 두 경우 동일한 401
        return user
```

## controller — HTTP 변환만

```python
"""로그인 엔드포인트 — 요청/응답 변환만, 규칙은 service 위임."""

@router.post("/login")
def login(body: LoginRequest, svc: AuthService = Depends(get_auth_service)):
    user = svc.login(body.username, body.password)  # 실패 시 AppError → 핸들러가 처리
    return {"token": svc.security.issue_token(user)}
```

## 실패 시 응답 (핸들러가 정규화한 결과)

```
HTTP/1.1 401 Unauthorized
{ "errorCode": "INVALID_CREDENTIALS",
  "message": "아이디 또는 비밀번호가 올바르지 않습니다." }
```

- 입력 형식 오류(빈 값 등)는 Pydantic 422 → `errorCode: "VALIDATION_ERROR"`로 별도 정규화.
