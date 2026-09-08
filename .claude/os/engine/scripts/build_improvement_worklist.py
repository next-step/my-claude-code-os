#!/usr/bin/env python3
"""심판이 귀책을 정한 run에서 다음에 손댈 개선 포인트만 골라 작업 목록을 만든다.

왜 스크립트가 먼저인가 — 목표(engine/goal.md §5)의 산출물은 두 장이고 **단위가 다르다.**
부족한 GT는 건 단위, 부족한 정책은 군집 단위다. 무엇을 어느 장에 넣을지, 각 군집이 몇 건인지는
세면 나오는 값이지 판단이 아니다. 세는 일을 에이전트에게 시키면 매번 다른 숫자가 나오고,
그 숫자가 사람의 시간 계획이 된다. 그래서 **고르고 세는 일은 여기서 결정적으로 하고,
판단만 워크플로우로 넘긴다.**

무엇으로 가르는가 — 신호 이름이 아니라 **심판이 정한 귀책(owner)** 이다.
신호 이름은 속성이 프로필에서 정하므로 엔진이 알면 안 되고, 귀책은 심판(arbitrate.py)이
쓰는 공통 어휘라 어떤 속성에서도 같은 뜻이다.

| 귀책 | 가는 곳 |
|---|---|
| `GOLDEN` | A · 부족한 GT — 건 단위. 사람이 확정한 GT를 뒤집자는 주장이라 반증까지 받는다 |
| `POLICY` · `GOAL` · `PENDING_PRECEDENT` | B · 부족한 정책 — 군집 단위. 한 번 답하면 여러 건이 닫힌다 |
| `EVIDENCE` | 어느 장도 아니다. 근거를 더 받아야 갈린다 |
| `RUNTIME` · `NONE` | 어느 장도 아니다. 실행 결함이거나 충돌 없음이다 |

사람 판정 원장에 이미 확정된 상품은 빼고, 상한에 걸려 빠진 것은 이유와 함께 남긴다.
조용히 잘라내면 다음 사람은 이 목록이 전부라고 읽는다.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from arbitrate import OWNERS
from catalog_profile import (
    default_profile,
    load_profile,
    output_root,
    project_path,
    relative_or_absolute,
)

SCHEMA = "catalog-improvement-worklist-v1"
# 건 단위로 사람 앞에 놓을 귀책. 하나가 하나의 상품 판정이다.
GT_LANE = ("GOLDEN",)
# 군집 단위로 접히는 귀책. 하나가 한 문장의 질문이다.
POLICY_LANE = ("POLICY", "GOAL", "PENDING_PRECEDENT")
# 이 스윕이 다루지 않는 귀책과, 대신 어디로 가야 하는지.
HANDOFF = {
    "EVIDENCE": "근거가 모자라 판정이 미뤄진 건이다. 사진·원장을 다시 받아 되짚어야 갈린다.",
    "RUNTIME": "정책이 아니라 실행이 어긴 건이다. 이 프로세스의 몫은 분리해 넘기는 것까지다.",
    "NONE": "심판이 충돌 없다고 본 건이다. 개선 포인트가 아니다.",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def declared(summary: dict[str, Any], key: str) -> Path | None:
    """요약이 `artifacts`로 선언한 경로만 읽는다. 관습으로 추측하지 않는다."""
    value = (summary.get("artifacts") or {}).get(key)
    return project_path(str(value)) if value else None


def decided_keys(path: Path | None) -> set[str]:
    """사람이 이미 확정한 상품. 다시 묻지 않는다."""
    if path is None or not path.is_file():
        return set()
    ledger = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(entry.get("productKey"))
        for entry in (ledger.get("decisions") or [])
        if entry.get("productKey")
    }


def queue_index(queue_dir: Path | None) -> dict[str, dict[str, Any]]:
    """상품마다 어느 큐에 걸렸고 어떤 근거가 붙어 있는지 모은다. 판정하지 않는다."""
    found: dict[str, dict[str, Any]] = defaultdict(lambda: {"queues": [], "sceneIds": [], "reason": None})
    if queue_dir is None or not queue_dir.is_dir():
        return found
    for queue_file in sorted(queue_dir.glob("*.jsonl")):
        for row in read_jsonl(queue_file):
            key = row.get("productKey")
            if not key:
                continue
            entry = found[str(key)]
            if queue_file.name not in entry["queues"]:
                entry["queues"].append(queue_file.name)
            for scene in row.get("policyEvidenceSceneIds") or []:
                if scene not in entry["sceneIds"]:
                    entry["sceneIds"].append(scene)
            if entry["reason"] is None and row.get("reason"):
                entry["reason"] = row["reason"]
    return found


def signal_rank(profile: dict[str, Any]) -> dict[str, int]:
    """어느 신호를 군집의 대표로 볼지는 프로필이 정한 우선순위를 그대로 쓴다."""
    declared_signals = profile.get("signals")
    if not isinstance(declared_signals, dict):
        return {}
    ranks: dict[str, int] = {}
    for name, value in declared_signals.items():
        priority = value.get("priority") if isinstance(value, dict) else None
        ranks[name] = int(priority) if isinstance(priority, (int, float)) else 10**6
    return ranks


def primary_signal(signals: list[str], ranks: dict[str, int]) -> str:
    if not signals:
        return "UNSIGNALED"
    return sorted(signals, key=lambda name: (ranks.get(name, 10**6), name))[0]


def cluster_key(verdict: dict[str, Any], ranks: dict[str, int]) -> str:
    """군집은 사람이 한 번 답하면 닫히는 단위로 묶는다.

    미결 판례에 막힌 건은 그 판례가 곧 질문이므로 판례로 묶고, 나머지는
    (귀책 · 적용 규칙 · 대표 신호)로 묶는다. 셋 다 심판이 이미 적어 둔 값이라
    묶는 기준이 실행마다 흔들리지 않는다.
    """
    blocked = sorted(str(item) for item in (verdict.get("blockedBy") or []))
    if blocked:
        return "PRECEDENT:" + "+".join(blocked)
    owner = str(verdict.get("owner"))
    rule = str(verdict.get("policyRule") or "UNSPECIFIED")
    return f"{owner}:{rule}:{primary_signal(list(verdict.get('signals') or []), ranks)}"


def build(profile: dict[str, Any], root: Path, limit_gt: int, limit_clusters: int) -> dict[str, Any]:
    summary_path = root / "run-summary.json"
    if not summary_path.is_file():
        raise SystemExit(f"사이클 요약이 없습니다: {summary_path}. 먼저 catalog-data-os로 사이클을 돌리세요.")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    verdict_path = declared(summary, "arbiterVerdicts")
    if verdict_path is None or not verdict_path.is_file():
        raise SystemExit(
            "심판 판정(arbiterVerdicts)이 선언되지 않았습니다. 귀책이 없으면 무엇이 GT 문제이고 "
            "무엇이 정책 문제인지 이 스크립트가 정할 수 없습니다. 프로필에 arbiter 어댑터를 선언하고 "
            "사이클을 다시 돌리세요."
        )

    ranks = signal_rank(profile)
    queues = queue_index(declared(summary, "queueDirectory"))
    settled = decided_keys(declared(summary, "decisionLedger"))
    verdicts = read_jsonl(verdict_path)

    gt_rows: list[dict[str, Any]] = []
    clusters: dict[str, dict[str, Any]] = {}
    handoff: dict[str, int] = defaultdict(int)
    already_decided = 0

    for verdict in verdicts:
        key = str(verdict.get("productKey") or "")
        owner = str(verdict.get("owner") or "NONE")
        if not key:
            continue
        if key in settled:
            already_decided += 1
            continue
        if owner in GT_LANE:
            extra = queues.get(key, {})
            gt_rows.append(
                {
                    "productKey": key,
                    "productName": verdict.get("productName"),
                    "currentGoldLabel": verdict.get("goldLabel"),
                    "runLabel": verdict.get("observedLabel"),
                    "policyRule": verdict.get("policyRule"),
                    "policyStrength": verdict.get("policyStrength"),
                    "ownerAction": verdict.get("ownerAction") or OWNERS.get(owner),
                    "arbiterReason": verdict.get("reason"),
                    "signals": sorted(str(item) for item in (verdict.get("signals") or [])),
                    "queues": extra.get("queues") or [],
                    "citedSceneIds": extra.get("sceneIds") or [],
                    "queueReason": extra.get("reason"),
                }
            )
        elif owner in POLICY_LANE:
            group = clusters.setdefault(
                cluster_key(verdict, ranks),
                {
                    "owner": owner,
                    "ownerAction": verdict.get("ownerAction") or OWNERS.get(owner),
                    "policyRules": set(),
                    "signals": set(),
                    "blockedBy": set(),
                    "products": [],
                    "queues": set(),
                    "reasons": [],
                },
            )
            group["products"].append(key)
            if verdict.get("policyRule"):
                group["policyRules"].add(str(verdict["policyRule"]))
            group["signals"].update(str(item) for item in (verdict.get("signals") or []))
            group["blockedBy"].update(str(item) for item in (verdict.get("blockedBy") or []))
            group["queues"].update(queues.get(key, {}).get("queues") or [])
            if verdict.get("reason") and verdict["reason"] not in group["reasons"]:
                group["reasons"].append(str(verdict["reason"]))
        else:
            handoff[owner] += 1

    gt_rows.sort(
        key=lambda row: (
            0 if row["policyStrength"] == "STRONG" else 1,
            -len(row["citedSceneIds"]),
            row["productKey"],
        )
    )
    cluster_rows = [
        {
            "clusterKey": key,
            "owner": value["owner"],
            "ownerAction": value["ownerAction"],
            "policyRules": sorted(value["policyRules"]),
            "signals": sorted(value["signals"]),
            "blockedBy": sorted(value["blockedBy"]),
            # 영향 건수는 여기서만 센다. 문서도 에이전트도 이 값을 가리키고 다시 세지 않는다.
            "products": len(value["products"]),
            "sampleProductKeys": sorted(value["products"])[:5],
            "queues": sorted(value["queues"]),
            "arbiterReasons": value["reasons"][:3],
        }
        for key, value in clusters.items()
    ]
    cluster_rows.sort(key=lambda row: (-row["products"], row["clusterKey"]))

    selected_gt = gt_rows if limit_gt <= 0 else gt_rows[:limit_gt]
    selected_clusters = cluster_rows if limit_clusters <= 0 else cluster_rows[:limit_clusters]
    for index, row in enumerate(selected_gt, start=1):
        row["id"] = f"GT-{index:02d}"
    for index, row in enumerate(selected_clusters, start=1):
        row["id"] = f"PC-{index:02d}"

    excluded = []
    if already_decided:
        excluded.append(
            {
                "reason": "사람 판정 원장에 이미 확정이 있다",
                "products": already_decided,
                "where": relative_or_absolute(declared(summary, "decisionLedger") or root),
            }
        )
    if len(gt_rows) > len(selected_gt):
        excluded.append(
            {
                "reason": "--limit-gt 상한에 걸렸다. 상한을 올리면 그대로 이어서 나온다",
                "products": len(gt_rows) - len(selected_gt),
                "nextProductKeys": [row["productKey"] for row in gt_rows[len(selected_gt) :]][:10],
            }
        )
    if len(cluster_rows) > len(selected_clusters):
        excluded.append(
            {
                "reason": "--limit-clusters 상한에 걸렸다. 상한을 올리면 그대로 이어서 나온다",
                "clusters": len(cluster_rows) - len(selected_clusters),
                "nextClusterKeys": [row["clusterKey"] for row in cluster_rows[len(selected_clusters) :]][:10],
            }
        )

    return {
        "schemaVersion": SCHEMA,
        "profileId": profile["id"],
        "profile": relative_or_absolute(project_path(str(profile["_path"]))),
        "run": relative_or_absolute(root),
        "basedOn": {
            "file": relative_or_absolute(summary_path),
            "generatedAt": summary.get("generatedAt"),
            "arbiterVerdicts": relative_or_absolute(verdict_path),
        },
        "labels": profile.get("labels") or [],
        "selection": {
            "gtLane": list(GT_LANE),
            "policyLane": list(POLICY_LANE),
            "limitGt": limit_gt,
            "limitClusters": limit_clusters,
            "rankedGtCandidates": len(gt_rows),
            "rankedPolicyClusters": len(cluster_rows),
        },
        "gtCandidates": selected_gt,
        "policyClusters": selected_clusters,
        "excluded": excluded,
        "handoff": [
            {"owner": owner, "products": count, "note": HANDOFF.get(owner, "")}
            for owner, count in sorted(handoff.items())
        ],
    }


def workflow_args(worklist: dict[str, Any], worklist_path: Path) -> dict[str, Any]:
    """워크플로우 스크립트는 파일을 못 읽는다. 그래서 포인터만 args로 넘기고 본문은 에이전트가 읽는다."""
    return {
        "profile": worklist["profile"],
        "run": worklist["run"],
        "worklist": relative_or_absolute(worklist_path),
        "labels": worklist["labels"],
        "gt": [
            {"id": row["id"], "productKey": row["productKey"], "productName": row.get("productName")}
            for row in worklist["gtCandidates"]
        ],
        "clusters": [
            {"id": row["id"], "clusterKey": row["clusterKey"], "owner": row["owner"]}
            for row in worklist["policyClusters"]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--limit-gt", type=int, default=4, help="건 단위로 판정할 상품 상한. 0이면 무제한")
    parser.add_argument("--limit-clusters", type=int, default=3, help="군집 상한. 0이면 무제한")
    args = parser.parse_args()

    profile_path = (args.profile or default_profile()).resolve()
    profile = load_profile(profile_path)
    root = args.output_root.resolve() if args.output_root else output_root(profile)

    worklist = build(profile, root, args.limit_gt, args.limit_clusters)
    target = root / "improvements" / "worklist.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(worklist, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(relative_or_absolute(target))
    print(
        json.dumps(
            {"workflowArgs": workflow_args(worklist, target)}, ensure_ascii=False, indent=2, sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
