"""환경변수 기반 애플리케이션 설정.

시크릿(JWT_SECRET)을 코드에 하드코딩하지 않고 환경변수로만 주입한다.
시크릿이 없으면 즉시 기동에 실패시켜, 시크릿 없는 상태로 서비스가 뜨는 것을 막는다.
"""

import os


class Settings:
    """환경변수에서 읽어오는 설정 값 묶음."""

    def __init__(self) -> None:
        secret = os.getenv("JWT_SECRET")
        if not secret:
            # 하드코딩 금지: 시크릿이 없으면 기동을 막는다.
            raise RuntimeError(
                "환경변수 JWT_SECRET 가 설정되지 않았습니다. "
                ".env 파일 또는 실행 환경에 JWT_SECRET 을 설정하세요."
            )
        self.jwt_secret: str = secret
        self.jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes: int = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
        )
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")


# 모듈 로드 시점에 설정을 구성한다.
# → JWT_SECRET 이 없으면 이 import 자체가 실패하여 기동이 중단된다.
settings = Settings()
