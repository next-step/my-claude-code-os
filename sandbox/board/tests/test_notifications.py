"""notifications.py 단위 테스트 (REQ-008).

app.py 는 다른 작업이 진행 중이라 이번 범위에서 건드리지 않는다 — 이 모듈만 독립적으로
검증한다. app.py 연결(create_post 트리거)은 이후 안전할 때 별도로 진행.
"""
from notifications import format_new_post_message, notify_admins, send_sms


def test_format_message_includes_title_and_author():
    msg = format_new_post_message("사과 파이", author="홍길동")
    assert "사과 파이" in msg
    assert "홍길동" in msg


def test_send_sms_returns_false_without_gateway():
    # 게이트웨이 미연결 상태 — 항상 실패(False)를 반환해야 한다 (조용히 성공한 척하지 않음).
    assert send_sms("010-0000-0000", "테스트") is False


def test_notify_admins_tries_every_number():
    result = notify_admins(["010-1111-1111", "010-2222-2222"], "새 글", author="담당자")
    assert set(result.keys()) == {"010-1111-1111", "010-2222-2222"}
    # 게이트웨이가 없으므로 전원 실패로 기록돼야 한다.
    assert all(ok is False for ok in result.values())
