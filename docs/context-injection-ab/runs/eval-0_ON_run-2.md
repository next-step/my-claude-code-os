# 비밀번호 변경 — 실패 처리 스케치

현재 비밀번호가 틀렸을 때를 중심으로. 레이어는 컨벤션 카드대로 `controller → service → repository → security`,
실패는 도메인 예외 `AppError` 팩토리로 던지고, 응답 바디는 `{ "errorCode", "message" }` 로 정규화한다.

## 1) errors.py — 실패 표현(팩토리 + 핸들러)

```python
# app/errors.py
"""도메인 실패를 AppError로 표현하고, 응답 바디를 통일 형식으로 정규화한다."""

class AppError(Exception):
    """도메인 규칙 위반. HTTP·프레임워크를 모른 채 error_code/status_code/message만 안다."""
    def __init__(self, error_code: str, status_code: int, message: str):
        self.error_code = error_code
        self.status_code = status_code
        self.message = message


def invalid_current_password_error() -> AppError:
    """현재 비밀번호 불일치. 보안상 원인을 세분화하지 않고 401로 통일."""
    return AppError("INVALID_CURRENT_PASSWORD", 401, "현재 비밀번호가 올바르지 않습니다.")


# main.py 에 등록되는 핸들러 — 모든 실패 바디를 한 형식으로.
async def app_error_handler(_request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"errorCode": exc.error_code, "message": exc.message},
    )
```

## 2) service — 도메인 규칙(여기서 실패를 던진다)

```python
# app/services/auth_service.py
"""비밀번호 변경 도메인 규칙. repository·security를 조합하고 위반 시 AppError를 던진다."""

class AuthService:
    def __init__(self, users: UserRepository):
        self.users = users

    def change_password(self, user_id: int, current_pw: str, new_pw: str) -> None:
        user = self.users.get_by_id(user_id)
        # 현재 비밀번호 검증 — security의 해시 비교. 틀리면 도메인 예외.
        if not verify_password(current_pw, user.password_hash):
            raise invalid_current_password_error()
        user.password_hash = hash_password(new_pw)  # security: 새 salt로 재해싱
        self.users.save(user)
```

## 3) controller — HTTP 변환만(로직·DB 없음)

```python
# app/controllers/auth_controller.py
"""비밀번호 변경 엔드포인트. 성공 시 204, 실패는 핸들러가 바디로 변환."""

@router.patch("/me/password", status_code=204)
def change_password(
    body: ChangePasswordRequest,                 # schema: trim·필드 검증(실패 시 422)
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    service.change_password(current_user.id, body.current_password, body.new_password)
    return Response(status_code=204)
```

## 실패 응답(현재 비밀번호 틀림)

```
HTTP/1.1 401 Unauthorized
{ "errorCode": "INVALID_CURRENT_PASSWORD", "message": "현재 비밀번호가 올바르지 않습니다." }
```

- 입력 형식 오류(빈 값·짧은 새 비번)는 Pydantic이 `422 / errorCode: "VALIDATION_ERROR"` 로 정규화.
- 언어: 사용자 노출 message는 한국어, docstring도 한국어 한 줄.
```
```
