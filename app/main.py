"""FastAPI 앱 조립: 라우터·예외 핸들러 등록, 기동 시 DB 테이블 생성."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.controllers.auth_controller import router as auth_router
from app.database import init_db
from app.errors import register_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """기동 시 테이블을 생성한다."""
    init_db()
    yield


app = FastAPI(title="회원가입·로그인 API", lifespan=lifespan)

register_error_handlers(app)
app.include_router(auth_router)
