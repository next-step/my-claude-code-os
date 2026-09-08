#!/usr/bin/env python3
"""SessionEnd / SessionStart hook: 미커밋 변경이 남아 있으면 알린다.

세션이 끝날 때 산출물이 커밋되지 않은 채 방치되면 되돌릴 지점 없이 다음 작업에
들어가게 된다. 실제로 배치 3 산출물이 3일간 미커밋으로 남아, 권한 설정 변경이
다른 세션에 재현되지 않는 일이 있었다.

두 시점에 모두 붙인다 — 종료 시 알림은 그 자리에서 커밋할 기회를 주고, 시작 시
알림은 종료 알림을 놓쳤더라도 다음 세션에서 잔여를 잡아준다.

알림일 뿐 차단하지 않는다. 커밋 여부는 사람이 정한다.
"""
import json
import subprocess
import sys

MAX_LISTED = 10


def porcelain(cwd: str | None = None) -> list[str] | None:
    """git status --porcelain 결과를 줄 목록으로. 저장소가 아니면 None."""
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10, cwd=cwd,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    return [ln for ln in res.stdout.splitlines() if ln.strip()]


def current_branch(cwd: str | None = None) -> str:
    try:
        res = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=10, cwd=cwd,
        )
        return res.stdout.strip() or "(detached)"
    except (OSError, subprocess.SubprocessError):
        return "?"


def build_message(lines: list[str], branch: str, event: str) -> dict:
    if not lines:
        return {"suppressOutput": True}

    shown = lines[:MAX_LISTED]
    body = "\n".join(f"  {ln}" for ln in shown)
    if len(lines) > MAX_LISTED:
        body += f"\n  … 외 {len(lines) - MAX_LISTED}개"

    when = "이전 세션에서" if event == "SessionStart" else ""
    msg = (
        f"{when} 커밋되지 않은 변경 {len(lines)}개가 있습니다 (브랜치: {branch})\n"
        f"{body}\n"
        "공유 파일과 private/ 를 한 커밋에 섞지 않습니다 (CLAUDE.md 규칙 4)."
    ).strip()

    out: dict = {"systemMessage": msg}
    if event == "SessionStart":
        # 세션 시작 시에는 모델 컨텍스트에도 넣어 첫 응답이 이 상태를 알게 한다
        out["hookSpecificOutput"] = {
            "hookEventName": "SessionStart",
            "additionalContext": msg,
        }
    return out


def main() -> None:
    event = ""
    try:
        payload = json.load(sys.stdin)
        event = payload.get("hook_event_name", "") or ""
    except (json.JSONDecodeError, ValueError):
        pass

    lines = porcelain()
    if lines is None:  # git 저장소가 아니면 조용히 끝낸다
        print(json.dumps({"suppressOutput": True}))
        return
    print(json.dumps(build_message(lines, current_branch(), event), ensure_ascii=False))


if __name__ == "__main__":
    main()
