#!/usr/bin/env python3
"""인터뷰 패키지의 합격 기준.

두 가지를 기계가 지킨다.
1. 스캐너는 낯선 속성에서도 빈칸을 정확히 센다 — 도메인을 몰라야 하므로.
2. 세 검사를 통과하지 못한 답은 RESOLVED로 원장에 들어가지 못한다.
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
INTERVIEW = PROJECT_ROOT / ".claude/os/interview"
SCAN = INTERVIEW / "scripts/scan_ambiguity.py"
RECORD = INTERVIEW / "scripts/record_interview_answer.py"
RENDER = INTERVIEW / "scripts/render_interview_adr.py"
IMPORT = INTERVIEW / "scripts/import_interview_sources.py"
ADR_TEMPLATE = INTERVIEW / "templates/adr.md"
POLICY_TEMPLATE = PROJECT_ROOT / ".claude/os/engine/templates/policy.md"
GOAL_TEMPLATE = PROJECT_ROOT / ".claude/os/engine/templates/goal.md"

# 인터뷰 기계도 엔진과 같은 규칙을 지킨다 — 어떤 속성이 있는지 몰라야 한다.
FORBIDDEN = ("가방", "성별", "29CM", "MALE", "FEMALE", "UNISEX", "productGender", "bag-category-gender")

FILLED_POLICY = """---
id: product-material
version: 1
owner: tester
updatedAt: 2026-09-02
---

## 허용값

- `COTTON` — 면이 대표 소재다
- `UNKNOWN` — 혼용률을 못 읽는다

## 근거 우선순위

1. 라벨 택
2. 상세 페이지 표기

## 판정 불가 조건

- 혼용률 합이 100%가 아니다

## 출처와 확신도

| 규칙 | 출처 | 확신도 | 소유자 |
|---|---|---|---|
| 라벨 택이 상세 표기를 이긴다 | OWNED | DECIDED | tester |

## 판례

- [PM-0001](precedents/PM-0001.md)
"""

FILLED_GOAL = """# 대표 소재 · 목표

## 이 라벨이 존재하는 이유

- 사용처: 검색 필터의 소재 항목
- 실패 장면: 면 알레르기 고객이 필터로 거른 목록에서 혼방을 받는다
- 비목표: 원단 품질 등급을 기술하지 않는다

## 판정 기준

이 소재로 상품을 거른 고객이 받아본 실물과 표기가 같으면 옳은 값이다.

## 목표 품질

| 지표 | 재는 단위 | 목표 | 현재 | 미달이면 |
|---|---|---|---|---|
| 정확도 | 카테고리별 | ≥ 95% | 미측정 | 배포 차단 |

## 귀책 원칙

1. 라벨 택 표기가 가장 강하다.
2. 정책이 답을 내는데 GT가 다르면 GT를 고친다.

## 목표로만 결정할 수 있는 경계

| 경계 | 판정 | 결정일 |
|---|---|---|
| 혼방 50:50 | 표기 순서상 앞선 소재 | 2026-09-02 |
"""

THIN_GOAL = FILLED_GOAL.replace(
    "| 혼방 50:50 | 표기 순서상 앞선 소재 | 2026-09-02 |", "| _(아직 없음)_ | | |"
)


def build_attribute(root: Path, policy: str | None, goal: str | None) -> Path:
    """낯선 속성 하나를 통째로 만든다. 엔진도 인터뷰도 이 속성을 모른다."""
    policy_dir = root / "policy"
    (policy_dir / "precedents").mkdir(parents=True)
    if policy is not None:
        (policy_dir / "policy.md").write_text(policy, encoding="utf-8")
    if goal is not None:
        (root / "goal.md").write_text(goal, encoding="utf-8")
    profile = root / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "schemaVersion": "catalog-data-profile-v1",
                "id": "product-material",
                "displayName": "상품 소재 감사",
                "attributeName": "대표 소재",
                "subjectName": "의류 상품",
                "outputRoot": str(root / "run"),
                "goal": str(root / "goal.md"),
                "labels": ["COTTON", "UNKNOWN"],
                "policy": {
                    "owned": str(policy_dir / "policy.md"),
                    "precedents": str(policy_dir / "precedents"),
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return profile


def add_queue(root: Path) -> None:
    """사이클이 이미 애매하다고 잡은 상품 둘. 하나는 큐 두 개에 걸린다."""
    queue = root / "run" / "queue"
    queue.mkdir(parents=True, exist_ok=True)
    rows = {
        "ratio-gap.jsonl": [("TEST:1", "혼방 니트", "COTTON", "UNKNOWN"), ("TEST:2", "면 셔츠", "COTTON", "COTTON")],
        "source-conflict.jsonl": [("TEST:1", "혼방 니트", "COTTON", "WOOL")],
    }
    for name, items in rows.items():
        (queue / name).write_text(
            "".join(
                json.dumps(
                    {"signal": name.upper(), "reason": "기준이 없다", "productKey": key, "productName": label,
                     "referenceLabel": reference, "observedLabel": observed},
                    ensure_ascii=False,
                ) + "\n"
                for key, label, reference, observed in items
            ),
            encoding="utf-8",
        )


def add_references(profile: Path, *items: dict) -> None:
    value = json.loads(profile.read_text(encoding="utf-8"))
    value["references"] = list(items)
    profile.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def import_sources(profile: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(IMPORT), "--profile", str(profile)],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )


def write_coverage(root: Path, based_on: dict, *candidates: dict) -> None:
    (root / "run" / "interview").mkdir(parents=True, exist_ok=True)
    (root / "run" / "interview" / "coverage.json").write_text(
        json.dumps({"schemaVersion": "catalog-interview-coverage-v1", "profileId": "product-material",
                    "generatedAt": "2026-09-02T00:00:00+00:00", "basedOn": based_on, "candidates": list(candidates)},
                   ensure_ascii=False),
        encoding="utf-8",
    )


def scan(profile: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCAN), "--profile", str(profile), "--json"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(f"스캐너 실패:\n{result.stderr}")
    return json.loads(result.stdout)


def record(profile: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RECORD), "--profile", str(profile), *arguments],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )


class ScannerTest(unittest.TestCase):
    def test_template_only_attribute_is_all_unfilled(self) -> None:
        """템플릿을 복사만 한 상태는 '채워짐'이 아니다. 자리표시자를 내용으로 세면 안 된다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = build_attribute(root, POLICY_TEMPLATE.read_text(encoding="utf-8"), None)
            result = scan(profile)
            statuses = {slot["id"]: slot["status"] for slot in result["slots"]}
            self.assertEqual(result["mode"], "NEW")
            self.assertEqual(statuses["SLOT-PURPOSE"], "EMPTY", "goal.md가 없으면 EMPTY다")
            self.assertEqual(statuses["SLOT-LABELS"], "THIN", "템플릿 허용값은 자리표시자다")
            self.assertEqual(statuses["SLOT-ABSTAIN"], "THIN")
            self.assertEqual(statuses["SLOT-SUBJECT"], "FILLED", "프로필 필드는 채워져 있다")
            self.assertEqual(result["nextSlot"], "SLOT-PURPOSE", "가장 위 모호함부터 묻는다")

    def test_goal_template_leaves_the_goal_layer_unfilled(self) -> None:
        """목표 뼈대를 복사만 한 상태는 목표가 정해진 것이 아니다. 슬로건은 판정 기준이 아니다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = build_attribute(
                root, FILLED_POLICY, GOAL_TEMPLATE.read_text(encoding="utf-8")
            )
            result = scan(profile)
            statuses = {slot["id"]: slot["status"] for slot in result["slots"]}
            self.assertEqual(statuses["SLOT-PURPOSE"], "THIN")
            self.assertEqual(statuses["SLOT-VERDICT"], "THIN")
            self.assertEqual(statuses["SLOT-QUALITY"], "THIN")
            self.assertEqual(statuses["SLOT-BLAME"], "THIN")

    def test_policy_without_provenance_is_an_open_slot(self) -> None:
        """무엇을 아는지 적히지 않은 정책은, 규칙이 다 있어도 출처가 비어 있는 것이다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            without = FILLED_POLICY.replace("## 출처와 확신도", "## 참고").replace(
                "| 라벨 택이 상세 표기를 이긴다 | OWNED | DECIDED | tester |", "| 없음 | | | |"
            )
            profile = build_attribute(root, without, FILLED_GOAL)
            statuses = {slot["id"]: slot["status"] for slot in scan(profile)["slots"]}
            self.assertEqual(statuses["SLOT-PROVENANCE"], "EMPTY")

    def test_filled_attribute_leaves_nothing_to_interview(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = build_attribute(root, FILLED_POLICY, FILLED_GOAL)
            result = scan(profile)
            self.assertEqual(result["counts"]["empty"], 0)
            self.assertEqual(result["counts"]["thin"], 0)
            self.assertEqual(result["mode"], "GAP")
            self.assertIsNone(result["nextSlot"], "물을 것이 없으면 질문을 만들지 않는다")

    def test_empty_table_is_thin_even_with_prose_around_it(self) -> None:
        """표가 있는 섹션은 표가 내용이다. 설명문만 있고 행이 없으면 아직 안 채운 것이다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = build_attribute(root, FILLED_POLICY, THIN_GOAL)
            result = scan(profile)
            statuses = {slot["id"]: slot["status"] for slot in result["slots"]}
            self.assertEqual(statuses["SLOT-SCOPE"], "THIN")
            self.assertEqual(result["nextSlot"], "SLOT-SCOPE")

    def test_incomplete_declaration_is_a_slot_not_a_crash(self) -> None:
        """선언이 덜 된 프로필은 인터뷰의 정상 입력이다. 사이클은 멈춰야 맞지만 인터뷰는 아니다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = root / "profile.json"
            profile.write_text(
                json.dumps({"schemaVersion": "catalog-data-profile-v1", "id": "product-material"}),
                encoding="utf-8",
            )
            result = scan(profile)
            self.assertIn("subjectName", result["undeclaredProfileFields"])
            self.assertEqual(result["mode"], "NEW")
            statuses = {slot["id"]: slot["status"] for slot in result["slots"]}
            self.assertEqual(statuses["SLOT-SUBJECT"], "EMPTY")

    def test_queued_products_are_attached_most_ambiguous_first(self) -> None:
        """반례는 지어내지 않는다. 사이클이 이미 애매하다고 잡은 상품이 앞에 온다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = build_attribute(root, FILLED_POLICY, FILLED_GOAL)
            add_queue(root)
            result = scan(profile)
            self.assertEqual(result["counts"]["ambiguousProducts"], 2)
            first = result["ambiguousProducts"][0]
            self.assertEqual(first["productKey"], "TEST:1", "큐 두 개에 걸린 상품이 먼저다")
            self.assertEqual(len(first["signals"]), 2)

    def test_open_precedent_becomes_a_question_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = build_attribute(root, FILLED_POLICY, FILLED_GOAL)
            (root / "policy/precedents/PM-0001.md").write_text(
                "---\nid: PM-0001\nprofile: product-material\nstatus: OPEN\nanswers: GQ-1\n---\n\n# 질문\n",
                encoding="utf-8",
            )
            result = scan(profile)
            self.assertEqual(result["counts"]["openPrecedents"], 1)
            self.assertEqual(result["nextSlot"], "PRECEDENT:PM-0001")


class SourceIntakeTest(unittest.TestCase):
    def test_sources_are_snapshotted_and_a_missing_one_is_not_fatal(self) -> None:
        """자료는 사본과 해시로 남는다. 자료 하나가 없다고 인터뷰가 멈추면 안 된다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = build_attribute(root, FILLED_POLICY, FILLED_GOAL)
            doc = root / "prd.md"
            doc.write_text("# PRD\n\n## 사용처\n\n검색 필터의 소재 항목에서 쓴다.\n", encoding="utf-8")
            add_references(
                profile,
                {"id": "prd", "kind": "PRD", "path": str(doc), "note": "사용처"},
                {"id": "gone", "kind": "GUIDE", "path": str(root / "없는파일.md")},
            )
            result = import_sources(profile)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("gone 자료가 없습니다", result.stderr)
            manifest = json.loads((root / "run/interview/sources/manifest.json").read_text(encoding="utf-8"))
            rows = {row["id"]: row for row in manifest["sources"]}
            self.assertTrue((root / "run/interview/sources/prd.md").is_file())
            self.assertEqual(len(rows["prd"]["sha256"]), 64)
            self.assertTrue(rows["gone"]["missing"])
            self.assertEqual(scan(profile)["counts"], scan(profile)["counts"] | {"sources": 2, "missingSources": 1})

    def test_coverage_turns_an_empty_slot_into_a_confirm_question_and_goes_stale(self) -> None:
        """자료 후보가 있으면 백지 질문이 아니라 확인 질문이다. 자료가 바뀌면 그 인용은 낡은 것이다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = build_attribute(root, FILLED_POLICY, None)  # goal.md 없음 → 목표층 EMPTY
            doc = root / "prd.md"
            doc.write_text("검색 필터의 소재 항목에서 쓴다.\n", encoding="utf-8")
            add_references(profile, {"id": "prd", "kind": "PRD", "path": str(doc)})
            self.assertEqual(import_sources(profile).returncode, 0)
            sha = json.loads((root / "run/interview/sources/manifest.json").read_text(encoding="utf-8"))["sources"][0]["sha256"]
            write_coverage(
                root, {"prd": sha},
                {"slot": "SLOT-PURPOSE", "sourceId": "prd", "cite": "§1", "quote": "검색 필터의 소재 항목에서 쓴다.", "note": "사용처"},
                {"slot": "SLOT-NOPE", "sourceId": "prd", "cite": "§9", "quote": "…"},
            )
            result = scan(profile)
            self.assertEqual(result["coverage"]["status"], "FRESH")
            self.assertEqual(len(result["coverage"]["orphans"]), 1, "모르는 슬롯을 가리키는 후보는 버린다")
            purpose = next(slot for slot in result["slots"] if slot["id"] == "SLOT-PURPOSE")
            self.assertEqual(purpose["status"], "EMPTY")
            self.assertEqual(purpose["questionShape"], "CONFIRM")
            self.assertIn("검색 필터의 소재 항목에서 쓴다.", result["nextQuestion"])
            verdict = next(slot for slot in result["slots"] if slot["id"] == "SLOT-VERDICT")
            self.assertEqual(verdict["questionShape"], "OPEN", "자료가 답하지 않은 슬롯은 빈 열이다")

            doc.write_text("검색 필터와 추천 양쪽에서 쓴다.\n", encoding="utf-8")
            self.assertEqual(import_sources(profile).returncode, 0)
            self.assertEqual(scan(profile)["coverage"]["status"], "STALE")


class LedgerGateTest(unittest.TestCase):
    BASE = (
        "--slot",
        "SLOT-ABSTAIN",
        "--question",
        "근거가 없을 때 값을 비우는가",
        "--answer",
        "라벨 택을 못 읽으면 UNKNOWN을 낸다",
        "--answered-by",
        "tester",
    )
    PAIR = (
        "--counter-example",
        "라벨 택에 면 100% => COTTON",
        "--counter-example",
        "라벨 택 사진 없음 => UNKNOWN",
    )
    PROVENANCE = ("--source", "OWNED", "--confidence", "DECIDED")
    PASSING = (*BASE, "--status", "RESOLVED", "--observable", "--closed", *PAIR, *PROVENANCE)

    def profile(self, root: Path) -> Path:
        return build_attribute(root, FILLED_POLICY, FILLED_GOAL)

    def test_resolved_needs_every_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            profile = self.profile(Path(temporary))
            result = record(profile, *self.BASE, "--status", "RESOLVED", "--observable")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("닫힘", result.stderr)
            self.assertIn("재현 가능", result.stderr)

    def test_counter_examples_must_produce_different_values(self) -> None:
        """같은 값만 내는 반례 쌍은 경계를 가르지 못한다. 이게 재현 검사의 실체다."""
        with tempfile.TemporaryDirectory() as temporary:
            profile = self.profile(Path(temporary))
            result = record(
                profile,
                *self.BASE,
                "--status",
                "RESOLVED",
                "--observable",
                "--closed",
                "--applies-to",
                "policy.md",
                *self.PROVENANCE,
                "--counter-example",
                "사례 A => COTTON",
                "--counter-example",
                "사례 B => COTTON",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("경계를 가르지 못한다", result.stderr)

    def test_a_guess_cannot_become_policy(self) -> None:
        """추측은 확신도가 낮은 답이 아니라 답이 아니다. 정할 수 있는 사람을 찾을 때까지 OPEN이다."""
        with tempfile.TemporaryDirectory() as temporary:
            profile = self.profile(Path(temporary))
            result = record(
                profile,
                *self.BASE,
                "--status",
                "RESOLVED",
                "--observable",
                "--closed",
                "--applies-to",
                "policy.md",
                *self.PAIR,
                "--source",
                "TACIT",
                "--confidence",
                "GUESS",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("추측(GUESS)은 정책이 될 수 없다", result.stderr)

    def test_document_source_requires_a_citation(self) -> None:
        """인용 없는 문서 근거는 확인할 수 없다. 나중에 '왜 이 규칙이냐'에 댈 줄이 없다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.profile(root)
            common = (*self.BASE, "--status", "RESOLVED", "--observable", "--closed", "--applies-to", "policy.md",
                      *self.PAIR, "--source", "DOCUMENT", "--confidence", "DECIDED")
            refused = record(profile, *common)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("--cite", refused.stderr)
            accepted = record(profile, *common, "--cite", "prd#§3.2", "--session", "S1")
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertEqual(json.loads(accepted.stdout)["provenance"]["cite"], "prd#§3.2")
            rendered = subprocess.run(
                [sys.executable, str(RENDER), "--profile", str(profile), "--adr-dir", str(root / "adr")],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            self.assertIn("인용 `prd#§3.2`", (root / "adr/ADR-0001-S1.md").read_text(encoding="utf-8"))

    def test_provenance_is_kept_with_the_answer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.profile(root)
            result = record(
                profile, *self.PASSING, "--applies-to", "policy.md", "--owner", "정책 소유자"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            ledger = json.loads((root / "run/interview/answers.json").read_text(encoding="utf-8"))
            self.assertEqual(
                ledger["answers"][0]["provenance"],
                {"source": "OWNED", "confidence": "DECIDED", "owner": "정책 소유자", "cite": None},
            )

    def test_quality_target_without_a_number_is_a_slogan(self) -> None:
        """'높은 정확도'는 목표가 아니다. 숫자가 없으면 달성했는지 아무도 모른다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.profile(root)
            common = (
                "--slot", "SLOT-QUALITY", "--question", "100건 중 몇 건까지 버티는가",
                "--answered-by", "tester", "--status", "RESOLVED", "--observable", "--closed",
                "--applies-to", "goal.md", *self.PROVENANCE,
                "--counter-example", "카테고리별 정확도 97% => 통과",
                "--counter-example", "카테고리별 정확도 90% => 배포 차단",
            )
            slogan = record(profile, *common, "--answer", "카테고리별로 높은 정확도를 유지한다")
            self.assertNotEqual(slogan.returncode, 0)
            self.assertIn("숫자", slogan.stderr)
            measured = record(profile, *common, "--answer", "카테고리별 정확도 95% 이상, 미달 시 배포 차단")
            self.assertEqual(measured.returncode, 0, measured.stderr)

    def test_open_answer_needs_no_checks(self) -> None:
        """모른다는 답도 산출물이다. 미정을 기록하는 길을 막으면 사람은 추측으로 채운다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.profile(root)
            result = record(profile, *self.BASE, "--status", "OPEN")
            self.assertEqual(result.returncode, 0, result.stderr)
            ledger = json.loads((root / "run/interview/answers.json").read_text(encoding="utf-8"))
            self.assertEqual(ledger["answers"][0]["status"], "OPEN")

    def test_history_is_preserved_on_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.profile(root)
            first = record(profile, *self.PASSING, "--applies-to", "policy.md")
            self.assertEqual(first.returncode, 0, first.stderr)
            answer_id = json.loads(first.stdout)["answerId"]

            blocked = record(profile, *self.PASSING, "--applies-to", "policy.md")
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("--supersedes", blocked.stderr)

            second = record(
                profile, *self.PASSING, "--applies-to", "policy.md", "--supersedes", answer_id
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            ledger = json.loads((root / "run/interview/answers.json").read_text(encoding="utf-8"))
            self.assertEqual(len(ledger["answers"]), 2, "이전 답을 덮어쓰지 않는다")
            self.assertEqual(ledger["answers"][1]["supersedes"], answer_id)

    def test_counter_examples_from_the_queue_are_marked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.profile(root)
            add_queue(root)
            result = record(
                profile, *self.BASE, "--status", "RESOLVED", "--observable", "--closed",
                "--applies-to", "policy.md", *self.PROVENANCE,
                "--counter-example", "TEST:1 혼방 니트 => UNKNOWN",
                "--counter-example", "라벨 택 사진 없는 가상 상품 => COTTON",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            examples = json.loads(result.stdout)["counterExamples"]
            self.assertEqual([item["queued"] for item in examples], [True, False])

    def test_session_renders_to_one_adr_with_the_qna(self) -> None:
        """사람이 읽는 것은 원장이 아니라 ADR이다. 질문·선택지·답·반례·출처가 한 덩어리로 남는다."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = self.profile(root)
            add_queue(root)
            first = record(
                profile, *self.PASSING, "--applies-to", "policy.md", "--session", "S1",
                "--option", "A: UNKNOWN을 낸다", "--option", "B: 기본값을 채운다", "--reason", "없는 근거를 메우지 않는다",
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            second = record(
                profile, "--slot", "SLOT-SCOPE", "--question", "반려동물 의류도 대상인가",
                "--answer", "", "--answered-by", "tester", "--status", "OPEN", "--session", "S1",
            )
            self.assertEqual(second.returncode, 0, second.stderr)

            adr_dir = root / "adr"
            rendered = subprocess.run(
                [sys.executable, str(RENDER), "--profile", str(profile), "--adr-dir", str(adr_dir)],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            files = sorted(adr_dir.glob("ADR-*.md"))
            self.assertEqual([path.name for path in files], ["ADR-0001-S1.md"])
            body = files[0].read_text(encoding="utf-8")
            for heading in ("## 맥락", "## 질문과 답", "## 결정", "## 열린 것", "## 결과"):
                self.assertIn(heading, body, "ADR 뼈대의 제목이 빠졌다")
                self.assertIn(heading, ADR_TEMPLATE.read_text(encoding="utf-8"))
            self.assertIn("status: PROPOSED", body, "열린 답이 있으면 PROPOSED다")
            self.assertIn("- A: UNKNOWN을 낸다", body)
            self.assertIn("없는 근거를 메우지 않는다", body)
            self.assertIn("OWNED · DECIDED", body)
            self.assertIn("반려동물 의류도 대상인가", body)

            files[0].write_text(body + "\n사람이 손본 줄\n", encoding="utf-8")
            again = subprocess.run(
                [sys.executable, str(RENDER), "--profile", str(profile), "--adr-dir", str(adr_dir)],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertIn("사람이 손본 줄", files[0].read_text(encoding="utf-8"), "있는 ADR은 덮어쓰지 않는다")
            self.assertIn("건너뜀", again.stdout)

    def test_unknown_slot_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            profile = self.profile(Path(temporary))
            result = record(
                profile, *self.PASSING, "--applies-to", "policy.md", "--slot", "SLOT-WHATEVER"
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("모르는 슬롯", result.stderr)


class InterviewPurityTest(unittest.TestCase):
    def test_no_domain_vocabulary(self) -> None:
        offenders: list[str] = []
        for path in sorted(INTERVIEW.glob("**/*.py")) + sorted(INTERVIEW.glob("**/*.json")):
            if "__pycache__" in path.parts or path.name == Path(__file__).name:
                continue
            body = path.read_text(encoding="utf-8")
            offenders.extend(
                f"{path.relative_to(INTERVIEW)}: `{term}`" for term in FORBIDDEN if term in body
            )
        self.assertEqual(
            offenders, [], "인터뷰 기계에 도메인 어휘가 있습니다:\n" + "\n".join(offenders)
        )


if __name__ == "__main__":
    unittest.main()
