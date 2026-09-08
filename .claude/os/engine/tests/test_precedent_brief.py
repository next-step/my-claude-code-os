#!/usr/bin/env python3
"""판례가 다음 실행에 닿는가 — 루프의 마지막 고리.

판례는 오랫동안 정책 폴더 안의 문서로만 살아 있었다. 사람이 경계를 하나 답해도 다음
판독은 그것을 모른 채 같은 자리에서 같은 실수를 했다. **다음 판독이 읽지 않는 판례는
자산이 아니라 기록이다.**

브리프가 그 사이를 잇는다. 여기서 기계가 지키는 것은 넷이다.

1. **정책 원문을 자르지 않는다.** 손으로 뜨던 발췌에서 표의 마지막 줄이 빠진 적이 있다.
   섹션을 통째로 실으면 자를 자리 자체가 없다.
2. **확정된 근거 판례가 브리프에 실린다.** 사람이 답한 경계가 판독자에게 닿는 자리다.
3. **판정 경계 판례는 실리지 않는다.** 「이 근거면 GT를 뒤집을 것인가」를 판독자가 알면,
   무엇이 보이는지 답해야 할 눈이 무엇이 답인지 먼저 정한다.
4. **없는 판례를 있는 것처럼 말하지 않는다.** 빈 자리는 빈 자리로 적힌다.
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
SCRIPTS = PROJECT_ROOT / ".claude/os/engine/scripts"

POLICY = """---
id: product-material
version: 3
owner: tester
updatedAt: 2026-09-07
---

# 대표 소재 정책

## 허용값

- `COTTON` — 면이 대표 소재다
- `WOOL` — 울이 대표 소재다

## 근거 우선순위

1. `R1_LABEL_TAG` — 라벨 택 혼용률
2. `R2_DESCRIPTION` — 상품 설명

### 혼용률 표를 읽는 법

| 줄 | 뜻 |
|---|---|
| 첫 줄 | 겉감 |
| 마지막 줄 | 안감 — **이 줄이 발췌에서 빠진 적이 있다** |

## 판정 불가 조건

- `R9_BAD_SUM` — 혼용률 합이 100%가 아니다

## 판례

- 없음
"""


def precedent(identifier: str, **fields: str) -> str:
    meta = {"id": identifier, "profile": "product-material", "status": "OPEN", **fields}
    lines = "\n".join(f"{key}: {value}" for key, value in meta.items())
    return f"---\n{lines}\n---\n\n# 질문\n\n안감도 대표 소재 후보로 세는가?\n\n## 영향\n\n걸린 건수는 요약이 센다.\n"


class BriefTest(unittest.TestCase):
    def build(self, precedents: dict[str, dict[str, str]], log: dict | None = None) -> Path:
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        layer = root / "policy"
        (layer / "precedents").mkdir(parents=True)
        (layer / "policy.md").write_text(POLICY, encoding="utf-8")
        for identifier, fields in precedents.items():
            (layer / "precedents" / f"{identifier}.md").write_text(
                precedent(identifier, **fields), encoding="utf-8"
            )
        run = root / "run"
        (run / "reports").mkdir(parents=True)
        gt = root / "gt" / "gt.jsonl"
        gt.parent.mkdir(parents=True)
        gt.write_text("", encoding="utf-8")
        if log is not None:
            out = gt.parent / "from-decisions"
            out.mkdir(parents=True, exist_ok=True)
            (out / "precedent-log.json").write_text(json.dumps(log), encoding="utf-8")
        profile = root / "material.json"
        profile.write_text(
            json.dumps({
                "schemaVersion": "catalog-data-profile-v1",
                "id": "product-material", "displayName": "상품 소재 감사",
                "attributeName": "대표 소재", "subjectName": "의류 상품",
                "outputRoot": str(run), "labels": ["COTTON", "WOOL"],
                "gt": {"path": str(gt)},
                "policy": {"owned": str(layer / "policy.md"),
                           "precedents": str(layer / "precedents")},
            }, ensure_ascii=False),
            encoding="utf-8",
        )
        for script in ("build_policy_index.py", "build_precedent_brief.py"):
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / script), "--profile", str(profile)],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            assert result.returncode == 0, f"{script}: {result.stderr or result.stdout}"
        return run / "policy" / "rule-briefs"

    def brief(self, out: Path, rule: str) -> str:
        return (out / f"{rule}.md").read_text(encoding="utf-8")

    def test_the_policy_section_arrives_whole(self) -> None:
        """손으로 뜨던 발췌에서 표의 마지막 줄이 빠진 적이 있다. 자를 자리를 없앤다."""
        out = self.build({})
        text = self.brief(out, "R1_LABEL_TAG")
        self.assertIn("마지막 줄 | 안감", text)
        # 같은 섹션의 다른 규칙도 함께 온다 — 순위는 서로를 보고서야 뜻이 선다.
        self.assertIn("R2_DESCRIPTION", text)

    def test_a_decided_evidence_precedent_reaches_the_reader(self) -> None:
        """사람이 답한 경계가 다음 판독에 닿는 자리. 이것이 없으면 판례는 기록일 뿐이다."""
        out = self.build({
            "PM-0001": {"rule": "R1_LABEL_TAG", "applies": "EVIDENCE", "status": "DECIDED",
                        "decision": "안감은 세지 않는다", "decidedBy": "mj", "decidedAt": "2026-09-07"},
        })
        text = self.brief(out, "R1_LABEL_TAG")
        self.assertIn("PM-0001", text)
        self.assertIn("안감은 세지 않는다", text)
        # 무엇에 대한 답인지 없이 답만 주면 다음 판독이 그 답을 쓸 자리를 모른다.
        self.assertIn("안감도 대표 소재 후보로 세는가", text)

    def test_a_ruling_precedent_never_reaches_the_reader(self) -> None:
        """판독자가 판정 규칙을 읽으면, 무엇이 보이는지 답할 눈이 무엇이 답인지 먼저 정한다."""
        out = self.build({
            "PM-0002": {"rule": "R1_LABEL_TAG", "applies": "RULING", "status": "DECIDED",
                        "decision": "GT를 고친다", "decidedBy": "mj", "decidedAt": "2026-09-07"},
        })
        text = self.brief(out, "R1_LABEL_TAG")
        self.assertNotIn("GT를 고친다", text)
        # 있다는 사실 자체는 감추지 않는다. 주석으로 남아 다음 사람이 찾을 수 있다.
        self.assertIn("PM-0002", text)

    def test_an_empty_rule_says_so_instead_of_guessing(self) -> None:
        out = self.build({})
        self.assertIn("확정된 판례가 아직 없다", self.brief(out, "R2_DESCRIPTION"))

    def test_applied_cases_ride_along_with_the_precedent(self) -> None:
        """말이 아니라 **실제로 어떻게 적용됐는가**가 다음 판단의 재료다."""
        out = self.build(
            {"PM-0001": {"rule": "R1_LABEL_TAG", "applies": "EVIDENCE", "status": "DECIDED",
                         "decision": "안감은 세지 않는다", "decidedBy": "mj", "decidedAt": "2026-09-07"}},
            log={"byPrecedent": {"PM-0001": [
                {"productKey": "T:1", "correctedLabel": "COTTON", "reason": "안감만 울이었다",
                 "reviewedAt": "2026-09-07T00:00:00+00:00"}
            ]}},
        )
        text = self.brief(out, "R1_LABEL_TAG")
        self.assertIn("T:1", text)
        self.assertIn("안감만 울이었다", text)

    def test_a_rule_people_keep_deciding_without_a_precedent_is_marked(self) -> None:
        """같은 경계를 사람이 매번 혼자 넘고 있으면, 그것이 판례를 열 자리다."""
        out = self.build({}, log={"ruleWithoutPrecedent": {"R2_DESCRIPTION": [{"productKey": "T:9"}]}})
        self.assertIn("판례를 열 자리", self.brief(out, "R2_DESCRIPTION"))

    def test_the_index_names_which_rules_readers_can_learn_from(self) -> None:
        out = self.build({
            "PM-0001": {"rule": "R1_LABEL_TAG", "applies": "EVIDENCE"},
            "PM-0002": {"rule": "R2_DESCRIPTION", "applies": "RULING"},
        })
        index = json.loads((out / "index.json").read_text(encoding="utf-8"))
        by_rule = {item["rule"]: item for item in index["briefs"]}
        self.assertEqual(by_rule["R1_LABEL_TAG"]["forReaders"], ["PM-0001"])
        self.assertEqual(by_rule["R2_DESCRIPTION"]["forReaders"], [])
        self.assertEqual(by_rule["R2_DESCRIPTION"]["precedents"], ["PM-0002"])


if __name__ == "__main__":
    unittest.main()
