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


# 규칙에 이름이 붙은 정책. 계약 밖의 자유 섹션(`## 근거 유형`)을 일부러 하나 둔다 —
# 거기 있는 값 목록이 규칙으로 둔갑하면 안 된다.
POLICY_WITH_RULES = """---
id: product-material
version: 3
owner: tester
updatedAt: 2026-09-07
---

# 대표 소재 정책

## 허용값

- `COTTON` — 면이 대표 소재다
- `WOOL` — 울이 대표 소재다
- `UNKNOWN` — 혼용률을 읽을 수 없다

## 근거 우선순위

1. `R1_LABEL_TAG` — 라벨 택 혼용률
2. `R2_DESCRIPTION` — 상품 설명

### 혼용률을 읽는 법

표의 마지막 줄까지 센다.

## 판정 불가 조건

- `R9_BAD_SUM` — 혼용률 합이 100%가 아니다

## 근거 유형

- `TAG` — 라벨 택
- `TEXT` — 상품 설명

## 판례

- [PM-0001](precedents/PM-0001.md)
"""


class Harness(unittest.TestCase):
    """시험 도구만 둔다. 여기에 시험을 두면 상속받는 반마다 같은 시험이 다시 돈다."""

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


class PolicyLayerTest(Harness):

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


class RuleLayerTest(Harness):
    """규칙에 이름이 있어야 판례가 걸릴 자리가 생긴다.

    이름이 없으면 「어느 규칙의 판례인가」를 물을 수 없고, 물을 수 없으면 다음 실행이
    그 판례를 골라 읽을 수 없다. 그때 판례는 정책 폴더 안의 문서로만 남는다 —
    사람이 답한 경계가 다음 판독에 한 번도 닿지 않는다.
    """

    def build_with_rules(self, root: Path) -> Path:
        return self.build(root, policy=POLICY_WITH_RULES)

    def write(self, root: Path, identifier: str, **fields: str) -> None:
        (root / f"policy/precedents/{identifier}.md").write_text(
            precedent(identifier, **fields), encoding="utf-8"
        )

    def test_only_contract_sections_yield_rules(self) -> None:
        """계약 밖의 자유 섹션은 훑지 않는다. 훑으면 값 목록이 규칙으로 둔갑한다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.build_with_rules(root)
            self.write(root, "PM-0001", rule="R1_LABEL_TAG")
            self.assertEqual(self.run_builder(profile).returncode, 0)
            rules = self.index(root)["owned"]["rules"]
            self.assertEqual(
                [item["id"] for item in rules], ["R1_LABEL_TAG", "R2_DESCRIPTION", "R9_BAD_SUM"]
            )
            # `## 근거 유형`의 TAG·TEXT는 규칙이 아니다.
            self.assertNotIn("TAG", [item["id"] for item in rules])
            self.assertEqual(rules[0]["section"], "근거 우선순위")

    def test_a_precedent_binds_to_the_rule_it_questions(self) -> None:
        """이 대조가 루프의 마지막 고리다 — 규칙으로 판례를 찾는 입구."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.build_with_rules(root)
            self.write(root, "PM-0001", rule="R1_LABEL_TAG", applies="EVIDENCE")
            self.assertEqual(self.run_builder(profile).returncode, 0)
            index = self.index(root)
            self.assertEqual(index["rulePrecedents"], {"R1_LABEL_TAG": ["PM-0001"]})
            self.assertEqual(index["precedents"][0]["applies"], "EVIDENCE")

    def test_a_reader_bound_precedent_without_a_rule_is_flagged(self) -> None:
        """판독자에게 갈 판례가 규칙을 안 걸면 어느 브리프에도 안 실려 영원히 안 닿는다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.build_with_rules(root)
            self.write(root, "PM-0001", applies="EVIDENCE")
            self.assertEqual(self.run_builder(profile).returncode, 0)
            codes = [item["code"] for item in self.index(root)["violations"]]
            self.assertIn("PRECEDENT_WITHOUT_RULE", codes)

    def test_a_ruling_precedent_may_stand_on_no_rule(self) -> None:
        """「두 GT 소스 중 무엇이 정본인가」는 어떤 근거 규칙 위에도 서지 않는다.

        규칙을 강요하면 그 판례는 거짓 결속을 달게 되고, 그때부터 규칙 브리프가
        엉뚱한 판례를 판독자에게 나른다.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.build_with_rules(root)
            self.write(root, "PM-0001", applies="RULING")
            self.assertEqual(self.run_builder(profile).returncode, 0)
            codes = [item["code"] for item in self.index(root)["violations"]]
            self.assertNotIn("PRECEDENT_WITHOUT_RULE", codes)

    def test_an_unknown_rule_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.build_with_rules(root)
            self.write(root, "PM-0001", rule="R7_NOPE")
            self.assertEqual(self.run_builder(profile).returncode, 0)
            codes = [item["code"] for item in self.index(root)["violations"]]
            self.assertIn("UNKNOWN_RULE", codes)

    def test_an_unknown_audience_blocks_the_cycle(self) -> None:
        """모르는 값을 만나면 멈춘다. 조용히 RULING으로 접으면 판독자에게 갈 판례가 사라진다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.build_with_rules(root)
            self.write(root, "PM-0001", rule="R1_LABEL_TAG", applies="EVERYONE")
            self.assertEqual(self.run_builder(profile).returncode, 1)

    def test_an_undeclared_audience_defaults_to_not_reaching_readers(self) -> None:
        """모르는 것을 판독자에게 주는 쪽이 안 주는 쪽보다 나쁘다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.build_with_rules(root)
            self.write(root, "PM-0001", rule="R1_LABEL_TAG")
            self.assertEqual(self.run_builder(profile).returncode, 0)
            self.assertEqual(self.index(root)["precedents"][0]["applies"], "RULING")
