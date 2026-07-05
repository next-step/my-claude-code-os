"""User 엔티티에 대한 DB 접근만 담당하는 Repository.

SQLAlchemy 세션은 이 계층에서만 다룬다(상위 계층은 DB 세부를 모른다).
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_username(self, username: str) -> Optional[User]:
        """아이디로 사용자를 조회한다(대소문자 구분). 없으면 None."""
        return self.db.query(User).filter(User.username == username).first()

    def create(self, user: User) -> User:
        """새 사용자를 저장하고, PK 등이 채워진 엔티티를 돌려준다."""
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def rollback(self) -> None:
        """진행 중인 트랜잭션을 되돌린다."""
        self.db.rollback()
