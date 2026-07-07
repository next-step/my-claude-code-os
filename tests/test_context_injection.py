"""컨텍스트 자동 주입 훅(inject-context.sh) 검증.

훅에 PreToolUse 입력(JSON)을 stdin으로 먹여, 규칙대로 주입/침묵/중복방지 하는지 확인한다.
(과제 도전1: 주입이 올바른지 확인하는 테스트 — 버그 방지.)
"""

import json
import os
import subprocess
import uuid
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
HOOK = PROJ / ".claude" / "hooks" / "inject-context.sh"
CARD_MARKER = "백엔드 컨벤션"  # backend-conventions.md 제목에 있는 표식
DOC_MARKER = "문서 작성 규칙"  # doc-conventions.md 제목에 있는 표식


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


def test_injects_backend_card_for_app_path():
    """app/ 파일을 만지면 backend-conventions 카드가 additionalContext로 주입된다."""
    res = run_hook(str(PROJ / "app" / "main.py"), "t-" + uuid.uuid4().hex)
    assert res.returncode == 0
    out = json.loads(res.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert CARD_MARKER in ctx


def test_injects_for_tests_path():
    """tests/ 경로도 백엔드 카드 대상이다."""
    res = run_hook(str(PROJ / "tests" / "test_login.py"), "t-" + uuid.uuid4().hex)
    assert res.returncode == 0
    assert CARD_MARKER in json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]


def test_injects_doc_card_for_docs_path():
    """docs/ 문서를 만지면 doc-conventions 카드가 주입된다(app/tests와 다른 카드)."""
    res = run_hook(str(PROJ / "docs" / "prd" / "whatever.md"), "t-" + uuid.uuid4().hex)
    assert res.returncode == 0
    ctx = json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]
    assert DOC_MARKER in ctx
    assert CARD_MARKER not in ctx  # 백엔드 카드가 잘못 섞이지 않는다


def test_no_inject_for_unrelated_path():
    """app·tests·docs 밖(저장소 루트 등)은 주입하지 않는다(침묵)."""
    res = run_hook(str(PROJ / "OS.md"), "t-" + uuid.uuid4().hex)
    assert res.returncode == 0
    assert res.stdout.strip() == ""


def test_dedup_injects_once_per_session():
    """같은 세션에서 두 번째 편집은 중복 주입하지 않는다(컨텍스트 최적화)."""
    sid = "t-" + uuid.uuid4().hex
    first = run_hook(str(PROJ / "app" / "main.py"), sid)
    assert first.stdout.strip() != ""  # 첫 편집: 주입
    second = run_hook(str(PROJ / "app" / "config.py"), sid)
    assert second.stdout.strip() == ""  # 같은 세션: 침묵


def test_dedup_is_per_card_not_global():
    """카드별 독립 dedup — 백엔드 카드를 한 번 주입해도 문서 카드는 여전히 주입된다."""
    sid = "t-" + uuid.uuid4().hex
    backend = run_hook(str(PROJ / "app" / "main.py"), sid)
    assert CARD_MARKER in json.loads(backend.stdout)["hookSpecificOutput"]["additionalContext"]
    docs = run_hook(str(PROJ / "docs" / "plan" / "x.md"), sid)  # 같은 세션, 다른 카드
    assert DOC_MARKER in json.loads(docs.stdout)["hookSpecificOutput"]["additionalContext"]
