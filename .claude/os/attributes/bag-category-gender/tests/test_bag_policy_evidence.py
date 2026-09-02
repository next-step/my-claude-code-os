#!/usr/bin/env python3
"""상세 이미지 정책 근거가 GT 오류 후보 큐에서 사라지지 않게 한다."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("프로젝트 루트를 찾지 못했습니다.")


PROJECT_ROOT = _find_project_root()
RUN_ROOT = PROJECT_ROOT / ".claude/os/runs/bag-category-gender"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class BagPolicyEvidenceTest(unittest.TestCase):
    def test_safe_sunday_is_policy_backed_gt_candidate(self) -> None:
        rows = read_jsonl(RUN_ROOT / "queue/golden-policy-violation-candidate.jsonl")
        row = next(item for item in rows if item["productKey"] == "EGOOCM:3398529")
        self.assertEqual("UNISEX", row["referenceLabel"])
        self.assertEqual("FEMALE", row["observedLabel"])
        self.assertEqual("HUMAN", row["detailEvidenceType"])
        self.assertIn("여성 모델", row["detailEvidence"])
        self.assertGreaterEqual(len(row["evidenceImageUrls"]), 1)

    def test_latest_fresh_evaluation_is_manifested(self) -> None:
        manifest = json.loads((RUN_ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["sources"]["evaluation"]["path"].endswith("final-complete.jsonl"))
        self.assertEqual(500, manifest["snapshots"]["bagPolicyEvaluation"]["count"])
        self.assertEqual(410, manifest["snapshots"]["bagPolicyDetailEvidence"]["count"])

    def test_denim_backpack_is_recovered_and_fully_processed(self) -> None:
        rows = read_jsonl(RUN_ROOT / "queue/image-collection-recovered.jsonl")
        row = next(item for item in rows if item["productKey"] == "EGOOCM:3411572")

        self.assertEqual("가방>캔버스백/에코백", row["standardCategory"])
        self.assertEqual("MALE", row["referenceLabel"])
        self.assertEqual("FEMALE", row["observedLabel"])
        self.assertEqual(19, row["allImageTileCount"])
        self.assertEqual(19, row["preparedTileCount"])
        self.assertEqual("COMPLETE", row["fullImageCoverageStatus"])
        self.assertEqual(["EGOOCM_PRODUCT_DETAIL_BFF"], row["collectionSources"])
        self.assertGreaterEqual(len(row["evidenceImageUrls"]), 1)

    def test_full_image_pipeline_is_summarized(self) -> None:
        summary = json.loads((RUN_ROOT / "run-summary.json").read_text(encoding="utf-8"))
        pipeline = summary["imagePipeline"]

        self.assertEqual(410, pipeline["detailProducts"])
        self.assertEqual(410, pipeline["completeCoverageProducts"])
        self.assertEqual(0, pipeline["failedDetailProducts"])
        self.assertEqual(105, pipeline["productsOverTwentyTiles"])

    def test_panier_color_variant_keeps_shared_detail_evidence(self) -> None:
        evaluations = read_jsonl(RUN_ROOT / "golden/bag-policy-evaluation.jsonl")
        evidence = read_jsonl(RUN_ROOT / "golden/bag-policy-detail-evidence.jsonl")
        row = next(item for item in evaluations if item["productKey"] == "EGOOCM:3424182")
        detail = next(item for item in evidence if item["productKey"] == "EGOOCM:3424182")

        self.assertEqual("FEMALE", row["productGender"])
        self.assertEqual("OK", row["detailStatus"])
        self.assertEqual("HUMAN", row["detailEvidenceType"])
        self.assertIn("여성 모델", row["detailEvidence"])
        self.assertEqual(9, detail["preparedTileCount"])
        self.assertEqual(11, detail["detailAssetCollectedTileCount"])
        self.assertEqual(9, detail["detailAssetRetainedTileCount"])
        self.assertEqual(9, detail["variantSharedRetainedTileCount"])
        self.assertEqual(
            "VARIANT_SHARED_ASSETS_RETAINED", detail["detailAssetFilterStatus"]
        )
        self.assertGreaterEqual(len(detail["evidenceImageUrls"]), 1)

        gaps = read_jsonl(RUN_ROOT / "queue/policy-golden-gap.jsonl")
        self.assertNotIn("EGOOCM:3424182", {item["productKey"] for item in gaps})
        recovered = read_jsonl(RUN_ROOT / "queue/evidence-pipeline-recovered.jsonl")
        self.assertIn("EGOOCM:3424182", {item["productKey"] for item in recovered})


if __name__ == "__main__":
    unittest.main()
