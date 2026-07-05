"""통합 테스트: POST /login."""

import os

from jose import jwt


def _signup(client, username="alice", password="abcd1234", name="앨리스"):
    return client.post(
        "/signup",
        json={"username": username, "password": password, "name": name},
    )


def test_정상_로그인_200_토큰_payload(client):
    signup_resp = _signup(client)
    user_id = signup_resp.json()["userId"]

    resp = client.post(
        "/login", json={"username": "alice", "password": "abcd1234"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tokenType"] == "bearer"
    assert body["expiresIn"] == 3600

    decoded = jwt.decode(
        body["accessToken"], os.environ["JWT_SECRET"], algorithms=["HS256"]
    )
    assert decoded["sub"] == str(user_id)


def test_없는_아이디_401(client):
    resp = client.post(
        "/login", json={"username": "nobody", "password": "abcd1234"}
    )
    assert resp.status_code == 401
    assert resp.json()["errorCode"] == "INVALID_CREDENTIALS"


def test_틀린_비번_없는아이디와_동일응답(client):
    _signup(client)

    없는_아이디 = client.post(
        "/login", json={"username": "ghost", "password": "abcd1234"}
    )
    틀린_비번 = client.post(
        "/login", json={"username": "alice", "password": "wrong0000"}
    )

    # 상태코드·응답 바디가 완전히 동일해야 한다(정보 누출 방지).
    assert 없는_아이디.status_code == 401
    assert 틀린_비번.status_code == 401
    assert 없는_아이디.json() == 틀린_비번.json()
    assert 틀린_비번.json()["errorCode"] == "INVALID_CREDENTIALS"
