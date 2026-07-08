#!/usr/bin/env python3
"""컨텍스트 주입 정적 검증 (step2 도전1).

혼합 주입 전략의 연결이 올바른지 결정론적으로 검사한다:
  ① 컨텍스트 파일 6종이 .claude/context/ 에 존재하는가
  ② 항상 로드 2종이 CLAUDE.md 에 연결(@임포트)돼 있는가
  ③ 현존 소비자(에이전트 md)가 자기 몫 컨텍스트 경로를 참조하는가
  ④ 새 루프 스킬(위원회·시뮬·회고 등, 아직 미신설)은 존재하면 검사, 없으면 건너뜀

자동 시뮬레이션 루프 개편으로 옛 3스킬·회고 전문가 4인이 폐기됐다. 새 루프 스킬은
후속 항목에서 신설되며, 그 소비자 링크는 ④에서 스킬이 생기는 대로 자동 검증된다.
실패 시 어떤 연결이 빠졌는지 출력하고 exit 1. (런타임에 모델이 지시를
실제로 따르는지는 A/B 비교가 검증 — 이 스크립트는 정적 연결만 책임진다.)

사용법: python3 scripts/check_context.py  (저장소 어디서 실행해도 됨)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTEXT_DIR = ".claude/context"

# ① 존재해야 하는 컨텍스트 파일 6종 (자동 시뮬레이션 루프 개편판)
#    retro-lessons.md(폐기)는 새 루프 회고용 loop-lessons.md로 교체됐다.
CONTEXT_FILES = [
    "investor-profile.md",
    "trading-principles.md",
    "data-sources.md",
    "record-conventions.md",
    "market-glossary.md",
    "loop-lessons.md",
]

# ② 항상 로드: CLAUDE.md 가 @임포트로 연결해야 하는 2종
ALWAYS_LOADED = {
    "CLAUDE.md": ["investor-profile.md", "trading-principles.md"],
}

# ③ Read 지시: 소비자 md → 참조해야 하는 컨텍스트 (현존 소비자만 강제)
#    옛 3스킬(analyze-company·recommend-stocks·portfolio-retrospect)과 회고 전문가 4인은
#    폐기됐다(os-docs-overhaul Q3·H2). 지금 현존하는 소비자는 아침 브리핑용 웹검색 리서처
#    3종뿐이다. record-conventions·market-glossary·loop-lessons를 소비할 새 루프 스킬
#    (위원회·시뮬 엔진·주간 회고)은 아직 존재하지 않으므로, 그 소비자 링크는 스킬 신설 항목에서
#    마감한다. 존재하지 않는 스킬 경로를 여기서 강제하지 않는다(PLANNED_CONSUMERS 참고).
CONSUMERS = {
    # data-sources → 아침 브리핑 웹검색 리서처 3종 (현존)
    ".claude/agents/stock-trend-researcher.md": ["data-sources.md"],
    ".claude/agents/company-news-researcher.md": ["data-sources.md"],
    ".claude/agents/kr-macro-researcher.md": ["data-sources.md"],
}

# 새 루프 스킬 신설 시 잇기로 예정된 소비자 링크(존재하면 검사, 없으면 건너뛴다).
# record-conventions·market-glossary·loop-lessons를 소비할 스킬은 후속 항목에서 만든다.
PLANNED_CONSUMERS = {
    ".claude/skills/investment-committee/SKILL.md":
        ["record-conventions.md", "market-glossary.md"],
    ".claude/skills/morning-briefing/SKILL.md": ["data-sources.md", "record-conventions.md"],
    ".claude/skills/sim-engine/SKILL.md": ["record-conventions.md", "market-glossary.md"],
    ".claude/skills/weekly-retrospect/SKILL.md": ["record-conventions.md", "loop-lessons.md"],
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

    print("④ 예정 소비자 (새 루프 스킬 — 존재하면 검사, 없으면 건너뜀)")
    planned_pending = 0
    for consumer, wanted in PLANNED_CONSUMERS.items():
        consumer_path = ROOT / consumer
        if not consumer_path.is_file():
            planned_pending += 1
            print(f"  · {consumer} — 미신설(스킬 신설 항목에서 마감)")
            continue
        text = consumer_path.read_text(encoding="utf-8")
        for name in wanted:
            ref = f"{CONTEXT_DIR}/{name}"
            check(ref in text, f"{consumer} → {ref}",
                  f"본문에 '{ref}' Read 지시가 없다")
    if planned_pending:
        print(f"  ({planned_pending}개 예정 스킬은 아직 없어 검증 대상에서 제외)")

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
