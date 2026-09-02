#!/usr/bin/env python3
"""정책·골든셋·실행이 다를 때 어느 쪽을 고칠지 귀책을 정하는 공통 심판.

라벨 비교만 한다. 속성 규칙은 프로필의 arbiter 어댑터가 갖는다.
사람 판정 원장(decisions.json)에는 쓰지 않는다. 여기 나오는 값은 전부 추천이다.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from catalog_profile import (
    PROJECT_ROOT,
    load_profile,
    output_root,
    project_path,
    relative_or_absolute,
)

UNDETERMINED = "UNDETERMINED"
UNRESOLVABLE = "UNRESOLVABLE"
NO_GOLD = (None, "", "UNCLASSIFIED")

OWNERS = {
    "GOLDEN": "골든셋을 고친다",
    "POLICY": "정책을 고친다",
    "RUNTIME": "실행을 고친다",
    "EVIDENCE": "근거를 더 모은다",
    "GOAL": "사람이 목표 기준으로 경계를 정한다",
    "PENDING_PRECEDENT": "미결 판례가 답해야 정해진다",
    "NONE": "충돌 없음",
}


def load_adapter(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("arbiter_adapter", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"어댑터를 불러올 수 없습니다: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "policy_answer"):
        raise SystemExit(f"어댑터에 policy_answer가 없습니다: {path}")
    return module


def read_precedents(directory: Path) -> dict[str, dict[str, str]]:
    """판례 frontmatter에서 id와 status를 읽는다."""
    found: dict[str, dict[str, str]] = {}
    if not directory.is_dir():
        return found
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if not match:
            continue
        meta: dict[str, str] = {}
        for line in match.group(1).splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                meta[key.strip()] = value.strip()
        if meta.get("id"):
            meta["path"] = str(path.relative_to(PROJECT_ROOT))
            found[meta["id"]] = meta
    return found


def merge_queue(queue_dir: Path) -> dict[str, dict[str, Any]]:
    """같은 상품이 여러 큐에 있으면 한 건으로 접는다. 필드가 가장 많은 행을 대표로 쓴다."""
    merged: dict[str, dict[str, Any]] = {}
    for path in sorted(queue_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = str(row.get("productKey") or "")
            if not key:
                continue
            entry = merged.setdefault(key, {"row": row, "signals": set()})
            entry["signals"].add(str(row.get("signal") or path.stem))
            if len(row) > len(entry["row"]):
                entry["row"] = row
    return merged


def decide(answer: dict[str, Any], gold: Any, observed: Any) -> tuple[str, str, bool]:
    """정책이 낸 답과 골든셋·실행을 비교해 귀책을 정한다. 도메인 지식을 쓰지 않는다."""
    label = answer["label"]
    strong = answer.get("strength") == "STRONG"
    if gold in NO_GOLD:
        return "GOLDEN", "골든셋에 정본 라벨이 없어 비교 자체가 성립하지 않는다.", False
    if label == UNRESOLVABLE:
        return "GOAL", "정책을 기계로 적용할 수 없다. 사람이 목표 기준으로 정한다.", False
    if label == UNDETERMINED:
        gap = observed not in NO_GOLD and observed != UNDETERMINED
        if gap:
            return "RUNTIME", "정책은 UNDETERMINED인데 실행이 라벨을 만들었다.", True
        return "EVIDENCE", "정책도 실행도 판정 불가인데 골든셋에는 답이 있다.", True
    if label == gold == observed:
        return "NONE", "정책·골든셋·실행이 모두 같다.", False
    if label == gold:
        return "RUNTIME", "정책과 골든셋이 같은데 실행만 다르다.", False
    if label == observed:
        if strong:
            return "GOLDEN", "정책의 강한 근거와 실행이 같은데 골든셋만 다르다.", False
        return "PENDING_PRECEDENT", "약한 근거라 골든셋을 의심할지 판례가 먼저 답해야 한다.", False
    if gold == observed:
        if strong:
            return "POLICY", "골든셋과 실행이 같은데 정책만 다르다. 정책이 목표를 옮기지 못했다.", False
        return "PENDING_PRECEDENT", "약한 근거라 정책을 의심할지 판례가 먼저 답해야 한다.", False
    return "GOAL", "정책·골든셋·실행이 셋 다 다르다.", False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()

    profile = load_profile(args.profile.resolve())
    root = args.output_root.resolve() if args.output_root else output_root(profile)

    goal_path = project_path(str(profile.get("goal") or ""))
    if not goal_path.is_file():
        raise SystemExit("프로필에 goal 문서 경로가 없거나 파일이 없습니다. 심판은 목표 없이 돌지 않습니다.")

    adapter_path = project_path(str((profile.get("adapters") or {}).get("arbiter") or ""))
    if not adapter_path.is_file():
        raise SystemExit(f"arbiter 어댑터가 없습니다: {adapter_path}")
    adapter = load_adapter(adapter_path)
    signal_precedents: dict[str, str] = getattr(adapter, "SIGNAL_PRECEDENTS", {})

    policy_cfg = profile.get("policy") or {}
    precedents = read_precedents(project_path(str(policy_cfg.get("precedents") or "")))
    open_ids = {pid for pid, meta in precedents.items() if meta.get("status", "OPEN").upper() == "OPEN"}

    merged = merge_queue(root / "queue")
    verdicts: list[dict[str, Any]] = []
    for key in sorted(merged):
        row = merged[key]["row"]
        signals = sorted(merged[key]["signals"])
        answer = adapter.policy_answer(row)
        gold = row.get("referenceLabel")
        observed = row.get("observedLabel")
        owner, reason, evidence_gap = decide(answer, gold, observed)

        blocked: set[str] = set()
        if owner != "NONE":
            blocked = {pid for pid in answer.get("blockedBy", []) if pid in open_ids}
            blocked |= {signal_precedents[s] for s in signals if signal_precedents.get(s) in open_ids}
        verdicts.append(
            {
                "productKey": key,
                "productName": row.get("productName"),
                "signals": signals,
                "policyAnswer": answer["label"],
                "policyRule": answer["rule"],
                "policyStrength": answer["strength"],
                "policyNote": answer["note"],
                "goldLabel": gold,
                "observedLabel": observed,
                "owner": owner,
                "ownerAction": OWNERS[owner],
                "reason": reason,
                "evidenceGap": evidence_gap,
                "blockedBy": sorted(blocked),
                "recommendation": True,
            }
        )

    review_dir = root / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    verdict_path = review_dir / "verdicts.jsonl"
    verdict_path.write_text(
        "".join(json.dumps(v, ensure_ascii=False, sort_keys=True) + "\n" for v in verdicts),
        encoding="utf-8",
    )

    owner_counts = Counter(v["owner"] for v in verdicts)
    blocked_counts = Counter(pid for v in verdicts for pid in v["blockedBy"])
    rule_counts = Counter(v["policyRule"] for v in verdicts)
    moved = Counter(
        (s, v["owner"]) for v in verdicts for s in v["signals"] if v["owner"] != "NONE"
    )

    report_dir = root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {profile['displayName']} · 심판 결과",
        "",
        f"- 목표 문서: `{goal_path.relative_to(PROJECT_ROOT)}`",
        f"- 정책 문서: `{policy_cfg.get('owned')}`",
        f"- 판정 대상: {len(verdicts)}건 (큐 중복 제거)",
        f"- 미결 판례: {', '.join(sorted(open_ids)) or '없음'}",
        "",
        "이 파일의 모든 판정은 **추천**이다. 사람 판정 원장에 자동으로 들어가지 않는다.",
        "",
        "## 귀책 분포",
        "",
        "| 고칠 곳 | 뜻 | 건수 |",
        "|---|---|---|",
    ]
    for owner, count in owner_counts.most_common():
        lines.append(f"| `{owner}` | {OWNERS[owner]} | {count} |")

    lines += ["", "## 적용된 정책 규칙", "", "| 규칙 | 건수 |", "|---|---|"]
    for rule, count in rule_counts.most_common():
        lines.append(f"| `{rule}` | {count} |")

    if blocked_counts:
        lines += ["", "## 미결 판례에 걸린 건수", "", "| 판례 | 건수 | 질문 |", "|---|---|---|"]
        for pid, count in blocked_counts.most_common():
            meta = precedents.get(pid, {})
            lines.append(f"| [{pid}]({meta.get('path','')}) | {count} | {meta.get('answers','')} |")

    lines += ["", "## 기존 신호가 어디로 갔나", "", "| 큐 신호 | 새 귀책 | 건수 |", "|---|---|---|"]
    for (signal, owner), count in sorted(moved.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| `{signal}` | `{owner}` | {count} |")
    lines.append("")

    report_path = report_dir / "arbiter.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")

    # 만든 것을 요약에 선언한다. 하류가 경로를 추측하기 시작하면 그것은 계약이 아니라 관습이다.
    summary_path = root / "run-summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if isinstance(summary, dict):
            artifacts = summary.setdefault("artifacts", {})
            artifacts["arbiterVerdicts"] = relative_or_absolute(verdict_path)
            artifacts["arbiterReport"] = relative_or_absolute(report_path)
            summary_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    print(
        json.dumps(
            {
                "generatedAt": datetime.now(UTC).isoformat(),
                "profileId": profile["id"],
                "goal": str(goal_path.relative_to(PROJECT_ROOT)),
                "adjudicated": len(verdicts),
                "owners": dict(owner_counts),
                "openPrecedents": sorted(open_ids),
                "blocked": dict(blocked_counts),
                "verdicts": str(verdict_path.relative_to(PROJECT_ROOT)),
                "report": str(report_path.relative_to(PROJECT_ROOT)),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
