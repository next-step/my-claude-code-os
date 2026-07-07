# 회원가입 아이디 중복 실패 처리 (스케치)

- **언어/스택**: Python 3, FastAPI + SQLAlchemy + Pydantic
- **판정 레이어**: 서비스 레이어에서 조회로 사전 판정하고, DB의 `UNIQUE` 제약을 최종 방어선으로 둔다(경쟁 조건 대비).
- **실패 표현**: 커스텀 예외 `DuplicateUsernameError`를 서비스가 raise → 라우터가 `HTTPException`(또는 예외 핸들러)으로 변환.
- **상태코드**: `409 Conflict` (리소스 충돌이 의미상 가장 정확).
- **응답 바디**: JSON. `{"error": {...}}` 형태로 코드·메시지·필드를 명시.

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter()


# --- 스키마 (Pydantic) ---
class SignupRequest(BaseModel):
    username: str
    password: str


# --- 도메인 예외 (실패 표현) ---
class DuplicateUsernameError(Exception):
    def __init__(self, username: str):
        self.username = username
        super().__init__(f"username already exists: {username}")


# --- 서비스 레이어: 여기서 중복을 판정 ---
def create_user(db: Session, req: SignupRequest) -> User:
    # 1차 판정: 명시적 조회 (친절한 에러 + 조기 반환)
    exists = db.query(User).filter(User.username == req.username).first()
    if exists is not None:
        raise DuplicateUsernameError(req.username)

    user = User(username=req.username, password_hash=hash_pw(req.password))
    db.add(user)
    try:
        db.commit()  # 2차 방어선: DB UNIQUE 제약 (동시 요청 경쟁 조건)
    except IntegrityError:
        db.rollback()
        raise DuplicateUsernameError(req.username)
    db.refresh(user)
    return user


# --- 라우터: 실패를 HTTP 응답으로 변환 ---
@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    try:
        user = create_user(db, req)
    except DuplicateUsernameError as e:
        # 상태코드 409 + 구조화된 응답 바디
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "USERNAME_ALREADY_EXISTS",
                    "message": "이미 사용 중인 아이디입니다.",
                    "field": "username",
                    "value": e.username,
                }
            },
        )
    return {"id": user.id, "username": user.username}
```

## 실패 시 응답 예시

```
HTTP/1.1 409 Conflict
Content-Type: application/json

{
  "error": {
    "code": "USERNAME_ALREADY_EXISTS",
    "message": "이미 사용 중인 아이디입니다.",
    "field": "username",
    "value": "alice"
  }
}
```

## 요약
| 항목 | 결정 |
|------|------|
| 판정 레이어 | 서비스(조회) + DB UNIQUE(최종) |
| 실패 표현 | `DuplicateUsernameError` → `HTTPException` |
| 상태코드 | `409 Conflict` |
| 응답 바디 | `{"error": {code, message, field, value}}` JSON |
| 언어/스택 | Python / FastAPI + SQLAlchemy |
