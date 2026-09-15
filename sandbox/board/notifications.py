"""게시글 알림 발송 — REQ-008.

관리자에게 새 게시글 알림을 보내는 어댑터. 실제 SMS 게이트웨이 계정·API 키가 없어
send_sms() 는 아직 외부 호출을 하지 않는 스텁이다 — 벤더 계약 후 내부 구현만 교체하면
호출부(app.py)는 안 건드려도 되게 분리해뒀다.
"""
import logging

logger = logging.getLogger("board.notifications")


def format_new_post_message(title, author="담당자"):
    return f"[게시판] 새 글: {title} (작성자: {author})"


def send_sms(number, message):
    """SMS 발송을 시도한다. 실제 게이트웨이가 없어 항상 로그만 남기고 실패로 반환한다.

    벤더 계약 후: 이 함수 내부만 실제 API 호출로 교체하면 된다 (호출부 변경 불필요).
    """
    logger.info("SMS 발송 시도 (게이트웨이 미연결): to=%s message=%s", number, message)
    return False  # 실제로 보내지지 않았다 — 벤더 연동 전까지는 항상 False


def notify_admins(admin_numbers, title, author="담당자"):
    """새 글 작성 시 등록된 관리자 전원에게 알림을 시도한다.

    반환값: {번호: 발송성공여부} — 지금은 게이트웨이가 없어 전원 False.
    """
    message = format_new_post_message(title, author)
    return {number: send_sms(number, message) for number in admin_numbers}
