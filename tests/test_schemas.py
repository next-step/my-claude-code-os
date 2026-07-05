"""단위 테스트: username/password validator."""

import pytest
from pydantic import ValidationError

from app.schemas.auth import SignupRequest


def _make(username="alice", password="abcd1234", name="앨리스"):
    return SignupRequest(username=username, password=password, name=name)


def test_username_21자_거부():
    with pytest.raises(ValidationError):
        _make(username="a" * 21)


def test_username_공백_포함_거부():
    with pytest.raises(ValidationError):
        _make(username="ab cd")


def test_username_앞뒤공백_trim():
    assert _make(username="  abc  ").username == "abc"


def test_username_대소문자_구분_유지():
    assert _make(username="Abc").username == "Abc"
    assert _make(username="abc").username == "abc"


def test_password_8자_미만_거부():
    with pytest.raises(ValidationError):
        _make(password="abc123")


def test_password_소문자_없음_거부():
    with pytest.raises(ValidationError):
        _make(password="ABCD1234")


def test_password_숫자_없음_거부():
    with pytest.raises(ValidationError):
        _make(password="abcdefgh")


def test_password_정상_통과():
    assert _make(password="abcd1234").password == "abcd1234"
