#!/usr/bin/env python3
"""PreToolUse 훅 (matcher: Write|Edit).

.claude 하위 파일에 머신 종속 절대경로(/Users/..., /home/...)가 쓰이는 것을 차단한다.
다른 머신·다른 사용자 환경에서 Claude OS가 깨지는 실수를 예방하는 가드.

동작: 차단 시 exit 2 → 도구 호출이 거부되고 stderr 메시지가 Claude에게 피드백된다.
예외: .claude/hooks/ 하위(이 스크립트 자신처럼 경로 패턴을 코드로 다루는 파일)는 검사 제외.
"""
import json
import os
import re
import sys


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # 입력 파싱 실패 시 차단하지 않음 (가드는 보조 장치)

    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or ""
    if not (file_path and project_dir):
        return 0

    rel = os.path.relpath(os.path.abspath(file_path), os.path.abspath(project_dir))
    inside_claude = rel == ".claude" or rel.startswith(".claude" + os.sep)
    is_hook_file = rel.startswith(os.path.join(".claude", "hooks") + os.sep)
    if not inside_claude or is_hook_file:
        return 0

    # Write는 content, Edit는 new_string만 검사 (old_string은 기존 내용이므로 제외)
    new_text = "\n".join(str(tool_input.get(k) or "") for k in ("content", "new_string"))
    pattern = re.compile(r"(?:/Users|/home)/[A-Za-z0-9._~-]+(?:/[^\s\"'`)\]]*)?")
    hits = sorted(set(m.group(0) for m in pattern.finditer(new_text)))
    if hits:
        print(
            "[absolute-path-guard] .claude 하위 파일에 머신 종속 절대경로가 감지되어 차단했습니다:\n"
            + "\n".join(f"  - {h}" for h in hits)
            + "\n프로젝트 상대경로(예: .claude/scripts/foo.py)나 $CLAUDE_PROJECT_DIR 변수를 사용하세요.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
