#!/usr/bin/env python3
"""현재 검토 큐와 사람 판정 원장을 합쳐 진행률을 만든다."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from catalog_profile import PROJECT_ROOT, default_profile, load_profile, output_root


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: object expected")
    return value


def queued_products(queue_dir: Path) -> dict[str, set[str]]:
    products: dict[str, set[str]] = defaultdict(set)
    for path in sorted(queue_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                row = json.loads(line)
                product_key = str(row.get("productKey") or "")
                if product_key:
                    products[product_key].add(str(row.get("signal") or path.stem))
    return products


def latest_decisions(decision_path: Path) -> dict[str, dict[str, Any]]:
    if not decision_path.is_file():
        return {}
    ledger = read_json(decision_path)
    if ledger.get("schemaVersion") != "catalog-review-v1":
        raise SystemExit("지원하지 않는 판정 원장 버전입니다.")
    decisions = ledger.get("decisions")
    if not isinstance(decisions, list):
        raise SystemExit("decisions는 배열이어야 합니다.")
    latest: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        product_key = str(decision.get("productKey") or "")
        if product_key:
            latest[product_key] = decision
    return latest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--queue-dir", type=Path)
    parser.add_argument("--decision-file", type=Path)
    parser.add_argument("--status-file", type=Path)
    parser.add_argument("--report-file", type=Path)
    parser.add_argument("--run-summary-file", type=Path)
    args = parser.parse_args()
    profile = load_profile(args.profile or default_profile())
    root = args.output_root.resolve() if args.output_root else output_root(profile)
    queue_dir = args.queue_dir.resolve() if args.queue_dir else root / "queue"
    decision_path = (
        args.decision_file.resolve() if args.decision_file else root / "review" / "decisions.json"
    )
    status_path = args.status_file.resolve() if args.status_file else root / "review" / "status.json"
    report_path = (
        args.report_file.resolve() if args.report_file else root / "reports" / "review-progress.md"
    )
    run_summary_path = (
        args.run_summary_file.resolve() if args.run_summary_file else root / "run-summary.json"
    )

    products = queued_products(queue_dir)
    decisions = latest_decisions(decision_path)
    pending = sorted(key for key in products if key not in decisions)
    deferred = sorted(
        key for key in products if decisions.get(key, {}).get("decision") == "DEFERRED"
    )
    adjudicated = sorted(
        key
        for key in products
        if key in decisions and decisions[key].get("decision") != "DEFERRED"
    )
    stale_decisions = sorted(key for key in decisions if key not in products)
    decision_counts = Counter(
        str(decisions[key].get("decision")) for key in products if key in decisions
    )
    total = len(products)
    completed_count = len(adjudicated)
    status = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "queuedProducts": total,
        "adjudicatedProducts": completed_count,
        "deferredProducts": len(deferred),
        "pendingProducts": len(pending),
        "adjudicationRate": completed_count / total if total else 1.0,
        "decisionCounts": dict(sorted(decision_counts.items())),
        "pendingSample": [
            {"productKey": key, "signals": sorted(products[key])} for key in pending[:20]
        ],
        "staleDecisionProductKeys": stale_decisions,
    }
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(
        json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    pending_lines = (
        "\n".join(
            f"- `{item['productKey']}`: {', '.join(item['signals'])}"
            for item in status["pendingSample"]
        )
        or "- 없음"
    )
    report_path.write_text(
        f"""# {profile['displayName']} 사람 검토 진행률

- 중복 제거된 검토 대상: {total}건
- 판정 완료: {completed_count}건
- 보류: {len(deferred)}건
- 미판정: {len(pending)}건
- 판정률: {status['adjudicationRate']:.2%}
- 판정 분포: {status['decisionCounts']}

## 다음 검토 대상

{pending_lines}

AI 판정은 추천일 뿐 이 숫자에 포함하지 않는다. `decisions.json`에는 사람이 명시적으로 확정한
결정만 기록한다. 큐에서 사라진 상품의 과거 판정은 삭제하지 않고 `staleDecisionProductKeys`로 남긴다.
""",
        encoding="utf-8",
    )

    if run_summary_path.is_file():
        summary = read_json(run_summary_path)
        summary["reviewProgress"] = {
            "queuedProducts": total,
            "adjudicatedProducts": completed_count,
            "deferredProducts": len(deferred),
            "pendingProducts": len(pending),
            "adjudicationRate": status["adjudicationRate"],
        }
        try:
            review_progress_path = str(report_path.relative_to(PROJECT_ROOT))
        except ValueError:
            review_progress_path = str(report_path)
        summary.setdefault("artifacts", {})["reviewProgress"] = review_progress_path
        try:
            ledger_path = str(decision_path.relative_to(PROJECT_ROOT))
        except ValueError:
            ledger_path = str(decision_path)
        summary["artifacts"]["decisionLedger"] = ledger_path
        try:
            summary["artifacts"]["reviewStatus"] = str(status_path.relative_to(PROJECT_ROOT))
        except ValueError:
            summary["artifacts"]["reviewStatus"] = str(status_path)
        if "사람 판정 진행률" not in summary.setdefault("cycle", []):
            summary["cycle"].append("사람 판정 진행률")
        run_summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
