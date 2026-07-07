"""세션 종료 회고 리마인더 훅(retro-reminder.sh) 검증.

SessionEnd 입력(JSON)을 stdin으로 먹여, 실질 작업 세션엔 안내하고
트리비얼 세션엔 침묵하는지 확인한다. (실제 알림은 RETRO_REMINDER_SILENT=1 로 억제.)
"""

import json
import os
import subprocess
import uuid
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
HOOK = PROJ / ".claude" / "hooks" / "retro-reminder.sh"
MARK = "retro-reminder"  # 안내 결정 시 stdout 표식


def run_hook(transcript_path: str) -> subprocess.CompletedProcess:
    payload = json.dumps(
        {
            "hook_event_name": "SessionEnd",
            "transcript_path": transcript_path,
            "session_id": "t-" + uuid.uuid4().hex,
        }
    )
    return subprocess.run(
        ["bash", str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env={**os.environ, "RETRO_REMINDER_SILENT": "1"},  # 테스트 중 실제 알림 억제
        cwd=str(PROJ),
    )


def _make_transcript(tmp_path: Path, n_lines: int) -> str:
    p = tmp_path / "transcript.jsonl"
    p.write_text("\n".join(f'{{"i": {i}}}' for i in range(n_lines)) + "\n", encoding="utf-8")
    return str(p)


def test_reminds_on_substantial_session(tmp_path):
    """줄 수가 임계(20) 이상인 실질 세션이면 회고 안내를 낸다."""
    res = run_hook(_make_transcript(tmp_path, 40))
    assert res.returncode == 0
    assert MARK in res.stdout


def test_silent_on_trivial_session(tmp_path):
    """1~2턴짜리 짧은 세션(임계 미만)이면 침묵한다(노이즈 방지)."""
    res = run_hook(_make_transcript(tmp_path, 5))
    assert res.returncode == 0
    assert res.stdout.strip() == ""


def test_silent_when_no_transcript(tmp_path):
    """transcript 경로가 없거나 파일이 없으면 조용히 종료한다."""
    res = run_hook(str(tmp_path / "does-not-exist.jsonl"))
    assert res.returncode == 0
    assert res.stdout.strip() == ""
