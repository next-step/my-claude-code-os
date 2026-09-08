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
POLICY_ROOT = PROJECT_ROOT / ".claude/os/attributes/bag-category-gender/policy"


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

    def test_wearer_evidence_is_weak_and_names_the_rule_it_stands_on(self) -> None:
        """어댑터는 **규칙 이름까지만** 답한다. 어느 판례가 이 규칙을 막고 있는지는 모른다.

        전에는 여기서 `blockedBy`에 `BG-0001`이 들어 있는지 봤다. 그러면 판례 ID가 코드에
        박혀, 판례를 새로 써도 심판은 모르고 판례를 닫아도 코드를 고쳐야 했다.
        지금은 판례 파일이 `rule: P3_WEARER`로 스스로 걸리고, 엔진이 그 대조로 막는다 —
        **판례를 더하는 것만으로 다음 실행이 달라진다.** 그 이음은 `test_arbitrate.py`가 본다.
        """
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
        self.assertEqual("P3_WEARER", result["rule"])

    def test_mixed_gender_evidence_cannot_be_settled_by_text(self) -> None:
        """「남녀가 모두 착용」은 **문자로 확인할 수 없는 주장**이다.

        정책 문장 자체는 그대로다 — 남녀가 같은 가방을 모두 착용했으면 UNISEX이고,
        한쪽만 보이는 것은 촬영 컷 선택으로 설명되지만 둘 다 보이는 것은 그렇지 않다.
        바뀐 것은 **그 조건이 성립하는지를 이 자리에서 알 수 있는가**다.

        한 문장이 두 가지를 함께 주장한다 — 두 성별이 관측됐다는 것과, 그들이
        **대상과 같은 가방**을 들었다는 것. 정규식은 어느 쪽도 보지 못하고 낱말만 본다.

        2026-09-07에 이 주장으로 사람 GT를 뒤집자고 한 건 6개를 전부 사진으로 되짚었더니
        **6건 다 무너졌다** — 셋은 착용자가 다른 컬러웨이를 들었고, 하나는 인용한 배너에
        가방이 아예 없었으며, 셋은 「남성」이라 적힌 인물이 반대로 읽혔다. 판독 12건에서
        MASCULINE 관측은 0이었다.

        그래서 STRONG을 주지 않는다. 지우지도 않는다 — 사진으로 보면 설 수도 있다.
        2순위 결합 디자인을 「문자로 판정할 수 없다」로 둔 것과 같은 처리다.
        """
        for evidence in (
            "남녀 모델이 함께 착용한 이미지가 확인됨.",
            "동일 대상 상품을 실제 착용한 남성·여성 모델이 모두 확인됨.",
        ):
            with self.subTest(evidence=evidence):
                result = bag.policy_answer(
                    {
                        "productName": "표준 백팩",
                        "detailStatus": "OK",
                        "detailEvidenceType": "HUMAN",
                        "detailEvidence": evidence,
                    }
                )
                self.assertEqual("UNRESOLVABLE", result["label"])
                self.assertEqual("WEAK", result["strength"])
                # 규칙 이름은 남긴다. 어느 주장이 이 자리에 왔는지 세려면 이름이 필요하다.
                self.assertEqual("P3_MIXED_WEARER", result["rule"])
                self.assertIn("이미지로 되짚어야", result["note"])

    def test_single_gender_wearer_still_weak(self) -> None:
        """혼재 규칙이 단일 성별 착용자 경로를 삼키지 않는지 지킨다."""
        result = bag.policy_answer(
            {
                "productName": "표준 백팩",
                "detailStatus": "OK",
                "detailEvidenceType": "HUMAN",
                "detailEvidence": "여성 모델만 동일 대상 상품을 실제 착용한 이미지가 확인됨.",
            }
        )
        self.assertEqual("FEMALE", result["label"])
        self.assertEqual("P3_WEARER", result["rule"])

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
        # 판례 ID가 아니라 규칙 이름을 본다. 이 규칙에 어느 판례가 걸리는지는 정책 레이어의 몫이다.
        self.assertEqual("P0_NO_EVIDENCE", result["rule"])

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

    def test_every_blocking_precedent_declared_itself(self) -> None:
        """판례 ID는 코드에 없다. **판례 파일이 스스로 걸었기 때문에** 여기 나타난다.

        전에는 어댑터가 `blockedBy: ["BG-0001"]`처럼 판례 이름을 코드에 적었다. 그러면
        판례를 새로 써도 심판은 모르고, 판례를 닫아도 코드를 고쳐야 했다 — 판례가
        자산이 아니라 상수였다. 지금은 판례가 `rule:`과 `signals:`로 걸고 엔진이 읽는다.

        그래서 이 시험은 「어느 판례가 걸렸나」가 아니라 **「걸린 판례가 전부 스스로
        선언한 것인가」**를 본다. 코드가 몰래 더한 이름이 하나라도 있으면 깨진다.
        """
        declared: set[str] = set()
        for path in sorted((POLICY_ROOT / "precedents").glob("*.md")):
            meta = path.read_text(encoding="utf-8").split("---")[1]
            for line in meta.splitlines():
                key, _, value = line.partition(":")
                if key.strip() in ("rule", "signals") and value.strip():
                    declared.add(path.stem)
        seen = {pid for verdict in self.verdicts for pid in verdict["blockedBy"]}
        self.assertTrue(seen, "막힌 건이 하나도 없다 — 이 시험이 아무것도 안 본다")
        self.assertLessEqual(seen, declared, "판례 파일이 걸지 않은 ID가 판정에 들어왔다")

    def test_the_adapter_names_no_precedent(self) -> None:
        """어댑터 코드에 판례 ID가 남아 있으면 정책 레이어와 조용히 갈린다."""
        source = (
            POLICY_ROOT.parent / "adapters" / "arbiter_bag_category_gender.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('"BG-', source)


if __name__ == "__main__":
    unittest.main()
