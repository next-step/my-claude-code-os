"""push 회고 게이트 훅(enforce-retro-gate.sh) 검증.

PreToolUse(Bash) 입력(JSON)을 stdin으로 먹여, `git push` 전에 "마지막 게이트 통과 이후
/retro 흔적"을 강제하는지 확인한다. 로그·마커는 임시 CLAUDE_PROJECT_DIR로 격리하고,
git 명령은 실제 저장소(cwd=PROJ) HEAD를 쓴다(최신 커밋 = 오늘).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
HOOK = PROJ / ".claude" / "hooks" / "enforce-retro-gate.sh"

OLD = "2026-07-05 09:00:00"      # 오래된 마커(= 이후 새 작업 있음)
FUTURE = "2099-01-01 00:00:00"   # 최신 커밋보다 미래(= 새 작업 없음)


def _claude_dir(tmp_path: Path, marker: str | None, log_lines: list[str]) -> Path:
    d = tmp_path / ".claude"
    d.mkdir(parents=True, exist_ok=True)
    (d / "skill-usage.log").write_text("".join(l + "\n" for l in log_lines), encoding="utf-8")
    if marker is not None:
        (d / ".retro-gate-marker").write_text(marker + "\n", encoding="utf-8")
    return d


def run_hook(tmp_path: Path, command: str) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_input": {"command": command}})
    return subprocess.run(
        ["bash", str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)},
        cwd=str(PROJ),
    )


def test_blocks_push_without_retro(tmp_path):
    """마커 이후 새 작업이 있는데 /retro 흔적이 없으면 push를 차단(exit 2)한다."""
    _claude_dir(tmp_path, OLD, ["2026-07-05 10:00:00\tcoverage"])
    res = run_hook(tmp_path, "git push origin step3")
    assert res.returncode == 2
    assert "회고 흔적이 없습니다" in res.stderr


def test_allows_push_with_retro_after_marker(tmp_path):
    """마커 이후 /retro 실행 기록이 있으면 통과(exit 0)한다."""
    _claude_dir(tmp_path, OLD, ["2026-07-05 10:00:00\tcoverage", "2026-07-14 17:00:00\tretro"])
    res = run_hook(tmp_path, "git push origin step3")
    assert res.returncode == 0


def test_skip_env_bypasses(tmp_path):
    """SKIP_RETRO_GATE 우회 지시가 있으면 검사 없이 통과한다."""
    _claude_dir(tmp_path, OLD, ["2026-07-05 10:00:00\tcoverage"])
    res = run_hook(tmp_path, "SKIP_RETRO_GATE=1 git push origin step3")
    assert res.returncode == 0


def test_ignores_non_push_command(tmp_path):
    """push가 아닌 명령(git status)엔 관여하지 않는다."""
    _claude_dir(tmp_path, OLD, ["2026-07-05 10:00:00\tcoverage"])
    res = run_hook(tmp_path, "git status")
    assert res.returncode == 0


def test_allows_when_no_new_work_since_marker(tmp_path):
    """마커가 최신 커밋보다 미래(= 마커 이후 새 작업 없음)면 통과한다(재시도 안전)."""
    _claude_dir(tmp_path, FUTURE, ["2026-07-05 10:00:00\tcoverage"])
    res = run_hook(tmp_path, "git push origin step3")
    assert res.returncode == 0


def test_first_run_seeds_marker_and_passes(tmp_path):
    """마커가 없으면(첫 실행) 지금 시각으로 씨딩하고 통과한다(설치 이후부터만 강제)."""
    _claude_dir(tmp_path, None, ["2026-07-05 10:00:00\tcoverage"])
    res = run_hook(tmp_path, "git push origin step3")
    assert res.returncode == 0
    assert (tmp_path / ".claude" / ".retro-gate-marker").exists()
