"""JWT 액세스 토큰 발급 (HS256).

payload 에는 user_id 만 담는다: sub=str(user_id), exp=발급시각+만료(기본 60분).
"""

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import settings


def create_access_token(user_id: int) -> str:
    """user_id 로 서명된 액세스 토큰을 발급한다."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
