#!/usr/bin/env python3
"""접촉 시트 합성기가 지켜야 할 것.

이 시트 위에서 「이 사람과 저 사람이 같은 사람인가」가 정해지고, 그 답 위에 값 판정이 올라간다.
그래서 여기서 지켜야 할 것은 그림이 예쁜지가 아니라 **답이 장면으로 되돌아오는가**다 —
셀 번호가 한 칸이라도 밀리면 판독이 옆 사람을 가리키고, 아무도 그걸 알아차리지 못한다.

넷을 기계가 지킨다. 셀 번호가 실제로 붙은 그림과 맞는가, 태깅용 시야에 실행의 답이
새지 않는가, 지난 시트가 남지 않는가, 그리고 심사답게 `run-review/` 밖으로 쓰지 않는가.
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
SCRIPT = PROJECT_ROOT / ".claude/os/review/scripts/build_contact_sheets.py"

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class Fixture:
    """타일이 이미 내려와 있는 run 하나. 합성기는 수집기의 산출물만 읽는다."""

    def __init__(self, root: Path) -> None:
        self.run = root / "runs" / "demo"
        self.scenes = self.run / "run-review" / "scenes"

    def build(self, scene_ids: list[str], *, missing: list[str] = ()) -> Path:
        product_dir = self.scenes / "DEMO-1"
        product_dir.mkdir(parents=True, exist_ok=True)
        scenes = []
        for scene_id in scene_ids:
            target = product_dir / f"{scene_id}.jpg"
            if scene_id not in missing:
                # 상세 타일과 같은 비율(폭×1.5)로 만든다. 셀에 들어갈 때 어떻게 눕는지가 달라진다.
                Image.new("RGB", (240, 360), "white").save(target)
            scenes.append(
                {"sceneId": scene_id, "path": str(target.relative_to(self.run)), "source": "ARTIFACT"}
            )
        index = {
            "basedOn": "2026-01-01T00:00:00+00:00",
            "selector": {"maxWidth": 640},
            "products": [
                {
                    "productKey": "DEMO:1",
                    "productName": "데모 상품",
                    "reference": {"path": "run-review/scenes/DEMO-1/_reference.jpg"},
                    # 실행의 주장. 태깅용 시야에는 하나도 넘어가면 안 된다.
                    "goldLabel": "GOLD_VALUE",
                    "observedLabel": "OBSERVED_VALUE",
                    "owner": "GOLDEN",
                    "judgeClaim": "판독기가 두 종류를 모두 보았다고 적은 문장",
                    "judgeSceneNotes": {"D01T01": "판독기의 장면 메모"},
                    "scenes": scenes,
                }
            ],
            "skipped": [],
        }
        self.scenes.mkdir(parents=True, exist_ok=True)
        (self.scenes / "index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return self.run

    def compose(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--run", str(self.run), *extra],
            capture_output=True,
            text=True,
        )

    def view(self) -> dict:
        return json.loads((self.scenes / "cast-view.json").read_text(encoding="utf-8"))


@unittest.skipIf(Image is None, "Pillow가 없다")
class ContactSheetTest(unittest.TestCase):
    def test_cells_are_grouped_four_to_a_sheet_in_scene_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            fixture.build(["D01T02", "D01T01", "D02T01", "D02T02", "D02T03"])
            result = fixture.compose()
            self.assertEqual(result.returncode, 0, result.stderr)
            task = fixture.view()["tasks"][0]
            self.assertEqual([len(sheet["cells"]) for sheet in task["sheets"]], [4, 1])
            # 섞인 순서로 들어와도 sceneId 순으로 눕는다. 이어지는 촬영이 나란히 붙어야
            # 같은 사람을 같은 사람으로 읽는다.
            self.assertEqual(
                [cell["sceneId"] for sheet in task["sheets"] for cell in sheet["cells"]],
                ["D01T01", "D01T02", "D02T01", "D02T02", "D02T03"],
            )

    def test_the_sheet_image_has_exactly_as_many_cells_as_the_index_claims(self) -> None:
        """셀 번호가 그림과 어긋나면 판독이 옆 사람을 가리킨다."""
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            run = fixture.build(["D01T01", "D01T02", "D01T03"])
            fixture.compose("--cell", "128", "--per-sheet", "2")
            sheets = fixture.view()["tasks"][0]["sheets"]
            self.assertEqual([len(sheet["cells"]) for sheet in sheets], [2, 1])
            for sheet in sheets:
                with Image.open(run / sheet["path"]) as image:
                    self.assertEqual(image.width, 128 * len(sheet["cells"]))
                    self.assertGreater(image.height, 128)  # 이름표 띠가 붙는다

    def test_a_tile_that_cannot_be_opened_does_not_shift_the_cell_numbers(self) -> None:
        """못 연 타일을 자리만 비우고 번호를 그대로 두면 뒤 칸이 전부 한 칸씩 밀린다."""
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            run = fixture.build(["D01T01", "D01T02", "D01T03"], missing=["D01T02"])
            fixture.compose("--cell", "128")
            sheet = fixture.view()["tasks"][0]["sheets"][0]
            self.assertEqual(
                [(cell["cell"], cell["sceneId"]) for cell in sheet["cells"]],
                [(1, "D01T01"), (2, "D01T03")],
            )
            with Image.open(run / sheet["path"]) as image:
                self.assertEqual(image.width, 128 * 2)

    def test_the_tagging_view_never_carries_the_run_answer(self) -> None:
        """정답을 알고 사진을 보면 그 정답이 보인다. 그것이 실행 판독기가 실패한 방식이다."""
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            fixture.build(["D01T01", "D01T02"])
            fixture.compose()
            text = (fixture.scenes / "cast-view.json").read_text(encoding="utf-8")
            for leak in ("GOLD_VALUE", "OBSERVED_VALUE", "judgeClaim", "판독기", "GOLDEN"):
                self.assertNotIn(leak, text, f"태깅용 시야에 실행의 답이 샜다: {leak}")

    def test_rerunning_with_fewer_scenes_leaves_no_stale_sheet(self) -> None:
        """옛 시트가 남으면 태깅이 목록에 없는 장면을 보고 답한다."""
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            run = fixture.build(["D01T01", "D01T02", "D01T03", "D01T04", "D01T05"])
            fixture.compose()
            fixture.build(["D01T01"])
            fixture.compose()
            on_disk = sorted(path.name for path in (run / "run-review/scenes/sheets/DEMO-1").glob("*.jpg"))
            self.assertEqual(on_disk, ["sheet-01.jpg"])

    def test_composing_writes_nothing_outside_the_review_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = Fixture(root)
            run = fixture.build(["D01T01", "D01T02"])
            (run / "run-summary.json").write_text("{}", encoding="utf-8")
            (run / "queue").mkdir(exist_ok=True)
            (run / "queue" / "signal.jsonl").write_text('{"productKey":"DEMO:1"}\n', encoding="utf-8")
            before = {
                name: content
                for name, content in snapshot(root).items()
                if "run-review" not in name
            }
            fixture.compose()
            after = {
                name: content
                for name, content in snapshot(root).items()
                if "run-review" not in name
            }
            self.assertEqual(before, after, "심사가 `run-review/` 밖을 건드렸다")

    def test_it_refuses_to_guess_when_the_collector_has_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            fixture.run.mkdir(parents=True, exist_ok=True)
            result = fixture.compose()
            self.assertEqual(result.returncode, 2)
            self.assertIn("index.json", result.stdout)



@unittest.skipIf(Image is None, "Pillow가 없다")
class PartialRebuildTest(unittest.TestCase):
    """수집기와 같은 규칙 — 한 상품만 다시 묶어도 나머지 시야가 사라지면 안 된다."""

    def test_rebuilding_one_product_keeps_the_other_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            fixture.build(["D01T01", "D01T02"])
            fixture.compose()
            # 다른 상품의 시야가 이미 있다고 두고 한 상품만 다시 묶는다.
            view = fixture.view()
            view["tasks"].append({"taskId": "OTHER:9", "productKey": "OTHER:9", "sheets": []})
            (fixture.scenes / "cast-view.json").write_text(
                json.dumps(view, ensure_ascii=False), encoding="utf-8"
            )
            fixture.compose("--product", "DEMO:1")
            keys = sorted(task["productKey"] for task in fixture.view()["tasks"])
            self.assertEqual(keys, ["DEMO:1", "OTHER:9"], "지정 재조립이 다른 시야를 지웠다")


if __name__ == "__main__":
    unittest.main()
