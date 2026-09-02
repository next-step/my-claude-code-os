#!/usr/bin/env python3
"""HTML 코어가 성별 외 속성에서도 그대로 동작하는지 확인한다."""

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
RENDERER = PROJECT_ROOT / ".claude/os/engine/scripts/render_catalog_report.py"


class GenericReportTest(unittest.TestCase):
    def test_material_profile_uses_same_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = root / "material.json"
            profile.write_text(
                json.dumps(
                    {
                        "schemaVersion": "catalog-data-profile-v1",
                        "id": "product-material",
                        "displayName": "상품 소재 정책·골든셋 감사",
                        "attributeName": "대표 소재",
                        "subjectName": "의류 상품",
                        "outputRoot": str(root / "run"),
                        "labels": ["COTTON", "WOOL", "POLYESTER", "UNKNOWN"],
                        "signals": {
                            "MATERIAL_RATIO_GAP": {
                                "label": "혼용률 정책 공백",
                                "description": "대표 소재를 고를 혼용률 기준이 없습니다.",
                                "priority": 1,
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            run = root / "run"
            (run / "queue").mkdir(parents=True)
            (run / "review").mkdir()
            (run / "reports").mkdir()
            (run / "queue/material-ratio-gap.jsonl").write_text(
                json.dumps(
                    {
                        "signal": "MATERIAL_RATIO_GAP",
                        "reason": "면 50%, 울 50%에서 대표 소재 기준이 없다.",
                        "productKey": "TEST:1",
                        "productName": "혼방 니트",
                        "referenceLabel": "WOOL",
                        "observedLabel": "COTTON",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (run / "run-summary.json").write_text(
                json.dumps({"completed": True, "products": 1, "artifacts": {}, "cycle": []}),
                encoding="utf-8",
            )
            (run / "review/status.json").write_text(
                json.dumps({"pendingProducts": 1, "adjudicationRate": 0}), encoding="utf-8"
            )
            (run / "manifest.json").write_text(
                json.dumps({"sourceDirty": False, "sourceCommit": "abc12345"}), encoding="utf-8"
            )
            (run / "reports/policy-questions.json").write_text("[]", encoding="utf-8")

            subprocess.run(
                [sys.executable, str(RENDERER), "--profile", str(profile)],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            index = (run / "reports/catalog-audit.html").read_text(encoding="utf-8")
            self.assertIn("대표 소재", index)
            self.assertIn("혼용률 정책 공백", index)
            # 심판이 없는 속성은 귀책이 미확정이라 두 사례 보고서에 모두 나온다.
            for name in ("suspect-gt.html", "policy-gaps.html"):
                report = (run / "reports" / name).read_text(encoding="utf-8")
                self.assertIn("혼방 니트", report, name)
                self.assertIn("혼용률 정책 공백", report, name)
            for output in (index, *[(run / "reports" / n).read_text(encoding="utf-8") for n in ("suspect-gt.html", "policy-gaps.html")]):
                self.assertNotIn("MALE", output)
                self.assertNotIn("productGender", output)


if __name__ == "__main__":
    unittest.main()
