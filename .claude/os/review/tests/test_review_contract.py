#!/usr/bin/env python3
"""심사 패키지의 계약을 지킨다.

심사의 값어치는 **엔진과 다른 눈으로 본다**는 데 있다. 엔진 코드를 부르는 순간 같은 오해가
양쪽에 그대로 들어가고, 산출물을 고치는 순간 어느 숫자가 원본인지 아무도 모르게 된다.
그래서 두 가지를 기계가 지킨다 — 엔진을 모르는가, 그리고 읽기만 하는가.
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
    raise RuntimeError("프로젝트 루트를 찾지 못했습니다.")


PROJECT_ROOT = _find_project_root()
OS_ROOT = PROJECT_ROOT / ".claude/os"
REVIEW_SCRIPTS = OS_ROOT / "review/scripts"
REVIEWER = REVIEW_SCRIPTS / "review_run.py"

# 엔진과 속성에 손을 뻗는 순간 나타나는 흔적들.
ENGINE_REACH = ("catalog_profile", "engine/scripts", "attributes/", "profile.json", "adapters")
# 엔진과 같은 금칙어. 심사는 속성이 무엇인지 모른 채 돈다.
FORBIDDEN = ("가방", "성별", "29CM", "MALE", "FEMALE", "UNISEX", "productGender", "bag-category-gender")


def review_sources() -> list[Path]:
    return sorted(path for path in REVIEW_SCRIPTS.glob("**/*.py") if "__pycache__" not in path.parts)


def run_review(run: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REVIEWER), "--run", str(run), *extra],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )


def snapshot(root: Path) -> dict[str, bytes]:
    """`run-review/` 밖의 모든 파일 내용. 심사가 무엇 하나라도 고치면 이 사전이 달라진다."""
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "run-review" not in path.relative_to(root).parts
    }


class RunFixture:
    """낯선 속성의 run 하나를 손으로 만든다. 심사는 이 속성이 무엇인지 알 길이 없다."""

    def __init__(self, root: Path) -> None:
        self.run = root / "run"
        for name in ("queue", "reports", "review"):
            (self.run / name).mkdir(parents=True, exist_ok=True)

    def queue(self, rows: list[dict[str, object]]) -> None:
        (self.run / "queue/ratio-gap.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
        )

    def verdicts(self, rows: list[dict[str, object]]) -> None:
        (self.run / "review/verdicts.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
        )

    def ledger(self, decisions: list[dict[str, object]]) -> None:
        (self.run / "review/decisions.json").write_text(
            json.dumps(
                {"schemaVersion": "catalog-review-v1", "profileId": "run-fixture", "decisions": decisions},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def summary(self, **overrides: object) -> None:
        artifacts = {
            "queueDirectory": str(self.run / "queue"),
            "arbiterVerdicts": str(self.run / "review/verdicts.jsonl"),
            "decisionLedger": str(self.run / "review/decisions.json"),
        }
        for key, value in dict(overrides.pop("artifacts", {})).items():  # type: ignore[arg-type]
            if value is None:
                artifacts.pop(key, None)  # 선언 자체가 없는 상태를 만든다
            else:
                artifacts[key] = str(value)
        summary = {
            "generatedAt": "2026-09-02T00:00:00+00:00",
            "profileId": "run-fixture",
            "artifacts": artifacts,
            "signals": {"ratioGap": 2},
            "reviewProgress": {
                "queuedProducts": 2,
                "adjudicatedProducts": 0,
                "deferredProducts": 0,
                "pendingProducts": 2,
            },
            "policyLayer": {"untrackedReviewViolations": 0, "blockingViolations": 0},
        }
        summary.update(overrides)
        (self.run / "run-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def healthy(self) -> Path:
        self.queue(
            [
                {
                    "signal": "MATERIAL_RATIO_GAP",
                    "reason": "면 50%, 울 50%에서 대표 소재 기준이 없다.",
                    "productKey": "TEST:1",
                    "referenceLabel": "COTTON",
                    "observedLabel": "UNKNOWN",
                },
                {
                    "signal": "MATERIAL_RATIO_GAP",
                    "reason": "혼용률 합이 100%가 아니다.",
                    "productKey": "TEST:2",
                    "referenceLabel": "COTTON",
                    "observedLabel": "UNKNOWN",
                },
            ]
        )
        self.verdicts(
            [
                {"productKey": "TEST:1", "owner": "POLICY", "blockedBy": []},
                {"productKey": "TEST:2", "owner": "GOLDEN", "blockedBy": []},
            ]
        )
        self.ledger([])
        self.summary()
        return self.run


class ReviewKnowsNothingTest(unittest.TestCase):
    def test_review_never_reaches_into_the_engine_or_an_attribute(self) -> None:
        offenders = [
            f"{path.relative_to(OS_ROOT)}: `{term}`"
            for path in review_sources()
            for term in ENGINE_REACH
            if term in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(
            offenders,
            [],
            "심사가 엔진이나 속성에 손을 뻗습니다. 인계는 run-summary.json 하나뿐입니다:\n"
            + "\n".join(offenders),
        )

    def test_no_domain_vocabulary(self) -> None:
        offenders = [
            f"{path.relative_to(OS_ROOT)}: `{term}`"
            for path in review_sources()
            for term in FORBIDDEN
            if term in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [], "심사에 도메인 어휘가 있습니다:\n" + "\n".join(offenders))


class HealthyRunTest(unittest.TestCase):
    def test_a_clean_run_passes_and_records_every_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = RunFixture(Path(temporary)).healthy()
            result = run_review(run, "--strict")
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((run / "run-review/run-review.json").read_text(encoding="utf-8"))
            self.assertEqual(report["verdict"], "PASS", report["findings"])
            self.assertEqual(report["recount"]["pendingProducts"], 2)
            self.assertEqual(report["reviewLoad"]["decidableNow"], 2)
            self.assertEqual(
                [check["status"] for check in report["checks"]], ["RAN"] * len(report["checks"])
            )

    def test_review_writes_nothing_outside_its_own_folder(self) -> None:
        """읽는 쪽이 원본을 고치면 어느 숫자가 원본인지 알 수 없게 된다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = RunFixture(root).healthy()
            before = snapshot(root)
            run_review(run)
            self.assertEqual(snapshot(root), before, "심사가 엔진 산출물이나 판정 원장을 고쳤습니다.")
            self.assertTrue((run / "run-review/findings.jsonl").is_file())


class BrokenRunTest(unittest.TestCase):
    def build(self, root: Path) -> Path:
        fixture = RunFixture(root)
        fixture.healthy()
        # 근거 없는 큐 행, 심판이 빠뜨린 상품, 옛 실행의 진행률, 추적되지 않는 공백.
        fixture.queue(
            [
                {
                    "signal": "MATERIAL_RATIO_GAP",
                    "reason": "",
                    "productKey": "TEST:1",
                    "referenceLabel": "COTTON",
                    "observedLabel": "UNKNOWN",
                },
                {
                    "signal": "MATERIAL_RATIO_GAP",
                    "reason": "혼용률 합이 100%가 아니다.",
                    "productKey": "TEST:3",
                    "referenceLabel": "COTTON",
                    "observedLabel": "UNKNOWN",
                },
            ]
        )
        fixture.summary(
            artifacts={"policyStatus": str(root / "run/reports/does-not-exist.md")},
            reviewProgress={
                "queuedProducts": 2,
                "adjudicatedProducts": 0,
                "deferredProducts": 0,
                "pendingProducts": 99,
            },
            policyLayer={"untrackedReviewViolations": 2, "blockingViolations": 0},
        )
        return fixture.run

    def test_a_broken_run_fails_with_one_finding_per_defect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = self.build(Path(temporary))
            self.assertEqual(run_review(run).returncode, 0, "기본값은 막지 않는다. 지목이 산출물이다")
            self.assertEqual(run_review(run, "--strict").returncode, 1)
            report = json.loads((run / "run-review/run-review.json").read_text(encoding="utf-8"))
            self.assertEqual(report["verdict"], "FAIL")
            errors = {
                finding["check"] for finding in report["findings"] if finding["severity"] == "ERROR"
            }
            self.assertEqual(
                errors,
                {"ARTIFACT_DECLARED", "QUEUE_CONTRACT", "PROGRESS_RECOUNT", "VERDICT_COVERAGE",
                 "POLICY_TRACKING"},
            )
            first = json.loads(
                (run / "run-review/findings.jsonl").read_text(encoding="utf-8").splitlines()[0]
            )
            self.assertTrue(first["sample"], "지적에 근거 표본이 없으면 지목이 아니다")


class LateDecisionTest(unittest.TestCase):
    """같은 불일치라도 원인이 다르면 사람이 할 일이 다르다."""

    def test_a_decision_recorded_after_the_summary_is_a_warning_not_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = RunFixture(Path(temporary))
            run = fixture.healthy()
            fixture.ledger(
                [
                    {
                        "decisionId": "BR-1",
                        "productKey": "TEST:1",
                        "decision": "GOLDEN_CONFIRMED",
                        "queueSignals": ["MATERIAL_RATIO_GAP"],
                        "reviewedAt": "2026-09-03T00:00:00+00:00",
                    }
                ]
            )
            run_review(run)
            report = json.loads((run / "run-review/run-review.json").read_text(encoding="utf-8"))
            recount = [f for f in report["findings"] if f["check"] == "PROGRESS_RECOUNT"]
            self.assertEqual([f["severity"] for f in recount], ["WARN"], report["findings"])
            self.assertEqual(report["verdict"], "WARN")


class UndeclaredArtifactTest(unittest.TestCase):
    """선언하지 않은 것은 심사하지 않는다. 대신 못 봤다고 남긴다."""

    def test_missing_declarations_become_skipped_checks_not_silent_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = RunFixture(Path(temporary))
            run = fixture.healthy()
            fixture.summary(
                artifacts={"arbiterVerdicts": None, "decisionLedger": None},
                reviewProgress={
                    "queuedProducts": 2,
                    "adjudicatedProducts": 0,
                    "deferredProducts": 0,
                    "pendingProducts": 2,
                },
            )
            run_review(run)
            report = json.loads((run / "run-review/run-review.json").read_text(encoding="utf-8"))
            skipped = {check["check"] for check in report["checks"] if check["status"] == "SKIPPED"}
            self.assertEqual(skipped, {"VERDICT_COVERAGE", "REVIEW_LOAD", "LEDGER_ALIGNMENT"})
            self.assertTrue(
                all(check.get("reason") for check in report["checks"] if check["status"] == "SKIPPED"),
                "건너뛴 이유가 없으면 통과와 구별되지 않는다",
            )
            self.assertEqual(report["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
