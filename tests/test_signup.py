"""통합 테스트: POST /signup."""


def test_정상_가입_201_및_민감정보_미노출(client):
    resp = client.post(
        "/signup",
        json={"username": "alice", "password": "abcd1234", "name": "앨리스"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "alice"
    assert body["name"] == "앨리스"
    assert isinstance(body["userId"], int)
    # 비밀번호/솔트/해시는 절대 응답에 없어야 한다.
    assert "password" not in body
    assert "salt" not in body
    assert "password_hash" not in body


def test_중복_username_409(client):
    payload = {"username": "bob", "password": "abcd1234", "name": "밥"}
    assert client.post("/signup", json=payload).status_code == 201
    resp = client.post("/signup", json=payload)
    assert resp.status_code == 409
    assert resp.json()["errorCode"] == "DUPLICATE_USERNAME"


def test_trim_후_동일하면_409(client):
    assert (
        client.post(
            "/signup",
            json={"username": "alice", "password": "abcd1234", "name": "앨리스"},
        ).status_code
        == 201
    )
    resp = client.post(
        "/signup",
        json={"username": "  alice  ", "password": "abcd1234", "name": "앨리스2"},
    )
    assert resp.status_code == 409
    assert resp.json()["errorCode"] == "DUPLICATE_USERNAME"


def test_대소문자_다르면_둘다_가입_성공(client):
    r1 = client.post(
        "/signup",
        json={"username": "alice", "password": "abcd1234", "name": "소문자"},
    )
    r2 = client.post(
        "/signup",
        json={"username": "Alice", "password": "abcd1234", "name": "대문자"},
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["userId"] != r2.json()["userId"]


def test_비밀번호_규칙_위반_검증실패(client):
    resp = client.post(
        "/signup",
        json={"username": "carol", "password": "short", "name": "캐롤"},
    )
    assert resp.status_code in (400, 422)
    assert resp.json()["errorCode"] == "VALIDATION_ERROR"


def test_username_21자_검증실패(client):
    resp = client.post(
        "/signup",
        json={"username": "a" * 21, "password": "abcd1234", "name": "이름"},
    )
    assert resp.status_code in (400, 422)
    assert resp.json()["errorCode"] == "VALIDATION_ERROR"
