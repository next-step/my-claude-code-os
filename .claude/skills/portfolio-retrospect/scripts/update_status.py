#!/usr/bin/env python3
"""회고 결과 반영 — 원본 분석 기록의 frontmatter `status:` 줄만 *제자리* 교체한다.

설계(OS.md "기록 방식 A" + append-only):
- status 는 save_analysis.py 가 `open` 으로 비워두고 "회고가 갱신"하라고 만든 칸이다.
  그래서 이 칸을 채우는 건 '예측을 고치는 것'이 아니라 '평가를 덧붙이는 것'이다.
- 진짜 박제 대상(진입/목표/손절·근거·본문)은 **절대 건드리지 않는다.** 오직 status: 한 줄만.
- 이 분리 덕에 save_run.py 추천표가 분석 기록의 status 를 역참조하면 회고 결과가 자동 반영된다.

안전장치:
- frontmatter(첫 `---`~`---`) 안의 `status:` 만 바꾼다. 본문에 'status:' 가 있어도 안 건드림.
- 허용 status 값만 받는다(open|hit_target|stopped|watching).
- 변경 없음(같은 값)이면 건너뛴다. 파일에 status 줄이 없으면 frontmatter 끝에 추가.

입력 JSON(stdin 또는 argv[1]):
{"updates": [{"file": "data/analyses/2026-06-20-기아.md", "status": "hit_target"}, ...]}
  - file 은 evaluate_records.py 가 돌려준 그 경로를 그대로 쓴다.
출력: {"changed":[...], "skipped":[...], "errors":[...]} JSON
"""
from __future__ import annotations
import json
import os
import re
import sys

ALLOWED = {"open", "hit_target", "stopped", "watching"}


def update_one(path: str, new_status: str) -> tuple[str, str]:
    """(결과종류, 메시지). 결과종류 ∈ changed|skipped|error."""
    if new_status not in ALLOWED:
        return "error", f"허용되지 않은 status: {new_status} (가능: {sorted(ALLOWED)})"
    abspath = path if os.path.isabs(path) else os.path.join(os.getcwd(), path)
    if not os.path.exists(abspath):
        return "error", f"파일 없음: {path}"
    text = open(abspath, encoding="utf-8").read()

    m = re.match(r"^(---\n)(.*?)(\n---)", text, re.S)
    if not m:
        return "error", f"frontmatter 없음: {path}"
    head, fm_body, tail = m.group(1), m.group(2), m.group(3)
    rest = text[m.end():]

    cur = re.search(r"^status:\s*(.*)$", fm_body, re.M)
    if cur and cur.group(1).strip() == new_status:
        return "skipped", f"{path}: 이미 {new_status}"

    if cur:
        new_fm = re.sub(r"^status:.*$", f"status: {new_status}", fm_body, count=1, flags=re.M)
    else:  # status 줄이 없으면 frontmatter 끝에 추가
        new_fm = fm_body.rstrip("\n") + f"\nstatus: {new_status}"

    with open(abspath, "w", encoding="utf-8") as f:
        f.write(head + new_fm + tail + rest)
    old = cur.group(1).strip() if cur else "(없음)"
    return "changed", f"{path}: {old} → {new_status}"


def main() -> int:
    raw = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else sys.stdin.read()
    data = json.loads(raw)
    out = {"changed": [], "skipped": [], "errors": []}
    for u in data.get("updates", []):
        kind, msg = update_one(u.get("file", ""), u.get("status", ""))
        {"changed": out["changed"], "skipped": out["skipped"], "error": out["errors"]}[kind].append(msg)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
