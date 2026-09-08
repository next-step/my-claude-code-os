#!/usr/bin/env python3
"""사람의 판정이 GT와 판례로 나가는 길.

이 자리가 없던 동안 결정은 원장에 **문장으로만** 남았다. 종류의 이름이 그 사실을 그대로
말하고 있었다 — `GOLDEN_CORRECTION_NEEDED`, 정정이 «필요하다». 필요하다고 적을 뿐
아무 일도 일어나지 않았고, 정정은 외부 하네스가 넘겨준 파일에서만 왔다.

여기서 기계가 지키는 것은 넷이다 — 고치라는 판정이 정정으로 나가는가, 맞다는 판정이
확인으로 나가는가, 이력 중 **지금 유효한 하나**만 나가는가, 그리고 판례에 쌓이는가.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("프로젝트 루트를 찾지 못했다")


PROJECT_ROOT = _find_project_root()
SCRIPT = PROJECT_ROOT / ".claude/os/engine/scripts/build_gt_decisions.py"


def decision(product: str, kind: str, **extra) -> dict:
    return {
        "decisionId": extra.pop("decisionId", f"BR-{product}"),
        "productKey": product,
        "decision": kind,
        "reviewer": "mj",
        "reviewedAt": "2026-09-07T00:00:00+00:00",
        "reason": "이유",
        "correctedLabel": None,
        "goldLabelAtDecision": None,
        "policyQuestionId": None,
        "queueSignals": [],
        "supersedes": None,
        **extra,
    }


class Harness(unittest.TestCase):
    """시험 도구만 둔다. 여기에 시험을 두면 상속받는 반마다 같은 시험이 다시 돈다."""

    def run_build(self, decisions: list[dict], precedents: list[dict] | None = None) -> tuple[dict, Path]:
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        run = tmp / "run"
        (run / "review").mkdir(parents=True)
        (run / "review/decisions.json").write_text(
            json.dumps({"schemaVersion": "catalog-review-v1", "profileId": "t",
                        "decisions": decisions}),
            encoding="utf-8",
        )
        if precedents is not None:
            (run / "policy").mkdir(parents=True)
            (run / "policy/policy-index.json").write_text(
                json.dumps({"precedents": precedents}), encoding="utf-8"
            )
        gt = tmp / "gt" / "t" / "gt.jsonl"
        gt.parent.mkdir(parents=True)
        gt.write_text("", encoding="utf-8")
        profile = tmp / "profile.json"
        profile.write_text(
            json.dumps({
                "schemaVersion": "catalog-data-profile-v1", "id": "t",
                "displayName": "t", "attributeName": "t", "subjectName": "t",
                "outputRoot": str(run), "gt": {"path": str(gt)},
            }),
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--profile", str(profile), "--output-root", str(run)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout), gt.parent / "from-decisions"

    def rows(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class DerivationTest(Harness):

    def test_a_correction_decision_becomes_a_correction_row(self) -> None:
        _, out = self.run_build([
            decision("P1", "GOLDEN_CORRECTION_NEEDED", correctedLabel="FEMALE")
        ])
        rows = self.rows(out / "corrections.jsonl")
        self.assertEqual(rows[0]["productKey"], "P1")
        self.assertEqual(rows[0]["goldLabel"], "FEMALE")
        # 출처가 사람 판정임이 라벨 옆에 남아야 한다.
        self.assertTrue(rows[0]["goldSource"].startswith("HUMAN_DECISION:"))

    def test_a_confirmation_carries_the_label_it_confirmed(self) -> None:
        """라벨 없이 «맞다»만 남기면, 나중에 GT가 바뀌었을 때 어느 값에 대한 확인인지 모른다."""
        _, out = self.run_build([
            decision("P2", "GOLDEN_CONFIRMED", goldLabelAtDecision="MALE")
        ])
        rows = self.rows(out / "confirmations.jsonl")
        self.assertEqual(rows[0]["goldLabel"], "MALE")
        self.assertEqual(self.rows(out / "corrections.jsonl"), [])

    def test_only_the_latest_decision_of_a_product_goes_out(self) -> None:
        """원장은 이력이다. 옛 판정까지 내보내면 순서에 따라 새 판정이 덮인다."""
        summary, out = self.run_build([
            decision("P3", "GOLDEN_CORRECTION_NEEDED", decisionId="BR-1", correctedLabel="FEMALE"),
            decision("P3", "GOLDEN_CONFIRMED", decisionId="BR-2",
                     goldLabelAtDecision="MALE", supersedes="BR-1"),
        ])
        self.assertEqual(summary["effective"], 1)
        self.assertEqual(self.rows(out / "corrections.jsonl"), [])
        self.assertEqual(self.rows(out / "confirmations.jsonl")[0]["goldLabel"], "MALE")
        # 이력 자체는 원장에 남는다 — 판례 로그는 뺀 것 없이 전부 센다.
        log = json.loads((out / "precedent-log.json").read_text(encoding="utf-8"))
        self.assertEqual(log["counts"]["decisions"], 2)

    def test_decisions_pile_up_under_the_precedent_they_answer(self) -> None:
        """판례는 «한 번 답하면 닫히는 질문»인데, 답이 어떻게 적용됐는지가 없었다.

        여기 쌓인 결정들이 그 판례의 적용 사례집이다 — 같은 질문이 다시 왔을 때 읽을 것.
        """
        _, out = self.run_build([
            decision("P4", "GOLDEN_CONFIRMED", goldLabelAtDecision="MALE",
                     policyQuestionId="GQ-1"),
            decision("P5", "GOLDEN_CORRECTION_NEEDED", correctedLabel="FEMALE",
                     policyQuestionId="GQ-1"),
            decision("P6", "POLICY_GAP_CONFIRMED"),
        ])
        log = json.loads((out / "precedent-log.json").read_text(encoding="utf-8"))
        self.assertEqual(len(log["byQuestion"]["GQ-1"]), 2)
        # 어느 판례에도 안 걸린 결정이 쌓이면 그것이 아직 없는 판례를 가리킨다.
        self.assertEqual([row["productKey"] for row in log["unassigned"]], ["P6"])
        self.assertEqual(log["counts"]["byDecision"]["GOLDEN_CONFIRMED"], 1)

class PrecedentGateTest(Harness):
    """미결 판례 위에 선 승인은 원장에 남되 GT로는 못 나간다.

    판례는 「한 번 답하면 닫히는 경계 질문」이다. 그 질문이 아직 열려 있는데 그 경계 위의
    개별 건을 GT에 반영하면 **그 건들이 곧 답이 되어 버린다.** 나중에 판례가 반대로 닫혀도
    무엇이 그 판례 때문에 바뀐 것인지 되짚을 수 없다.
    """

    OPEN = [{"id": "BG-1", "status": "OPEN", "answers": ["GQ-1"]}]
    CLOSED = [{"id": "BG-1", "status": "DECIDED", "answers": ["GQ-1"]}]

    def approved(self) -> list[dict]:
        return [decision("P1", "GOLDEN_CORRECTION_NEEDED", correctedLabel="FEMALE",
                         precedentId="BG-1", policyQuestionId="GQ-1")]

    def test_an_approval_on_an_open_precedent_waits_instead_of_reaching_gt(self) -> None:
        summary, out = self.run_build(self.approved(), precedents=self.OPEN)
        self.assertEqual(self.rows(out / "corrections.jsonl"), [])
        held = self.rows(out / "pending-precedent.jsonl")
        self.assertEqual(held[0]["waitingOn"], "BG-1")
        # 무엇을 답해야 이것이 풀리는지가 요약에 그대로 있어야 한다.
        self.assertEqual(summary["waitingOn"], {"BG-1": 1})

    def test_answering_the_precedent_releases_it_without_re_approving(self) -> None:
        """판례를 닫으면 기다리던 건이 **다시 돌리는 것만으로** 나간다.

        여기서 사람이 열한 건을 다시 눌러야 한다면, 승인 화면은 판례를 답할 이유가 아니라
        판례를 피할 이유가 된다.
        """
        _, out = self.run_build(self.approved(), precedents=self.CLOSED)
        self.assertEqual(self.rows(out / "corrections.jsonl")[0]["goldLabel"], "FEMALE")
        self.assertEqual(self.rows(out / "pending-precedent.jsonl"), [])

    def test_a_decision_that_names_no_precedent_is_not_held(self) -> None:
        """«걸리는 판례가 없다»는 판정에는 막을 경계가 없다. 그대로 나간다."""
        _, out = self.run_build(
            [decision("P2", "GOLDEN_CORRECTION_NEEDED", correctedLabel="MALE")],
            precedents=self.OPEN,
        )
        self.assertEqual(self.rows(out / "corrections.jsonl")[0]["goldLabel"], "MALE")

    def test_approvals_pile_up_under_the_precedent_they_rest_on(self) -> None:
        """한 판례에 쌓인 건수가 곧 그 판례를 답할 이유다."""
        _, out = self.run_build(
            [decision("P1", "GOLDEN_CORRECTION_NEEDED", correctedLabel="FEMALE", precedentId="BG-1"),
             decision("P2", "GOLDEN_CONFIRMED", goldLabelAtDecision="MALE", precedentId="BG-1")],
            precedents=self.OPEN,
        )
        log = json.loads((out / "precedent-log.json").read_text(encoding="utf-8"))
        self.assertEqual(len(log["byPrecedent"]["BG-1"]), 2)


class LedgerIsUntouchedTest(Harness):
    def test_it_never_writes_to_the_decision_ledger(self) -> None:
        """확정은 사람의 답으로만 한다. 파생기가 원장을 고치면 그 원칙이 깨진다."""
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        run = tmp / "run"
        (run / "review").mkdir(parents=True)
        ledger = run / "review/decisions.json"
        payload = {"schemaVersion": "catalog-review-v1", "profileId": "t",
                   "decisions": [decision("P7", "GOLDEN_CORRECTION_NEEDED", correctedLabel="FEMALE")]}
        ledger.write_text(json.dumps(payload), encoding="utf-8")
        before = ledger.read_bytes()
        gt = tmp / "gt" / "t" / "gt.jsonl"
        gt.parent.mkdir(parents=True)
        gt.write_text("", encoding="utf-8")
        profile = tmp / "profile.json"
        profile.write_text(
            json.dumps({"schemaVersion": "catalog-data-profile-v1", "id": "t", "displayName": "t",
                        "attributeName": "t", "subjectName": "t", "outputRoot": str(run),
                        "gt": {"path": str(gt)}}),
            encoding="utf-8",
        )
        subprocess.run(
            [sys.executable, str(SCRIPT), "--profile", str(profile), "--output-root", str(run)],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(ledger.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
