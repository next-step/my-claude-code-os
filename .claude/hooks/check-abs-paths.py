#!/usr/bin/env python3
"""PreToolUse 훅: git commit 직전, 커밋될 변경에 "이 머신의 절대경로"가 있으면 커밋을 막는다.

AI가 작업하다 /Users/<나> · /home/<나> 같은 절대경로를 실수로 남기면 다른 환경에서 깨진다.
사람이 AI 코드를 다 읽지 않으므로, 커밋 시점에 "추가된 줄"을 검사해
발견되면 exit 2 로 커밋을 결정적으로 차단한다(없으면 항상 통과).

오탐 방지 두 가지:
- **이 머신의 경로만** 잡는다(실제 $HOME·사용자명 기반). 문서 속 예시 경로(/Users/alice,
  /home/runner 등 남의 경로)는 이식성 문제가 아니므로 차단하지 않는다.
- **부분 커밋 정합**: `git commit <경로들>` 은 스테이징과 무관하게 그 경로만 커밋되므로,
  명령에서 경로 인자를 파싱해 **커밋될 파일만** 검사한다(무관한 스테이징 파일로 차단 금지).
"""
import json
import os
import re
import shlex
import subprocess
import sys

# 이 가드 파일 자체는 패턴을 정의상 포함할 수 있으므로 검사에서 제외(자기 차단 방지).
SELF = ".claude/hooks/check-abs-paths.py"

# 값을 받는 커밋 옵션 — 다음 토큰은 경로가 아니다.
OPTS_WITH_VALUE = {"-m", "--message", "-F", "--file", "-C", "-c", "--reuse-message",
                   "--reedit-message", "--author", "--date", "-t", "--template",
                   "--fixup", "--squash", "--trailer", "--pathspec-from-file"}
STOPPERS = {"&&", "||", ";", "|"}


def machine_pattern():  # -> re.Pattern | None (유니온 표기는 py3.10+라 주석으로)
    """실제 이 머신을 특정하는 경로 패턴. 알 수 없으면 None(보수적 폴백은 호출부에서)."""
    parts = []
    home = os.path.expanduser("~")
    if home and home != "~":
        parts.append(re.escape(home))
    user = os.environ.get("USER") or os.environ.get("LOGNAME")
    if user:
        parts.append(rf"/(?:Users|home)/{re.escape(user)}\b")
    return re.compile("|".join(parts)) if parts else None


def commit_pathspec(cmd: str) -> list[str]:
    """명령 문자열에서 `git commit` 의 경로 인자만 뽑는다. 파싱 실패·없음이면 []."""
    try:
        toks = shlex.split(cmd)
    except ValueError:
        return []
    paths, in_commit, skip_next = [], False, False
    for i, t in enumerate(toks):
        if t in STOPPERS:
            in_commit = False
            continue
        if not in_commit:
            # "git [글로벌옵션] commit" 진입 감지
            if t == "commit" and "git" in toks[max(0, i - 4):i]:
                in_commit = True
            continue
        if skip_next:
            skip_next = False
            continue
        if t == "--":
            continue
        if t in OPTS_WITH_VALUE:
            skip_next = True
        elif not t.startswith("-"):
            paths.append(t)
    return paths


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # 입력 이상 시 흐름을 막지 않는다.

    if payload.get("tool_name") != "Bash":
        return 0
    cmd = (payload.get("tool_input") or {}).get("command", "")
    if "git commit" not in cmd:
        return 0  # 커밋 명령일 때만 검사

    pat = machine_pattern()
    if pat is None:
        return 0  # 머신을 특정 못 하면 검사 불가 — 막지 않는다.

    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    # 부분 커밋(git commit <경로>)이면 그 경로의 HEAD 대비 변경만,
    # 아니면 스테이징 전체를 검사한다 — "실제로 커밋될 것"과 검사 대상을 일치시킨다.
    paths = commit_pathspec(cmd)
    base = ["git", "diff", "--unified=0", "--no-color"]
    args = base + ["HEAD", "--"] + paths if paths else base + ["--cached"]
    try:
        diff = subprocess.run(args, cwd=root, capture_output=True, text=True, check=True).stdout
    except Exception:
        # HEAD 부재(리포 첫 커밋) 등으로 실패하면 스테이징 전체로 폴백 — 가드가 조용히 꺼지지 않게.
        try:
            diff = subprocess.run(base + ["--cached"], cwd=root,
                                  capture_output=True, text=True, check=True).stdout
        except Exception:
            return 0

    hits, cur = [], None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            if cur == SELF:
                continue  # 가드 파일 자체는 건너뜀
            if pat.search(line):
                hits.append(f"{cur}: {line[1:].strip()[:100]}")

    if hits:
        sys.stderr.write(
            "❌ 커밋 차단: 커밋될 변경에 이 머신의 절대경로가 있습니다 (다른 환경에서 깨짐).\n"
            "   $CLAUDE_PROJECT_DIR 등 상대/환경변수 경로로 바꾼 뒤 다시 커밋하세요:\n"
        )
        for h in hits[:20]:
            sys.stderr.write("   - " + h + "\n")
        return 2  # 도구(커밋) 차단

    return 0


if __name__ == "__main__":
    sys.exit(main())
