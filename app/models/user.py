"""users 테이블 ORM 엔티티."""

from sqlalchemy import Column, Integer, String

from app.database import Base


class User(Base):
    """사용자 계정.

    비밀번호는 평문으로 저장하지 않고, 사용자별 솔트와 SHA-512 해시로만 보관한다.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # trim 후 저장, 대소문자 구분. DB UNIQUE 로 중복 가입 경합을 최종 방어한다.
    username = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    # SHA-512 hex digest (128자)
    password_hash = Column(String, nullable=False)
    # 사용자별 랜덤 솔트 (token_hex(32) → 64자 hex). 별도 컬럼 저장.
    salt = Column(String, nullable=False)
    # 생성 시각(ISO8601 UTC 문자열)
    created_at = Column(String, nullable=False)
