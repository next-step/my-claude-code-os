"""테스트 공용 픽스처.

- 실제 .db/.env 를 절대 건드리지 않는다: 인메모리 SQLite(StaticPool)로 격리.
- JWT_SECRET 등 환경변수는 app import 이전에 테스트 전용 값으로 주입한다.
"""

import os

# app.config 가 import 되는 순간 JWT_SECRET 을 읽으므로 반드시 import 이전에 설정한다.
os.environ.setdefault("JWT_SECRET", "테스트-전용-시크릿-키-절대-운영에-쓰지말것")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
# 실제 파일이 생기지 않도록 인메모리로 고정.
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def db_engine():
    """테스트마다 격리된 인메모리 SQLite 엔진.

    StaticPool + 단일 커넥션으로 :memory: DB 가 여러 커넥션 사이에서도 공유되게 한다.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client(db_engine):
    """테스트 DB 세션을 주입한 TestClient."""
    TestingSessionLocal = sessionmaker(
        bind=db_engine, autoflush=False, autocommit=False
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
