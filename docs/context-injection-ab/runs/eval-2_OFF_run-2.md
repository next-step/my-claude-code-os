# 로그인 실패 처리 스케치 (FastAPI)

레이어: `router → service → 예외 → 핸들러`. 핵심 보안 원칙은
**"아이디 없음"과 "비밀번호 틀림"을 구별하지 않는다** (사용자 열거 방지) —
둘 다 동일한 `401` + 동일 메시지. 또한 사용자 부재 시에도 더미 해시로
비교를 수행해 **응답 시간을 균일화**(타이밍 공격 방지)한다.

```python
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from passlib.hash import bcrypt

router = APIRouter()

# 실제 사용자가 없을 때도 비교 연산을 태워 응답 시간을 맞추기 위한 더미 해시
_DUMMY_HASH = bcrypt.hash("dummy-password-for-timing-safety")

# 실패 시 클라이언트에 노출하는 단일 메시지 (원인을 구분하지 않음)
_INVALID_CREDENTIALS = "아이디 또는 비밀번호가 올바르지 않습니다."


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthError(Exception):
    """인증 실패를 표현하는 도메인 예외. 내부 로그용 reason만 따로 보관."""
    def __init__(self, reason: str):
        self.reason = reason  # "user_not_found" | "bad_password" — 내부 로깅 전용


class AuthService:
    def __init__(self, repo, logger):
        self.repo = repo
        self.logger = logger

    def authenticate(self, username: str, password: str):
        user = self.repo.find_by_username(username)

        if user is None:
            # 사용자가 없어도 해시 비교를 수행해 타이밍을 균일화
            bcrypt.verify(password, _DUMMY_HASH)
            self.logger.warning("login failed reason=user_not_found user=%s", username)
            raise AuthError("user_not_found")

        if not bcrypt.verify(password, user.password_hash):
            # 내부 로그엔 상세 사유를 남기되, 응답엔 절대 노출하지 않음
            self.logger.warning("login failed reason=bad_password user_id=%s", user.id)
            raise AuthError("bad_password")

        return user


@router.post("/login")
def login(body: LoginRequest, service: AuthService = ...):
    try:
        user = service.authenticate(body.username, body.password)
    except AuthError:
        # 원인(없음/틀림) 구분 없이 동일한 401 + 동일 메시지 → 사용자 열거 차단
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": issue_token(user), "token_type": "bearer"}
```

## 보안 요점
- **401 Unauthorized** 사용 (404/403 아님) — 존재 여부 힌트를 주지 않음.
- 응답 바디는 `{"detail": "아이디 또는 비밀번호가 올바르지 않습니다."}` 하나로 통일.
- 상세 사유(`user_not_found` / `bad_password`)는 **서버 로그에만** 기록.
- 더미 해시 비교로 **타이밍 사이드채널** 완화.
- 추가 권장: 로그인 시도 **레이트리밋 / 계정 잠금**, 무차별 대입 대비.
```
