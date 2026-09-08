#!/usr/bin/env python3
"""컨텍스트 주입 연결 검증 테스트.

이 OS의 전제 — "모든 컨텍스트 파일은 자동 주입 경로를 가진다" — 를 정적으로
검사한다. 사람이 grep으로 확인하던 것을 고정한 것 (docs/share/context-injection-map.html
의 연결 지도가 검사 기준의 원본).

실행: python3 .claude/tests/test_context_injection.py  (실패 시 exit 1)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / ".claude" / "skills"
AGENTS_DIR = ROOT / ".claude" / "agents"

# 검사 4(쓰기 연결)의 기준: OS.md "문서 · SSOT" 표의 '쓰는 스킬' 열
SSOT_WRITERS = {
    "experiments/": "experiment",
    "knowledge/": "research",
    "metrics.md": "retrospect",
    "project.md": "os",
}
# 프로젝트 밖(플러그인)에서 오는 에이전트는 존재 검사에서 제외
EXTERNAL_AGENTS = {"adr-writer"}

failures = []


def check(name: str, ok: bool, detail: str) -> None:
    print(f"{'✅' if ok else '❌'} {name} — {detail}")
    if not ok:
        failures.append(name)


def skill_texts() -> dict:
    return {
        p.parent.name: p.read_text(encoding="utf-8")
        for p in sorted(SKILLS_DIR.glob("*/SKILL.md"))
    }


def main() -> int:
    skills = skill_texts()

    # 1. 컨텍스트 파일 존재 (6종, 파일 수 5개 이상)
    roots = ["CLAUDE.md", "OS.md", "metrics.md", "project.md"]
    missing = [f for f in roots if not (ROOT / f).is_file()]
    exp = list((ROOT / "experiments").glob("*.md"))
    kn = list((ROOT / "knowledge").glob("*.md"))
    total = len(roots) - len(missing) + len(exp) + len(kn)
    check(
        "1. 컨텍스트 파일 존재",
        not missing and exp and kn and total >= 5,
        f"루트 4종{'(누락: ' + ', '.join(missing) + ')' if missing else ''} + "
        f"experiments {len(exp)}개 + knowledge {len(kn)}개 = 총 {total}개 (기준 ≥5)",
    )

    # 2. 하네스 층 연결 — CLAUDE.md가 OS.md 읽기를 지시하는가
    claude_md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8") if (ROOT / "CLAUDE.md").is_file() else ""
    check(
        "2. 하네스 층 연결 (CLAUDE.md → OS.md)",
        "OS.md" in claude_md,
        "CLAUDE.md 본문에 OS.md 참조 있음" if "OS.md" in claude_md
        else "CLAUDE.md에 OS.md 참조 없음 — 무조건 주입 사슬 절단",
    )

    # 3. 읽기 연결 — SSOT마다 참조하는 스킬이 1개 이상
    for ssot in SSOT_WRITERS:
        readers = [name for name, text in skills.items() if ssot in text]
        check(
            f"3. 읽기 연결: {ssot}",
            len(readers) >= 1,
            f"참조 스킬 {len(readers)}개: {', '.join(readers) if readers else '없음 — 고아 문서'}",
        )

    # 4. 쓰기 연결 — 갱신 루프의 writer 스킬이 해당 SSOT를 언급하는가
    for ssot, writer in SSOT_WRITERS.items():
        text = skills.get(writer, "")
        check(
            f"4. 쓰기 연결: {writer} → {ssot}",
            ssot in text,
            "OS.md SSOT 표의 쓰기 관계가 스킬 절차서에 반영됨" if ssot in text
            else f"/{writer} SKILL.md가 {ssot}를 언급하지 않음 — 갱신 루프 단절 의심",
        )

    # 5. 에이전트 참조 무결성 — 스킬이 언급한 에이전트가 실제로 존재
    referenced = set()
    for text in skills.values():
        referenced |= set(
            re.findall(
                r"\b[a-z]+-(?:analyst|reporter|investigator|curator|applier|measurer|researcher|drafter|writer)\b",
                text,
            )
        )
    referenced -= EXTERNAL_AGENTS
    ghosts = sorted(a for a in referenced if not (AGENTS_DIR / f"{a}.md").is_file())
    check(
        "5. 에이전트 참조 무결성",
        not ghosts,
        f"참조 {len(referenced)}개 전부 실존" if not ghosts else f"정의 없는 에이전트 참조: {', '.join(ghosts)}",
    )

    print()
    if failures:
        print(f"FAIL — {len(failures)}건: {', '.join(failures)}")
        return 1
    print("PASS — 컨텍스트 주입 연결 이상 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
