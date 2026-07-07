"""도메인 문서 자동 주입 훅(inject-domain.sh) 검증 — 계층형.

훅에 PreToolUse 입력(JSON)을 stdin으로 먹여, 영역 매핑(_territory.tsv)대로
편집 파일이 속한 도메인의 **목차(항상) + 상세(작으면 전체·크면 머리+포인터)**를
주입/침묵/중복방지 하는지 확인한다. (훅도 테스트와 함께. OS.md 원칙 3.)
"""

import json
import os
import subprocess
import uuid
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
HOOK = PROJ / ".claude" / "hooks" / "inject-domain.sh"
DOC_MARKER = "도메인 — auth"   # docs/domain/auth.md 제목의 표식
TOC_MARKER = "도메인 지도"     # docs/domain/README.md(목차) 제목의 표식


def run_hook(file_path: str, session_id: str, proj: Path = PROJ) -> subprocess.CompletedProcess:
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
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(proj)},
        cwd=str(proj),
    )


def _ctx(res: subprocess.CompletedProcess) -> str:
    return json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]


def test_injects_toc_and_small_doc_full_for_app_path():
    """app/ 파일을 만지면 목차 + (작은) auth 문서 전체가 함께 주입된다(계층형)."""
    res = run_hook(str(PROJ / "app" / "services" / "auth_service.py"), "t-" + uuid.uuid4().hex)
    assert res.returncode == 0
    ctx = _ctx(res)
    assert TOC_MARKER in ctx      # 목차는 항상
    assert DOC_MARKER in ctx      # auth.md 는 작으니 전체
    assert "## 관계" in ctx       # 본문(관계 절)까지 실림 = 전체 주입 확인


def test_injects_for_tests_path():
    """tests/ 경로도 영역 매핑상 auth 대상이다."""
    res = run_hook(str(PROJ / "tests" / "test_login.py"), "t-" + uuid.uuid4().hex)
    assert res.returncode == 0
    assert DOC_MARKER in _ctx(res)


def test_no_inject_for_unmapped_path():
    """영역 매핑에 없는 경로(docs 등)는 주입하지 않는다(침묵)."""
    res = run_hook(str(PROJ / "docs" / "whatever.md"), "t-" + uuid.uuid4().hex)
    assert res.returncode == 0
    assert res.stdout.strip() == ""


def test_dedup_injects_once_per_session():
    """같은 세션·같은 도메인에서 두 번째 편집은 중복 주입하지 않는다(컨텍스트 최적화)."""
    sid = "t-" + uuid.uuid4().hex
    first = run_hook(str(PROJ / "app" / "main.py"), sid)
    assert first.stdout.strip() != ""   # 첫 편집: 주입
    second = run_hook(str(PROJ / "app" / "config.py"), sid)
    assert second.stdout.strip() == ""  # 같은 세션·같은 도메인: 침묵


def test_tiered_truncates_large_doc(tmp_path):
    """큰 도메인 문서는 머리(요약)+포인터만 주입하고 본문 뒷부분은 빼는 계층형(격리 임시 프로젝트)."""
    # 임시 프로젝트 구조: docs/domain/{_territory.tsv, README.md, big.md}
    dom = tmp_path / "docs" / "domain"
    dom.mkdir(parents=True)
    (dom / "_territory.tsv").write_text("app/*\tbig\n", encoding="utf-8")
    (dom / "README.md").write_text("# 도메인 지도\n- [big](big.md) — 큰 도메인\n", encoding="utf-8")
    # 80줄짜리 큰 문서: 머리에 HEAD_MARK(주입돼야), 깊은 곳에 DEEP_MARK(잘려나가야).
    body = ["# 도메인 — big", "> 한 줄 정의: HEAD_MARK 큰 도메인"]
    body += [f"line {i}" for i in range(3, 70)]
    body += ["## 깊은 절", "DEEP_MARK 여기는 머리 밖이라 잘려야 한다"]
    (dom / "big.md").write_text("\n".join(body) + "\n", encoding="utf-8")

    res = run_hook(str(tmp_path / "app" / "svc.py"), "t-" + uuid.uuid4().hex, proj=tmp_path)
    assert res.returncode == 0
    ctx = _ctx(res)
    assert "도메인 지도" in ctx        # 목차는 항상
    assert "HEAD_MARK" in ctx          # 머리(요약)는 실림
    assert "DEEP_MARK" not in ctx      # 본문 뒷부분은 잘림
    assert "Read" in ctx               # "전체는 Read" 포인터
