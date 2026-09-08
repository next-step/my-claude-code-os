#!/usr/bin/env python3
"""상품 단위 이미지 갤러리가 하네스 리포트에서 빠짐없이 옮겨지는지 고정한다.

보고서가 상품마다 대표 이미지와 상세 타일을 밀집해 보여 주려면, 근거로 채택된 한두 장이
아니라 판단기가 실제로 본 전부가 스냅샷에 있어야 한다. 로컬 파일뿐인 대표 이미지는
run의 asset/ 아래로 복사돼야 원본 워크트리가 사라져도 보고서가 깨지지 않는다.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("프로젝트 루트를 찾지 못했습니다.")


PROJECT_ROOT = _find_project_root()
RUN_ROOT = PROJECT_ROOT / ".claude/os/runs/bag-category-gender"
ADAPTER = PROJECT_ROOT / ".claude/os/attributes/bag-category-gender/adapters/import_bag_category_gender_sources.py"


def load_adapter():
    spec = importlib.util.spec_from_file_location("import_bag_sources", ADAPTER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class BagGalleryTest(unittest.TestCase):
    def test_local_thumbnail_is_copied_into_asset_and_detail_scene_is_kept(self) -> None:
        adapter = load_adapter()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            local = root / "worktree" / "target.jpg"
            local.parent.mkdir(parents=True)
            local.write_bytes(b"\xff\xd8fake")
            output_root = root / "run"
            rows = [
                {
                    "productKey": "EGOOCM:1",
                    "goodsNo": "1",
                    "images": [
                        {"id": "1-TARGET", "gender": "", "imageIndex": 1, "resolvedSourceUrl": local.as_uri()},
                        {"id": "1-02", "gender": "FEMALE", "presence": "TARGET_WORN", "imageIndex": 2,
                         "resolvedSourceUrl": "https://img.example/2.jpg", "localPath": "/nowhere/2.jpg"},
                    ],
                    "detailImages": [
                        {"id": "1-D03T01", "sourceUrl": "https://img.example/d3.jpg", "gender": ""},
                        {"id": "1-D04T01", "sourceUrl": "file:///gone.jpg", "gender": ""},
                    ],
                }
            ]
            gallery = adapter.compact_gallery(rows, output_root)
            self.assertEqual(1, len(gallery))
            item = gallery[0]
            self.assertEqual("EGOOCM:1", item["productKey"])
            self.assertEqual(2, len(item["thumbnails"]))
            copied = item["thumbnails"][0]["url"]
            self.assertEqual("asset/thumbnails/EGOOCM-1-1.jpg", copied)
            self.assertTrue((output_root / copied).is_file())
            self.assertEqual("https://img.example/2.jpg", item["thumbnails"][1]["url"])
            self.assertEqual("FEMALE", item["thumbnails"][1]["label"])
            # http가 아닌 상세 타일은 싣지 않는다. 장면 ID는 goodsNo 접두어를 뗀다.
            self.assertEqual([{"index": 1, "sceneId": "D03T01", "url": "https://img.example/d3.jpg", "label": ""}], item["details"])

    def test_run_snapshot_carries_gallery_for_every_evaluated_product(self) -> None:
        manifest = json.loads((RUN_ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["snapshots"]["bagPolicyEvaluation"]["count"],
            manifest["snapshots"]["bagProductGallery"]["count"],
        )
        rows = read_jsonl(RUN_ROOT / "golden/bag-product-gallery.jsonl")
        row = next(item for item in rows if item["productKey"] == "EGOOCM:3398529")
        self.assertGreaterEqual(len(row["details"]), 1)
        self.assertTrue(all(detail["url"].startswith("http") for detail in row["details"]))
        self.assertTrue(row["thumbnails"], "대표 이미지가 비어 있다")


if __name__ == "__main__":
    unittest.main()
