#!/usr/bin/env python3
"""사람이 확정한 판정을 GT가 읽을 수 있는 모양으로 내보낸다. 그리고 판례에 쌓는다.

지금까지 끊겨 있던 자리다. 사람이 「이 GT를 고쳐라」라고 판정해도 그 결정은 원장에
문장으로만 남았고, 정정은 **외부 하네스가 넘겨준 파일**에서만 왔다. 결정 종류의 이름이
그 사실을 그대로 말하고 있었다 — `GOLDEN_CORRECTION_NEEDED`, 정정이 «필요하다».
필요하다고 적을 뿐 아무 일도 일어나지 않았다.

「유지」는 더 조용히 사라졌다. 사람이 「이 GT가 맞다」고 확정해도 GT 원장에 흔적이 없어서,
다음 사이클이 같은 건을 같은 이유로 다시 올렸다. **사람이 자기가 이미 답한 것을 또 답했다.**

이 스크립트가 그 둘을 잇는다. 세 파일을 낸다.

| 파일 | 무엇 | GT에 미치는 영향 |
|---|---|---|
| `corrections.jsonl` | 사람이 고치라고 한 라벨 | `build_gt.py`가 순위와 무관하게 덮는다 |
| `confirmations.jsonl` | 사람이 맞다고 확인한 라벨 | 라벨은 그대로. 확인 사실만 붙는다 |
| `pending-precedent.jsonl` | 미결 판례 위에 선 판정 | **없다. 판례가 답할 때까지 기다린다** |
| `precedent-log.json` | 판례별로 그 판례를 근거로 내린 결정들 | 없다. 다음 판단의 재료다 |

## 왜 기다리는 줄이 따로 있는가

판례는 「한 번 답하면 닫히는 경계 질문」이다. 그 질문이 아직 `OPEN`인데 그 경계 위의
개별 건을 GT에 반영하면, **그 건들이 곧 답이 되어 버린다.** 나중에 판례가 반대로 닫히면
이미 뒤집힌 GT를 되돌려야 하는데, 그때는 무엇이 그 판례 때문에 바뀐 것인지 알 수 없다.

그래서 갈림은 이렇다 — **원장은 사람이 말한 것을 다 담고, GT는 판례가 답한 것만 받는다.**
승인은 버리지 않는다. 사람이 실제로 그렇게 판단했고, 그 판단들이 한자리에 쌓이는 것이
판례를 답할 이유가 되기 때문이다. 판례가 `DECIDED`가 되면 기다리던 줄이 **다시 돌리는
것만으로** 한꺼번에 정정으로 나간다. 사람이 열한 번 다시 누르지 않아도 된다.

판례를 가리키지 않은 판정(«걸리는 판례가 없다»)은 기다리지 않는다. 막을 경계가 없다.

**정본은 결정 원장이다.** 이 넷은 전부 거기서 파생된 것이라 지워도 다시 만들어진다.
반대로 여기서 원장을 고치지 않는다 — 확정은 `record_review_decision.py`가 사람의 답으로만 한다.

속성을 모른다. 결정 원장의 모양, 프로필의 `gt.path`, 그리고 엔진이 쓴 정책 인덱스의
판례 상태만 안다. 판례 레이어가 없는 프로필에서는 막을 것이 없으므로 전부 그대로 나간다.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from catalog_profile import default_profile, load_profile, output_root, project_path

# 판례 목록은 기록하는 쪽과 **같은 함수로** 읽는다. 읽는 곳이 둘이면 한쪽이 `DECIDED`로
# 보는 판례를 다른 쪽이 `OPEN`으로 보고, 그때부터 승인과 반영이 서로 다른 사실 위에 선다.
from record_review_decision import precedent_catalog

# 결정 종류가 GT에 어떻게 닿는가. 여기 없는 종류는 GT를 건드리지 않는다 —
# 정책 공백과 실행 결함은 GT의 문제가 아니라서 고칠 곳이 정반대다.
TO_CORRECTION = "GOLDEN_CORRECTION_NEEDED"
TO_CONFIRMATION = "GOLDEN_CONFIRMED"

# 판례가 이 상태여야 그 경계 위의 판정이 GT로 나간다.
ANSWERED = "DECIDED"


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def latest_by_product(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """상품마다 **마지막 판정**만 남긴다.

    원장은 이력이라 한 상품에 여러 줄이 쌓인다(`supersedes`로 앞을 가리킨다).
    GT에 나가는 것은 지금 유효한 하나뿐이다 — 이력을 전부 내보내면 옛 판정이
    새 판정을 덮는 순서 사고가 난다. 이력 자체는 원장에 그대로 남는다.
    """
    latest: dict[str, dict[str, Any]] = {}
    for row in decisions:
        key = str(row.get("productKey") or "")
        if key:
            latest[key] = row
    return [latest[key] for key in sorted(latest)]


def to_row(decision: dict[str, Any], label_field: str) -> dict[str, Any]:
    return {
        "productKey": decision.get("productKey"),
        "goldLabel": decision.get(label_field),
        "goldSource": f"HUMAN_DECISION:{decision.get('decisionId')}",
        # 누가 언제 왜. 라벨만 남으면 다음 사람이 그 값을 되짚을 수 없다.
        "decisionId": decision.get("decisionId"),
        "reviewer": decision.get("reviewer"),
        "reviewedAt": decision.get("reviewedAt"),
        "reason": decision.get("reason"),
        "policyQuestionId": decision.get("policyQuestionId"),
    }


def waiting_on(decision: dict[str, Any], precedents: dict[str, dict[str, Any]]) -> str:
    """이 판정을 붙잡고 있는 미결 판례. 없으면 빈 문자열이다.

    **지금 상태를 본다.** 판정 당시 상태(`precedentStatusAtDecision`)는 이력이라
    나중에 판례가 닫혀도 그대로 `OPEN`이다. 그 값으로 막으면 판례를 답해도 아무것도
    풀리지 않는다 — 사람이 열한 건을 다시 눌러야 한다.
    """
    key = str(decision.get("precedentId") or "")
    if not key:
        return ""
    status = str((precedents.get(key) or {}).get("status") or "")
    # 목록에 없는 판례는 막지 않는다. 판례 파일이 지워졌거나 인덱스가 아직 안 돌았을 때
    # 조용히 전부 멈추면, 멈춘 이유가 화면 어디에도 안 나온다.
    return key if (key in precedents and status != ANSWERED) else ""


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return len(rows)


def precedent_log(decisions: list[dict[str, Any]], profile_id: str) -> dict[str, Any]:
    """판례별로 그 판례를 근거로 내린 결정들을 쌓는다.

    판례는 「한 번 답하면 닫히는 질문」인데, 답이 실제로 어떻게 적용됐는지가 어디에도
    없었다. 그러면 판례는 문서로만 있고 **다음 판단의 기준이 되지 못한다.**
    여기 쌓인 결정들이 그 판례의 적용 사례집이다 — 같은 질문이 다시 왔을 때 읽을 것.

    판례를 가리키지 않은 결정도 버리지 않는다. 어느 판례에도 안 걸린 결정이 쌓이면
    그것이 **아직 없는 판례**를 가리킨다.
    """
    by_question: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_precedent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rule_without_precedent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unassigned: list[dict[str, Any]] = []
    for row in decisions:
        entry = {
            "decisionId": row.get("decisionId"),
            "productKey": row.get("productKey"),
            "decision": row.get("decision"),
            "correctedLabel": row.get("correctedLabel"),
            "reviewer": row.get("reviewer"),
            "reviewedAt": row.get("reviewedAt"),
            "reason": row.get("reason"),
            "queueSignals": row.get("queueSignals"),
            "precedentId": row.get("precedentId"),
            "policyRuleId": row.get("policyRuleId"),
        }
        question = str(row.get("policyQuestionId") or "")
        precedent = str(row.get("precedentId") or "")
        rule = str(row.get("policyRuleId") or "")
        if precedent:
            by_precedent[precedent].append(entry)
        if question:
            by_question[question].append(entry)
        if rule:
            by_rule[rule].append(entry)
            # 규칙 위에서 판단했는데 걸리는 판례가 없었다. 이것이 쌓이는 규칙이
            # **다음에 판례를 열 자리**다 — 사람이 매번 같은 경계를 혼자 다시 넘고 있다.
            if not precedent:
                rule_without_precedent[rule].append(entry)
        # 판례도 질문도 규칙도 없는 결정. 정책과 아무 데서도 만나지 않는다.
        if not precedent and not question and not rule:
            unassigned.append(entry)
    return {
        "schemaVersion": "catalog-precedent-log-v1",
        "profileId": profile_id,
        "builtAt": datetime.now(UTC).isoformat(),
        "note": "결정 원장에서 파생됐다. 정본은 review/decisions.json이고 여기서 고치지 않는다.",
        "byQuestion": {key: by_question[key] for key in sorted(by_question)},
        # 판례가 앵커다. 질문은 사이클마다 다시 만들어지지만 판례는 파일이라 남는다.
        "byPrecedent": {key: by_precedent[key] for key in sorted(by_precedent)},
        # 규칙별 판단 이력. 규칙 브리프가 이걸 읽어 다음 판독에 실어 나른다.
        "byRule": {key: by_rule[key] for key in sorted(by_rule)},
        # 판례 없이 그 규칙 위에서 내린 판단. 쌓이는 규칙이 곧 판례를 열 자리다.
        "ruleWithoutPrecedent": {
            key: rule_without_precedent[key] for key in sorted(rule_without_precedent)
        },
        # 어느 판례에도 안 걸린 결정. 쌓이면 아직 없는 판례를 가리킨다.
        "unassigned": unassigned,
        "counts": {
            "decisions": len(decisions),
            "questions": len(by_question),
            "precedents": len(by_precedent),
            "rules": len(by_rule),
            "unassigned": len(unassigned),
            "byDecision": dict(sorted(Counter(str(row.get("decision")) for row in decisions).items())),
        },
    }


def derive(profile: dict[str, Any], root: Path) -> dict[str, Any]:
    """원장 하나에서 파생 파일 넷을 다시 만든다.

    사이클이 부르든 승인 버튼이 부르든 같은 함수다. 승인 직후에 다시 도는 이유는,
    방금 누른 것이 GT에 나갔는지 판례에 막혔는지를 **그 자리에서** 알아야 하기 때문이다.
    """
    ledger = read_json(root / "review" / "decisions.json", {})
    decisions = ledger.get("decisions")
    if not isinstance(decisions, list):
        decisions = []
    effective = latest_by_product(decisions)

    # 파생물은 GT 원장 옆에 둔다. 계보 파일들과 같은 자리라야 «무엇이 이 라벨을 정했나»를
    # 한 폴더에서 볼 수 있다. runs/ 아래가 아닌 이유는 그쪽이 지워도 되는 폴더이기 때문이다.
    gt_path = project_path(str((profile.get("gt") or {}).get("path") or ""))
    out_dir = gt_path.parent / "from-decisions"

    # 판례가 아직 답하지 않은 경계 위에 선 판정은 GT로 내보내지 않는다. 원장에는 남아 있고,
    # 여기서는 «무엇이 어느 판례를 기다리는지»로만 적힌다.
    precedents = precedent_catalog(root)
    blocked: dict[str, str] = {}
    ready: list[dict[str, Any]] = []
    for row in effective:
        if row.get("decision") not in (TO_CORRECTION, TO_CONFIRMATION):
            continue
        holder = waiting_on(row, precedents)
        if holder:
            blocked[str(row.get("productKey"))] = holder
        else:
            ready.append(row)

    corrections = [
        to_row(row, "correctedLabel") for row in ready if row.get("decision") == TO_CORRECTION
    ]
    confirmations = [
        {**to_row(row, "correctedLabel"), "goldLabel": row.get("goldLabelAtDecision")}
        for row in ready
        if row.get("decision") == TO_CONFIRMATION
    ]
    pending = [
        {
            **to_row(row, "correctedLabel"),
            "goldLabel": row.get("correctedLabel") or row.get("goldLabelAtDecision"),
            "decision": row.get("decision"),
            # 이것만 닫히면 이 줄이 나간다. 사람이 다음에 무엇을 답해야 하는지가 곧 이 값이다.
            "waitingOn": blocked[str(row.get("productKey"))],
        }
        for row in effective
        if str(row.get("productKey")) in blocked
    ]

    written = {
        "corrections": write_jsonl(out_dir / "corrections.jsonl", corrections),
        "confirmations": write_jsonl(out_dir / "confirmations.jsonl", confirmations),
        "pending": write_jsonl(out_dir / "pending-precedent.jsonl", pending),
    }
    log = precedent_log(decisions, str(profile["id"]))
    log_path = out_dir / "precedent-log.json"
    log_path.write_text(
        json.dumps(log, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    return {
        "decisions": len(decisions),
        "effective": len(effective),
        "corrections": written["corrections"],
        "confirmations": written["confirmations"],
        # 사람이 승인했지만 미결 판례에 막혀 GT로 못 나간 줄. 0이 아니면
        # 다음에 할 일은 개별 건이 아니라 **판례 하나를 답하는 것**이다.
        "pendingPrecedent": written["pending"],
        "waitingOn": dict(sorted(Counter(blocked.values()).items())),
        # 상품별로 무엇이 붙잡고 있는가. 승인한 사람에게 그 자리에서 되돌려 준다.
        "blockedBy": dict(sorted(blocked.items())),
        "precedentLog": str(log_path),
        "counts": log["counts"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()

    profile = load_profile((args.profile or default_profile()).resolve())
    root = args.output_root.resolve() if args.output_root else output_root(profile)
    print(json.dumps(derive(profile, root), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
