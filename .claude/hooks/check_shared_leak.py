#!/usr/bin/env python3
"""PreToolUse hook: 공유 파일에 대상 프로젝트 고유명이 섞였는지 커밋 전에 막는다.

`step*` 브랜치는 미션 저장소로 PR을 보내는 공유 브랜치다. 사내 저장소명·환경변수명·
인프라 고유명이 한 번 커밋되면 git 히스토리에서 지우기 어려우므로, 커밋이 만들어지기
전에 차단한다 (ADR-0012 · ADR-0025).

금지어 목록을 이 파일에 적으면 **이 파일 자체가 공유 파일이라 유출이 된다.** 그래서
패턴은 gitignore된 별도 파일에 두고 여기서는 경로만 안다. `private/`가 아니라
`.local` 파일에 두는 이유는 브랜치를 바꿔도 남아 있어야 하기 때문이다 — `private/`는
`step*` 체크아웃 시 사라져 정작 위험한 브랜치에서 점검이 꺼진다.

patterns 파일 형식: 한 줄에 하나, `#`로 시작하면 주석, 빈 줄 무시.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
PATTERNS_PATH = HOOKS_DIR / "leak-patterns.local.txt"
# 개인 보관 경로 — 공유 대상이 아니므로 검사하지 않는다
PRIVATE_PREFIXES = ("private/",)
PRIVATE_FILES = ("CLAUDE.local.md",)


def load_patterns(path: Path) -> list[str]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def staged_shared_files(cwd: str | None = None) -> list[str]:
    """스테이징된 파일 중 공유 대상만 반환한다."""
    try:
        res = subprocess.run(
            ["git", "diff", "--staged", "--name-only", "--diff-filter=ACMR"],
            capture_output=True, text=True, timeout=10, cwd=cwd,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if res.returncode != 0:
        return []
    files = []
    for name in res.stdout.splitlines():
        name = name.strip()
        if not name:
            continue
        if name.startswith(PRIVATE_PREFIXES) or name in PRIVATE_FILES:
            continue
        files.append(name)
    return files


def scan(files: list[str], patterns: list[str], root: Path) -> list[tuple[str, int, str]]:
    """(파일, 줄번호, 매치된 패턴) 목록을 반환한다."""
    if not patterns:
        return []
    regex = re.compile("|".join(f"({re.escape(p)})" for p in patterns), re.IGNORECASE)
    hits = []
    for name in files:
        path = root / name
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue  # 바이너리 등은 건너뛴다
        for lineno, line in enumerate(text.splitlines(), 1):
            m = regex.search(line)
            if m:
                hits.append((name, lineno, m.group(0)))
    return hits


def build_output(hits: list[tuple[str, int, str]], patterns: list[str]) -> dict:
    if not patterns:
        return {
            "systemMessage": (
                "유출 점검이 꺼져 있습니다 — .claude/hooks/leak-patterns.local.txt 가 없습니다. "
                "공유 파일에 대상 프로젝트 고유명이 섞여도 잡히지 않습니다."
            )
        }
    if not hits:
        return {"suppressOutput": True}

    lines = [f"  {f}:{n} — \"{m}\"" for f, n, m in hits[:20]]
    if len(hits) > 20:
        lines.append(f"  … 외 {len(hits) - 20}건")
    reason = (
        "공유 파일에 대상 프로젝트 고유명이 있어 커밋을 막았습니다 (ADR-0012 · ADR-0025).\n"
        + "\n".join(lines)
        + "\n\n해당 내용을 private/ 아래로 옮기거나 추상 표현으로 바꾼 뒤 다시 커밋하세요. "
        "오탐이면 .claude/hooks/leak-patterns.local.txt 에서 해당 패턴을 조정하면 됩니다."
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def main() -> None:
    try:
        json.load(sys.stdin)  # payload는 쓰지 않지만 stdin은 비워둔다
    except (json.JSONDecodeError, ValueError):
        pass

    root = Path.cwd()
    patterns = load_patterns(PATTERNS_PATH)
    files = staged_shared_files()
    hits = scan(files, patterns, root)
    print(json.dumps(build_output(hits, patterns), ensure_ascii=False))


if __name__ == "__main__":
    main()
