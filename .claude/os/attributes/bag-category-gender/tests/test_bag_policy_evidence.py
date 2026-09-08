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
    def test_policy_backed_gt_candidates_carry_their_detail_evidence(self) -> None:
        """GT 오류 후보는 근거 없이 큐에 오르지 않는다.

        특정 상품 하나를 못 박지 않는다. GT는 원본 저장소가 갱신하고, 이 큐가 지목한 건이
        다음 스냅샷에서 고쳐지면 큐에서 **빠지는 것이 정상**이다 — 실제로 EGOOCM:3398529는
        9/2 검수에서 UNISEX가 FEMALE로 바뀌며 후보에서 내려갔다. 라벨을 테스트에 적어 두면
        원본이 이 OS의 지적을 반영할 때마다 테스트가 깨진다. 변하면 안 되는 것은
        후보마다 상세 근거와 그 근거를 본 이미지가 붙어 있다는 것이다.
        """
        rows = read_jsonl(RUN_ROOT / "queue/golden-policy-violation-candidate.jsonl")
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(productKey=row["productKey"]):
                self.assertNotEqual(row["referenceLabel"], row["observedLabel"])
                self.assertEqual("HUMAN", row["detailEvidenceType"])
                self.assertTrue(row["detailEvidence"])
                self.assertGreaterEqual(len(row["evidenceImageUrls"]), 1)

    def test_latest_fresh_evaluation_is_manifested(self) -> None:
        manifest = json.loads((RUN_ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["sources"]["evaluation"]["path"].endswith("final-complete.jsonl"))
        self.assertEqual(500, manifest["snapshots"]["bagPolicyEvaluation"]["count"])
        self.assertEqual(410, manifest["snapshots"]["bagPolicyDetailEvidence"]["count"])

    def test_denim_backpack_is_recovered_and_fully_processed(self) -> None:
        rows = read_jsonl(RUN_ROOT / "queue/image-collection-recovered.jsonl")
        row = next(item for item in rows if item["productKey"] == "EGOOCM:3411572")

        # 라벨은 적지 않는다. 이 테스트가 지키는 것은 수집 복구이지 이번 GT의 값이 아니다.
        # (이 상품의 GT도 9/3 검수에서 MALE에서 FEMALE로 바뀌었다.)
        self.assertEqual("가방>캔버스백/에코백", row["standardCategory"])
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
