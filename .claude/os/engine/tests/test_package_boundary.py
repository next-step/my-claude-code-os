#!/usr/bin/env python3
"""패키지 경계를 자동으로 지킨다.

이 OS의 합격 기준은 하나다 — 속성 패키지를 통째로 지워도 엔진이 그대로 돈다.
사람이 매번 확인할 수 없으므로 여기서 기계가 확인한다.
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
ENGINE_SCRIPTS = OS_ROOT / "engine/scripts"
DECLARED_LEAKS = OS_ROOT / "engine/contracts/declared-leaks.json"

# 엔진이 알아서는 안 되는 어휘. 특정 속성의 이름·라벨·데이터 출처가 여기 들어온다.
FORBIDDEN = ("가방", "성별", "29CM", "MALE", "FEMALE", "UNISEX", "productGender", "bag-category-gender")


def engine_sources() -> list[Path]:
    return sorted(
        path
        for pattern in ("**/*.py", "**/*.sh")
        for path in ENGINE_SCRIPTS.glob(pattern)
        if "__pycache__" not in path.parts
    )


def declared() -> dict[str, set[str]]:
    value = json.loads(DECLARED_LEAKS.read_text(encoding="utf-8"))
    return {item["file"]: set(item["terms"]) for item in value["leaks"]}


class EnginePurityTest(unittest.TestCase):
    """엔진 코드에는 도메인 어휘가 없어야 한다. 남은 것은 전부 선언되어야 한다."""

    def test_no_undeclared_domain_vocabulary(self) -> None:
        allowlist = declared()
        undeclared: list[str] = []
        for path in engine_sources():
            key = str(path.relative_to(OS_ROOT))
            body = path.read_text(encoding="utf-8")
            allowed = allowlist.get(key, set())
            for term in FORBIDDEN:
                if term in body and term not in allowed:
                    undeclared.append(f"{key}: `{term}`")
        self.assertEqual(
            undeclared,
            [],
            "엔진에 선언되지 않은 도메인 어휘가 있습니다. 어댑터로 옮기거나 "
            f"{DECLARED_LEAKS.name}에 이유와 함께 선언하세요:\n" + "\n".join(undeclared),
        )

    def test_declared_leaks_are_not_stale(self) -> None:
        """고쳐 놓고 선언만 남으면 목록이 거짓말이 된다."""
        stale: list[str] = []
        for file_key, terms in declared().items():
            path = OS_ROOT / file_key
            self.assertTrue(path.is_file(), f"선언된 파일이 없습니다: {file_key}")
            body = path.read_text(encoding="utf-8")
            stale.extend(f"{file_key}: `{term}`" for term in terms if term not in body)
        self.assertEqual(stale, [], "이미 사라진 누수가 선언에 남아 있습니다:\n" + "\n".join(stale))

    def test_engine_never_points_at_an_attribute_package(self) -> None:
        offenders = [
            str(path.relative_to(OS_ROOT))
            for path in engine_sources()
            if "attributes/" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(
            offenders, [], f"엔진이 속성 패키지 경로를 직접 가리킵니다: {offenders}"
        )


class EngineRunsWithoutTheAttributeTest(unittest.TestCase):
    """가방 패키지가 없다고 가정하고 사이클 후반부를 통째로 돌린다."""

    def build_attribute(self, root: Path) -> Path:
        policy_dir = root / "policy"
        (policy_dir / "precedents").mkdir(parents=True)
        (policy_dir / "policy.md").write_text(
            "---\nid: product-material\nversion: 1\nowner: tester\nupdatedAt: 2026-09-02\n---\n\n"
            "## 허용값\n\n- `COTTON` — 면이 대표 소재다\n- `UNKNOWN` — 혼용률을 못 읽는다\n\n"
            "## 근거 우선순위\n\n1. 라벨 택\n\n## 판정 불가 조건\n\n- 합이 100%가 아니다\n\n"
            "## 판례\n\n없음\n",
            encoding="utf-8",
        )
        run = root / "run"
        (run / "queue").mkdir(parents=True)
        (run / "reports").mkdir(parents=True)
        (run / "queue/ratio-gap.jsonl").write_text(
            json.dumps(
                {
                    "signal": "MATERIAL_RATIO_GAP",
                    "reason": "면 50%, 울 50%에서 대표 소재 기준이 없다.",
                    "productKey": "TEST:1",
                    "productName": "혼방 니트",
                    "referenceLabel": "COTTON",
                    "observedLabel": "UNKNOWN",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        (run / "reports/policy-questions.json").write_text("[]", encoding="utf-8")
        (run / "manifest.json").write_text(
            json.dumps({"sourceDirty": False, "sourceCommit": "abc12345"}), encoding="utf-8"
        )
        profile = root / "profile.json"
        profile.write_text(
            json.dumps(
                {
                    "schemaVersion": "catalog-data-profile-v1",
                    "id": "product-material",
                    "displayName": "상품 소재 감사",
                    "attributeName": "대표 소재",
                    "subjectName": "의류 상품",
                    "outputRoot": str(run),
                    "labels": ["COTTON", "UNKNOWN"],
                    "policy": {
                        "owned": str(policy_dir / "policy.md"),
                        "precedents": str(policy_dir / "precedents"),
                    },
                    "signals": {
                        "MATERIAL_RATIO_GAP": {
                            "label": "혼용률 정책 공백",
                            "description": "대표 소재를 고를 기준이 없습니다.",
                            "priority": 1,
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return profile

    def test_pipeline_tail_runs_on_a_foreign_attribute(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.build_attribute(root)
            run = root / "run"
            for script in (
                "build_policy_index.py",
                "build_review_progress.py",
                "render_catalog_report.py",
            ):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ENGINE_SCRIPTS / script),
                        "--profile",
                        str(profile),
                        "--output-root",
                        str(run),
                    ],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, f"{script} 실패:\n{result.stderr}")

            index = (run / "reports/catalog-audit.html").read_text(encoding="utf-8")
            self.assertIn("대표 소재", index)
            self.assertIn("혼용률 정책 공백", index)
            for name in ("suspect-gt.html", "policy-gaps.html"):
                report = (run / "reports" / name).read_text(encoding="utf-8")
                self.assertIn("혼방 니트", report, name)
                self.assertNotIn("MALE", report, name)
                self.assertNotIn("productGender", report, name)
            index = json.loads((run / "policy/policy-index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["owned"]["labels"], ["COTTON", "UNKNOWN"])


if __name__ == "__main__":
    unittest.main()
