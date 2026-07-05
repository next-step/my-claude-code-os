"""회원가입·로그인 비즈니스 규칙.

Repository(DB 접근)와 Security(해싱·토큰)를 조합해 도메인 규칙을 수행하고,
규칙 위반 시 도메인 예외(AppError)를 발생시킨다.
"""

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.errors import duplicate_username_error, invalid_credentials_error
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.security.password import hash_password, make_salt, verify_password
from app.security.token import create_access_token


class AuthService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    def signup(self, username: str, password: str, name: str) -> User:
        """신규 가입. 중복 아이디면 DUPLICATE_USERNAME(409).

        username·name 은 스키마 validator 에서 이미 trim 되어 들어온다.
        """
        # 1차 판정: 애플리케이션 레벨 중복 조회.
        if self.repo.get_by_username(username) is not None:
            raise duplicate_username_error()

        salt = make_salt()
        password_hash = hash_password(password, salt)
        created_at = datetime.now(timezone.utc).isoformat()

        user = User(
            username=username,
            name=name,
            password_hash=password_hash,
            salt=salt,
            created_at=created_at,
        )
        try:
            return self.repo.create(user)
        except IntegrityError:
            # 최종 방어: UNIQUE 제약 위반(동시 가입 경합 등) → 중복으로 정규화.
            self.repo.rollback()
            raise duplicate_username_error()

    def login(self, username: str, password: str) -> str:
        """로그인 성공 시 액세스 토큰을 발급한다.

        아이디 없음/비밀번호 불일치는 보안상 구분하지 않고 동일하게
        INVALID_CREDENTIALS(401) 로 처리한다.
        """
        user = self.repo.get_by_username(username)
        if user is None:
            raise invalid_credentials_error()
        if not verify_password(password, user.salt, user.password_hash):
            raise invalid_credentials_error()
        return create_access_token(user.id)
