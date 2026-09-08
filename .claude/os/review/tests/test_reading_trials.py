#!/usr/bin/env python3
"""채점기가 지켜야 할 것.

이 채점기의 값은 「몇 점인가」가 아니라 **「갈렸는가」**에 있다. 3번 중 2번 맞힌 것을
다수결로 「맞음」으로 접으면, 그 사례가 아직 어렵다는 사실이 지워진다. 판독을 다수결로
합치지 않는다는 규칙과 같은 것이고, 여기서는 기계가 지킨다.
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
SCRIPT = PROJECT_ROOT / ".claude/os/review/scripts/score_reading_trials.py"
CASES = PROJECT_ROOT / ".claude/os/review/cases/reading-cases.json"


def score(root: Path, trials: dict) -> dict:
    run = root / "runs" / "demo"
    run.mkdir(parents=True, exist_ok=True)
    path = root / "trials.json"
    path.write_text(json.dumps(trials, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--run", str(run), "--cases", str(CASES), "--trials", str(path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads((run / "run-review/reading-trials.json").read_text(encoding="utf-8"))


class ScoringTest(unittest.TestCase):
    def test_a_split_is_reported_not_folded(self) -> None:
        """2:1로 갈린 것을 «맞음»으로 접으면 그 사례가 어렵다는 사실이 사라진다."""
        with tempfile.TemporaryDirectory() as temporary:
            record = score(
                Path(temporary),
                {"trials": [
                    {"caseId": "G4-clear-face", "run": 1,
                     "answer": {"appearance": "FEMININE", "faceVisibility": "VISIBLE"}},
                    {"caseId": "G4-clear-face", "run": 2,
                     "answer": {"appearance": "FEMININE", "faceVisibility": "PARTIAL"}},
                    {"caseId": "G4-clear-face", "run": 3,
                     "answer": {"appearance": "FEMININE", "faceVisibility": "VISIBLE"}},
                ]},
            )
            item = record["results"][0]
            self.assertEqual(item["hits"], 2)
            self.assertEqual(item["distinctAnswers"], 2)
            self.assertEqual(len(item["misses"]), 1)

    def test_phases_are_not_merged(self) -> None:
        """고치기 전과 후를 섞으면 «고쳐서 좋아졌다»와 «원래 그랬다»가 구분되지 않는다."""
        with tempfile.TemporaryDirectory() as temporary:
            record = score(
                Path(temporary),
                {"trials": [
                    {"caseId": "L2-variant-colorway", "phase": "before", "run": 1,
                     "answer": {"isTarget": "MATCH"}},
                    {"caseId": "L2-variant-colorway", "run": 1, "answer": {"isTarget": "VARIANT"}},
                ]},
            )
            phases = {item["phase"]: item["hits"] for item in record["results"]}
            self.assertEqual(phases, {"before": 0, "final": 1})

    def test_a_contrast_pair_that_collapses_is_counted(self) -> None:
        """같은 프레임의 두 사람이 같은 값으로 나오면 판독기가 한쪽으로 쏠린 것이다."""
        with tempfile.TemporaryDirectory() as temporary:
            record = score(
                Path(temporary),
                {"trials": [
                    {"caseId": "G1-banner-left", "run": 1,
                     "answer": {"appearance": "FEMININE", "faceVisibility": "VISIBLE"}},
                    {"caseId": "G2-banner-right", "run": 1,
                     "answer": {"appearance": "FEMININE", "faceVisibility": "VISIBLE"}},
                ]},
            )
            self.assertEqual(record["contrasts"][0]["collapsed"], 1)

    def test_an_either_or_expectation_accepts_both(self) -> None:
        """정책이 착용과 휴대를 같이 세는 자리가 있다. 한쪽만 정답으로 두면 틀린 채점이 된다."""
        with tempfile.TemporaryDirectory() as temporary:
            record = score(
                Path(temporary),
                {"trials": [
                    {"caseId": "L4-true-carry", "run": 1,
                     "answer": {"isTarget": "MATCH", "holds": "CARRIED"}},
                ]},
            )
            self.assertEqual(record["results"][0]["hits"], 1)

    def test_every_case_declares_why_its_expectation_is_right(self) -> None:
        """근거 없는 정답은 채점을 «내가 그렇게 생각한다»로 만든다."""
        cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
        allowed = {"STRUCTURAL", "CONTRAST", "CORROBORATED"}
        for case in cases:
            self.assertIn(case["truthBasis"], allowed, case["id"])
            self.assertTrue(case.get("why"), f"{case['id']}에 기대의 근거가 없다")


if __name__ == "__main__":
    unittest.main()
