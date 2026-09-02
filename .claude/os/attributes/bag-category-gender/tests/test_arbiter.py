#!/usr/bin/env python3
"""심판의 결정표와 가방 정책 술어를 고정한다.

정책·골든셋·실행 셋 중 어디를 고칠지가 이 OS의 유일한 판단 지점이다.
결정표가 조용히 바뀌면 사람이 엉뚱한 곳을 고치게 되므로 여기서 못 박는다.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("프로젝트 루트를 찾지 못했습니다.")


PROJECT_ROOT = _find_project_root()
SCRIPTS = PROJECT_ROOT / ".claude/os/engine/scripts"
ADAPTERS = PROJECT_ROOT / ".claude/os/attributes/bag-category-gender/adapters"
RUN_ROOT = PROJECT_ROOT / ".claude/os/runs/bag-category-gender"


def load(name: str, directory: Path = SCRIPTS):
    sys.path.insert(0, str(directory))
    spec = importlib.util.spec_from_file_location(name, directory / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


arbitrate = load("arbitrate")
bag = load("arbiter_bag_category_gender", ADAPTERS)


def answer(label: str, strength: str = "STRONG", blocked: list[str] | None = None) -> dict:
    return {"label": label, "strength": strength, "rule": "T", "note": "", "blockedBy": blocked or []}


class DecisionTableTest(unittest.TestCase):
    """공통 결정표. 도메인 지식 없이 라벨 비교만으로 귀책이 결정되어야 한다."""

    def test_missing_gold_goes_to_golden(self) -> None:
        owner, _, _ = arbitrate.decide(answer("FEMALE"), "UNCLASSIFIED", "FEMALE")
        self.assertEqual("GOLDEN", owner)

    def test_unresolvable_policy_goes_to_goal(self) -> None:
        owner, _, _ = arbitrate.decide(answer("UNRESOLVABLE"), "UNISEX", "FEMALE")
        self.assertEqual("GOAL", owner)

    def test_undetermined_policy_with_produced_label_is_runtime(self) -> None:
        owner, _, gap = arbitrate.decide(answer("UNDETERMINED"), "FEMALE", "UNISEX")
        self.assertEqual("RUNTIME", owner)
        self.assertTrue(gap)

    def test_undetermined_everywhere_but_gold_needs_evidence(self) -> None:
        owner, _, gap = arbitrate.decide(answer("UNDETERMINED"), "FEMALE", "UNDETERMINED")
        self.assertEqual("EVIDENCE", owner)
        self.assertTrue(gap)

    def test_all_agree_is_no_conflict(self) -> None:
        owner, _, _ = arbitrate.decide(answer("FEMALE"), "FEMALE", "FEMALE")
        self.assertEqual("NONE", owner)

    def test_policy_and_gold_agree_blames_runtime(self) -> None:
        owner, _, _ = arbitrate.decide(answer("UNISEX"), "UNISEX", "FEMALE")
        self.assertEqual("RUNTIME", owner)

    def test_strong_policy_and_runtime_agree_blames_golden(self) -> None:
        owner, _, _ = arbitrate.decide(answer("FEMALE"), "UNISEX", "FEMALE")
        self.assertEqual("GOLDEN", owner)

    def test_weak_policy_cannot_blame_golden(self) -> None:
        owner, _, _ = arbitrate.decide(answer("FEMALE", "WEAK"), "UNISEX", "FEMALE")
        self.assertEqual("PENDING_PRECEDENT", owner)

    def test_strong_policy_alone_blames_policy(self) -> None:
        owner, _, _ = arbitrate.decide(answer("FEMALE"), "UNISEX", "UNISEX")
        self.assertEqual("POLICY", owner)

    def test_weak_policy_cannot_blame_policy(self) -> None:
        owner, _, _ = arbitrate.decide(answer("FEMALE", "WEAK"), "UNISEX", "UNISEX")
        self.assertEqual("PENDING_PRECEDENT", owner)

    def test_three_way_split_goes_to_goal(self) -> None:
        owner, _, _ = arbitrate.decide(answer("FEMALE"), "UNISEX", "MALE")
        self.assertEqual("GOAL", owner)


class BagPolicyPredicateTest(unittest.TestCase):
    """가방 정책의 근거 우선순위를 그대로 적용하는지 본다."""

    def test_direct_text_outranks_wearer_evidence(self) -> None:
        result = bag.policy_answer(
            {
                "productName": "컬럼비아 공용 본레 포레스트 20L 백팩",
                "detailStatus": "OK",
                "detailEvidenceType": "HUMAN",
                "detailEvidence": "여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.",
            }
        )
        self.assertEqual("UNISEX", result["label"])
        self.assertEqual("P1_DIRECT_TEXT", result["rule"])
        self.assertEqual("STRONG", result["strength"])

    def test_unisex_token_wins_over_shorter_overlap(self) -> None:
        self.assertEqual("UNISEX", bag.policy_answer({"productName": "남녀공용 백팩"})["label"])

    def test_female_token_is_not_shadowed_by_men_substring(self) -> None:
        self.assertEqual("FEMALE", bag.policy_answer({"productName": "Women's Tote Bag"})["label"])

    def test_wearer_evidence_is_weak_and_blocked_by_precedent(self) -> None:
        result = bag.policy_answer(
            {
                "productName": "세이프선데이 스트랩 숄더백",
                "detailStatus": "OK",
                "detailEvidenceType": "HUMAN",
                "detailEvidence": "여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.",
            }
        )
        self.assertEqual("FEMALE", result["label"])
        self.assertEqual("WEAK", result["strength"])
        self.assertIn("BG-0001", result["blockedBy"])

    def test_mixed_gender_evidence_is_not_a_single_label(self) -> None:
        result = bag.policy_answer(
            {
                "productName": "표준 백팩",
                "detailStatus": "OK",
                "detailEvidenceType": "HUMAN",
                "detailEvidence": "남녀 모델이 함께 착용한 이미지가 확인됨.",
            }
        )
        self.assertEqual("UNRESOLVABLE", result["label"])

    def test_no_evidence_is_undetermined_not_unisex(self) -> None:
        result = bag.policy_answer(
            {
                "productName": "무근거 가방",
                "decisionSource": "NONE",
                "thumbnailFold": None,
                "detailFold": None,
                "detailEvidence": "",
                "textSignal": None,
            }
        )
        self.assertEqual("UNDETERMINED", result["label"])
        self.assertIn("BG-0002", result["blockedBy"])

    def test_combined_design_cannot_be_judged_from_text(self) -> None:
        result = bag.policy_answer(
            {"productName": "미니 리본 백", "detailStatus": "OK", "detailEvidenceType": "PRODUCT_ONLY"}
        )
        self.assertEqual("UNRESOLVABLE", result["label"])
        self.assertEqual("P2_COMBINED_DESIGN", result["rule"])


class ArbiterOutputTest(unittest.TestCase):
    """심판이 실제 실행에서 만든 원장이 계약을 지키는지 본다."""

    def setUp(self) -> None:
        path = RUN_ROOT / "review/verdicts.jsonl"
        if not path.is_file():
            self.skipTest("심판을 아직 실행하지 않았다")
        self.verdicts = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def test_every_verdict_is_a_recommendation(self) -> None:
        self.assertTrue(all(v["recommendation"] for v in self.verdicts))

    def test_human_ledger_is_untouched_by_the_arbiter(self) -> None:
        ledger = json.loads((RUN_ROOT / "review/decisions.json").read_text(encoding="utf-8"))
        self.assertEqual([], ledger["decisions"])

    def test_direct_text_case_is_runtime_not_golden(self) -> None:
        row = next(v for v in self.verdicts if v["productKey"] == "EGOOCM:3417183")
        self.assertEqual("RUNTIME", row["owner"])
        self.assertEqual("P1_DIRECT_TEXT", row["policyRule"])

    def test_settled_verdicts_carry_no_open_precedent(self) -> None:
        for verdict in self.verdicts:
            if verdict["owner"] == "NONE":
                self.assertEqual([], verdict["blockedBy"], verdict["productKey"])


if __name__ == "__main__":
    unittest.main()
