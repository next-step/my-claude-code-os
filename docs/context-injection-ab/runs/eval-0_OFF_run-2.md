# 비밀번호 변경 — 실패 처리 스케치 (현재 비밀번호 불일치 중심)

**설계 요약**
- **레이어 구분**: 실패는 *서비스 레이어*에서 도메인 예외로 표현하고, *라우터 레이어*에서 HTTP로 변환한다.
- **실패 표현**: 도메인 예외 클래스(`InvalidCurrentPassword`)를 던진다. 서비스는 HTTP를 모른다.
- **HTTP 응답**: 상태코드 `400 Bad Request`, 바디는 `{"detail": {"code": ..., "message": ...}}` 형태.
- **언어**: 사용자 노출 메시지는 영어(범용). `code`는 클라이언트 분기용 안정 키.

```python
# ---------- domain/exceptions.py ----------
class AuthError(Exception):
    """인증/자격증명 관련 도메인 에러의 베이스."""
    code = "auth_error"
    message = "Authentication error."


class InvalidCurrentPassword(AuthError):
    code = "invalid_current_password"
    message = "The current password is incorrect."


# ---------- services/user_service.py ----------
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def change_password(db, user, current_password: str, new_password: str) -> None:
    # 핵심: 현재 비밀번호가 저장된 해시와 일치하지 않으면 도메인 예외.
    if not pwd_context.verify(current_password, user.hashed_password):
        raise InvalidCurrentPassword()

    user.hashed_password = pwd_context.hash(new_password)
    db.add(user)
    db.commit()


# ---------- schemas.py ----------
from pydantic import BaseModel, Field


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


# ---------- routers/users.py ----------
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(
    payload: ChangePasswordRequest,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        change_password(db, user, payload.current_password, payload.new_password)
    except InvalidCurrentPassword as exc:
        # 도메인 예외 → HTTP 400 으로 변환. 바디는 code + message.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": exc.message},
        )
    return  # 204: 성공 시 바디 없음


# ---------- (선택) 전역 핸들러로 변환을 한곳에 모으는 대안 ----------
# from fastapi import Request
# from fastapi.responses import JSONResponse
#
# @app.exception_handler(AuthError)
# async def auth_error_handler(request: Request, exc: AuthError):
#     return JSONResponse(
#         status_code=status.HTTP_400_BAD_REQUEST,
#         content={"detail": {"code": exc.code, "message": exc.message}},
#     )
```

**실패 응답 예시 (400)**
```json
{
  "detail": {
    "code": "invalid_current_password",
    "message": "The current password is incorrect."
  }
}
```

**설계 노트**
- `401` 대신 `400`을 선택: 사용자는 이미 인증된 상태(로그인됨)이며, 문제는 요청 바디의 값(현재 비밀번호)이 잘못된 것이므로 "잘못된 요청"이 의미상 더 정확. (조직에 따라 422/401도 가능.)
- 잘못된 비밀번호와 존재하지 않는 계정을 구분해 노출하지 않도록, 여기서는 이미 인증된 `user`만 다뤄 열거 공격 표면을 줄임.
