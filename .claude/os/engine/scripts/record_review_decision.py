#!/usr/bin/env python3
"""사람의 골든셋 검토 결정을 이력을 보존하며 기록한다.

**문은 하나다.** 터미널에서 오든 보고서의 승인 버튼에서 오든 `record()`를 지난다.
문이 둘이면 규격도 둘이 되고, 그때부터 원장에는 검증된 줄과 안 된 줄이 섞인다.

## 승인 규격 — 판정은 어느 경계 위에 서는가

정정은 라벨만으로 서지 않는다. **어느 정책 경계에 근거해 고치는가**를 함께 적어야 한다.
그 자리가 `precedentId`다. 비워 두면 다음 사이클에 같은 건이 올라왔을 때, 지난번에
무엇을 근거로 뒤집었는지 아무도 되짚지 못한다 — 골든셋이 정책에서 조용히 떨어져 나가는
경로가 정확히 이것이다.

그래서 판례 레이어가 있는 프로필에서 GT를 건드리는 판정은 둘 중 하나를 명시해야 한다.

| 무엇을 적는가 | 뜻 | 어디로 쌓이는가 |
|---|---|---|
| `precedentId` | 이 판정은 그 판례가 그은 경계 위에 선다 | 판례별 사례집 |
| `noPrecedent` + `ruleId` | 그 규칙에 **걸리는 판례가 없다** | 그 규칙의 브리프에 「아직 답 없음」으로 |

둘 다 없으면 거절한다. 「안 적음」과 「없다고 판단함」은 다른 사실인데, 필드를 비워 두면
둘이 같은 모양이 된다.

판례를 고르면 **규칙은 판례가 알려 준다** — 판례가 이미 `rule:`로 걸려 있기 때문이다.
판례가 없다고 밝힐 때만 규칙을 직접 고른다. 그때 규칙이 유일한 정책 앵커이고,
그 값이 곧 «이 규칙에 판례가 필요하다»는 신호가 된다.

**판례의 상태는 여기서 막지 않는다.** 미결 판례를 가리키는 승인도 그대로 기록한다.
사람이 실제로 그렇게 판단했기 때문이다. 다만 GT에 나가는 것은 막힌다 —
그 갈림은 `build_gt_decisions.py`가 하고, 이유는 거기 적혀 있다.

속성을 모른다. 프로필이 선언한 허용 라벨과, 엔진이 쓴 정책 인덱스의 판례 목록만 읽는다.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from catalog_profile import default_profile, load_profile, output_root

DECISIONS = {
    "GOLDEN_CONFIRMED",
    "GOLDEN_CORRECTION_NEEDED",
    "POLICY_GAP_CONFIRMED",
    "RUNTIME_FIX_NEEDED",
    "DEFERRED",
}

# GT 원장에 닿는 판정. 이것들만 정책 경계를 밝혀야 한다 — 정책 공백과 실행 결함은
# 애초에 GT를 건드리지 않으므로 판례를 물을 이유가 없다.
TOUCHES_GT = {"GOLDEN_CONFIRMED", "GOLDEN_CORRECTION_NEEDED"}

LEDGER_SCHEMA = "catalog-review-v1"


class DecisionRejected(ValueError):
    """규격을 어긴 판정. 부르는 쪽이 사람에게 그대로 보여줄 수 있는 문장을 담는다."""


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: object expected")
    return value


def read_json_or(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


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


def policy_index(root: Path) -> dict[str, Any]:
    index = read_json_or(root / "policy" / "policy-index.json", {})
    return index if isinstance(index, dict) else {}


def precedent_catalog(root: Path) -> dict[str, dict[str, Any]]:
    """이 속성이 가진 판례들. 엔진이 쓴 정책 인덱스에서만 읽는다.

    판례 파일을 직접 훑지 않는 이유는 프론트매터 해석이 두 벌이 되기 때문이다.
    읽는 곳이 둘이면 한쪽이 `DECIDED`로 보는 판례를 다른 쪽이 `OPEN`으로 본다.
    """
    listed = policy_index(root).get("precedents")
    if not isinstance(listed, list):
        return {}
    return {str(item["id"]): item for item in listed if isinstance(item, dict) and item.get("id")}


def rule_catalog(root: Path) -> dict[str, dict[str, Any]]:
    """정책이 이름 붙인 규칙들. 판정이 「어느 규칙 위에 섰는가」를 고를 목록이다."""
    owned = policy_index(root).get("owned")
    listed = owned.get("rules") if isinstance(owned, dict) else None
    if not isinstance(listed, list):
        return {}
    return {str(item["id"]): item for item in listed if isinstance(item, dict) and item.get("id")}


def bind_policy(
    catalog: dict[str, dict[str, Any]],
    rules: dict[str, dict[str, Any]],
    decision: str,
    precedent_id: str | None,
    no_precedent: bool,
    rule_id: str | None,
    policy_question_id: str | None,
) -> dict[str, Any]:
    """판정을 정책 경계에 묶는다. 규격의 심장이다.

    묶이는 곳은 둘이다 — **판례**(사람이 답한 경계)와 **규칙**(정책이 이름 붙인 조항).
    판례는 규칙 위에 서므로 보통 규칙은 판례가 알려 준다. 사람이 손으로 옮겨 적게 두면
    오타 하나가 조용히 엉뚱한 규칙에 붙는다.

    판례 레이어가 없는 프로필에서는 아무것도 요구하지 않는다 — 정책 레이어는 선택이고,
    없는 것을 요구하면 엔진이 특정 속성의 구성을 강요하는 셈이 된다.
    """
    if precedent_id and no_precedent:
        raise DecisionRejected("판례를 가리키면서 동시에 «해당 판례 없음»일 수는 없습니다.")
    if rule_id and rules and rule_id not in rules:
        known = ", ".join(sorted(rules))
        raise DecisionRejected(f"그런 정책 규칙이 없습니다: {rule_id}. 이 정책의 규칙: {known}")

    if precedent_id:
        found = catalog.get(precedent_id)
        if found is None:
            known = ", ".join(sorted(catalog)) or "없음"
            raise DecisionRejected(
                f"그런 판례가 없습니다: {precedent_id}. 이 속성의 판례: {known}"
            )
        answers = [str(value) for value in (found.get("answers") or []) if value]
        bound = [str(value) for value in (found.get("rules") or []) if value]
        if rule_id and bound and rule_id not in bound:
            raise DecisionRejected(
                f"{precedent_id}는 `{', '.join(bound)}` 위의 판례입니다. "
                f"`{rule_id}`를 근거로 삼으려면 그 규칙에 걸린 판례를 고르세요."
            )
        return {
            "precedentId": precedent_id,
            # 판정 당시 상태. 지금 GT에 나갔는지는 살아 있는 상태가 정하고, 이 값은 이력이다.
            "precedentStatusAtDecision": str(found.get("status") or ""),
            # 어느 규칙 위에 섰나. 판례가 하나를 걸고 있으면 그것이 답이다.
            "policyRuleId": rule_id or (bound[0] if bound else None),
            # 어느 질문을 닫는 판례였나. 사람이 따로 적지 않으면 판례가 스스로 답한다 —
            # 손으로 옮겨 적게 두면 오타 하나가 조용히 미배정 더미로 떨어진다.
            "policyQuestionId": policy_question_id or (answers[0] if answers else None),
        }

    if no_precedent:
        # 판례가 없다면 규칙이 유일한 정책 앵커다. 그것마저 없으면 이 판정은 정책과
        # 아무 데서도 만나지 않고, **어느 규칙에 판례가 필요한지**도 남지 않는다.
        if rules and decision in TOUCHES_GT and not rule_id:
            known = ", ".join(sorted(rules))
            raise DecisionRejected(
                "걸리는 판례가 없다면 최소한 어느 규칙 위의 판단인지는 밝혀야 합니다. "
                "그래야 «이 규칙에 판례가 필요하다»가 남습니다. "
                f"이 정책의 규칙: {known}"
            )
        return {
            "precedentId": None,
            "precedentStatusAtDecision": None,
            "policyRuleId": rule_id,
            "policyQuestionId": policy_question_id,
        }

    if catalog and decision in TOUCHES_GT:
        known = ", ".join(sorted(catalog))
        # 문 이름(플래그·필드)을 여기 적지 않는다. 터미널과 버튼이 같은 문장을 받아야 한다.
        raise DecisionRejected(
            "GT를 건드리는 판정에는 근거가 된 판례를 밝혀야 합니다. "
            "판례 하나를 고르거나, 걸리는 판례가 없다면 «해당 판례 없음»을 명시하세요. "
            f"이 속성의 판례: {known}"
        )
    return {
        "precedentId": None,
        "precedentStatusAtDecision": None,
        "policyRuleId": rule_id,
        "policyQuestionId": policy_question_id,
    }


def check_labels(
    decision: str, labels: set[str], corrected_label: str | None, confirmed_label: str | None
) -> None:
    if decision == "GOLDEN_CORRECTION_NEEDED":
        if corrected_label not in labels:
            raise DecisionRejected(
                "GOLDEN_CORRECTION_NEEDED에는 정정 라벨과 프로필의 허용 라벨이 필요합니다. "
                f"허용값: {', '.join(sorted(labels))}"
            )
    elif corrected_label is not None:
        raise DecisionRejected("정정 라벨은 GOLDEN_CORRECTION_NEEDED에서만 사용합니다.")

    # **유지도 무엇을 유지했는지 적어야 한다.** 라벨 없이 「맞다」만 남기면, 나중에 GT가
    # 바뀌었을 때 그 확인이 어느 값에 대한 것이었는지 알 수 없다. 그러면 사람이 확인한
    # 적 없는 라벨이 «사람이 확인함»을 달고 다닌다.
    if decision == "GOLDEN_CONFIRMED":
        if confirmed_label not in labels:
            raise DecisionRejected(
                "GOLDEN_CONFIRMED에는 확인 라벨과 프로필의 허용 라벨이 필요합니다. "
                f"허용값: {', '.join(sorted(labels))}"
            )
    elif confirmed_label is not None:
        raise DecisionRejected("확인 라벨은 GOLDEN_CONFIRMED에서만 사용합니다.")


def record(
    *,
    profile: dict[str, Any],
    root: Path,
    product_key: str,
    decision: str,
    reviewer: str,
    reason: str,
    corrected_label: str | None = None,
    confirmed_label: str | None = None,
    precedent_id: str | None = None,
    no_precedent: bool = False,
    rule_id: str | None = None,
    policy_question_id: str | None = None,
    supersedes: str | None = None,
    allow_unqueued: bool = False,
    decision_path: Path | None = None,
) -> dict[str, Any]:
    """판정 한 줄을 원장에 덧붙인다. 규격을 통과한 것만 들어간다.

    되돌리지 않는다 — 원장은 이력이라 고쳐 쓰지 않고 `supersedes`로 덮는다.
    """
    if decision not in DECISIONS:
        raise DecisionRejected(f"모르는 판정 종류입니다: {decision}")
    if not str(product_key).strip():
        raise DecisionRejected("상품 키가 필요합니다.")
    if not str(reviewer).strip():
        raise DecisionRejected("누가 판정했는지 필요합니다.")
    if not str(reason).strip():
        raise DecisionRejected("판정 사유가 필요합니다. 라벨만으로는 다음 사람이 되짚지 못합니다.")

    labels = {str(label) for label in profile.get("labels", [])}
    check_labels(decision, labels, corrected_label, confirmed_label)
    binding = bind_policy(
        precedent_catalog(root),
        rule_catalog(root),
        decision,
        precedent_id,
        no_precedent,
        rule_id,
        policy_question_id,
    )

    signals = queued_signals(root / "queue", product_key)
    if not signals and not allow_unqueued:
        raise DecisionRejected(
            f"{product_key}는 현재 검토 큐에 없습니다. 의도한 경우에만 큐 밖 판정을 허용하세요."
        )

    path = decision_path or root / "review" / "decisions.json"
    ledger = (
        read_json(path)
        if path.is_file()
        else {"schemaVersion": LEDGER_SCHEMA, "profileId": profile["id"], "decisions": []}
    )
    if ledger.get("schemaVersion") != LEDGER_SCHEMA:
        raise DecisionRejected("지원하지 않는 판정 원장 버전입니다.")
    decisions = ledger.get("decisions")
    if not isinstance(decisions, list):
        raise DecisionRejected("decisions는 배열이어야 합니다.")

    previous = [row for row in decisions if row.get("productKey") == product_key]
    known_ids = {str(row.get("decisionId")) for row in decisions}
    if previous:
        if not supersedes:
            raise DecisionRejected(
                f"{product_key}에는 이미 판정이 있습니다. "
                "새 판정은 이전 판정 ID를 supersedes로 명시하세요."
            )
        if supersedes not in known_ids:
            raise DecisionRejected(f"supersedes 대상이 없습니다: {supersedes}")
        latest_product_id = str(previous[-1].get("decisionId"))
        if supersedes != latest_product_id:
            raise DecisionRejected(f"가장 최근 판정 {latest_product_id}만 supersede할 수 있습니다.")
    elif supersedes:
        raise DecisionRejected("이 상품에는 supersede할 이전 판정이 없습니다.")

    now = datetime.now(UTC)
    normalized_key = "".join(
        character if character.isalnum() else "-" for character in product_key
    ).strip("-")
    manifest = read_json_or(root / "manifest.json", {})
    run_summary = read_json_or(root / "run-summary.json", {})
    entry = {
        "decisionId": f"BR-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{normalized_key}",
        "profileId": profile["id"],
        "productKey": product_key,
        "decision": decision,
        "reviewer": reviewer,
        "reason": reason,
        "correctedLabel": corrected_label,
        # 이 판정이 어느 라벨에 대한 것이었나. 유지는 이 값이 곧 판정 내용이다.
        "goldLabelAtDecision": confirmed_label or corrected_label,
        "queueSignals": signals,
        "reviewedAt": now.isoformat(),
        "supersedes": supersedes,
        "sourceCommit": manifest.get("sourceCommit"),
        "auditGeneratedAt": run_summary.get("generatedAt"),
    } | binding
    decisions.append(entry)
    write_json_atomic(path, ledger)
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description="사람의 검토 결정을 원장에 기록한다.")
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--product-key", required=True)
    parser.add_argument("--decision", required=True, choices=sorted(DECISIONS))
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--confirmed-label", help="GOLDEN_CONFIRMED에서 «이 라벨이 맞다»고 확인한 값")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--corrected-label")
    parser.add_argument("--precedent-id", help="이 판정이 근거로 선 판례 ID")
    parser.add_argument("--rule-id", help="이 판정이 선 정책 규칙 ID. 판례를 고르면 판례가 알려 준다")
    parser.add_argument(
        "--no-precedent",
        action="store_true",
        help="걸리는 판례가 없다고 밝힌다 — 새 판례가 필요하다는 신호로 쌓인다",
    )
    parser.add_argument("--policy-question-id")
    parser.add_argument("--supersedes")
    parser.add_argument("--allow-unqueued", action="store_true")
    parser.add_argument("--decision-file", type=Path)
    args = parser.parse_args()

    profile = load_profile(args.profile or default_profile())
    root = args.output_root.resolve() if args.output_root else output_root(profile)
    try:
        entry = record(
            profile=profile,
            root=root,
            product_key=args.product_key,
            decision=args.decision,
            reviewer=args.reviewer,
            reason=args.reason,
            corrected_label=args.corrected_label,
            confirmed_label=args.confirmed_label,
            precedent_id=args.precedent_id,
            no_precedent=args.no_precedent,
            rule_id=args.rule_id,
            policy_question_id=args.policy_question_id,
            supersedes=args.supersedes,
            allow_unqueued=args.allow_unqueued,
            decision_path=args.decision_file.resolve() if args.decision_file else None,
        )
    except DecisionRejected as rejected:
        raise SystemExit(str(rejected)) from rejected
    print(json.dumps(entry, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
