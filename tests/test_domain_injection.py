"""도메인 문서 자동 주입 훅(inject-domain.sh) 검증.

훅에 PreToolUse 입력(JSON)을 stdin으로 먹여, 영역 매핑(_territory.tsv)대로
편집 파일이 속한 도메인 문서를 주입/침묵/중복방지 하는지 확인한다.
(inject-context.sh 검증과 같은 방식 — 훅도 테스트와 함께. OS.md 원칙 3.)
"""

import json
import os
import subprocess
import uuid
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
HOOK = PROJ / ".claude" / "hooks" / "inject-domain.sh"
DOC_MARKER = "도메인 — auth"  # docs/domain/auth.md 제목에 있는 표식


def run_hook(file_path: str, session_id: str) -> subprocess.CompletedProcess:
    payload = json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {"file_path": file_path},
            "session_id": session_id,
        }
    )
    return subprocess.run(
        ["bash", str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(PROJ)},
        cwd=str(PROJ),
    )


def test_injects_auth_doc_for_app_path():
    """app/ 파일을 만지면 auth 도메인 문서가 additionalContext로 주입된다."""
    res = run_hook(str(PROJ / "app" / "services" / "auth_service.py"), "t-" + uuid.uuid4().hex)
    assert res.returncode == 0
    out = json.loads(res.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert DOC_MARKER in ctx


def test_injects_for_tests_path():
    """tests/ 경로도 영역 매핑상 auth 대상이다."""
    res = run_hook(str(PROJ / "tests" / "test_login.py"), "t-" + uuid.uuid4().hex)
    assert res.returncode == 0
    assert DOC_MARKER in json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]


def test_no_inject_for_unmapped_path():
    """영역 매핑에 없는 경로(docs 등)는 주입하지 않는다(침묵)."""
    res = run_hook(str(PROJ / "docs" / "whatever.md"), "t-" + uuid.uuid4().hex)
    assert res.returncode == 0
    assert res.stdout.strip() == ""


def test_dedup_injects_once_per_session():
    """같은 세션·같은 도메인에서 두 번째 편집은 중복 주입하지 않는다(컨텍스트 최적화)."""
    sid = "t-" + uuid.uuid4().hex
    first = run_hook(str(PROJ / "app" / "main.py"), sid)
    assert first.stdout.strip() != ""  # 첫 편집: 주입
    second = run_hook(str(PROJ / "app" / "config.py"), sid)
    assert second.stdout.strip() == ""  # 같은 세션·같은 도메인: 침묵
