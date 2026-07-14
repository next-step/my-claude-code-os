"""E2E: 실서버에 진짜 HTTP로 가입·로그인 플로우를 관통한다(해피 + 실패).

세션 스코프 서버를 공유하므로 테스트마다 username 을 다르게 써 서로 오염되지 않게 한다.
"""

import httpx
import pytest
from jose import jwt

pytestmark = pytest.mark.e2e


def _client(e2e_server):
    return httpx.Client(base_url=e2e_server["base_url"], timeout=5.0)


def test_e2e_가입_로그인_토큰발급_해피패스(e2e_server):
    with _client(e2e_server) as c:
        # 1) 가입 → 201
        r = c.post(
            "/signup",
            json={"username": "e2e_alice", "password": "abcd1234", "name": "앨리스"},
        )
        assert r.status_code == 201, r.text
        user_id = r.json()["userId"]

        # 2) 로그인 → 200 + 토큰
        r = c.post("/login", json={"username": "e2e_alice", "password": "abcd1234"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["tokenType"] == "bearer"
        assert body["expiresIn"] == 3600

        # 3) 토큰이 실서버 시크릿으로 서명됐고 sub=userId (종단간: 발급 → 검증)
        decoded = jwt.decode(
            body["accessToken"], e2e_server["jwt_secret"], algorithms=["HS256"]
        )
        assert decoded["sub"] == str(user_id)


def test_e2e_중복가입_409_DUPLICATE_USERNAME(e2e_server):
    with _client(e2e_server) as c:
        payload = {"username": "e2e_dup", "password": "abcd1234", "name": "중복"}
        assert c.post("/signup", json=payload).status_code == 201
        r = c.post("/signup", json=payload)
        assert r.status_code == 409
        assert r.json()["errorCode"] == "DUPLICATE_USERNAME"


def test_e2e_잘못된_자격증명_401_없는아이디와_동일응답(e2e_server):
    with _client(e2e_server) as c:
        c.post(
            "/signup",
            json={"username": "e2e_bob", "password": "abcd1234", "name": "밥"},
        )
        없는_아이디 = c.post(
            "/login", json={"username": "e2e_ghost", "password": "abcd1234"}
        )
        틀린_비번 = c.post(
            "/login", json={"username": "e2e_bob", "password": "wrong0000"}
        )
        # 정보 누출 방지: 상태코드·바디가 완전히 동일해야 한다.
        assert 없는_아이디.status_code == 401
        assert 틀린_비번.status_code == 401
        assert 없는_아이디.json() == 틀린_비번.json()
        assert 틀린_비번.json()["errorCode"] == "INVALID_CREDENTIALS"
