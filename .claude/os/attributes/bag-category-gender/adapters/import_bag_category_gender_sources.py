#!/usr/bin/env python3
"""가방 성별 정책과 상품 단위 GT를 재현 가능한 로컬 스냅샷으로 가져온다."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("프로젝트 루트(.claude를 가진 폴더)를 찾지 못했습니다.")


PROJECT_ROOT = _find_project_root()
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / ".claude" / "os" / "runs" / "bag-category-gender"
DEFAULT_SOURCE_REPO = PROJECT_ROOT.parent / "core-catalog-platfom"
POLICY_SOURCE = Path(
    "core/src/main/resources/prompts/image-gender/v1000/bag-role-aware-judge.txt"
)
CANONICAL_GT_SOURCE = Path("tool/product-gender/gt-harness/data/gt.jsonl")
EVALUATION_SOURCE = Path(
    "tool/image-gender/gt-harness/results/"
    "bags-v1000-two-stage-image-complete-2026-08-31/final-complete.jsonl"
)
DETAIL_TRACE_SOURCE = Path(
    "tool/image-gender/gt-harness/results/"
    "bags-v1000-two-stage-image-complete-2026-08-31/detail-complete.jsonl"
)
SUMMARY_SOURCE = Path(
    "tool/image-gender/gt-harness/results/"
    "bags-v1000-two-stage-image-complete-2026-08-31/summary-complete.json"
)
PREVIOUS_COLLECTION_ERRORS_SOURCE = Path(
    "tool/image-gender/gt-harness/results/"
    "multi-category-budgeted-v1-full500-2026-08-28/bags-detail-manifest.errors.json"
)
CURRENT_COLLECTION_ERRORS_SOURCE = Path(
    "tool/image-gender/gt-harness/results/"
    "multi-category-image-complete-2026-08-31/bags-detail-manifest.errors.json"
)
WORN_RECOVERY_SOURCE = Path(
    "tool/image-gender/gt-harness/results/"
    "bags-v1000-two-stage-image-complete-2026-08-31/worn-interaction-recovered-ids.json"
)
INVALID_TEXT_RECOVERY_SOURCE = Path(
    "tool/image-gender/gt-harness/results/"
    "bags-v1000-two-stage-image-complete-2026-08-31/invalid-explicit-text-recovered-ids.json"
)
# 하네스 리포트가 상품마다 늘어놓는 대표 이미지·상세 타일. 보고서의 이미지 갤러리는 여기서 온다.
HARNESS_PRODUCT_RESULTS_SOURCE = Path(
    "tool/image-gender/gt-harness/results/"
    "bags-v1000-two-stage-image-complete-2026-08-31/harness-product-results.jsonl"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as failure:
                raise ValueError(f"{path}:{line_number}: invalid JSONL") from failure
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: object expected")
            yield value


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def git_value(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def compact_canonical(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "productKey": f"MUSINSA:{row.get('musinsaGoodsNo')}",
        "goodsNo": str(row.get("musinsaGoodsNo") or ""),
        "sellerProductId": str(row.get("sellerProductId") or ""),
        "productName": row.get("productName"),
        "brand": row.get("brand"),
        "standardCategory": row.get("standardCategory"),
        "goldLabel": row.get("goldLabel"),
        "goldSource": row.get("goldSource"),
        "reviewStatus": row.get("reviewStatus"),
        "datasetVersion": row.get("datasetVersion"),
        "pdpUrl": f"https://www.musinsa.com/products/{row.get('musinsaGoodsNo')}",
    }


def compact_evaluation(row: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "productKey",
        "platformCode",
        "goodsNo",
        "productName",
        "brand",
        "standardCategory",
        "goldLabel",
        "goldSource",
        "gtReviewStatus",
        "decisionSource",
        "thumbnailFold",
        "detailFold",
        "detailEvidenceType",
        "detailEvidence",
        "textSignal",
        "nameAgreement",
        "pdpUrl",
        "detailImageCount",
        "detailStatus",
        "detailStageGender",
        "detailEffectiveStage",
        "mismatchClassification",
        "mismatchClassificationBasis",
        "correct",
    )
    compact = {field: row.get(field) for field in fields}
    compact["baselineProductGender"] = row.get("productGender")
    compact["productGender"] = row.get("prediction") or row.get("productGender")
    compact["prediction"] = compact["productGender"]
    return compact


def display_path(path: Path, source_repo: Path) -> str:
    try:
        return str(path.relative_to(source_repo))
    except ValueError:
        return str(path)


def parse_mapper(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("rawMapperResponse")
    if not raw:
        return {}
    try:
        value = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def compact_detail_evidence(
    detail_rows: Iterable[dict[str, Any]],
    evaluation_by_goods_no: dict[str, dict[str, Any]],
    detail_manifest: dict[str, Any],
    target_reference_by_goods_no: dict[str, dict[str, Any]],
    previous_collection_errors: dict[str, str],
    current_collection_errors: dict[str, str],
    worn_recovered_ids: set[str],
    invalid_text_recovered_ids: set[str],
) -> list[dict[str, Any]]:
    compact_rows: list[dict[str, Any]] = []
    for row in detail_rows:
        goods_no = str(row.get("groupKey") or "").split(":", 1)[0]
        evaluation = evaluation_by_goods_no.get(goods_no)
        if not goods_no or evaluation is None:
            continue
        mapper = parse_mapper(row)
        human_scene_ids = [str(value) for value in mapper.get("humanSceneIds", [])]
        mixed_scene_ids = [str(value) for value in mapper.get("mixedHumanSceneIds", [])]
        text_scene_ids = [str(value) for value in mapper.get("directGenderWordIds", [])]
        observations = row.get("visibleWearerObservations") or []
        matched_wearer_ids = [
            str(observation.get("sourceImageId") or "")
            for observation in observations
            if isinstance(observation, dict)
            and observation.get("targetProductMatch") == "MATCH"
        ]
        direct_source_ids = [
            str(row.get(field) or "")
            for field in (
                "exactProductGenderSourceImageId",
                "exactSizeTableSourceImageId",
            )
            if row.get(field)
        ]
        evidence_scene_ids = list(dict.fromkeys(
            value for value in matched_wearer_ids + direct_source_ids if value
        ))
        manifest_rows = detail_manifest.get(goods_no, [])
        url_by_scene: dict[str, str] = {}
        all_image_sources = row.get("allImageSources") or []
        for source in all_image_sources:
            if not isinstance(source, dict):
                continue
            scene_id = str(source.get("label") or "")
            source_url = str(source.get("sourceUrl") or "")
            if scene_id and source_url:
                url_by_scene[scene_id] = source_url
        if isinstance(manifest_rows, list):
            for manifest_row in manifest_rows:
                if not isinstance(manifest_row, dict):
                    continue
                scene_id = str(manifest_row.get("id") or "").removeprefix(f"{goods_no}-")
                source_url = str(manifest_row.get("sourceUrl") or "")
                if scene_id and source_url:
                    url_by_scene[scene_id] = source_url
        target_reference = target_reference_by_goods_no.get(goods_no, {})
        target_url = str(
            target_reference.get("resolvedSourceUrl") or target_reference.get("sourceUrl") or ""
        )
        for scene_id in evidence_scene_ids:
            if scene_id.startswith("D01") and scene_id not in url_by_scene and target_url:
                url_by_scene[scene_id] = target_url
        evidence_urls = list(
            dict.fromkeys(url_by_scene[scene_id] for scene_id in evidence_scene_ids if scene_id in url_by_scene)
        )
        collection_recovered = bool(
            previous_collection_errors.get(goods_no)
            and not current_collection_errors.get(goods_no)
            and all_image_sources
        )
        compact_rows.append(
            {
                "productKey": evaluation["productKey"],
                "goodsNo": goods_no,
                "status": row.get("status"),
                "policyPrediction": row.get("productGender"),
                "evidenceType": row.get("evidenceType"),
                "evidence": row.get("evidence"),
                "preparedTileCount": row.get("preparedTileCount"),
                "detailAssetCollectedTileCount": row.get("detailAssetCollectedTileCount"),
                "detailAssetRetainedTileCount": row.get("detailAssetRetainedTileCount"),
                "detailAssetRemovedSharedTileCount": row.get(
                    "detailAssetRemovedSharedTileCount"
                ),
                "variantSharedRetainedTileCount": row.get(
                    "variantSharedRetainedTileCount"
                ),
                "detailAssetFilterStatus": row.get("detailAssetFilterStatus"),
                "selectedImageIds": row.get("selectedImageIds") or [],
                "selectedImageCount": row.get("selectedImageCount"),
                "omittedImageCount": row.get("omittedImageCount"),
                "allImageTileCount": len(all_image_sources),
                "fullImageCoverageStatus": row.get("fullImageCoverageStatus"),
                "collectionSources": row.get("collectionSources") or [],
                "collectionRecovered": collection_recovered,
                "previousCollectionError": previous_collection_errors.get(goods_no),
                "currentCollectionError": current_collection_errors.get(goods_no),
                "interactionPolicyRecovered": goods_no in worn_recovered_ids,
                "invalidExplicitTextRecovered": goods_no in invalid_text_recovered_ids,
                "judgeRetryReason": row.get("judgeRetryReason"),
                "humanSceneIds": human_scene_ids,
                "mixedHumanSceneIds": mixed_scene_ids,
                "directGenderWordIds": text_scene_ids,
                "policyEvidenceSceneIds": evidence_scene_ids,
                "evidenceImageUrls": evidence_urls,
                "promptVersion": row.get("promptVersion"),
                "promptSha256": row.get("promptSha256"),
            }
        )
    return sorted(compact_rows, key=lambda row: str(row["productKey"]))


def compact_gallery(
    rows: Iterable[dict[str, Any]], output_root: Path
) -> list[dict[str, Any]]:
    """하네스 리포트가 상품마다 늘어놓는 대표 이미지·상세 타일을 공통 갤러리 계약으로 옮긴다.

    보고서가 상품 단위로 이미지를 밀집해 보여 주려면 근거로 채택된 한두 장이 아니라
    판단기가 실제로 본 전부가 필요하다. 로컬 파일뿐인 대표 이미지는 run의 `asset/` 아래로
    복사한다 — 원본 워크트리는 언제 사라질지 모르고, `asset/`은 다시 돌리면 복구된다.
    `url`이 http가 아니면 run 폴더 기준 상대 경로다. 렌더러가 보고서 위치에 맞춰 다시 잇는다.
    """
    asset_root = output_root / "asset" / "thumbnails"
    gallery: list[dict[str, Any]] = []
    for row in rows:
        product_key = str(row.get("productKey") or "")
        goods_no = str(row.get("goodsNo") or "")
        if not product_key:
            continue
        thumbnails: list[dict[str, Any]] = []
        for index, image in enumerate(row.get("images") or [], start=1):
            url = str(image.get("resolvedSourceUrl") or image.get("sourceUrl") or "")
            if not url.startswith("http"):
                source = (
                    Path(url.removeprefix("file://"))
                    if url.startswith("file://")
                    else Path(str(image.get("localPath") or ""))
                )
                if not source.is_file():
                    continue
                target = asset_root / (
                    f"{product_key.replace(':', '-')}-{index}{source.suffix or '.jpg'}"
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.is_file() or target.stat().st_size != source.stat().st_size:
                    shutil.copyfile(source, target)
                url = str(target.relative_to(output_root))
            thumbnails.append(
                {
                    "index": image.get("imageIndex") or index,
                    "url": url,
                    "label": str(image.get("gender") or ""),
                    "presence": str(image.get("presence") or ""),
                    "note": str(image.get("note") or ""),
                }
            )
        details: list[dict[str, Any]] = []
        for index, image in enumerate(row.get("detailImages") or [], start=1):
            url = str(image.get("sourceUrl") or "")
            if not url.startswith("http"):
                continue
            details.append(
                {
                    "index": index,
                    "sceneId": str(image.get("id") or "").removeprefix(f"{goods_no}-"),
                    "url": url,
                    "label": str(image.get("gender") or ""),
                }
            )
        gallery.append({"productKey": product_key, "thumbnails": thumbnails, "details": details})
    return sorted(gallery, key=lambda item: item["productKey"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-repo", type=Path, default=DEFAULT_SOURCE_REPO)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    source_repo = args.source_repo.resolve()
    output_root = args.output_root.resolve()

    sources = {
        "policy": source_repo / POLICY_SOURCE,
        "canonicalGt": source_repo / CANONICAL_GT_SOURCE,
        "evaluation": source_repo / EVALUATION_SOURCE,
        "detailTrace": source_repo / DETAIL_TRACE_SOURCE,
        "evaluationSummary": source_repo / SUMMARY_SOURCE,
        "previousCollectionErrors": source_repo / PREVIOUS_COLLECTION_ERRORS_SOURCE,
        "currentCollectionErrors": source_repo / CURRENT_COLLECTION_ERRORS_SOURCE,
        "wornInteractionRecoveries": source_repo / WORN_RECOVERY_SOURCE,
        "invalidExplicitTextRecoveries": source_repo / INVALID_TEXT_RECOVERY_SOURCE,
        "harnessProductResults": source_repo / HARNESS_PRODUCT_RESULTS_SOURCE,
    }
    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise SystemExit("missing source files:\n- " + "\n- ".join(missing))

    policy_text = sources["policy"].read_text(encoding="utf-8").strip()
    policy_output = output_root / "policy" / "bag-category-gender.md"
    policy_output.parent.mkdir(parents=True, exist_ok=True)
    policy_output.write_text(
        "# 가방 상품 대상 성별 정책\n\n"
        "> 자동 생성 스냅샷입니다. 원본 프롬프트를 수정하고 이 파일을 직접 고치지 마세요.\n\n"
        f"- 원본: `{POLICY_SOURCE}`\n"
        f"- SHA-256: `{sha256(sources['policy'])}`\n\n"
        "## 판정 프롬프트\n\n"
        + policy_text
        + "\n",
        encoding="utf-8",
    )

    summary = json.loads(sources["evaluationSummary"].read_text(encoding="utf-8"))
    input_files = summary.get("run", {}).get("inputFiles", [])
    def input_path(item: dict[str, Any]) -> Path:
        candidate = Path(str(item.get("path") or ""))
        return candidate if candidate.is_absolute() else source_repo / candidate

    manifest_candidates = [
        input_path(item)
        for item in input_files
        if isinstance(item, dict)
        and "bags-detail-manifest" in Path(str(item.get("path") or "")).name
        and "errors" not in Path(str(item.get("path") or "")).name
        and Path(str(item.get("path") or "")).suffix == ".json"
    ]
    detail_manifest_path = next((path for path in manifest_candidates if path.is_file()), None)
    if detail_manifest_path is None:
        raise SystemExit("evaluation summary가 가리키는 상세 이미지 manifest를 찾을 수 없습니다.")
    target_reference_candidates = [
        input_path(item)
        for item in input_files
        if isinstance(item, dict) and "target-reference" in str(item.get("path") or "")
    ]
    target_reference_path = next(
        (path for path in target_reference_candidates if path.is_file()), None
    )
    if target_reference_path is None:
        raise SystemExit("evaluation summary가 가리키는 TARGET_REFERENCE를 찾을 수 없습니다.")
    sources["detailImageManifest"] = detail_manifest_path
    sources["targetReference"] = target_reference_path
    detail_manifest = json.loads(detail_manifest_path.read_text(encoding="utf-8"))
    target_reference_rows = list(read_jsonl(target_reference_path))
    target_reference_by_goods_no = {
        str(row.get("goodsNo") or row.get("platformProductId") or ""): row
        for row in target_reference_rows
    }

    canonical_rows = sorted(
        (
            compact_canonical(row)
            for row in read_jsonl(sources["canonicalGt"])
            if str(row.get("standardCategory") or "").startswith("가방>")
        ),
        key=lambda row: row["productKey"],
    )
    evaluation_rows = sorted(
        (compact_evaluation(row) for row in read_jsonl(sources["evaluation"])),
        key=lambda row: str(row["productKey"]),
    )
    evaluation_by_goods_no = {str(row.get("goodsNo")): row for row in evaluation_rows}
    detail_evidence_rows = compact_detail_evidence(
        read_jsonl(sources["detailTrace"]),
        evaluation_by_goods_no,
        detail_manifest,
        target_reference_by_goods_no,
        json.loads(sources["previousCollectionErrors"].read_text(encoding="utf-8")),
        json.loads(sources["currentCollectionErrors"].read_text(encoding="utf-8")),
        set(json.loads(sources["wornInteractionRecoveries"].read_text(encoding="utf-8"))),
        set(json.loads(sources["invalidExplicitTextRecoveries"].read_text(encoding="utf-8"))),
    )

    canonical_output = output_root / "golden" / "bag-product-gt.jsonl"
    evaluation_output = output_root / "golden" / "bag-policy-evaluation.jsonl"
    detail_evidence_output = output_root / "golden" / "bag-policy-detail-evidence.jsonl"
    canonical_count = write_jsonl(canonical_output, canonical_rows)
    evaluation_count = write_jsonl(evaluation_output, evaluation_rows)
    detail_evidence_count = write_jsonl(detail_evidence_output, detail_evidence_rows)
    gallery_output = output_root / "golden" / "bag-product-gallery.jsonl"
    gallery_count = write_jsonl(
        gallery_output,
        compact_gallery(read_jsonl(sources["harnessProductResults"]), output_root),
    )

    canonical_keys = {row["productKey"] for row in canonical_rows}
    evaluation_keys = {row["productKey"] for row in evaluation_rows}
    overlapping = canonical_keys & evaluation_keys
    canonical_labels = {row["productKey"]: row["goldLabel"] for row in canonical_rows}
    evaluation_labels = {row["productKey"]: row["goldLabel"] for row in evaluation_rows}
    label_conflicts = sorted(
        key for key in overlapping if canonical_labels[key] != evaluation_labels[key]
    )

    manifest = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "sourceRepository": str(source_repo),
        "sourceCommit": git_value(source_repo, "rev-parse", "HEAD"),
        "sourceDirty": bool(git_value(source_repo, "status", "--short")),
        "sources": {
            name: {
                "path": display_path(path, source_repo),
                "sha256": sha256(path),
            }
            for name, path in sources.items()
        },
        "snapshots": {
            "policy": str(policy_output.relative_to(PROJECT_ROOT)),
            "canonicalBagProductGt": {
                "path": str(canonical_output.relative_to(PROJECT_ROOT)),
                "count": canonical_count,
            },
            "bagPolicyEvaluation": {
                "path": str(evaluation_output.relative_to(PROJECT_ROOT)),
                "count": evaluation_count,
            },
            "bagPolicyDetailEvidence": {
                "path": str(detail_evidence_output.relative_to(PROJECT_ROOT)),
                "count": detail_evidence_count,
            },
            "bagProductGallery": {
                "path": str(gallery_output.relative_to(PROJECT_ROOT)),
                "count": gallery_count,
            },
        },
        "integrity": {
            "overlappingProducts": len(overlapping),
            "goldLabelConflicts": label_conflicts,
        },
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "policy": str(policy_output),
                "canonicalGtCount": canonical_count,
                "evaluationCount": evaluation_count,
                "detailEvidenceCount": detail_evidence_count,
                "galleryCount": gallery_count,
                "overlap": len(overlapping),
                "goldLabelConflicts": len(label_conflicts),
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
