#!/usr/bin/env python3
"""사람이 확정한 인터뷰 답을 ADR 한 장으로 옮긴다.

원장(answers.json)이 정본이고 ADR은 사람이 읽고 리뷰하는 쪽이다. 세션 하나가 ADR 한 장이다.
이미 있는 ADR은 덮어쓰지 않는다 — 사람이 손본 문장을 기계가 지우면 안 된다.
모양은 templates/adr.md에 있다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine" / "scripts"))

from catalog_profile import default_profile, load_profile, output_root, relative_or_absolute  # noqa: E402

CONTRACT = Path(__file__).resolve().parents[1] / "contracts" / "slots.json"
SCHEMA = "catalog-interview-v1"
FILENAME = re.compile(r"^ADR-(\d{4})-(.+)\.md$")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def slot_names(contract: Path) -> dict[str, dict[str, Any]]:
    return {str(slot["id"]): slot for slot in read_json(contract)["slots"]}


def sessions(answers: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in answers:
        grouped.setdefault(str(row.get("session") or row["answeredAt"][:10]), []).append(row)
    return sorted(grouped.items(), key=lambda item: min(row["answeredAt"] for row in item[1]))


def latest_per_slot(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    superseded = {row.get("supersedes") for row in rows if row.get("supersedes")}
    return [row for row in rows if row["answerId"] not in superseded]


def describe(row: dict[str, Any], slots: dict[str, dict[str, Any]]) -> tuple[str, str]:
    slot = slots.get(row["slot"])
    if slot:
        return slot["name"], f"`{row['slot']}` · `{slot['ambiguity']}`"
    return row["slot"], f"`{row['slot']}`"


def render(profile: dict[str, Any], number: int, session: str, rows: list[dict[str, Any]],
           slots: dict[str, dict[str, Any]], snapshot: dict[str, Any] | None, ledger_path: Path) -> str:
    current = latest_per_slot(rows)
    status = "ACCEPTED" if current and all(row["status"] == "RESOLVED" for row in current) else "PROPOSED"
    people = sorted({str(row["answeredBy"]) for row in rows})
    lines = [
        "---",
        f"id: ADR-{number:04d}",
        f"profile: {profile['id']}",
        f"session: {session}",
        f"status: {status}",
        f"renderedAt: {datetime.now(UTC).isoformat()}",
        f"source: {relative_or_absolute(ledger_path)}",
        "---",
        "",
        f"# ADR-{number:04d} · {profile['displayName']} · 정의 인터뷰 {session}",
        "",
        "> 원장에서 렌더한 문서다. 사람이 확정한 답만 담겨 있고, AI가 만든 질문·권고는 여기 없다.",
        "> 문장을 손보려면 원장을 고치고 다시 렌더하거나, 이 파일을 직접 고치되 다시 렌더하지 않는다.",
        "",
        "## 맥락",
        "",
    ]
    if snapshot:
        counts = snapshot.get("counts", {})
        lines.append(
            f"- 인터뷰 전 스캔: 빈 슬롯 {counts.get('empty', 0)}개 · 자리표시자 {counts.get('thin', 0)}개 · "
            f"열린 판례 {counts.get('openPrecedents', 0)}건 · 큐의 애매 상품 {counts.get('ambiguousProducts', 0)}건"
        )
    lines += [f"- 답한 사람: {', '.join(people)}", f"- 답 {len(rows)}건 (유효 {len(current)}건)", "", "## 질문과 답", ""]

    for index, row in enumerate(rows, start=1):
        name, tag = describe(row, slots)
        superseded = " · 이후 답으로 대체됨" if row not in current else ""
        lines += [f"### Q{index} · {name} ({tag}) — {row['status']}{superseded}", "", f"**질문** {row['question']}", ""]
        if row.get("options"):
            lines += ["**선택지**", ""] + [f"- {option}" for option in row["options"]] + [""]
        lines += [f"**답** {row['answer']}", ""]
        if row.get("reason"):
            lines += [f"**이유** {row['reason']}", ""]
        if row.get("counterExamples"):
            lines += ["**반례** — 이 답으로 갈리는 사례", "", "| 사례 | 값 | 큐 상품 |", "|---|---|---|"]
            lines += [
                f"| {item['case']} | {item['expected']} | {'예' if item.get('queued') else '아니오'} |"
                for item in row["counterExamples"]
            ] + [""]
        provenance = row.get("provenance") or {}
        if provenance.get("source"):
            owner = f" · 소유자 {provenance['owner']}" if provenance.get("owner") else ""
            cite = f" · 인용 `{provenance['cite']}`" if provenance.get("cite") else ""
            lines += [f"**출처** {provenance['source']} · {provenance['confidence']}{cite}{owner}", ""]
        if row.get("appliesTo"):
            lines += [f"**적용처** `{row['appliesTo']}`", ""]
        lines += [f"_{row['answeredBy']} · {row['answeredAt']} · `{row['answerId']}`_", ""]

    resolved = [row for row in current if row["status"] == "RESOLVED"]
    pending = [row for row in current if row["status"] != "RESOLVED"]
    lines += ["## 결정", ""]
    lines += [f"- **{describe(row, slots)[0]}** — {row['answer']}" for row in resolved] or ["- 확정된 답이 없다"]
    lines += ["", "## 열린 것", ""]
    lines += [
        f"- **{describe(row, slots)[0]}** ({row['status']}) — {row['question']}"
        + (f" · {row['reason']}" if row.get("reason") else "")
        for row in pending
    ] or ["- 없음"]
    targets = sorted({str(row["appliesTo"]) for row in resolved if row.get("appliesTo")})
    queued = [item["case"] for row in resolved for item in row.get("counterExamples", []) if item.get("queued")]
    lines += ["", "## 결과", "", "- 갱신할 파일: " + (", ".join(f"`{target}`" for target in targets) or "없음")]
    customs = [describe(row, slots)[0] for row in resolved if (row.get("provenance") or {}).get("confidence") == "CUSTOM"]
    if customs:
        # 관행은 쓰되 근거를 남겨야 한다. 여기 적히지 않으면 "왜 그런지 아무도 모르는 규칙"으로 남는다.
        lines.append("- 판례로 승격할 것 (관행이라 근거가 없다): " + ", ".join(f"**{name}**" for name in customs))
    lines += [
        "- 다음 사이클에서 확인할 것: "
        + (f"반례로 든 큐 상품 {len(queued)}건이 큐에서 빠지는가 — " + ", ".join(queued[:5]) if queued else "반례에 큐 상품이 없다. 답이 맞는지 다음 사이클에서 검증할 길이 없다")
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="인터뷰 원장을 ADR로 렌더한다.")
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--adr-dir", type=Path, help="기본값: 프로필이 있는 폴더의 adr/")
    parser.add_argument("--force", action="store_true", help="이미 있는 ADR도 다시 쓴다")
    args = parser.parse_args()

    profile = load_profile(args.profile or default_profile())
    root = args.output_root.resolve() if args.output_root else output_root(profile)
    ledger_path = root / "interview" / "answers.json"
    if not ledger_path.is_file():
        raise SystemExit(f"기록된 답이 없습니다: {relative_or_absolute(ledger_path)}")
    ledger = read_json(ledger_path)
    if ledger.get("schemaVersion") != SCHEMA:
        raise SystemExit("지원하지 않는 인터뷰 원장 버전입니다.")
    snapshot_path = root / "interview" / "slots.json"
    snapshot = read_json(snapshot_path) if snapshot_path.is_file() else None
    slots = slot_names(args.contract)

    adr_dir = args.adr_dir.resolve() if args.adr_dir else Path(profile["_path"]).parent / "adr"
    adr_dir.mkdir(parents=True, exist_ok=True)
    existing: dict[str, tuple[int, Path]] = {}
    for path in adr_dir.glob("ADR-*.md"):
        match = FILENAME.match(path.name)
        if match:
            existing[match.group(2)] = (int(match.group(1)), path)
    next_number = max((number for number, _ in existing.values()), default=0) + 1

    for session, rows in sessions(ledger.get("answers", [])):
        safe = re.sub(r"[^A-Za-z0-9_-]+", "-", session).strip("-")
        if safe in existing and not args.force:
            print(f"건너뜀 {relative_or_absolute(existing[safe][1])} — 이미 있다. 다시 쓰려면 --force")
            continue
        number = existing[safe][0] if safe in existing else next_number
        if safe not in existing:
            next_number += 1
        path = adr_dir / f"ADR-{number:04d}-{safe}.md"
        path.write_text(render(profile, number, session, rows, slots, snapshot, ledger_path), encoding="utf-8")
        print(f"작성 {relative_or_absolute(path)} — 답 {len(rows)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
