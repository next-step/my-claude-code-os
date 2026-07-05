"""회원가입·로그인 요청/응답 DTO 와 입력 검증(validator)."""

import re

from pydantic import BaseModel, field_validator

# 비밀번호 규칙: 영문 소문자 + 숫자 포함, 8자 이상.
_LOWER_RE = re.compile(r"[a-z]")
_DIGIT_RE = re.compile(r"[0-9]")


def _normalize_username(value: str) -> str:
    """아이디 공통 정규화: 앞뒤 공백 제거 + 형식 검증(≤20자, 공백 불가)."""
    value = value.strip()
    if not value:
        raise ValueError("아이디는 비어 있을 수 없습니다.")
    if " " in value:
        raise ValueError("아이디에는 공백을 포함할 수 없습니다.")
    if len(value) > 20:
        raise ValueError("아이디는 최대 20자까지 가능합니다.")
    return value


class SignupRequest(BaseModel):
    """회원가입 요청 바디."""

    username: str
    password: str
    name: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return _normalize_username(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("이름은 비어 있을 수 없습니다.")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다.")
        if not _LOWER_RE.search(value):
            raise ValueError("비밀번호에는 영문 소문자가 포함되어야 합니다.")
        if not _DIGIT_RE.search(value):
            raise ValueError("비밀번호에는 숫자가 포함되어야 합니다.")
        return value


class SignupResponse(BaseModel):
    """회원가입 성공 응답. 비밀번호·솔트·해시는 절대 포함하지 않는다."""

    userId: int
    username: str
    name: str


class LoginRequest(BaseModel):
    """로그인 요청 바디.

    로그인 시에는 비밀번호 규칙 검증을 하지 않는다(실패 응답을 동일하게 유지하기 위함).
    아이디는 가입 때와 동일 기준으로 매칭하기 위해 앞뒤 공백만 제거한다.
    """

    username: str
    password: str

    @field_validator("username")
    @classmethod
    def strip_username(cls, value: str) -> str:
        return value.strip()


class LoginResponse(BaseModel):
    """로그인 성공 응답(액세스 토큰)."""

    accessToken: str
    tokenType: str = "bearer"
    expiresIn: int


class ErrorResponse(BaseModel):
    """공통 실패 응답 스키마."""

    errorCode: str
    message: str
