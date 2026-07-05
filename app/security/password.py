"""비밀번호 솔트 생성·해싱·검증 (SHA-512 + 사용자별 솔트).

⚠️ SHA-512 는 빠른 해시라 솔트가 있어도 대량 대입에 취약하다(PRD 에서 수용된 잔여 리스크).
추후 bcrypt/Argon2 로 교체할 때 이 파일의 함수만 바꾸면 되도록 계층을 분리해 둔다.
"""

import hashlib
import secrets


def make_salt() -> str:
    """사용자별 랜덤 솔트를 생성한다. 32바이트 → 64자 hex 문자열."""
    return secrets.token_hex(32)


def hash_password(password: str, salt: str) -> str:
    """(salt + password) 를 SHA-512 로 해싱한 128자 hex digest 를 돌려준다."""
    return hashlib.sha512((salt + password).encode("utf-8")).hexdigest()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """평문 비밀번호가 저장된 해시와 일치하는지 상수시간 비교로 검증한다."""
    actual_hash = hash_password(password, salt)
    return secrets.compare_digest(actual_hash, expected_hash)
