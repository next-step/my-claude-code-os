# 로그인 실패 처리 스케치 (FastAPI)

레이어: 라우터(HTTP) → 서비스(인증 로직) → 리포지토리(DB 조회).
실패 표현: 도메인 예외(`AuthError`)로 통일 → 라우터에서 HTTP로 변환.
핵심 보안 원칙: **아이디 없음 / 비밀번호 틀림을 구분하지 않는다**(사용자 열거 방지),
타이밍 공격 방지를 위해 유저가 없어도 더미 해시로 검증을 수행한다.

```python
# domain/errors.py -------------------------------------------------
class AuthError(Exception):
    """인증 실패. 원인은 로그로만 남기고 클라이언트에는 노출하지 않는다."""


# service/auth_service.py ------------------------------------------
import logging
from passlib.context import CryptContext

logger = logging.getLogger("auth")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 유저가 없을 때도 동일한 시간이 걸리도록 미리 만든 더미 해시
_DUMMY_HASH = pwd_context.hash("dummy-password-for-timing")


class AuthService:
    def __init__(self, users_repo):
        self.users_repo = users_repo

    def authenticate(self, username: str, password: str):
        user = self.users_repo.get_by_username(username)

        if user is None:
            # 타이밍 공격 방지: 존재하지 않아도 해시 비교를 수행
            pwd_context.verify(password, _DUMMY_HASH)
            logger.info("login_failed reason=user_not_found username=%s", username)
            raise AuthError()  # 아이디 없음 → 동일한 실패로 취급

        if not pwd_context.verify(password, user.password_hash):
            logger.info("login_failed reason=bad_password user_id=%s", user.id)
            raise AuthError()  # 비밀번호 틀림 → 동일한 실패로 취급

        return user


# api/routes/auth.py ------------------------------------------------
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, service: AuthService = Depends(get_auth_service)):
    try:
        user = service.authenticate(body.username, body.password)
    except AuthError:
        # 상태코드 401, 바디는 원인 불문 동일 메시지 (열거 방지)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=issue_token(user))
```

## 요점

- **상태코드**: 인증 실패는 항상 `401 Unauthorized`. (아이디 없음도 404 아님 — 존재 여부 노출 금지)
- **응답 바디**: 두 실패 케이스 모두 완전히 동일한 `detail`. 어떤 필드가 틀렸는지 알려주지 않는다.
- **로그**: 실제 원인(`user_not_found` / `bad_password`)은 서버 로그에만. 비밀번호 원문은 절대 로깅하지 않는다.
- **타이밍**: 유저 부재 시에도 더미 해시 검증으로 응답 시간을 균일화.
- **추가 방어(권장)**: 로그인 시도 rate limit / 계정 잠금, 실패 카운트, 감사 로그.
