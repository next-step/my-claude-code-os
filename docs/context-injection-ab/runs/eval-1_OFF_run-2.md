# 회원가입 아이디 중복 실패 처리 스케치 (FastAPI)

- **언어/프레임워크**: Python 3.11 / FastAPI + SQLAlchemy + Pydantic
- **판정 레이어**: 서비스 레이어에서 조회로 1차 판정하고, DB `UNIQUE` 제약(username)으로 최종 판정(레이스 컨디션 방어). 라우터는 서비스 예외를 HTTP 응답으로 변환.
- **실패 표현**: 도메인 예외 `DuplicateUsernameError` → 라우터에서 `HTTPException`로 매핑.
- **상태코드**: `409 Conflict` (자원 충돌).
- **응답 바디 형식**: JSON `{ "error": { "code": "...", "message": "...", "field": "..." } }`

```python
# domain/exceptions.py -------------------------------------------------
class DuplicateUsernameError(Exception):
    """이미 존재하는 아이디로 가입을 시도할 때 발생하는 도메인 예외."""
    def __init__(self, username: str):
        self.username = username
        super().__init__(f"username already exists: {username}")


# schemas.py -----------------------------------------------------------
from pydantic import BaseModel, Field

class SignupIn(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=8)

class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None

class ErrorResponse(BaseModel):
    error: ErrorDetail


# service.py -----------------------------------------------------------
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from domain.exceptions import DuplicateUsernameError

def register_user(db: Session, data: SignupIn) -> User:
    # 1차 판정: 조회로 사전 차단(빠른 실패 + 친절한 메시지)
    if db.query(User).filter(User.username == data.username).first():
        raise DuplicateUsernameError(data.username)

    user = User(username=data.username,
                password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.commit()               # 최종 판정: DB UNIQUE 제약
    except IntegrityError:
        db.rollback()
        raise DuplicateUsernameError(data.username)  # 동시 가입 레이스 방어
    db.refresh(user)
    return user


# router.py ------------------------------------------------------------
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter()

@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
def signup(payload: SignupIn, db: Session = Depends(get_db)):
    try:
        user = register_user(db, payload)
    except DuplicateUsernameError:
        # 실패 표현: 도메인 예외 → 409 + 구조화 에러 바디
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "USERNAME_ALREADY_EXISTS",
                    "message": "이미 사용 중인 아이디입니다.",
                    "field": "username",
                }
            },
        )
    return {"id": user.id, "username": user.username}
```

**요약**: 조회(서비스) + UNIQUE 제약(DB) 이중 판정 → 실패는 `DuplicateUsernameError` 도메인 예외로 표현 → 라우터가 `409 Conflict` + `{"error": {...}}` JSON 바디로 응답.
