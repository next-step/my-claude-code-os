"""SQLAlchemy 엔진·세션·Base 및 DB 세션 의존성.

DB 접근 세부는 Repository 계층에서만 다루고, 여기서는 연결 자원만 제공한다.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# SQLite 는 기본적으로 스레드 간 커넥션 공유를 막으므로 check_same_thread 를 끈다.
_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# 모든 ORM 모델이 상속하는 선언적 베이스.
Base = declarative_base()


def get_db():
    """요청 단위 DB 세션을 제공하는 FastAPI 의존성."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """등록된 모든 테이블을 생성한다(없으면 만든다)."""
    # 모델이 Base 에 등록되도록 import 를 보장한다.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
