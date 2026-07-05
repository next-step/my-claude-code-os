"""단위 테스트: 솔트·해시·검증·토큰."""

import os
from datetime import datetime, timezone

from jose import jwt

from app.security.password import hash_password, make_salt, verify_password
from app.security.token import create_access_token


def test_make_salt_길이와_유일성():
    """솔트는 64자 hex 이고 매 호출마다 서로 다르다."""
    salt1 = make_salt()
    salt2 = make_salt()
    assert len(salt1) == 64
    assert len(salt2) == 64
    assert salt1 != salt2


def test_같은_입력_같은_해시_다른_솔트_다른_해시():
    """같은 (pw, salt) → 동일 해시, 다른 salt → 다른 해시(솔트 효과)."""
    pw = "abcd1234"
    salt = make_salt()
    assert hash_password(pw, salt) == hash_password(pw, salt)
    assert hash_password(pw, salt) != hash_password(pw, make_salt())
    # SHA-512 hex digest 는 128자.
    assert len(hash_password(pw, salt)) == 128


def test_verify_password_정답_오답():
    """정답 비밀번호는 True, 오답은 False."""
    pw = "abcd1234"
    salt = make_salt()
    expected = hash_password(pw, salt)
    assert verify_password(pw, salt, expected) is True
    assert verify_password("wrong0000", salt, expected) is False


def test_create_access_token_payload_와_만료():
    """토큰을 디코드하면 sub=str(user_id), exp 가 ~60분 뒤여야 한다."""
    secret = os.environ["JWT_SECRET"]
    token = create_access_token(42)
    decoded = jwt.decode(token, secret, algorithms=["HS256"])
    assert decoded["sub"] == "42"

    now = datetime.now(timezone.utc).timestamp()
    # 만료는 지금보다 미래이며 대략 60분(±2분) 뒤.
    assert decoded["exp"] > now
    assert abs(decoded["exp"] - (now + 3600)) < 120


def test_잘못된_시크릿으로_디코드_실패():
    """다른 시크릿으로는 검증이 실패한다."""
    token = create_access_token(1)
    try:
        jwt.decode(token, "완전히-다른-시크릿", algorithms=["HS256"])
        assert False, "잘못된 시크릿인데 디코드가 성공하면 안 된다."
    except Exception:
        pass
