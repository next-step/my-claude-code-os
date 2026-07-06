#!/usr/bin/env python3
"""컨텍스트 고정 로드량 측정 (step2 도전2).

"항상/매번 로드되는 양"(고정 로드량)을 결정론적으로 집계한다.
최적화 전후 수치 비교가 재실행 가능하도록 결정론적 스크립트로 측정한다
(OS 기존 규약: "정밀 수치=스크립트"). 실제 세션 토큰(/context·/cost)은
실행마다 변동이 커 비교가 흐려져 기각됐다(인터뷰 Q9).

집계 대상을 세 범주로 나눈다:
  - **항상 로드**: 매 세션마다 무조건 로드되는 본문.
    - CLAUDE.md 본문 + 거기에 @임포트된 컨텍스트 파일 2종(investor-profile·trading-principles)
    - 스킬 description 3종(SKILL.md frontmatter의 description 필드 — 목록에 항상 노출)
    - 에이전트 md의 항상 노출분(description/frontmatter 한 줄)
  - **호출 시 로드**: 스킬/에이전트가 실제로 소집됐을 때만 로드되는 본문.
    - 스킬 SKILL.md 본문(frontmatter 제외)
    - 에이전트 md 본문(frontmatter 제외)
    - 나머지 컨텍스트 파일 4종(소비자 Read 지시로 필요 시 로드)
  - **특정 단계 로드** (점진적 공개 최적화 도입 후): 스킬 실행 중 특정 단계에서만
    references/ 파일을 읽을 때 로드. 본문에서 분리한 긴 템플릿·스키마 상세.
    - .claude/skills/*/references/*.md

토큰은 근사치다(바이트/4 — 한국어+영어 혼합 대랪). 정확 토큰은 토크나이저가
아니라 이 스크립트의 목적이 아니다(상대 비교가 목적이므로 근사로 충분).

사용법:
  python3 scripts/measure_context.py                  # 현재 워크트리 측정
  python3 scripts/measure_context.py --root /path/to/repo  # 다른 경로(과거 커밋 워크트리 등)

출력: JSON(기계 판독용) + 사람 읽기 표.
"""
import argparse
import json
import re
import sys
from pathlib import Path


# ── 집계 대상 정의 ────────────────────────────────────────────────
# (인터뷰 파생 세부 1의 매핑과 check_context.py 구조를 따른다)

# 항상 로드: CLAUDE.md가 @임포트하는 컨텍스트 2종
ALWAYS_LOADED_CONTEXT = ["investor-profile.md", "trading-principles.md"]
# 호출 시 로드: 나머지 컨텍스트 4종
ON_DEMAND_CONTEXT = ["data-sources.md", "record-conventions.md",
                      "market-glossary.md", "retro-lessons.md"]

# 스킬 3종(메인 투자 스킬 — skill-stat은 인프라라 제외)
SKILLS = [
    ".claude/skills/analyze-company/SKILL.md",
    ".claude/skills/recommend-stocks/SKILL.md",
    ".claude/skills/portfolio-retrospect/SKILL.md",
]
# 에이전트 7종
AGENTS = [
    ".claude/agents/stock-trend-researcher.md",
    ".claude/agents/company-news-researcher.md",
    ".claude/agents/kr-macro-researcher.md",
    ".claude/agents/retro-technical-analyst.md",
    ".claude/agents/retro-fundamental-analyst.md",
    ".claude/agents/retro-macro-analyst.md",
    ".claude/agents/retro-skeptic.md",
]

CONTEXT_DIR = ".claude/context"
REFERENCES_GLOB = ".claude/skills/*/references/*.md"


# ── 유틸 ────────────────────────────────────────────────────────

def bytes_to_tokens(b: int) -> int:
    """근사 토큰: 바이트/4. 한국어 1글자 ≈ 2~3바이트·1토큰, 영어 4바이트≈1토큰
    이라 바이트/4는 한국어 비중 높은 문서를 약간 과소평가하지만
    상대 비교가 목적이므로 일관된 환산으로 충분하다."""
    return (b + 3) // 4  # 반올림


def read_bytes(path: Path) -> int:
    """파일이 없으면 0. 존재하면 UTF-8 바이트 수."""
    if not path.is_file():
        return 0
    return len(path.read_bytes())


def extract_description(text: str) -> str:
    """SKILL.md/에이전트 md의 frontmatter에서 description 필드 값만 추출.
    항상 로드분(목록 노출분)은 description 한 줄이다."""
    # frontmatter 블록 (--- ... ---)
    m = re.search(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return ""
    fm = m.group(1)
    # description: <값> (여러 줄이면 첫 줄만 — 여기선 모두 한 줄)
    m2 = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
    return m2.group(1).strip() if m2 else ""


def split_frontmatter_body(path: Path):
    """파일을 (frontmatter 바이트, 본문 바이트)로 분리.
    본문 = 호출 시 로드분. frontmatter의 description은 항상 로드분."""
    if not path.is_file():
        return 0, 0
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^(---\s*\n.*?\n---\s*\n)", text, re.DOTALL)
    if not m:
        return 0, len(text.encode("utf-8"))
    fm = m.group(1)
    body = text[m.end():]
    return len(fm.encode("utf-8")), len(body.encode("utf-8"))


# ── 집계 ─────────────────────────────────────────────────────────

def measure(root: Path) -> dict:
    """root 아래 파일들을 읽어 항상 로드/호출 시 로드/특정 단계 로드 분량을 집계."""
    always = {"files": [], "bytes": 0, "tokens": 0}
    ondemand = {"files": [], "bytes": 0, "tokens": 0}
    staged = {"files": [], "bytes": 0, "tokens": 0}  # 점진적 공개 references

    def add(bucket, label, b):
        bucket["files"].append({"path": label, "bytes": b, "tokens": bytes_to_tokens(b)})
        bucket["bytes"] += b
        bucket["tokens"] += bytes_to_tokens(b)

    # ── 항상 로드 ──
    # 1) CLAUDE.md 본문 전체(@임포트는 런타임에 확장되지만, 고정분은 CLAUDE.md 자체 바이트)
    add(always, "CLAUDE.md", read_bytes(root / "CLAUDE.md"))
    # 2) CLAUDE.md가 @임포트하는 컨텍스트 2종 (항상 로드)
    for name in ALWAYS_LOADED_CONTEXT:
        add(always, f"{CONTEXT_DIR}/{name}", read_bytes(root / CONTEXT_DIR / name))
    # 3) 스킬 description (항상 로드 — 스킬 목록에 노출)
    for rel in SKILLS:
        p = root / rel
        if p.is_file():
            desc = extract_description(p.read_text(encoding="utf-8"))
            add(always, f"{rel} (description)", len(desc.encode("utf-8")))
    # 4) 에이전트 description (항상 로드 — 에이전트 목록에 노출)
    for rel in AGENTS:
        p = root / rel
        if p.is_file():
            desc = extract_description(p.read_text(encoding="utf-8"))
            add(always, f"{rel} (description)", len(desc.encode("utf-8")))

    # ── 호출 시 로드 ──
    # 5) 스킬 SKILL.md 본문(frontmatter 제외)
    for rel in SKILLS:
        fm, body = split_frontmatter_body(root / rel)
        add(ondemand, f"{rel} (본문)", body)
    # 6) 에이전트 md 본문(frontmatter 제외)
    for rel in AGENTS:
        fm, body = split_frontmatter_body(root / rel)
        add(ondemand, f"{rel} (본문)", body)
    # 7) 나머지 컨텍스트 4종 (소비자 Read 지시로 필요 시 로드)
    for name in ON_DEMAND_CONTEXT:
        add(ondemand, f"{CONTEXT_DIR}/{name}", read_bytes(root / CONTEXT_DIR / name))
    # 8) 점진적 공개 references (스킬 특정 단계에서만 로드)
    for ref_path in sorted((root).glob(REFERENCES_GLOB)):
        rel = str(ref_path.relative_to(root))
        add(staged, rel, read_bytes(ref_path))

    total_bytes = always["bytes"] + ondemand["bytes"] + staged["bytes"]
    total_tokens = always["tokens"] + ondemand["tokens"] + staged["tokens"]
    return {
        "always": always,
        "ondemand": ondemand,
        "staged": staged,
        "total": {"bytes": total_bytes, "tokens": total_tokens},
    }


# ── 출력 ─────────────────────────────────────────────────────────

def print_report(result: dict, label: str):
    print(f"\n{'=' * 72}")
    print(f"  컨텍스트 고정 로드량 — {label}")
    print(f"{'=' * 72}")

    for cat, title in [("always", "항상 로드 (매 세션)"), ("ondemand", "호출 시 로드"), ("staged", "특정 단계 로드 (references)")]:
        bucket = result[cat]
        if not bucket["files"]:
            continue
        print(f"\n■ {title}  —  {bucket['bytes']:,} B / ~{bucket['tokens']:,} 토큰")
        print(f"  {'파일':<52} {'B':>8} {'~tok':>7}")
        print(f"  {'-' * 52} {'-' * 8} {'-' * 7}")
        for f in bucket["files"]:
            # 경로가 길면 뒤에 맞춤
            p = f["path"]
            if len(p) > 52:
                p = "..." + p[-49:]
            print(f"  {p:<52} {f['bytes']:>8,} {f['tokens']:>7,}")

    t = result["total"]
    print(f"\n■ 합계  —  {t['bytes']:,} B / ~{t['tokens']:,} 토큰")
    al = result["always"]["bytes"]
    od = result["ondemand"]["bytes"]
    st = result["staged"]["bytes"]
    if t["bytes"]:
        print(f"  항상 {al/t['bytes']*100:.1f}% · 호출 시 {od/t['bytes']*100:.1f}% · 특정 단계 {st/t['bytes']*100:.1f}%")


def main() -> int:
    ap = argparse.ArgumentParser(description="컨텍스트 고정 로드량 측정")
    ap.add_argument("--root", default=".", help="측정할 저장소 루트(기본: 현재 디렉토리)")
    ap.add_argument("--json", action="store_true", help="JSON만 출력(기계 판독)")
    ap.add_argument("--label", default=None, help="출력에 표시할 라벨(기본: 루트 경로)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"오류: {root} 가 디렉토리가 아니다", file=sys.stderr)
        return 1

    result = measure(root)

    if args.json:
        # JSON 모드는 라벨 없이 수치만
        out = {}
        for k, v in result.items():
            if k == "total":
                out[k] = {"bytes": v["bytes"], "tokens": v["tokens"]}
            else:
                out[k] = {"bytes": v["bytes"], "tokens": v["tokens"],
                          "files": v["files"]}
        print(json.dumps({"root": str(root), **out}, ensure_ascii=False, indent=2))
        return 0

    label = args.label or str(root)
    print_report(result, label)
    return 0


if __name__ == "__main__":
    sys.exit(main())