# 로그인 실패 처리 스케치 (FastAPI · 레이어 분리)

컨벤션 준수: 실패는 `AppError`로, 응답 바디는 `{errorCode, message}`,
보안상 "아이디 없음"과 "비밀번호 불일치"를 **동일하게** `INVALID_CREDENTIALS(401)`.

```python
# app/errors.py — 도메인 예외 + 팩토리
class AppError(Exception):
    """도메인 실패를 error_code·status_code·message로 표준화해 던진다."""
    def __init__(self, error_code: str, status_code: int, message: str):
        self.error_code = error_code
        self.status_code = status_code
        self.message = message


def invalid_credentials_error() -> AppError:
    """로그인 실패를 원인 구분 없이 하나로 — 계정 존재 여부 노출 차단."""
    # 메시지도 뭉뚱그린다: "아이디/비밀번호가 올바르지 않습니다"
    return AppError("INVALID_CREDENTIALS", 401, "아이디 또는 비밀번호가 올바르지 않습니다.")


# app/security/password.py — 해시 검증
def verify_password(plain: str, password_hash: str | None) -> bool:
    """평문 비밀번호를 해시와 대조한다(느린 해시·상수시간 비교)."""
    # 유저가 없어도 더미 해시로 반드시 1회 검증 → 타이밍 차이로 계정 유무 추론 방지
    return _hasher.verify(plain, password_hash or _DUMMY_HASH)


# app/services/auth_service.py — 도메인 규칙 (HTTP 모름)
class AuthService:
    def __init__(self, users: "UserRepository", tokens: "TokenIssuer"):
        self._users = users
        self._tokens = tokens

    def login(self, username: str, password: str) -> str:
        """자격 증명 확인 후 토큰 발급. 실패는 원인 무관하게 동일 예외."""
        user = self._users.get_by_username(username)  # 없으면 None

        # 유저가 없어도 verify를 건너뛰지 않는다(타이밍 공격 완화)
        ok = verify_password(password, user.password_hash if user else None)
        if user is None or not ok:
            # 로그로만 원인 남기고(운영 관측), 응답으로는 구분 안 함
            log.info("login_failed username=%s reason=%s",
                     username, "no_user" if user is None else "bad_password")
            raise invalid_credentials_error()

        return self._tokens.issue(user.id)


# app/controllers/auth_controller.py — HTTP 변환만
@router.post("/login")
def login(body: LoginRequest, svc: AuthService = Depends(get_auth_service)):
    """로그인 요청→토큰. 실패 예외는 errors.py 핸들러가 바디로 정규화."""
    token = svc.login(body.username, body.password)
    return {"accessToken": token}
    # AppError 발생 시 등록된 예외 핸들러가
    #   status=401, body={"errorCode": "INVALID_CREDENTIALS", "message": ...}
    # Pydantic 검증 실패는 자동으로 422 / errorCode="VALIDATION_ERROR"
```

## 보안 관점 요약
- **원인 미구분**: 아이디 없음 == 비밀번호 틀림 → `INVALID_CREDENTIALS(401)`. 계정 열거(enumeration) 차단.
- **타이밍 방어**: 유저 부재 시에도 더미 해시로 검증 1회 수행 → 응답 시간으로 계정 유무 추론 불가.
- **상수시간 비교 + 느린 해시**(bcrypt/argon2)로 해시 대조.
- **관측성 분리**: 실제 원인(no_user/bad_password)은 서버 로그에만, 클라이언트 응답엔 노출 안 함.
- (권장) 반복 실패 rate-limit / 지수 백오프로 무차별 대입 완화.
```
```
