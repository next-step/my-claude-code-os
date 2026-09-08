"""GT 원장 계약. 정답이 하나라는 것과, 진 라벨이 사라지지 않는다는 것을 지킨다."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BUILD_GT = Path(__file__).resolve().parents[1] / "scripts" / "build_gt.py"


def write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    return path


class BuildGtTest(unittest.TestCase):
    def build(self, lineages, corrections=None):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        args = [sys.executable, str(BUILD_GT), "--profile-id", "t"]
        for spec in lineages:
            path = write_jsonl(tmp / f"{spec['id']}.jsonl", spec.pop("rows"))
            args += ["--lineage", json.dumps({**spec, "path": str(path)})]
        if corrections is not None:
            args += ["--corrections", str(write_jsonl(tmp / "fix.jsonl", corrections))]
        out, index = tmp / "gt.jsonl", tmp / "lineage.json"
        args += ["--out", str(out), "--lineage-index", str(index)]
        subprocess.run(args, check=True, capture_output=True)
        rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
        return {row["productKey"]: row for row in rows}, json.loads(index.read_text(encoding="utf-8"))

    def test_lower_rank_number_wins_and_loser_is_kept(self) -> None:
        rows, index = self.build(
            [
                {"id": "hi", "rank": 1, "rows": [{"productKey": "P1", "goldLabel": "MALE", "goldSource": "사람"}]},
                {"id": "lo", "rank": 2, "rows": [{"productKey": "P1", "goldLabel": "UNISEX", "goldSource": "폴백"}]},
            ]
        )
        row = rows["P1"]
        self.assertEqual("MALE", row["goldLabel"])
        self.assertEqual("hi", row["goldLineage"])
        self.assertTrue(row["conflict"])
        self.assertEqual("LINEAGE_RANK", row["resolvedBy"])
        # 진 라벨은 사라지지 않는다 — 왜 이겼는지 되짚을 수 없으면 원장이 아니다
        self.assertEqual([{"lineage": "lo", "goldLabel": "UNISEX", "goldSource": "폴백"}], row["otherLineages"])
        self.assertEqual(1, index["counts"]["conflicts"])

    def test_same_label_is_not_a_conflict(self) -> None:
        rows, index = self.build(
            [
                {"id": "hi", "rank": 1, "rows": [{"productKey": "P1", "goldLabel": "MALE", "goldSource": "a"}]},
                {"id": "lo", "rank": 2, "rows": [{"productKey": "P1", "goldLabel": "MALE", "goldSource": "b"}]},
            ]
        )
        self.assertFalse(rows["P1"]["conflict"])
        self.assertEqual(0, index["counts"]["conflicts"])

    def test_correction_beats_every_lineage(self) -> None:
        rows, _ = self.build(
            [{"id": "hi", "rank": 1, "rows": [{"productKey": "P1", "goldLabel": "MALE", "goldSource": "a"}]}],
            corrections=[{"productKey": "P1", "goldLabel": "UNISEX", "goldSource": "사람 정정"}],
        )
        row = rows["P1"]
        self.assertEqual("UNISEX", row["goldLabel"])
        self.assertEqual("corrections", row["goldLineage"])
        self.assertEqual("CORRECTION", row["resolvedBy"])

    def test_unicode_line_separator_does_not_split_a_row(self) -> None:
        """상세 HTML에 섞여 오는 U+2028은 JSON에서 줄바꿈이 아니다."""
        rows, _ = self.build(
            [{"id": "hi", "rank": 1, "rows": [{"productKey": "P1", "goldLabel": "MALE", "goldSource": "a", "note": "앞 뒤"}]}]
        )
        self.assertEqual(1, len(rows))


if __name__ == "__main__":
    unittest.main()
