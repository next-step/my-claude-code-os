"""단위 테스트: get_db 요청 세션 의존성의 수명주기(yield 후 close 호출)."""

import pytest
from sqlalchemy.orm import Session

import app.database as database


def test_get_db_는_세션을_yield하고_소진시_close를_호출한다(monkeypatch):
    # get_db 가 만드는 세션을 스파이로 감싸 close 호출 여부를 기록한다.
    session = database.SessionLocal()
    closed = []
    monkeypatch.setattr(session, "close", lambda: closed.append(True))
    monkeypatch.setattr(database, "SessionLocal", lambda: session)

    gen = database.get_db()
    db = next(gen)                     # SessionLocal() 생성 → yield
    assert isinstance(db, Session)
    assert db is session
    assert closed == []                # yield 중에는 아직 close 전

    with pytest.raises(StopIteration):
        next(gen)                      # 제너레이터 소진 → finally: db.close()
    assert closed == [True]            # close 가 정확히 1회 호출됐다(finally 회귀 방어)
