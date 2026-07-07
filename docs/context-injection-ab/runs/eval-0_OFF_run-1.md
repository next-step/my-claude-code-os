# 비밀번호 변경 — 실패 처리 스케치 (현재 비밀번호 불일치 중심)

- **레이어**: 서비스 레이어에서 도메인 예외(`InvalidCurrentPasswordError`)를 raise → 라우터에서 `HTTPException`으로 변환.
- **실패 표현**: 도메인 예외 클래스 + FastAPI `HTTPException`.
- **상태코드**: 현재 비밀번호 틀림 → `400 Bad Request` (인증은 됐으나 입력값 검증 실패).
- **응답 바디**: FastAPI 기본 형식 `{"detail": "..."}`.
- **언어**: 메시지는 영어.

```python
# ---- domain/errors.py -----------------------------------------------------
class PasswordChangeError(Exception):
    """비밀번호 변경 관련 도메인 실패의 베이스."""


class InvalidCurrentPasswordError(PasswordChangeError):
    """제출한 현재 비밀번호가 저장된 해시와 일치하지 않음."""


# ---- schemas.py -----------------------------------------------------------
from pydantic import BaseModel, Field


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


# ---- services/user_service.py --------------------------------------------
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def change_password(db, user, current_password: str, new_password: str) -> None:
    # 1) 현재 비밀번호 검증 — 실패 시 도메인 예외
    if not pwd_context.verify(current_password, user.hashed_password):
        raise InvalidCurrentPasswordError()

    # 2) 통과 시에만 새 해시 저장
    user.hashed_password = pwd_context.hash(new_password)
    db.add(user)
    db.commit()


# ---- routers/users.py -----------------------------------------------------
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(
    payload: ChangePasswordRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),  # 인증(JWT/세션)으로 로그인 보장
):
    try:
        change_password(
            db,
            current_user,
            payload.current_password,
            payload.new_password,
        )
    except InvalidCurrentPasswordError:
        # 실패를 HTTP 400 + {"detail": ...} 로 표현
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    # 성공: 204 No Content (바디 없음)
```

## 응답 예시

**현재 비밀번호 불일치 (400)**
```json
{ "detail": "Current password is incorrect." }
```

**성공 (204)** — 바디 없음.
