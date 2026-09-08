#!/usr/bin/env python3
"""개선 포인트 스윕의 계약을 지킨다.

이 스윕은 사람에게 "다음에 이걸 손대라"고 말하는 목록을 만든다. 그래서 두 가지가 틀리면
안 된다 — **무엇을 골랐는가**(귀책으로 갈랐는가, 이미 확정된 건을 다시 묻지 않는가,
잘라낸 것을 말하는가)와 **숫자가 어디서 왔는가**(문서의 건수가 워크리스트가 센 값인가).

속성 이름을 모른 채 돈다. 여기서 쓰는 가짜 속성은 소재(material)이고, 가방도 성별도 모른다.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("프로젝트 루트를 찾지 못했습니다.")


PROJECT_ROOT = _find_project_root()
SCRIPTS = PROJECT_ROOT / ".claude/os/engine/scripts"
BUILDER = SCRIPTS / "build_improvement_worklist.py"
RENDERER = SCRIPTS / "render_improvements.py"


def verdict(product: str, owner: str, **extra) -> dict:
    row = {
        "productKey": product,
        "productName": f"제품 {product}",
        "owner": owner,
        "ownerAction": owner,
        "goldLabel": "COTTON",
        "observedLabel": "WOOL",
        "policyRule": "R1",
        "policyStrength": "STRONG",
        "signals": ["RATIO_GAP"],
        "blockedBy": [],
        "reason": "테스트",
    }
    row.update(extra)
    return row


class ImprovementSweepTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.run = root / "run"
        (self.run / "queue").mkdir(parents=True)
        (self.run / "review").mkdir(parents=True)
        (self.run / "reports").mkdir(parents=True)

        self.profile_path = root / "profile.json"
        self.profile_path.write_text(
            json.dumps(
                {
                    "schemaVersion": "catalog-data-profile-v1",
                    "id": "product-material",
                    "displayName": "소재 감사",
                    "attributeName": "대표 소재",
                    "subjectName": "의류 상품",
                    "outputRoot": str(self.run),
                    "labels": ["COTTON", "WOOL", "UNKNOWN"],
                    "signals": {"RATIO_GAP": {"label": "혼용률 공백", "priority": 1}},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        rows = [
            verdict("T:1", "GOLDEN"),
            verdict("T:2", "GOLDEN", policyStrength="WEAK"),
            verdict("T:3", "GOLDEN"),  # 원장에서 이미 확정됐다
            verdict("T:4", "GOAL"),
            verdict("T:5", "GOAL"),
            verdict("T:6", "GOAL"),
            verdict("T:7", "PENDING_PRECEDENT", blockedBy=["PR-1"]),
            verdict("T:8", "PENDING_PRECEDENT", blockedBy=["PR-1"]),
            verdict("T:9", "RUNTIME"),
            verdict("T:10", "NONE"),
        ]
        (self.run / "review/verdicts.jsonl").write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8"
        )
        (self.run / "review/decisions.json").write_text(
            json.dumps(
                {
                    "schemaVersion": "catalog-review-v1",
                    "profileId": "product-material",
                    "decisions": [{"productKey": "T:3", "decision": "GOLDEN_FIX"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (self.run / "queue/ratio-gap.jsonl").write_text(
            "\n".join(
                json.dumps(
                    {
                        "signal": "RATIO_GAP",
                        "productKey": row["productKey"],
                        "reason": "혼용률 기준이 없다",
                        "policyEvidenceSceneIds": ["D01T01"] if row["productKey"] == "T:1" else [],
                    },
                    ensure_ascii=False,
                )
                for row in rows
            )
            + "\n",
            encoding="utf-8",
        )
        (self.run / "run-summary.json").write_text(
            json.dumps(
                {
                    "profileId": "product-material",
                    "completed": True,
                    "generatedAt": "2026-01-01T00:00:00+00:00",
                    "artifacts": {
                        "arbiterVerdicts": str(self.run / "review/verdicts.jsonl"),
                        "decisionLedger": str(self.run / "review/decisions.json"),
                        "queueDirectory": str(self.run / "queue"),
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def build(self, *extra: str) -> dict:
        completed = subprocess.run(
            [sys.executable, str(BUILDER), "--profile", str(self.profile_path), *extra],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.stdout = completed.stdout
        return json.loads((self.run / "improvements/worklist.json").read_text(encoding="utf-8"))

    def test_lanes_split_by_owner_not_by_signal_name(self) -> None:
        """귀책이 갈라야 한다. 신호 이름은 속성이 정하므로 엔진이 알면 안 된다."""
        worklist = self.build("--limit-gt", "0", "--limit-clusters", "0")
        self.assertEqual([row["productKey"] for row in worklist["gtCandidates"]], ["T:1", "T:2"])
        clusters = {row["clusterKey"]: row for row in worklist["policyClusters"]}
        self.assertIn("PRECEDENT:PR-1", clusters)
        self.assertEqual(clusters["PRECEDENT:PR-1"]["products"], 2)
        self.assertEqual(clusters["GOAL:R1:RATIO_GAP"]["products"], 3)
        handoff = {row["owner"]: row["products"] for row in worklist["handoff"]}
        self.assertEqual(handoff, {"RUNTIME": 1, "NONE": 1})

    def test_already_decided_products_are_not_asked_again(self) -> None:
        worklist = self.build("--limit-gt", "0", "--limit-clusters", "0")
        self.assertNotIn("T:3", [row["productKey"] for row in worklist["gtCandidates"]])
        reasons = " ".join(item["reason"] for item in worklist["excluded"])
        self.assertIn("원장", reasons)

    def test_caps_are_declared_not_silent(self) -> None:
        """잘라낸 것을 말하지 않으면 다음 사람은 이 목록이 전부라고 읽는다."""
        worklist = self.build("--limit-gt", "1", "--limit-clusters", "1")
        self.assertEqual(len(worklist["gtCandidates"]), 1)
        self.assertEqual(len(worklist["policyClusters"]), 1)
        dropped = [item for item in worklist["excluded"] if "상한" in item["reason"]]
        self.assertEqual(len(dropped), 2)
        self.assertIn("T:2", dropped[0]["nextProductKeys"])

    def test_workflow_args_carry_pointers_only(self) -> None:
        """워크플로우 스크립트는 파일을 못 읽는다. 그래서 args는 가볍고, 본문은 에이전트가 읽는다."""
        self.build()
        payload = json.loads(self.stdout[self.stdout.index("{") :])["workflowArgs"]
        self.assertEqual(
            Path(payload["worklist"]).resolve(), (self.run / "improvements/worklist.json").resolve()
        )
        self.assertTrue(all(set(item) == {"id", "productKey", "productName"} for item in payload["gt"]))
        self.assertTrue(all(set(item) == {"id", "clusterKey", "owner"} for item in payload["clusters"]))

    def sweep(self, worklist: dict) -> Path:
        gt = {row["id"]: row for row in worklist["gtCandidates"]}
        path = self.run / "improvements/sweep-raw.json"
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": "catalog-improvement-sweep-v1",
                    "worklist": str(self.run / "improvements/worklist.json"),
                    "gt": [
                        {
                            "id": "GT-01",
                            "productKey": gt["GT-01"]["productKey"],
                            "claim": {
                                "productKey": gt["GT-01"]["productKey"],
                                "classification": "GOLDEN_SUSPECT",
                                "currentGoldLabel": "COTTON",
                                "proposedLabel": "WOOL",
                                "policySentence": "근거 우선순위 1",
                                "evidence": ["라벨 택에 울 70%"],
                                "question": "이 GT를 고칠까?",
                                "confidence": "HIGH",
                            },
                            "refutation": {
                                "productKey": gt["GT-01"]["productKey"],
                                "verdict": "GT_SUSPECT_CONFIRMED",
                                "weakestLink": "타일 하나에만 걸려 있다",
                            },
                        },
                        {
                            "id": "GT-02",
                            "productKey": gt["GT-02"]["productKey"],
                            "claim": {
                                "productKey": gt["GT-02"]["productKey"],
                                "classification": "GOLDEN_SUSPECT",
                                "currentGoldLabel": "COTTON",
                                "proposedLabel": "SILK",
                                "evidence": [],
                                "question": "?",
                                "confidence": "LOW",
                            },
                            "refutation": {
                                "productKey": gt["GT-02"]["productKey"],
                                "verdict": "GT_STANDS",
                                "weakestLink": "근거가 없다",
                            },
                        },
                    ],
                    "clusters": [
                        {
                            "id": "PC-01",
                            "clusterKey": worklist["policyClusters"][0]["clusterKey"],
                            "question": {
                                "clusterKey": worklist["policyClusters"][0]["clusterKey"],
                                "defectType": "GAP",
                                "boundary": "혼용률이 동률인 상품",
                                "question": "동률이면 무엇을 대표로 볼까?",
                                "options": [{"choice": "앞선 항목", "changes": "동률 전부"}],
                                "recommendation": "앞선 항목",
                            },
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def render(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(RENDERER), "--profile", str(self.profile_path)],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

    def test_report_numbers_come_from_the_worklist(self) -> None:
        """문서의 `N건`은 전부 워크리스트가 센 값이어야 한다. 규칙 8이 문서에 요구하는 것과 같다."""
        worklist = self.build("--limit-gt", "0", "--limit-clusters", "0")
        self.sweep(worklist)
        completed = self.render()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        merged = json.loads((self.run / "improvements/improvements.json").read_text(encoding="utf-8"))
        body = (self.run / "improvements/improvements.md").read_text(encoding="utf-8")

        def numbers(value) -> set[str]:
            if isinstance(value, bool):
                return set()
            if isinstance(value, (int, float)):
                return {str(int(value))}
            if isinstance(value, dict):
                return set().union(*(numbers(item) for item in value.values()), set())
            if isinstance(value, list):
                return set().union(*(numbers(item) for item in value), set())
            return set()

        grounded = numbers(merged) | numbers(worklist)
        printed = set(re.findall(r"(\d+)\s*건", body))
        self.assertTrue(printed <= grounded, f"근거 없는 숫자: {sorted(printed - grounded)}")

    def test_status_is_the_meeting_of_judgment_and_refutation(self) -> None:
        worklist = self.build("--limit-gt", "0", "--limit-clusters", "0")
        self.sweep(worklist)
        self.assertEqual(self.render().returncode, 0)
        merged = json.loads((self.run / "improvements/improvements.json").read_text(encoding="utf-8"))
        status = {row["id"]: row["status"] for row in merged["gt"]}
        self.assertEqual(status["GT-01"], "GT_FIX_CANDIDATE")
        # 허용 라벨 밖의 제안은 반증 결과와 무관하게 되돌린다.
        self.assertEqual(status["GT-02"], "LABEL_OUT_OF_RANGE")

    def test_nothing_is_written_to_the_human_ledger(self) -> None:
        """이 스윕의 산출물은 전부 제안이다. 확정은 사람만 한다."""
        worklist = self.build()
        before = (self.run / "review/decisions.json").read_text(encoding="utf-8")
        self.sweep(worklist)
        self.render()
        self.assertEqual((self.run / "review/decisions.json").read_text(encoding="utf-8"), before)

    def test_a_sweep_from_another_worklist_is_refused(self) -> None:
        worklist = self.build()
        path = self.sweep(worklist)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["worklist"] = "다른/실행/worklist.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        completed = self.render()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("작업 목록", completed.stderr)

    def test_missing_arbiter_stops_with_a_reason(self) -> None:
        summary = json.loads((self.run / "run-summary.json").read_text(encoding="utf-8"))
        del summary["artifacts"]["arbiterVerdicts"]
        (self.run / "run-summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(BUILDER), "--profile", str(self.profile_path)],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("심판", completed.stderr)


if __name__ == "__main__":
    unittest.main()
