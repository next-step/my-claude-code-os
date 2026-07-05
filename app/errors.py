"""도메인 예외(AppError)와 errorCode 로 정규화하는 예외 핸들러.

모든 실패 응답 바디는 { "errorCode": ..., "message": ... } 형태로 통일한다.
Pydantic 검증 실패(422)도 여기서 errorCode:"VALIDATION_ERROR" 로 정규화한다.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """errorCode·상태코드·메시지를 함께 나르는 도메인 예외."""

    def __init__(self, error_code: str, status_code: int, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code
        self.message = message


def duplicate_username_error() -> AppError:
    """이미 존재하는 아이디로 가입을 시도했을 때."""
    return AppError("DUPLICATE_USERNAME", 409, "이미 사용 중인 아이디입니다.")


def invalid_credentials_error() -> AppError:
    """로그인 실패(아이디 없음/비밀번호 불일치). 두 경우를 구분하지 않는다."""
    return AppError(
        "INVALID_CREDENTIALS", 401, "아이디 또는 비밀번호가 올바르지 않습니다."
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """AppError 를 표준 실패 응답으로 변환한다."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"errorCode": exc.error_code, "message": exc.message},
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Pydantic 검증 실패를 errorCode:"VALIDATION_ERROR" 로 정규화한다."""
    return JSONResponse(
        status_code=422,
        content={
            "errorCode": "VALIDATION_ERROR",
            "message": "입력값이 올바르지 않습니다.",
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    """앱에 예외 핸들러를 등록한다."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
