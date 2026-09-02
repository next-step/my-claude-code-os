#!/usr/bin/env python3
"""소유 정책 레이어가 계약을 지키는지, 그리고 정책 공백을 추적하는지 확인한다."""

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
BUILDER = PROJECT_ROOT / ".claude/os/engine/scripts/build_policy_index.py"

POLICY = """---
id: product-material
version: 2
owner: tester
updatedAt: 2026-09-02
---

# 대표 소재 정책

## 허용값

- `COTTON` — 면이 대표 소재다
- `WOOL` — 울이 대표 소재다
- `UNKNOWN` — 혼용률을 읽을 수 없다

## 근거 우선순위

1. 라벨 택 혼용률
2. 상품 설명

## 판정 불가 조건

- 혼용률 합이 100%가 아니다

## 판례

- [PM-0001](precedents/PM-0001.md)
"""


def precedent(identifier: str, **fields: str) -> str:
    meta = {"id": identifier, "profile": "product-material", "status": "OPEN", **fields}
    lines = "\n".join(f"{key}: {value}" for key, value in meta.items())
    return f"---\n{lines}\n---\n\n# 질문\n\n혼방에서 대표 소재를 무엇으로 정하는가?\n"


class PolicyLayerTest(unittest.TestCase):
    def build(self, root: Path, *, policy: str = POLICY, labels: list[str] | None = None) -> Path:
        layer = root / "policy"
        (layer / "precedents").mkdir(parents=True, exist_ok=True)
        (layer / "policy.md").write_text(policy, encoding="utf-8")
        run = root / "run"
        (run / "reports").mkdir(parents=True, exist_ok=True)
        profile = root / "material.json"
        profile.write_text(
            json.dumps(
                {
                    "schemaVersion": "catalog-data-profile-v1",
                    "id": "product-material",
                    "displayName": "상품 소재 감사",
                    "attributeName": "대표 소재",
                    "subjectName": "의류 상품",
                    "outputRoot": str(run),
                    "labels": labels if labels is not None else ["COTTON", "WOOL", "UNKNOWN"],
                    "policy": {
                        "owned": str(layer / "policy.md"),
                        "precedents": str(layer / "precedents"),
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return profile

    def run_builder(self, profile: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(BUILDER), "--profile", str(profile)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

    def index(self, root: Path) -> dict:
        return json.loads((root / "run/policy/policy-index.json").read_text(encoding="utf-8"))

    def test_valid_layer_reads_labels_and_precedents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.build(root)
            (root / "policy/precedents/PM-0001.md").write_text(
                precedent("PM-0001"), encoding="utf-8"
            )
            result = self.run_builder(profile)
            self.assertEqual(result.returncode, 0, result.stderr)
            index = self.index(root)
            self.assertEqual(index["owned"]["labels"], ["COTTON", "WOOL", "UNKNOWN"])
            self.assertEqual(index["owned"]["version"], "2")
            self.assertEqual(index["counts"]["open"], 1)
            self.assertEqual(index["counts"]["blockingViolations"], 0)
            self.assertTrue((root / "run/reports/policy-status.md").is_file())

    def test_missing_required_section_blocks_the_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            broken = POLICY.replace("## 판정 불가 조건", "## 잡담")
            profile = self.build(root, policy=broken)
            result = self.run_builder(profile)
            self.assertEqual(result.returncode, 1)
            self.assertIn("POLICY_SECTION_MISSING", result.stdout)

    def test_label_gap_is_untracked_until_a_precedent_acknowledges_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.build(root, labels=["COTTON", "WOOL", "UNCLASSIFIED"])
            result = self.run_builder(profile)
            self.assertEqual(result.returncode, 0, result.stderr)
            index = self.index(root)
            codes = {item["code"]: item for item in index["violations"]}
            self.assertIn("LABEL_NOT_IN_PROFILE", codes)
            self.assertFalse(codes["LABEL_NOT_IN_PROFILE"]["tracked"])
            self.assertEqual(index["counts"]["untrackedReviewViolations"], 2)

            (root / "policy/precedents/PM-0002.md").write_text(
                precedent("PM-0002", acknowledges="LABEL_NOT_IN_PROFILE, LABEL_NOT_IN_POLICY"),
                encoding="utf-8",
            )
            self.assertEqual(self.run_builder(profile).returncode, 0)
            index = self.index(root)
            codes = {item["code"]: item for item in index["violations"]}
            self.assertTrue(codes["LABEL_NOT_IN_PROFILE"]["tracked"])
            self.assertEqual(codes["LABEL_NOT_IN_PROFILE"]["trackedBy"], ["PM-0002"])
            self.assertEqual(index["counts"]["untrackedReviewViolations"], 0)

    def test_decided_precedent_needs_who_and_when(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.build(root)
            (root / "policy/precedents/PM-0001.md").write_text(
                precedent("PM-0001", status="DECIDED", decision="RATIO_MAJORITY"),
                encoding="utf-8",
            )
            result = self.run_builder(profile)
            self.assertEqual(result.returncode, 1)
            self.assertIn("PRECEDENT_MALFORMED", result.stdout)
            self.assertIn("decidedBy", result.stdout)

    def test_filename_and_id_must_agree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.build(root)
            (root / "policy/precedents/PM-0009.md").write_text(
                precedent("PM-0001"), encoding="utf-8"
            )
            result = self.run_builder(profile)
            self.assertEqual(result.returncode, 1)
            self.assertIn("PRECEDENT_MALFORMED", result.stdout)

    def test_profile_without_policy_block_skips_the_step(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.build(root)
            value = json.loads(profile.read_text(encoding="utf-8"))
            del value["policy"]
            profile.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            result = self.run_builder(profile)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("건너뜁니다", result.stdout)
            self.assertFalse((root / "run/policy/policy-index.json").exists())


if __name__ == "__main__":
    unittest.main()
