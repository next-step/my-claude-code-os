"""E2E 픽스처: 실제 uvicorn 서버를 서브프로세스로 띄운다.

통합 테스트(TestClient, 인프로세스)와 달리 — 진짜 HTTP 전송·실 DB 파일·서버 기동
(lifespan init_db)·환경설정 로딩까지 종단간으로 검증한다.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

# tests/e2e/conftest.py → parents[2] = 저장소 루트 (app 패키지를 import 하려면 여기가 cwd)
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    """OS가 비어 있는 포트를 하나 골라준다(테스트 병렬·재실행 충돌 방지)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def e2e_server(tmp_path_factory):
    """실 uvicorn 서버를 임시 DB·테스트 env로 띄우고 base_url 을 준다.

    - 실제 파일 sqlite(임시 디렉토리) — .env·운영 DB 를 절대 건드리지 않는다.
    - JWT_SECRET 등은 서브프로세스 env 로만 주입한다.
    - 준비될 때까지 /docs 를 폴링하고, 끝나면 프로세스를 정리한다.
    """
    port = _free_port()
    db_path = tmp_path_factory.mktemp("e2e") / "e2e.db"

    env = os.environ.copy()
    env["JWT_SECRET"] = "e2e-테스트-전용-시크릿-절대-운영에-쓰지말것"
    env["JWT_ALGORITHM"] = "HS256"
    env["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"
    env["DATABASE_URL"] = f"sqlite:///{db_path}"

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(port),
            "--log-level", "warning",
        ],
        cwd=str(_REPO_ROOT),
        env=env,
    )
    base_url = f"http://127.0.0.1:{port}"

    try:
        _wait_until_ready(proc, base_url, timeout=30.0)
        yield {"base_url": base_url, "jwt_secret": env["JWT_SECRET"]}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def _wait_until_ready(proc, base_url, timeout):
    """서버가 요청을 받을 때까지 폴링한다. 서버가 먼저 죽으면 즉시 실패시킨다."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"uvicorn 이 기동 중 종료됨 (returncode={proc.returncode})")
        try:
            if httpx.get(f"{base_url}/docs", timeout=1.0).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError("서버 기동 대기 타임아웃(30s)")
