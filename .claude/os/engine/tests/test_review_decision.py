#!/usr/bin/env python3
"""승인 규격 — 판정은 어느 경계 위에 서는가.

정정은 라벨만으로 서지 않는다. 「이 GT를 FEMALE로 고쳐라」는 문장에는 **왜**가 없어서,
다음 사이클에 같은 건이 올라왔을 때 지난번에 무엇을 근거로 뒤집었는지 아무도 되짚지 못한다.
골든셋이 정책에서 조용히 떨어져 나가는 경로가 정확히 이것이다.

그래서 GT를 건드리는 판정은 근거가 된 판례를 밝히거나, 「걸리는 판례가 없다」를 명시해야
한다. 둘 다 없는 것과 「없다고 판단했다」는 다른 사실이고, 필드를 비워 두면 그 둘이
같은 모양이 된다.

여기서 기계가 지키는 것은 넷이다 — 규격을 어긴 판정이 거절되는가, 판례를 가리키면 어느
질문을 닫는지가 **저절로** 붙는가, 판례 레이어가 없는 속성은 그대로 도는가, 그리고
문이 둘이어도 규격이 하나인가.
"""

from __future__ import annotations

import json
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
SCRIPTS = PROJECT_ROOT / ".claude/os/engine/scripts"


def module():
    sys.path.insert(0, str(SCRIPTS))
    try:
        return __import__("record_review_decision")
    finally:
        sys.path.pop(0)


class Harness(unittest.TestCase):
    """가짜 속성 하나. 엔진이 이름을 아는 속성으로 시험하면 «속성을 지워도 돈다»가 안 보인다."""

    OPEN = {"id": "PR-1", "status": "OPEN", "answers": ["GQ-1"]}
    CLOSED = {"id": "PR-2", "status": "DECIDED", "answers": ["GQ-2"]}

    def build(self, precedents: list[dict] | None = None) -> tuple[dict, Path]:
        root = Path(self.enterContext(tempfile.TemporaryDirectory())) / "run"
        (root / "queue").mkdir(parents=True)
        # 큐에 있어야 판정할 수 있다. 그 규칙 자체는 여기서 시험하지 않으므로 한 줄 넣어 둔다.
        (root / "queue/signal.jsonl").write_text(
            json.dumps({"productKey": "P1", "signal": "SOME_SIGNAL"}) + "\n", encoding="utf-8"
        )
        if precedents is not None:
            (root / "policy").mkdir(parents=True)
            (root / "policy/policy-index.json").write_text(
                json.dumps({"precedents": precedents}), encoding="utf-8"
            )
        profile = {"id": "widget-finish", "labels": ["MATTE", "GLOSS"]}
        return profile, root

    def put(self, profile: dict, root: Path, **kwargs):
        base = {
            "product_key": "P1",
            "decision": "GOLDEN_CORRECTION_NEEDED",
            "reviewer": "mj",
            "reason": "근거를 봤다",
            "corrected_label": "MATTE",
        }
        return module().record(profile=profile, root=root, **(base | kwargs))


class BindingTest(Harness):
    def test_a_gt_decision_without_a_policy_binding_is_refused(self) -> None:
        """비워 두면 규격이 장식이 된다. 안 적은 것과 없다고 판단한 것은 다른 사실이다."""
        profile, root = self.build([self.OPEN])
        with self.assertRaises(module().DecisionRejected) as refused:
            self.put(profile, root)
        # 무엇을 골라야 하는지가 거절 문장 안에 있어야 한다.
        self.assertIn("PR-1", str(refused.exception))

    def test_naming_no_precedent_is_itself_an_answer(self) -> None:
        """«걸리는 판례가 없다»는 판단이다. 그런 판정이 쌓이는 것이 아직 없는 판례를 가리킨다."""
        profile, root = self.build([self.OPEN])
        entry = self.put(profile, root, no_precedent=True)
        self.assertIsNone(entry["precedentId"])

    def test_an_unknown_precedent_is_refused(self) -> None:
        """오타 하나가 조용히 미배정 더미로 떨어지면, 매핑은 있으나 마나다."""
        profile, root = self.build([self.OPEN])
        with self.assertRaises(module().DecisionRejected):
            self.put(profile, root, precedent_id="PR-9")

    def test_the_precedent_says_which_question_it_closes(self) -> None:
        """사람이 질문 ID를 손으로 옮겨 적게 두면 오타가 난다. 판례가 스스로 답한다."""
        profile, root = self.build([self.OPEN, self.CLOSED])
        entry = self.put(profile, root, precedent_id="PR-2")
        self.assertEqual(entry["policyQuestionId"], "GQ-2")
        # 판정 당시 상태는 이력으로 남는다. 지금 나갈지 말지는 파생기가 살아 있는 상태로 정한다.
        self.assertEqual(entry["precedentStatusAtDecision"], "DECIDED")

    def test_pointing_at_a_precedent_and_denying_one_at_once_is_refused(self) -> None:
        profile, root = self.build([self.OPEN])
        with self.assertRaises(module().DecisionRejected):
            self.put(profile, root, precedent_id="PR-1", no_precedent=True)


class AttributeAgnosticTest(Harness):
    """정책 레이어는 선택이다. 없는 것을 요구하면 엔진이 속성의 구성을 강요하게 된다."""

    def test_an_attribute_without_a_precedent_layer_records_as_before(self) -> None:
        profile, root = self.build(precedents=None)
        entry = self.put(profile, root)
        self.assertIsNone(entry["precedentId"])
        self.assertEqual(entry["correctedLabel"], "MATTE")

    def test_a_decision_that_never_touches_gt_needs_no_binding(self) -> None:
        """정책 공백과 실행 결함은 GT의 문제가 아니다. 고칠 곳이 정반대라 판례를 물을 이유가 없다."""
        profile, root = self.build([self.OPEN])
        entry = self.put(profile, root, decision="POLICY_GAP_CONFIRMED", corrected_label=None)
        self.assertEqual(entry["decision"], "POLICY_GAP_CONFIRMED")


class OneDoorTest(Harness):
    """터미널로 온 판정과 버튼으로 온 판정이 같은 검사를 받아야 원장이 한 벌로 남는다."""

    def test_the_server_records_through_the_same_function(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        try:
            serve = __import__("serve_reports")
        finally:
            sys.path.pop(0)
        self.assertIs(serve.record, module().record)

    def test_a_label_outside_the_profile_is_refused(self) -> None:
        profile, root = self.build([self.OPEN])
        with self.assertRaises(module().DecisionRejected):
            self.put(profile, root, corrected_label="CHROME", precedent_id="PR-1")

    def test_a_reason_is_required(self) -> None:
        """라벨만 남으면 다음 사람이 그 값을 되짚을 수 없다."""
        profile, root = self.build([self.OPEN])
        with self.assertRaises(module().DecisionRejected):
            self.put(profile, root, reason="  ", precedent_id="PR-1")


if __name__ == "__main__":
    unittest.main()
