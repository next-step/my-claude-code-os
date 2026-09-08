#!/usr/bin/env python3
"""A1/A4 기계 채점.

grader 서브에이전트에게 맡기지 않고 스크립트로 재는 두 assertion만 다룬다.
`SKILL.md:214`가 "프로그램으로 확인 가능한 것은 스크립트로 써라"라고 권한다 —
사람이 눈으로 세면 런마다 기준이 흔들리기 때문이다.

한계(의도적으로 남김):
- A1은 '번호가 붙어 분리돼 있는가'만 본다. 그 항목이 인수기준으로서 말이 되는지는
  보지 않는다. 그건 A2가 grader에게 묻는 것이다.
- A4는 '코드를 안 썼는가'를 파일 확장자와 코드펜스로 근사한다. 산문 안에 섞인
  의사코드는 잡지 못한다.

사용법: python3 grade_mechanical.py <iteration-dir>
"""
import json
import re
import sys
from pathlib import Path

# 번호가 붙은 항목으로 인정하는 형태.
#
# 1차 버전은 형태별로 정규식 4개를 나열했다가 `## AC-1: ...` 제목형을 통째로
# 놓쳤다(0개로 오판). 이 저장소가 세 번 기록한 실패 —— 정규식은 미리 정한 만큼만
# 본다 —— 가 그대로 재현된 것이라, 열거를 버리고 규칙 하나로 바꿨다:
#   줄 앞의 마크다운 잡음(#, -, *, |, >, 굵게)을 걷어낸 뒤
#   맨 앞에 오는 라벨(AC-1 / 1. / 1)) 을 잡고, **라벨을 유일값으로 센다.**
# 유일값으로 세는 이유: 같은 AC가 제목과 표 행에 두 번 나와도 항목 2개가 아니다.
LABEL = re.compile(
    r"^[#\s\-*+|>]*\**\s*(?:(AC)[-_ ]?(\d+)|(\d+)[.)])(?=[\s:.)\]|*]|$)",
    re.I,
)

# 한계: 본문 중 "- AC-6은 범위 밖" 같은 참조 줄도 라벨로 세어 과대 계수될 수 있다.
# A1 기준이 "3개 이상"이라 통과/탈락을 뒤집을 위험은 낮다고 보고 허용한다.

# 구현/테스트 코드로 간주하는 토큰. 코드펜스 안에서만 찾는다.
CODE_TOKENS = re.compile(
    r"\b(?:describe|it|test)\s*\(|\bassert\w*\s*\(|\bfunction\s+\w+\s*\(|"
    r"\bmodule\.exports\b|\brequire\s*\(|\bdef\s+\w+\s*\(|=>\s*\{",
)
FENCE = re.compile(r"^```(\w*)", re.M)


def count_items(text: str) -> int:
    labels = set()
    for line in text.splitlines():
        m = LABEL.match(line)
        if not m:
            continue
        labels.add(("ac", m.group(2)) if m.group(1) else ("n", m.group(3)))
    return len(labels)


def find_code(text: str):
    """코드펜스 블록만 훑어 구현/테스트 코드 토큰을 찾는다."""
    hits = []
    parts = text.split("```")
    # 홀수 인덱스가 펜스 내부
    for i in range(1, len(parts), 2):
        block = parts[i]
        lang = block.split("\n", 1)[0].strip().lower()
        body = block.split("\n", 1)[1] if "\n" in block else ""
        m = CODE_TOKENS.search(body)
        if m:
            hits.append(f"```{lang or '?'} 블록에 `{m.group(0).strip()}`")
    return hits


def grade_run(run_dir: Path) -> dict:
    out = run_dir / "outputs"
    md_files = sorted(out.glob("*.md")) if out.is_dir() else []
    other = sorted(p for p in out.iterdir() if p.is_file() and p.suffix != ".md") if out.is_dir() else []

    if not md_files:
        return {
            "A1": (False, "outputs/에 .md 산출물이 없다"),
            "A4": (False, "산출물이 없어 판정 불가 — 실패로 센다"),
        }

    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in md_files)

    n = count_items(text)
    a1 = (n >= 3, f"번호 붙은 항목 {n}개 검출 (기준 3개)")

    reasons = []
    if other:
        reasons.append("outputs/에 .md 아닌 파일: " + ", ".join(p.name for p in other))
    reasons += find_code(text)
    a4 = (not reasons, "; ".join(reasons) if reasons else "코드 파일 없음, 코드펜스에 구현/테스트 토큰 없음")

    return {"A1": a1, "A4": a4}


def main() -> int:
    it = Path(sys.argv[1])
    results = {}
    for eval_dir in sorted(d for d in it.iterdir() if d.is_dir()):
        for arm_dir in sorted(d for d in eval_dir.iterdir() if d.is_dir()):
            for run_dir in sorted(d for d in arm_dir.iterdir() if d.is_dir()):
                key = f"{eval_dir.name}/{arm_dir.name}/{run_dir.name}"
                results[key] = {k: {"passed": v[0], "evidence": v[1]}
                                for k, v in grade_run(run_dir).items()}
    dest = it / "mechanical_grades.json"
    dest.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for k, v in results.items():
        print(f"{k}: A1={'PASS' if v['A1']['passed'] else 'FAIL'} ({v['A1']['evidence']}) "
              f"| A4={'PASS' if v['A4']['passed'] else 'FAIL'} ({v['A4']['evidence']})")
    print(f"\n-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
