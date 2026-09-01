#!/usr/bin/env python3
# SKILL.md의 구조를 기계적으로 채점한다. skill-forge 오케스트레이터의 관문.
#
# 표준 라이브러리만 쓴다 — 스킬 하나 만들려고 의존성을 설치하게 만들지 않는다.
#
# 이 스크립트는 "구조가 갖춰졌는지"만 본다. 내용이 좋은지는 판정하지 않는다.
#   구조 판정  → 이 스크립트 (사람 없이 갈린다, 재현성이 있다)
#   내용 판정  → 서브에이전트 검토자·반박자 (SKILL.md 3~4단계)
# 둘을 섞으면 채점기가 자연어 판정으로 미끄러진다. OS.md 4절 규칙 7.
#
# 입력 : SKILL.md 경로 또는 스킬 디렉터리 (여러 개 가능)
# 출력 : 항목별 PASS/FAIL 표 + 기록 한 줄. --json 으로 기계용 출력.
# 종료 : 0 전부 통과 / 1 하나라도 실패 / 2 읽을 수 없음

import argparse
import json
import os
import re
import sys

MAX_DESC = 1024  # Claude Code가 description을 읽는 상한. 넘으면 잘린다.


def dwidth(text):
    """터미널 표시 폭. 한글·CJK는 두 칸으로 센다."""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def pad(text, width):
    return text + " " * max(0, width - dwidth(text))


def split_frontmatter(text):
    """(frontmatter dict, 본문) 반환. frontmatter가 없으면 (None, 전체)."""
    if not text.startswith("---"):
        return None, text
    end = re.search(r"(?m)^---\s*$", text[3:])
    if not end:
        return None, text
    raw = text[3:3 + end.start()]
    body = text[3 + end.end():]
    fm = {}
    for line in raw.splitlines():
        m = re.match(r"^([A-Za-z-]+)\s*:\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm, body


# ------------------------------------------------------------------ 검사 항목
# 각 항목은 (id, 라벨, 판정함수) — 판정함수는 (통과여부, 고칠 것) 을 돌려준다.
# 고칠 것 문장은 실패했을 때 "다음에 무엇을 하라"까지 말해야 한다. OS.md 6절 요건 3.

def check_frontmatter(fm, body, name):
    if fm is None:
        return False, "파일 첫 줄부터 --- 로 감싼 frontmatter 블록을 넣어라"
    return True, ""


def check_name(fm, body, name):
    if not fm or "name" not in fm:
        return False, "frontmatter에 name: 을 넣어라"
    if fm["name"] != name:
        return False, f"name({fm['name']})이 디렉터리명({name})과 다르다. 디렉터리명에 맞춰라"
    return True, ""


def check_description(fm, body, name):
    if not fm or not fm.get("description"):
        return False, "frontmatter에 description: 을 넣어라. 이 문장만 보고 호출 여부가 결정된다"
    if len(fm["description"]) > MAX_DESC:
        return False, f"description이 {len(fm['description'])}자다. {MAX_DESC}자 이하로 줄여라"
    return True, ""


def check_triggers(fm, body, name):
    desc = (fm or {}).get("description", "")
    n = len(re.findall(r"'[^']+'", desc))
    if n < 3:
        return False, (f"description에 트리거 문구가 {n}개다. 내가 실제로 쓰는 말을 "
                       "'따옴표'로 3개 이상 넣어라 (안 불리는 스킬의 1순위 원인)")
    return True, ""


def check_allowed_tools(fm, body, name):
    if not fm or "allowed-tools" not in fm:
        return False, "frontmatter에 allowed-tools: 를 넣어라. 필요한 도구만 열어야 한다"
    return True, ""


def check_title(fm, body, name):
    if not re.search(r"(?m)^# \S", body):
        return False, "본문에 '# 제목' H1 한 줄을 넣어라"
    return True, ""


def check_failure_mode(fm, body, name):
    if not re.search(r"(이 스킬의 실패|이 스킬이 막는|실패 모드)", body):
        return False, ("이 스킬이 무엇을 막는지 / 어떻게 실패하는지 적어라 "
                       "(\"이 스킬의 실패는 ~로 일어난다\" 또는 \"이 스킬이 막는 ~\")")
    return True, ""


def check_prohibition(fm, body, name):
    if not re.search(r"(금지|❌|하지 않는다|않는다\.)", body):
        return False, "금지 규칙을 적어라. 할 일만 적힌 스킬은 사고를 막지 못한다"
    return True, ""


def check_self_check(fm, body, name):
    if not re.search(r"(?m)^#{2,3} .*자기 점검", body):
        return False, "'## 출력 전 자기 점검' 섹션을 넣어라"
    return True, ""


def check_checkboxes(fm, body, name):
    n = len(re.findall(r"(?m)^- \[ \]", body))
    if n < 4:
        return False, f"자기 점검 체크박스가 {n}개다. '- [ ] ' 형식으로 4개 이상 넣어라"
    return True, ""


CHECKS = [
    ("frontmatter", "frontmatter 블록", check_frontmatter),
    ("name", "name 필드 · 디렉터리명 일치", check_name),
    ("description", "description 필드 · 길이", check_description),
    ("triggers", "트리거 문구 3개 이상", check_triggers),
    ("allowed-tools", "allowed-tools 필드", check_allowed_tools),
    ("title", "본문 H1 제목", check_title),
    ("failure-mode", "실패 모드 명시", check_failure_mode),
    ("prohibition", "금지 규칙 존재", check_prohibition),
    ("self-check", "출력 전 자기 점검 섹션", check_self_check),
    ("checkboxes", "체크박스 4개 이상", check_checkboxes),
]


def resolve(path):
    """디렉터리를 주면 그 안의 SKILL.md를 찾는다."""
    if os.path.isdir(path):
        return os.path.join(path, "SKILL.md")
    return path


def lint(path):
    target = resolve(path)
    name = os.path.basename(os.path.dirname(os.path.abspath(target)))
    try:
        with open(target, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        return {"path": target, "skill": name, "error": str(e), "results": [], "passed": 0}

    fm, body = split_frontmatter(text)
    results = []
    for cid, label, fn in CHECKS:
        ok, hint = fn(fm, body, name)
        results.append({"id": cid, "label": label, "ok": ok, "hint": hint})
    return {
        "path": target,
        "skill": name,
        "results": results,
        "passed": sum(1 for r in results if r["ok"]),
    }


def render(report):
    lines = []
    if report.get("error"):
        lines.append(f"{report['skill']} — 읽을 수 없다: {report['error']}")
        return "\n".join(lines), False

    total = len(report["results"])
    passed = report["passed"]
    lines.append(f"구조 검사 · {report['path']}")
    width = max(dwidth(r["label"]) for r in report["results"])
    for r in report["results"]:
        mark = "PASS" if r["ok"] else "FAIL"
        lines.append(f"  {mark}  {pad(r['label'], width)}")
        if not r["ok"]:
            lines.append(f"        → {r['hint']}")
    verdict = "PASS" if passed == total else "FAIL"
    lines.append("")
    # 기록 한 줄 — 주차별로 추적할 수 있게 한 줄로 남긴다. OS.md 6절 요건 4.
    lines.append(f"기록: {report['skill']} {verdict} {passed}/{total}")
    return "\n".join(lines), passed == total


def main():
    ap = argparse.ArgumentParser(description="SKILL.md의 구조를 기계적으로 채점한다.")
    ap.add_argument("paths", nargs="+", help="SKILL.md 경로 또는 스킬 디렉터리")
    ap.add_argument("--json", action="store_true", help="JSON으로 출력")
    args = ap.parse_args()

    reports = [lint(p) for p in args.paths]

    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
    else:
        outs = []
        for rep in reports:
            text, _ = render(rep)
            outs.append(text)
        print("\n\n".join(outs))

    if any(r.get("error") for r in reports):
        return 2
    return 0 if all(r["passed"] == len(CHECKS) for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
