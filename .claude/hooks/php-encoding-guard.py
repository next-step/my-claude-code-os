#!/usr/bin/env python3
"""Pre/PostToolUse(Edit|Write) — preserve per-file encoding in the legacy checkout.

The legacy PHP tree is not uniformly encoded. Measured in the target checkout:
two data-access files of the same service, two directories apart, are UTF-8 and
EUC-KR/CP949 respectively. An agent that writes Korean into the wrong one produces
a file that decodes as neither, and the page renders mojibake in production.
Nothing in the test suite catches it, because the bytes are only wrong for humans.

The concrete filenames are deliberately not quoted here: this file is tracked and
the repository is public, and a path from the legacy tree is company information
just as much as the code inside it.

So the encoding is measured before the edit and re-measured after:

  PreToolUse   record path -> encoding in .claude/.state/php-encoding.json
  PostToolUse  re-detect; block if it changed or became undecodable

Files outside the legacy root are ignored. Pure-ASCII files carry no constraint.
Exit 2 on the Post phase blocks and tells Claude how to repair.
"""
import json
import os
import sys

STATE = os.path.join(".claude", ".state", "php-encoding.json")
WATCHED_SUFFIXES = (".php", ".inc", ".html", ".htm", ".js", ".css", ".tpl")


def detect(path):
    """'ascii' | 'utf-8' | 'cp949' | 'undecodable' | None(missing)."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    if not raw:
        return "ascii"
    try:
        raw.decode("ascii")
        return "ascii"
    except UnicodeDecodeError:
        pass
    # UTF-8 first: a byte sequence valid as UTF-8 is almost never CP949 Korean by
    # accident, while the reverse happens often. This is the same order `file` uses.
    for enc in ("utf-8", "cp949"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "undecodable"


def legacy_root(project_dir):
    cfg = os.path.join(project_dir, ".claude", "config", "workspace.json")
    try:
        with open(cfg, encoding="utf-8") as fh:
            return (json.load(fh).get("legacy") or {}).get("root") or None
    except (OSError, json.JSONDecodeError):
        return None


def load_state(project_dir):
    try:
        with open(os.path.join(project_dir, STATE), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(project_dir, state):
    path = os.path.join(project_dir, STATE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Keep the file from growing without bound across a long session.
    if len(state) > 200:
        state = dict(list(state.items())[-100:])
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh)


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path")
    if not path or not path.endswith(WATCHED_SUFFIXES):
        return 0

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    root = legacy_root(project_dir)
    if not root or not os.path.abspath(path).startswith(os.path.abspath(root)):
        return 0

    event = payload.get("hook_event_name", "")
    state = load_state(project_dir)

    if event == "PreToolUse":
        before = detect(path)
        if before is not None:
            state[path] = before
            save_state(project_dir, state)
        return 0

    # PostToolUse
    before = state.pop(path, None)
    save_state(project_dir, state)
    after = detect(path)

    if after == "undecodable":
        sys.stderr.write(
            f"인코딩이 깨졌습니다: {path}\n"
            f"  편집 전: {before or '알 수 없음'} -> 편집 후: 어떤 인코딩으로도 디코딩 불가\n\n"
            "한 파일 안에 서로 다른 인코딩의 바이트가 섞였습니다. 편집을 되돌리세요.\n"
            + (
                f"이 파일의 원본 인코딩은 {before} 입니다 — 그 인코딩으로만 쓰세요.\n"
                if before in ("utf-8", "cp949")
                else "되돌린 뒤 원본 인코딩을 먼저 확인하세요.\n"
            )
            + "  (한글을 넣지 않고 ASCII 만 쓰면 이 문제를 통째로 피할 수 있습니다)\n"
        )
        return 2

    if before in ("utf-8", "cp949") and after in ("utf-8", "cp949") and before != after:
        sys.stderr.write(
            f"파일 인코딩이 바뀌었습니다: {path}\n"
            f"  {before} -> {after}\n\n"
            "이 레거시 트리는 파일마다 인코딩이 다르고, 페이지 헤더가 원래 인코딩을\n"
            "선언합니다. 인코딩을 바꾸면 화면이 깨집니다. 되돌린 뒤 원본 인코딩을 유지하세요.\n"
            "  (한글을 넣지 않고 ASCII 식별자만 쓰면 이 문제를 통째로 피할 수 있습니다)\n"
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
