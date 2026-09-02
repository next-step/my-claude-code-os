#!/usr/bin/env python3
"""사람이 확정한 인터뷰 답만 이력을 보존하며 기록한다.

세 검사(관찰 가능·재현 가능·닫힘)를 통과하지 못한 답은 RESOLVED로 들어오지 못한다.
규약을 문서에만 두면 바쁠 때 가장 먼저 생략되므로, 여기서 게이트로 만든다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine" / "scripts"))

from catalog_profile import default_profile, load_profile, output_root  # noqa: E402

CONTRACT = Path(__file__).resolve().parents[1] / "contracts" / "slots.json"
SCHEMA = "catalog-interview-v1"
STATUSES = ("RESOLVED", "OPEN", "DEFERRED")
# 이 답이 어디서 왔는가. 정한 것과 해온 것을 섞으면 근거 없는 정책이 된다.
SOURCES = ("OWNED", "SNAPSHOT", "DOCUMENT", "TACIT", "NEW")
CONFIDENCES = ("DECIDED", "CUSTOM", "GUESS")
SEPARATORS = ("=>", "→")


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            json.dump(value, target, ensure_ascii=False, indent=2, sort_keys=True)
            target.write("\n")
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def queued_product_keys(root: Path) -> set[str]:
    keys: set[str] = set()
    for path in sorted((root / "queue").glob("*.jsonl")) if (root / "queue").is_dir() else []:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                key = json.loads(line).get("productKey")
                if key:
                    keys.add(str(key))
    return keys


def parse_counter_examples(values: list[str]) -> list[dict[str, str]]:
    """반례는 `사례 => 기대값` 형식이다. 값이 없는 반례는 경계를 가르지 못한다."""
    parsed: list[dict[str, str]] = []
    for value in values:
        for separator in SEPARATORS:
            case, found, expected = value.partition(separator)
            if found and case.strip() and expected.strip():
                parsed.append({"case": case.strip(), "expected": expected.strip()})
                break
        else:
            raise SystemExit(f"반례는 '사례 => 기대값' 형식이어야 합니다: {value}")
    return parsed


def gate(args: argparse.Namespace, examples: list[dict[str, str]], slot: dict[str, Any] | None) -> None:
    """RESOLVED의 조건. 하나라도 못 넘으면 후속 질문 한 개가 남는다."""
    if args.status != "RESOLVED":
        return
    failed: list[str] = []
    if slot and slot.get("answerMustContain") == "number" and not any(ch.isdigit() for ch in args.answer):
        failed.append("측정 가능: 이 슬롯의 답에는 숫자가 있어야 한다. 숫자 없는 품질 목표는 슬로건이다")
    if not args.observable:
        failed.append("관찰 가능: 답의 술어를 상품 데이터에서 확인할 수 있어야 한다 (--observable)")
    if not args.closed:
        failed.append("닫힘: 모든 입력이 허용값이나 판정 불가로 떨어져야 한다 (--closed)")
    if len(examples) < 2:
        failed.append("재현 가능: 반례 쌍이 2건 이상이어야 한다 (--counter-example)")
    elif len({item["expected"] for item in examples}) < 2:
        failed.append(
            "재현 가능: 반례들이 모두 같은 값을 낸다. 이 답은 아직 경계를 가르지 못한다"
        )
    if not args.applies_to:
        failed.append("적용처: 이 답이 들어갈 파일을 --applies-to로 지정한다")
    if not args.source or not args.confidence:
        failed.append("출처: --source와 --confidence로 이 규칙이 어디서 왔는지 밝힌다")
    elif args.confidence == "GUESS":
        failed.append(
            "출처: 추측(GUESS)은 정책이 될 수 없다. 정할 수 있는 사람을 찾을 때까지 --status OPEN으로 둔다"
        )
    if failed:
        raise SystemExit(
            "RESOLVED로 기록할 수 없습니다. 아래를 못 넘었습니다:\n  - "
            + "\n  - ".join(failed)
            + "\n못 넘은 검사마다 후속 질문 한 개를 만들거나, --status OPEN으로 남기세요."
        )


def contract_slots(contract: Path) -> dict[str, dict[str, Any]]:
    value = json.loads(contract.read_text(encoding="utf-8"))
    return {str(slot["id"]): slot for slot in value["slots"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="사람이 확정한 인터뷰 답을 기록한다.")
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--slot", required=True, help="슬롯 ID 또는 PRECEDENT:<ID> · QUESTION:<ID>")
    parser.add_argument("--question", required=True)
    parser.add_argument("--answer", required=True)
    parser.add_argument("--answered-by", required=True)
    parser.add_argument("--status", required=True, choices=STATUSES)
    parser.add_argument("--observable", action="store_true", help="관찰 가능 검사 통과")
    parser.add_argument("--closed", action="store_true", help="닫힘 검사 통과")
    parser.add_argument("--counter-example", action="append", default=[], help="'사례 => 기대값'")
    parser.add_argument("--applies-to", help="답이 들어갈 파일 경로")
    parser.add_argument("--source", choices=SOURCES, help="OWNED 소유 정책 · SNAPSHOT 프롬프트에만 · TACIT 아무 데도 없음 · NEW 이번에 정함")
    parser.add_argument("--confidence", choices=CONFIDENCES, help="DECIDED 정해진 것 · CUSTOM 해온 것 · GUESS 추측")
    parser.add_argument("--owner", help="이 규칙을 확정할 수 있는 사람. CUSTOM·TACIT일수록 중요하다")
    parser.add_argument("--cite", help="DOCUMENT일 때 필수. '<자료ID>#<위치>' — 나중에 왜 이 규칙이냐에 문서 줄을 댄다")
    parser.add_argument("--supersedes", help="같은 슬롯의 이전 answerId")
    parser.add_argument("--session", help="인터뷰 세션 ID. ADR 한 장이 세션 하나다 (기본: 오늘 날짜)")
    parser.add_argument("--option", action="append", default=[], help="사람 앞에 놓였던 선택지. 'A: ...' 형식")
    parser.add_argument("--reason", help="왜 이 답인가")
    args = parser.parse_args()

    slots = contract_slots(args.contract)
    if not args.slot.startswith(("PRECEDENT:", "QUESTION:")) and args.slot not in slots:
        raise SystemExit(
            f"모르는 슬롯입니다: {args.slot}. "
            "슬롯은 contracts/slots.json에 선언된 것이거나 PRECEDENT:<ID> · QUESTION:<ID> 형식이어야 합니다."
        )

    if args.source == "DOCUMENT" and not args.cite:
        raise SystemExit("--source DOCUMENT에는 --cite '<자료ID>#<위치>'가 필요합니다. 인용 없는 문서 근거는 확인할 수 없습니다.")
    examples = parse_counter_examples(args.counter_example)
    gate(args, examples, slots.get(args.slot))

    profile = load_profile(args.profile or default_profile())
    root = args.output_root.resolve() if args.output_root else output_root(profile)
    path = root / "interview" / "answers.json"
    ledger = (
        json.loads(path.read_text(encoding="utf-8"))
        if path.is_file()
        else {"schemaVersion": SCHEMA, "profileId": profile["id"], "answers": []}
    )
    if ledger.get("schemaVersion") != SCHEMA:
        raise SystemExit("지원하지 않는 인터뷰 원장 버전입니다.")
    answers = ledger.get("answers")
    if not isinstance(answers, list):
        raise SystemExit("answers는 배열이어야 합니다.")

    previous = [row for row in answers if row.get("slot") == args.slot]
    if previous and not args.supersedes:
        raise SystemExit(
            f"{args.slot}에는 이미 답이 있습니다. 기준을 바꾸려면 "
            f"--supersedes {previous[-1].get('answerId')}로 이전 답을 명시하세요."
        )
    if args.supersedes:
        if not previous:
            raise SystemExit("이 슬롯에는 supersede할 이전 답이 없습니다.")
        latest = str(previous[-1].get("answerId"))
        if args.supersedes != latest:
            raise SystemExit(f"가장 최근 답 {latest}만 supersede할 수 있습니다.")

    now = datetime.now(UTC)
    queued = queued_product_keys(root)
    for example in examples:
        # 지어낸 반례와 큐에서 고른 반례를 구분해 남긴다. 실제 상품이 갈린 답만 다음 사이클에서 검증된다.
        example["queued"] = any(key in example["case"] for key in queued)
    record = {
        "answerId": f"IV-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{args.slot.replace(':', '-')}",
        "profileId": profile["id"],
        "slot": args.slot,
        "session": args.session or now.strftime("%Y-%m-%d"),
        "question": args.question,
        "options": args.option,
        "answer": args.answer,
        "reason": args.reason,
        "answeredBy": args.answered_by,
        "answeredAt": now.isoformat(),
        "status": args.status,
        "checks": {
            "observable": bool(args.observable),
            "reproducible": len({item["expected"] for item in examples}) >= 2,
            "closed": bool(args.closed),
        },
        "counterExamples": examples,
        "provenance": {"source": args.source, "confidence": args.confidence, "owner": args.owner, "cite": args.cite},
        "appliesTo": args.applies_to,
        "supersedes": args.supersedes,
    }
    answers.append(record)
    write_json_atomic(path, ledger)
    print(json.dumps(record, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
