#!/usr/bin/env python3
"""컨텍스트 주입 정적 검증 (step2 도전1).

혼합 주입 전략의 연결이 올바른지 결정론적으로 검사한다:
  ① 컨텍스트 파일 8종이 .claude/context/ 에 존재하는가
  ② 항상 로드 2종이 CLAUDE.md 에 연결(@임포트)돼 있는가
  ③ 현존 소비자(에이전트·스킬 md)가 자기 몫 컨텍스트 경로를 참조하는가

자동 시뮬레이션 루프 개편으로 옛 3스킬·회고 전문가 4인이 폐기됐다. 새 루프 스킬
(아침 브리핑·위원회·시뮬 엔진·주간 회고)이 모두 신설돼, 그 소비자 링크를 ③에서 강제한다
(루프 오케스트레이션 항목의 check_context 마감). 실패 시 어떤 연결이 빠졌는지 출력하고
exit 1. (런타임에 모델이 지시를 실제로 따르는지는 A/B 비교가 검증 — 이 스크립트는 정적
연결만 책임진다.)

사용법: python3 scripts/check_context.py  (저장소 어디서 실행해도 됨)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTEXT_DIR = ".claude/context"

# ① 존재해야 하는 컨텍스트 파일 8종 (자동 시뮬레이션 루프 개편판)
#    retro-lessons.md(폐기)는 새 루프 회고용 loop-lessons.md로 교체됐다.
#    committee-personas.md는 위원회 항목에서 신설된 공유 페르소나 정의(정규위·긴급위·회고 공유).
#    etf-universe.md는 자산군 다변화 항목에서 신설된 상시 ETF 후보 목록(위원회가 계획 합의에서 Read).
CONTEXT_FILES = [
    "investor-profile.md",
    "trading-principles.md",
    "data-sources.md",
    "record-conventions.md",
    "market-glossary.md",
    "loop-lessons.md",
    "committee-personas.md",
    "etf-universe.md",
]

# ② 항상 로드: CLAUDE.md 가 @임포트로 연결해야 하는 2종
ALWAYS_LOADED = {
    "CLAUDE.md": ["investor-profile.md", "trading-principles.md"],
}

# ③ Read 지시: 소비자 md → 참조해야 하는 컨텍스트 (현존 소비자 강제)
#    옛 3스킬(analyze-company·recommend-stocks·portfolio-retrospect)과 회고 전문가 4인은
#    폐기됐다(os-docs-overhaul Q3·H2). 새 루프 스킬 4종(아침 브리핑·위원회·시뮬 엔진·주간 회고)이
#    모두 신설돼 여기서 강제한다(루프 오케스트레이션 항목의 check_context 마감 — 예정 소비자
#    블록을 현존 강제로 승격). 아침 브리핑용 웹검색 리서처 3종도 현존 소비자다.
CONSUMERS = {
    # data-sources → 아침 브리핑 웹검색 리서처 3종
    ".claude/agents/stock-trend-researcher.md": ["data-sources.md"],
    ".claude/agents/company-news-researcher.md": ["data-sources.md"],
    ".claude/agents/kr-macro-researcher.md": ["data-sources.md"],
    # 새 루프 스킬 4종 (신설 완료 — 현존 강제)
    ".claude/skills/morning-briefing/SKILL.md": ["data-sources.md", "record-conventions.md"],
    ".claude/skills/investment-committee/SKILL.md":
        ["record-conventions.md", "market-glossary.md", "committee-personas.md",
         "etf-universe.md"],
    ".claude/skills/sim-engine/SKILL.md":
        ["record-conventions.md", "market-glossary.md", "committee-personas.md"],
    ".claude/skills/weekly-retrospect/SKILL.md":
        ["record-conventions.md", "loop-lessons.md", "committee-personas.md"],
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
