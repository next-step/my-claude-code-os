"""회원가입·로그인 라우터. HTTP 요청/응답 변환만 담당한다.

비즈니스 로직·DB 접근은 하지 않고 Service 에 위임한다.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    ErrorResponse,
    LoginRequest,
    LoginResponse,
    SignupRequest,
    SignupResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(tags=["auth"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """요청 단위로 AuthService(+Repository)를 조립하는 의존성."""
    return AuthService(UserRepository(db))


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def signup(
    payload: SignupRequest,
    service: AuthService = Depends(get_auth_service),
) -> SignupResponse:
    """회원가입. 성공 시 201 + {userId, username, name}."""
    user = service.signup(payload.username, payload.password, payload.name)
    return SignupResponse(userId=user.id, username=user.username, name=user.name)


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def login(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    """로그인. 성공 시 200 + 액세스 토큰."""
    token = service.login(payload.username, payload.password)
    return LoginResponse(
        accessToken=token,
        expiresIn=settings.access_token_expire_minutes * 60,
    )
