#!/usr/bin/env python3
"""잡화(카테고리 대분류 `잡화`) 상품 GT와 그 GT가 참조한 이미지 전량을 로컬 스냅샷으로 가져온다.

가방 어댑터는 이미지 바이트를 복사하지 않는다 — 정책·GT 문장만으로 감사가 돌기 때문이다.
잡화는 반대다. 판정 근거가 상세 타일 이미지 자체에 있어서, 원본 저장소가 `work/`를 지우면
근거를 다시 볼 수 없다. 그래서 여기서는 참조된 이미지 파일을 실제로 복사한다.

이미지 바이트는 `runs/<id>/asset/`에만 들어가고 git이 추적하지 않는다. 대신 어떤 파일이
어떤 상품의 몇 번째 근거였는지는 `accessories-image-index.jsonl`에 남아 추적된다.

색인에는 **asset으로 실제 들어온 파일만** 적는다. 원본에 파일이 없어 가져오지 못한 참조는
색인에서 빼고 manifest의 `droppedImageReferences`에 남긴다 — 조용히 사라지면 안 되기 때문이다.
"""

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
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / ".claude" / "os" / "runs" / "accessories-category-gender"
DEFAULT_SOURCE_REPO = PROJECT_ROOT.parent / "core-catalog-platfom"

HARNESS = Path("tool/image-gender/gt-harness")
GT_SOURCE = HARNESS / "data/accessories-product-gt-20260902.jsonl"
EVALUATION_SOURCE = (
    HARNESS
    / "results/accessories-current-refresh-2026-09-01-prompt-v11-upper-body-context"
    / "accessories-harness-products-report.jsonl"
)
ASSET_DIR = "asset"

# 이미지 경로는 이 두 필드에만 있다. 앞은 PDP 썸네일 갤러리, 뒤는 Judge에 실제로 넘어간 상세 타일이다.
IMAGE_FIELDS = (("images", "THUMBNAIL"), ("detailImages", "DETAIL_TILE"))

GT_FIELDS = (
    "productKey",
    "platformCode",
    "goodsNo",
    "productName",
    "standardCategory",
    "pdpUrl",
    "goldLabel",
    "goldLabelSource",
    "previousGoldLabel",
    "finalReviewLabel",
    "reviewStatus",
    "usedExcluded",
    "sourceSheet",
    "sourceCell",
)
EVALUATION_FIELDS = (
    "productKey",
    "brand",
    "categoryDepth1",
    "productGender",
    "inferredProductGender",
    "rawProductGender",
    "decisionSource",
    "thumbnailFold",
    "detailFold",
    "detailEvidenceType",
    "detailEvidence",
    "textSignal",
    "genderCounts",
    "currentThumbnailImageCount",
    "currentDetailTileCount",
    "usedProduct",
    "gtEvaluationStatus",
    "gtExclusionReason",
)


def sha256_file(path: Path) -> str:
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
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def resolve_local_path(local_path: str, harness_root: Path) -> Path:
    """리포트의 localPath는 절대 경로와 하네스 상대 경로가 섞여 있다."""
    candidate = Path(local_path)
    return candidate if candidate.is_absolute() else harness_root / candidate


def remote_url(image: dict[str, Any]) -> str | None:
    """상세 타일의 sourceUrl은 원본 저장소의 file:// 경로다. 옮겨오면 곧 깨지므로 남기지 않는다."""
    for field in ("resolvedSourceUrl", "sourceUrl"):
        value = str(image.get(field) or "")
        if value.startswith(("http://", "https://")):
            return value
    return None


def origin_path(source: Path, harness_root: Path) -> str:
    """어느 수집 폴더에서 왔는지. 기계 이름이 섞이지 않게 하네스 기준 상대 경로로 남긴다."""
    try:
        return str(source.relative_to(harness_root))
    except ValueError:
        return str(source)


def collect_references(
    evaluation_rows: list[dict[str, Any]], harness_root: Path
) -> tuple[list[dict[str, Any]], dict[str, Path], list[dict[str, Any]]]:
    """상품별 이미지 목록과, 복사해야 할 파일 이름 → 원본 경로 표, 그리고 버린 참조를 만든다."""
    index_rows: list[dict[str, Any]] = []
    wanted: dict[str, Path] = {}
    dropped: list[dict[str, Any]] = []
    for row in evaluation_rows:
        images: list[dict[str, Any]] = []
        for field, role in IMAGE_FIELDS:
            for order, image in enumerate(row.get(field) or [], start=1):
                if not isinstance(image, dict):
                    continue
                local_path = str(image.get("localPath") or "")
                if not local_path:
                    continue
                source = resolve_local_path(local_path, harness_root)
                if not source.is_file():
                    dropped.append(
                        {
                            "productKey": row.get("productKey"),
                            "imageId": image.get("id"),
                            "role": role,
                            "origin": origin_path(source, harness_root),
                        }
                    )
                    continue
                images.append(
                    {
                        "role": role,
                        "order": order,
                        "imageId": image.get("id"),
                        "imageIndex": image.get("imageIndex"),
                        "sourceUrl": remote_url(image),
                        "origin": origin_path(source, harness_root),
                        "file": f"{ASSET_DIR}/{source.name}",
                    }
                )
                wanted.setdefault(source.name, source)
        index_rows.append(
            {
                "productKey": row.get("productKey"),
                "goodsNo": row.get("goodsNo"),
                "platformCode": row.get("platformCode"),
                "standardCategory": row.get("standardCategory"),
                "images": images,
            }
        )
    return (
        sorted(index_rows, key=lambda item: str(item["productKey"])),
        wanted,
        sorted(dropped, key=lambda item: (str(item["productKey"]), str(item["imageId"]))),
    )


def copy_images(wanted: dict[str, Path], target_dir: Path) -> dict[str, Any]:
    """이미 같은 크기로 있는 파일은 건너뛴다. 이름이 같은데 내용이 다르면 조용히 덮지 않고 신고한다."""
    target_dir.mkdir(parents=True, exist_ok=True)
    copied = skipped = 0
    total_bytes = 0
    conflicts: list[str] = []
    fingerprints: list[str] = []
    for name in sorted(wanted):
        source = wanted[name]
        destination = target_dir / name
        size = source.stat().st_size
        if destination.is_file() and destination.stat().st_size == size:
            skipped += 1
        else:
            if destination.is_file():
                conflicts.append(name)
            shutil.copyfile(source, destination)
            copied += 1
        total_bytes += size
        fingerprints.append(f"{name}:{sha256_file(destination)}")
    digest = hashlib.sha256("\n".join(fingerprints).encode("utf-8")).hexdigest()
    return {
        "files": len(wanted),
        "copied": copied,
        "reusedExisting": skipped,
        "bytes": total_bytes,
        "nameConflicts": conflicts,
        "contentDigest": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-repo", type=Path, default=DEFAULT_SOURCE_REPO)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--skip-asset",
        action="store_true",
        help="이미지 바이트 복사 없이 GT와 이미지 색인만 갱신한다",
    )
    args = parser.parse_args()
    source_repo = args.source_repo.resolve()
    output_root = args.output_root.resolve()
    harness_root = source_repo / HARNESS

    sources = {"gt": source_repo / GT_SOURCE, "evaluation": source_repo / EVALUATION_SOURCE}
    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise SystemExit("missing source files:\n- " + "\n- ".join(missing))

    gt_rows = sorted(
        ({field: row.get(field) for field in GT_FIELDS} for row in read_jsonl(sources["gt"])),
        key=lambda row: str(row["productKey"]),
    )
    evaluation_rows = list(read_jsonl(sources["evaluation"]))
    off_category = sorted(
        {
            str(row.get("productKey"))
            for row in evaluation_rows
            if not str(row.get("standardCategory") or "").startswith("잡화>")
        }
    )
    if off_category:
        raise SystemExit(f"잡화가 아닌 상품이 섞여 있습니다: {off_category[:5]}")

    index_rows, wanted, dropped = collect_references(evaluation_rows, harness_root)
    evaluation_snapshot = sorted(
        ({field: row.get(field) for field in EVALUATION_FIELDS} for row in evaluation_rows),
        key=lambda row: str(row["productKey"]),
    )

    gt_keys = {str(row["productKey"]) for row in gt_rows}
    index_keys = {str(row["productKey"]) for row in index_rows}
    golden = output_root / "golden"
    gt_count = write_jsonl(golden / "accessories-product-gt.jsonl", gt_rows)
    index_count = write_jsonl(golden / "accessories-image-index.jsonl", index_rows)
    evaluation_count = write_jsonl(
        golden / "accessories-policy-evaluation.jsonl", evaluation_snapshot
    )

    asset_dir = output_root / ASSET_DIR
    asset = (
        {"skipped": True, "files": len(wanted)}
        if args.skip_asset
        else copy_images(wanted, asset_dir)
    )

    manifest = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "sourceRepository": str(source_repo),
        "sourceCommit": git_value(source_repo, "rev-parse", "HEAD"),
        "sourceDirty": bool(git_value(source_repo, "status", "--short")),
        "sources": {
            name: {
                "path": str(path.relative_to(source_repo)),
                "sha256": sha256_file(path),
            }
            for name, path in sources.items()
        },
        "snapshots": {
            "accessoriesProductGt": {
                "count": gt_count,
                "path": str((golden / "accessories-product-gt.jsonl").relative_to(PROJECT_ROOT)),
            },
            "accessoriesPolicyEvaluation": {
                "count": evaluation_count,
                "path": str(
                    (golden / "accessories-policy-evaluation.jsonl").relative_to(PROJECT_ROOT)
                ),
            },
            "accessoriesImageIndex": {
                "count": index_count,
                "path": str((golden / "accessories-image-index.jsonl").relative_to(PROJECT_ROOT)),
            },
            "asset": {
                "path": str(asset_dir.relative_to(PROJECT_ROOT)),
                "tracked": False,
                **asset,
            },
        },
        "integrity": {
            "gtOnlyProducts": sorted(gt_keys - index_keys),
            "evaluationOnlyProducts": sorted(index_keys - gt_keys),
            "imageReferences": sum(len(row["images"]) for row in index_rows),
            "droppedImageReferences": dropped,
        },
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest["snapshots"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
