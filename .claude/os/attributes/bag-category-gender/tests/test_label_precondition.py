#!/usr/bin/env python3
"""GT를 **실행과 무관하게** 정책과 대조하는 검사가 지켜야 할 것.

이 검사가 없던 동안의 사각은 커버리지가 아니라 **동조**였다. 실행이 GT와 같은 값을 내면
비교할 것이 없어 조용했고, 둘이 함께 정책을 어긴 자리가 그대로 지나갔다.
실측으로 17건이 어떤 큐에도 없었고 전부 `GT=UNISEX · 실행=UNISEX`였다.

여기서 기계가 지키는 것은 넷이다 — 실행을 안 봐도 잡는가, 정책이 허용한 자리는 놔두는가,
정책이 말하지 않은 자리를 «위반»으로 부르지 않는가, 그리고 심판이 그 지적을
「충돌 없음」으로 덮지 않는가.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("프로젝트 루트를 찾지 못했다")


PROJECT_ROOT = _find_project_root()
PACK = PROJECT_ROOT / ".claude/os/attributes/bag-category-gender"
PRECONDITIONS = json.loads(
    (PACK / "policy/label-preconditions.json").read_text(encoding="utf-8")
)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = _load("audit_bcg", PACK / "adapters/audit_bag_category_gender.py")
ARBITER = _load("arbiter_bcg", PACK / "adapters/arbiter_bag_category_gender.py")
POLICY = (PACK / "policy/policy.md").read_text(encoding="utf-8")


def gt(product_key: str, label: str, category: str, **extra):
    return {
        "productKey": product_key,
        "productName": f"{product_key} 상품",
        "goldLabel": label,
        "standardCategory": category,
        **extra,
    }


class PreconditionTest(unittest.TestCase):
    def test_it_catches_a_violation_the_executor_agreed_with(self) -> None:
        """실행과 GT가 같으면 비교할 것이 없다. 그때도 잡아야 한다 — 사각의 정체가 이것이었다."""
        rows = [gt("A:1", "UNISEX", "가방>토트백")]
        evaluations = {"A:1": {"productGender": "UNISEX"}}
        violations, silent = AUDIT.label_precondition_findings(rows, evaluations, PRECONDITIONS)
        self.assertEqual([item["productKey"] for item in violations], ["A:1"])
        self.assertEqual(violations[0]["observedLabel"], "UNISEX")
        self.assertEqual(silent, [])

    def test_it_catches_a_product_the_executor_never_evaluated(self) -> None:
        rows = [gt("A:2", "UNISEX", "가방>숄더백/쇼퍼백>숄더백")]
        violations, _ = AUDIT.label_precondition_findings(rows, {}, PRECONDITIONS)
        self.assertEqual(violations[0]["observedLabel"], "NOT_EVALUATED")
        self.assertFalse(violations[0]["evaluated"])

    def test_the_category_the_policy_allows_is_left_alone(self) -> None:
        """정책이 «기능·구조가 명확히 공용»으로 인정한 자리까지 지목하면 잡음이 된다."""
        rows = [
            gt("A:3", "UNISEX", "가방>백팩>스탠다드 백팩"),
            gt("A:4", "UNISEX", "가방>여행용 가방>캐리어"),
        ]
        violations, silent = AUDIT.label_precondition_findings(rows, {}, PRECONDITIONS)
        self.assertEqual(violations, [])
        self.assertEqual(silent, [])

    def test_a_category_the_policy_never_mentions_is_a_policy_gap_not_a_gt_error(self) -> None:
        """정책이 말하지 않은 자리를 «위반»으로 부르면, 고칠 대상이 GT로 잘못 지목된다."""
        rows = [gt("A:5", "UNISEX", "가방>클러치/파우치>파우치")]
        violations, silent = AUDIT.label_precondition_findings(rows, {}, PRECONDITIONS)
        self.assertEqual(violations, [])
        self.assertEqual([item["signal"] for item in silent], ["POLICY_LABEL_SILENT"])

    def test_a_parent_segment_does_not_trigger_the_match(self) -> None:
        """분류 경로 전체로 맞추면 부모 마디에 걸린다.

        `가방>숄더백/쇼퍼백>쇼퍼백`이 부모의 «숄더» 때문에 지목된 적이 있다.
        정책이 말한 것은 그 상품이 무엇인가이지 어느 묶음에 속하는가가 아니다.
        """
        rows = [gt("A:11", "UNISEX", "가방>숄더백/쇼퍼백>쇼퍼백")]
        violations, silent = AUDIT.label_precondition_findings(rows, {}, PRECONDITIONS)
        self.assertEqual(violations, [])
        self.assertEqual([item["productKey"] for item in silent], ["A:11"])

    def test_the_matched_word_reported_is_the_policy_word(self) -> None:
        """지적을 읽는 사람이 정책의 어느 문장에 걸렸는지 바로 알아야 한다."""
        rows = [gt("A:12", "UNISEX", "가방>숄더백/쇼퍼백>숄더백")]
        violations, _ = AUDIT.label_precondition_findings(rows, {}, PRECONDITIONS)
        self.assertEqual(violations[0]["matchedToken"], "숄더")

    def test_other_labels_are_not_touched(self) -> None:
        rows = [gt("A:6", "FEMALE", "가방>토트백"), gt("A:7", "MALE", "가방>토트백")]
        violations, silent = AUDIT.label_precondition_findings(rows, {}, PRECONDITIONS)
        self.assertEqual((violations, silent), ([], []))

    def test_a_losing_lineage_that_passes_is_named(self) -> None:
        """원장의 순위 규칙이 정책을 어기는 쪽을 골랐다면, 그게 이 건의 가장 강한 근거다."""
        rows = [
            gt(
                "A:8",
                "UNISEX",
                "가방>토트백",
                otherLineages=[{"goldLabel": "FEMALE", "lineage": "reviewSheet"}],
            ),
            gt(
                "A:9",
                "UNISEX",
                "가방>토트백",
                otherLineages=[{"goldLabel": "UNDETERMINED", "lineage": "reviewSheet"}],
            ),
            gt("A:10", "UNISEX", "가방>토트백"),
        ]
        violations, _ = AUDIT.label_precondition_findings(rows, {}, PRECONDITIONS)
        kinds = {item["productKey"]: item["lineageAlternativeKind"] for item in violations}
        # 「진 계보가 다른 확정 라벨을 갖고 있다」와 「진 계보도 판정 못 했다」는 다른 사건이다.
        self.assertEqual(kinds, {"A:8": "DECIDED_LABEL", "A:9": "UNDETERMINED_ONLY", "A:10": "NONE"})


class NearMissTest(unittest.TestCase):
    """공백 72건을 뭉뚱그리지 않는다. 정책 한 줄이면 갈리는 자리를 먼저 물어야 한다."""

    def test_a_policy_word_in_the_parent_segment_is_flagged(self) -> None:
        rows = [gt("A:20", "UNISEX", "가방>숄더백/쇼퍼백>쇼퍼백")]
        _, silent = AUDIT.label_precondition_findings(rows, {}, PRECONDITIONS)
        self.assertEqual(silent[0]["nearMiss"]["policyWord"], "숄더")
        self.assertEqual(silent[0]["nearMiss"]["where"], "분류의 상위 마디")

    def test_a_policy_word_in_the_product_name_is_flagged(self) -> None:
        """분류가 «기타 가방»인데 이름이 «…토트백»인 건이 실제로 둘 있었다."""
        rows = [gt("A:21", "UNISEX", "가방>기타 가방")]
        rows[0]["productName"] = "CO 멀티 포켓 토트백_Black"
        _, silent = AUDIT.label_precondition_findings(rows, {}, PRECONDITIONS)
        self.assertEqual(silent[0]["nearMiss"]["where"], "상품명")

    def test_a_plain_gap_carries_no_hint(self) -> None:
        rows = [gt("A:22", "UNISEX", "가방>클러치/파우치>파우치")]
        _, silent = AUDIT.label_precondition_findings(rows, {}, PRECONDITIONS)
        self.assertIsNone(silent[0]["nearMiss"])


class TokensComeFromThePolicyTest(unittest.TestCase):
    """술어에 **정책에 없는 낱말**을 넣으면 검사가 정책보다 넓게 잡는다.

    실제로 그랬다 — 호보·버킷·슬링·메신저를 넣어 정책에 없는 근거로 다섯 건을 지목했고,
    그 차이는 아무 데도 안 적혀 있었다. 「정책을 옮긴 것」이라 써 놓고 정책을 늘린 셈이다.
    사람이 매번 대조할 수 없으므로 여기서 기계가 막는다.
    """

    def test_every_policy_word_appears_verbatim_in_the_quote(self) -> None:
        for rule in PRECONDITIONS["rules"]:
            quote = " ".join(rule["quote"])
            for side in ("allow", "deny"):
                for entry in rule[side]:
                    word = entry["policyWord"]
                    with self.subTest(side=side, word=word):
                        self.assertIn(word, quote, f"인용문에 없는 낱말이다: {word}")

    def test_the_quote_appears_verbatim_in_the_policy(self) -> None:
        """인용문 자체가 정책에서 왔는지도 본다. 인용이 흘러가면 위 검사가 무의미해진다."""
        for rule in PRECONDITIONS["rules"]:
            for line in rule["quote"]:
                with self.subTest(line=line[:24]):
                    self.assertIn(line, POLICY)


class ArbiterAgreesWithTheAuditTest(unittest.TestCase):
    """감사가 지목한 자리를 심판이 「충돌 없음」으로 덮으면 지적이 사라진다.

    실제로 그랬다 — 감사가 36건을 올렸는데 심판이 그중 넷을 조용히 덮었다.
    둘이 같은 술어 파일을 읽는 것이 그 재발을 막는다.
    """

    def test_the_arbiter_reads_the_same_precondition_file(self) -> None:
        self.assertEqual(ARBITER._PRECONDITIONS, PRECONDITIONS)

    def test_a_denied_category_gets_a_policy_answer_instead_of_no_rule(self) -> None:
        row = {"standardCategory": "가방>토트백", "detailStatus": "SKIPPED"}
        answer = ARBITER.policy_answer(row)
        self.assertEqual(answer["rule"], "P0_CATEGORY_NOT_UNISEX")
        self.assertEqual(answer["strength"], ARBITER.STRONG)

    def test_an_allowed_category_still_falls_through(self) -> None:
        row = {"standardCategory": "가방>백팩>스탠다드 백팩", "detailStatus": "SKIPPED"}
        self.assertEqual(ARBITER.policy_answer(row)["rule"], "NO_APPLICABLE_RULE")

    def test_a_mixed_wearer_sentence_is_not_strong_evidence(self) -> None:
        """이 주장으로 사람 GT를 뒤집자고 한 6건을 사진으로 되짚었더니 전부 무너졌다.

        문자열 하나가 두 가지를 함께 주장한다 — 두 성별 관측과 대상 동일성.
        정규식은 어느 쪽도 못 본다. 지우지는 않는다. 사진으로 보면 설 수도 있다.
        """
        row = {
            "detailStatus": "OK",
            "detailEvidenceType": "HUMAN",
            "detailEvidence": "동일 대상 상품을 실제 착용한 남성·여성 모델이 모두 확인됨.",
        }
        answer = ARBITER.policy_answer(row)
        self.assertEqual(answer["rule"], "P3_MIXED_WEARER")
        self.assertEqual(answer["strength"], ARBITER.WEAK)
        self.assertEqual(answer["label"], ARBITER.UNRESOLVABLE)


if __name__ == "__main__":
    unittest.main()
