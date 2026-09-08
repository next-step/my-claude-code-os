#!/usr/bin/env python3
"""보고서 형태 점검이 실제로 무엇을 잡는지 고정한다.

점검이 조용히 아무것도 안 잡는 것이 가장 나쁜 실패다. 통과 케이스 하나로는
그걸 구별할 수 없으므로, 검사마다 그 검사만 깨지는 run을 만들어 확인한다.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("프로젝트 루트를 찾지 못했습니다.")


PROJECT_ROOT = _find_project_root()
CHECKER = PROJECT_ROOT / ".claude/os/engine/scripts/check_report_shape.py"


def build_run(root: Path, run_id: str = "demo") -> Path:
    """계약을 지키는 최소한의 run. 각 테스트는 여기서 한 군데만 망가뜨린다."""
    run = root / ".claude/os/runs" / run_id
    (run / "queue").mkdir(parents=True)
    (run / "reports").mkdir()
    (run / "queue/sample-gap.jsonl").write_text(
        '{"signal": "SAMPLE_GAP", "productKey": "TEST:1"}\n'
        '{"signal": "SAMPLE_GAP", "productKey": "TEST:2"}\n',
        encoding="utf-8",
    )
    html = run / "reports/catalog-audit.html"
    html.write_text("<html><body>SAMPLE_GAP 2</body></html>", encoding="utf-8")
    audit = run / "reports/audit.md"
    audit.write_text("# 감사\n\n- 대상: 7건\n- 공백: 2건\n- 처리율: 25.00%\n", encoding="utf-8")
    summary: dict[str, Any] = {
        "profileId": run_id,
        "products": 7,
        "completed": True,
        "adjudicationRate": 0.25,
        "signals": {"sampleGap": 2},
        "artifacts": {
            "htmlReport": str(html.relative_to(root)),
            "auditReport": str(audit.relative_to(root)),
        },
    }
    (run / "run-summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    return run


def check(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--project-root", str(root), "--all"],
        capture_output=True,
        text=True,
        input="{}",
    )


class ReportShapeCheckTest(unittest.TestCase):
    def test_a_contract_abiding_run_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_run(root)
            result = check(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")

    def test_declared_artifact_that_is_missing_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = build_run(root)
            (run / "reports/audit.md").unlink()
            result = check(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("artifacts.auditReport", result.stderr)

    def test_queue_count_drifting_from_the_summary_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = build_run(root)
            with (run / "queue/sample-gap.jsonl").open("a", encoding="utf-8") as queue:
                queue.write('{"signal": "SAMPLE_GAP", "productKey": "TEST:3"}\n')
            result = check(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("signals.sampleGap", result.stderr)
            self.assertIn("3건", result.stderr)

    def test_a_queue_the_summary_never_counted_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = build_run(root)
            (run / "queue/unknown-signal.jsonl").write_text(
                '{"signal": "UNKNOWN_SIGNAL", "productKey": "TEST:9"}\n', encoding="utf-8"
            )
            result = check(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("unknown-signal.jsonl", result.stderr)

    def test_a_number_the_summary_cannot_produce_is_caught(self) -> None:
        """이 프로젝트의 규칙 — 다시 세어야 하는 숫자를 문서에 적지 않는다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = build_run(root)
            report = run / "reports/audit.md"
            report.write_text(report.read_text(encoding="utf-8") + "- 손으로 적은 값: 41건\n", encoding="utf-8")
            result = check(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("41건", result.stderr)

    def test_version_and_year_numbers_are_not_mistaken_for_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = build_run(root)
            report = run / "reports/audit.md"
            report.write_text(
                report.read_text(encoding="utf-8") + "- 정책 v3, 2026-09-02 기준, 우선순위 2\n",
                encoding="utf-8",
            )
            result = check(root)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_html_missing_a_signal_the_summary_counted_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = build_run(root)
            (run / "reports/catalog-audit.html").write_text(
                "<html><body>옛 실행</body></html>", encoding="utf-8"
            )
            result = check(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("SAMPLE_GAP", result.stderr)

    def test_runs_untouched_recently_are_left_alone(self) -> None:
        """훅은 모든 Bash 뒤에 붙는다. 무관한 명령에서 옛 run을 들추면 소음이 된다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = build_run(root)
            (run / "reports/audit.md").unlink()
            result = subprocess.run(
                [sys.executable, str(CHECKER), "--project-root", str(root), "--fresh-seconds", "0"],
                capture_output=True,
                text=True,
                input="{}",
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
