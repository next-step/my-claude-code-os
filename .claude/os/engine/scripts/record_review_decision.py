#!/usr/bin/env python3
"""사람의 골든셋 검토 결정을 이력을 보존하며 기록한다."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from catalog_profile import PROJECT_ROOT, default_profile, load_profile, output_root

DECISIONS = {
    "GOLDEN_CONFIRMED",
    "GOLDEN_CORRECTION_NEEDED",
    "POLICY_GAP_CONFIRMED",
    "RUNTIME_FIX_NEEDED",
    "DEFERRED",
}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: object expected")
    return value


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            json.dump(value, target, ensure_ascii=False, indent=2, sort_keys=True)
            target.write("\n")
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def queued_signals(queue_dir: Path, product_key: str) -> list[str]:
    signals: set[str] = set()
    for path in sorted(queue_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("productKey") == product_key:
                    signals.add(str(row.get("signal") or path.stem))
    return sorted(signals)


def validate_args(args: argparse.Namespace, labels: set[str]) -> None:
    if args.decision == "GOLDEN_CORRECTION_NEEDED":
        if args.corrected_label not in labels:
            raise SystemExit(
                "GOLDEN_CORRECTION_NEEDED에는 --corrected-label과 프로필의 허용 라벨이 필요합니다. "
                f"허용값: {', '.join(sorted(labels))}"
            )
    elif args.corrected_label is not None:
        raise SystemExit("--corrected-label은 GOLDEN_CORRECTION_NEEDED에서만 사용합니다.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--product-key", required=True)
    parser.add_argument("--decision", required=True, choices=sorted(DECISIONS))
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--corrected-label")
    parser.add_argument("--policy-question-id")
    parser.add_argument("--supersedes")
    parser.add_argument("--allow-unqueued", action="store_true")
    parser.add_argument("--decision-file", type=Path)
    args = parser.parse_args()
    profile = load_profile(args.profile or default_profile())
    labels = {str(label) for label in profile.get("labels", [])}
    validate_args(args, labels)
    root = args.output_root.resolve() if args.output_root else output_root(profile)
    queue_dir = root / "queue"
    manifest_path = root / "manifest.json"
    run_summary_path = root / "run-summary.json"

    signals = queued_signals(queue_dir, args.product_key)
    if not signals and not args.allow_unqueued:
        raise SystemExit(
            f"{args.product_key}는 현재 검토 큐에 없습니다. "
            "의도한 경우에만 --allow-unqueued를 사용하세요."
        )

    decision_path = (
        args.decision_file.resolve() if args.decision_file else root / "review" / "decisions.json"
    )
    ledger = (
        read_json(decision_path)
        if decision_path.is_file()
        else {"schemaVersion": "catalog-review-v1", "profileId": profile["id"], "decisions": []}
    )
    if ledger.get("schemaVersion") != "catalog-review-v1":
        raise SystemExit("지원하지 않는 판정 원장 버전입니다.")
    decisions = ledger.get("decisions")
    if not isinstance(decisions, list):
        raise SystemExit("decisions는 배열이어야 합니다.")

    previous = [row for row in decisions if row.get("productKey") == args.product_key]
    known_ids = {str(row.get("decisionId")) for row in decisions}
    if previous:
        if not args.supersedes:
            raise SystemExit(
                f"{args.product_key}에는 이미 판정이 있습니다. "
                "새 판정은 --supersedes <decisionId>로 이전 판정을 명시하세요."
            )
        if args.supersedes not in known_ids:
            raise SystemExit(f"supersedes 대상이 없습니다: {args.supersedes}")
        latest_product_id = str(previous[-1].get("decisionId"))
        if args.supersedes != latest_product_id:
            raise SystemExit(
                f"가장 최근 판정 {latest_product_id}만 supersede할 수 있습니다."
            )
    elif args.supersedes:
        raise SystemExit("이 상품에는 supersede할 이전 판정이 없습니다.")

    now = datetime.now(UTC)
    normalized_key = "".join(
        character if character.isalnum() else "-" for character in args.product_key
    ).strip("-")
    decision_id = f"BR-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{normalized_key}"
    manifest = read_json(manifest_path) if manifest_path.is_file() else {}
    run_summary = read_json(run_summary_path) if run_summary_path.is_file() else {}
    record = {
        "decisionId": decision_id,
        "profileId": profile["id"],
        "productKey": args.product_key,
        "decision": args.decision,
        "reviewer": args.reviewer,
        "reason": args.reason,
        "correctedLabel": args.corrected_label,
        "policyQuestionId": args.policy_question_id,
        "queueSignals": signals,
        "reviewedAt": now.isoformat(),
        "supersedes": args.supersedes,
        "sourceCommit": manifest.get("sourceCommit"),
        "auditGeneratedAt": run_summary.get("generatedAt"),
    }
    decisions.append(record)
    write_json_atomic(decision_path, ledger)
    print(json.dumps(record, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
