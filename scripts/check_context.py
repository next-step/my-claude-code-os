#!/usr/bin/env python3
"""컨텍스트 주입 정적 검증 (step2 도전1).

혼합 주입 전략의 연결이 올바른지 결정론적으로 검사한다:
  ① 컨텍스트 파일 6종이 .claude/context/ 에 존재하는가
  ② 항상 로드 2종이 CLAUDE.md 에 연결(@임포트)돼 있는가
  ③ 각 소비자(SKILL.md·에이전트 md)가 자기 몫 컨텍스트 경로를 참조하는가

실패 시 어떤 연결이 빠졌는지 출력하고 exit 1. (런타임에 모델이 지시를
실제로 따르는지는 A/B 비교가 검증 — 이 스크립트는 정적 연결만 책임진다.)

사용법: python3 scripts/check_context.py  (저장소 어디서 실행해도 됨)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTEXT_DIR = ".claude/context"

# ① 존재해야 하는 컨텍스트 파일 6종
CONTEXT_FILES = [
    "investor-profile.md",
    "trading-principles.md",
    "data-sources.md",
    "record-conventions.md",
    "market-glossary.md",
    "retro-lessons.md",
]

# ② 항상 로드: CLAUDE.md 가 @임포트로 연결해야 하는 2종
ALWAYS_LOADED = {
    "CLAUDE.md": ["investor-profile.md", "trading-principles.md"],
}

# ③ Read 지시: 소비자 md → 참조해야 하는 컨텍스트 (인터뷰 파생 세부 1의 매핑)
CONSUMERS = {
    # data-sources → 웹검색 리서처 에이전트 3종
    ".claude/agents/stock-trend-researcher.md": ["data-sources.md"],
    ".claude/agents/company-news-researcher.md": ["data-sources.md"],
    ".claude/agents/kr-macro-researcher.md": ["data-sources.md"],
    # market-glossary → 회고 토론 전문가 4인
    ".claude/agents/retro-technical-analyst.md": ["market-glossary.md"],
    ".claude/agents/retro-fundamental-analyst.md": ["market-glossary.md"],
    ".claude/agents/retro-macro-analyst.md": ["market-glossary.md"],
    ".claude/agents/retro-skeptic.md": ["market-glossary.md"],
    # record-conventions → 기록을 남기는 스킬 3종 / retro-lessons → 분석·추천 2종
    ".claude/skills/analyze-company/SKILL.md": ["record-conventions.md", "retro-lessons.md"],
    ".claude/skills/recommend-stocks/SKILL.md": ["record-conventions.md", "retro-lessons.md"],
    ".claude/skills/portfolio-retrospect/SKILL.md": ["record-conventions.md"],
}


def main() -> int:
    failures = []
    checks = 0

    def check(ok: bool, label: str, detail: str = ""):
        nonlocal checks
        checks += 1
        mark = "✓" if ok else "✗"
        print(f"  {mark} {label}")
        if not ok:
            failures.append(f"{label}" + (f" — {detail}" if detail else ""))

    print("① 컨텍스트 파일 존재")
    for name in CONTEXT_FILES:
        path = ROOT / CONTEXT_DIR / name
        check(path.is_file(), f"{CONTEXT_DIR}/{name}", "파일이 없다")

    print("② 항상 로드 (CLAUDE.md @임포트)")
    for loader, wanted in ALWAYS_LOADED.items():
        loader_path = ROOT / loader
        if not loader_path.is_file():
            check(False, loader, "로더 파일 자체가 없다")
            continue
        text = loader_path.read_text(encoding="utf-8")
        for name in wanted:
            ref = f"@{CONTEXT_DIR}/{name}"
            check(ref in text, f"{loader} → {ref}",
                  f"CLAUDE.md 에 '{ref}' 임포트 줄을 추가해야 한다")

    print("③ Read 지시 (소비자 md → 컨텍스트 경로 참조)")
    for consumer, wanted in CONSUMERS.items():
        consumer_path = ROOT / consumer
        if not consumer_path.is_file():
            check(False, consumer, "소비자 md 파일이 없다")
            continue
        text = consumer_path.read_text(encoding="utf-8")
        for name in wanted:
            ref = f"{CONTEXT_DIR}/{name}"
            check(ref in text, f"{consumer} → {ref}",
                  f"본문에 '{ref}' Read 지시가 없다")

    print()
    if failures:
        print(f"FAIL — {len(failures)}/{checks} 연결이 빠졌다:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"PASS — {checks}개 연결 모두 정상.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
