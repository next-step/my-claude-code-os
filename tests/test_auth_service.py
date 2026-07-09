"""단위 테스트: AuthService 도메인 규칙 — 특히 동시성 경합 최종 방어 분기.

통합 경로(client)로는 닿기 어려운 IntegrityError 경합 분기를 스텁 Repository 로 직접 친다.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.errors import AppError
from app.services.auth_service import AuthService


class _StubRepo:
    """UserRepository 를 흉내내는 스텁 — signup 분기 검증용(DB 없이)."""

    def __init__(self, existing=None, create_raises=False):
        self._existing = existing
        self._create_raises = create_raises
        self.rolled_back = False

    def get_by_username(self, username):
        return self._existing

    def create(self, user):
        if self._create_raises:
            # 실제 UNIQUE 제약 위반을 흉내낸다(동시 가입 경합 등).
            raise IntegrityError("INSERT ...", {}, Exception("UNIQUE constraint failed"))
        return user

    def rollback(self):
        self.rolled_back = True


def test_signup_1차조회_중복이면_409_DUPLICATE_USERNAME():
    repo = _StubRepo(existing=object())  # 이미 존재하는 유저
    service = AuthService(repo)
    with pytest.raises(AppError) as exc:
        service.signup("alice", "abcd1234", "앨리스")
    assert exc.value.error_code == "DUPLICATE_USERNAME"
    assert exc.value.status_code == 409


def test_signup_경합_IntegrityError는_rollback후_중복오류로_정규화():
    repo = _StubRepo(existing=None, create_raises=True)
    service = AuthService(repo)
    with pytest.raises(AppError) as exc:
        service.signup("alice", "abcd1234", "앨리스")
    assert exc.value.error_code == "DUPLICATE_USERNAME"
    # 최종 방어 분기에서 rollback 이 반드시 호출돼야 한다.
    assert repo.rolled_back is True
