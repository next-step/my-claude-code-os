#!/usr/bin/env python3
"""소유 정책과 판례를 검증하고 실행 산출물에 정책 인덱스를 남긴다."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from catalog_profile import (
    PROJECT_ROOT,
    default_profile,
    load_profile,
    output_root,
    policy_layer,
    relative_or_absolute,
)


INDEX_SCHEMA = "catalog-policy-index-v1"
REQUIRED_SECTIONS = ("허용값", "근거 우선순위", "판정 불가 조건", "판례")
PRECEDENT_STATUSES = {"OPEN", "DECIDED", "SUPERSEDED"}
DECIDED_FIELDS = ("decision", "decidedBy", "decidedAt")
SECTION = re.compile(r"^##\s+(.+?)\s*$")
LABEL_LINE = re.compile(r"^-\s+`([A-Z][A-Z0-9_]*)`")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_front_matter(text: str) -> tuple[dict[str, str], str]:
    """`---`로 감싼 key: value 블록과 본문을 나눈다. 스킬 프론트매터와 같은 형식이다."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 3)
    if end == -1:
        return {}, text
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip():
            meta[key.strip()] = value.strip()
    return meta, text[end + 5 :]


def as_list(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def sections(body: str) -> dict[str, str]:
    found: dict[str, str] = {}
    title: str | None = None
    buffer: list[str] = []
    for line in body.splitlines():
        match = SECTION.match(line)
        if match:
            if title is not None:
                found[title] = "\n".join(buffer)
            title, buffer = match.group(1), []
        else:
            buffer.append(line)
    if title is not None:
        found[title] = "\n".join(buffer)
    return found


def violation(code: str, severity: str, detail: str) -> dict[str, Any]:
    return {"code": code, "severity": severity, "detail": detail}


def link_from(report_dir: Path, stored: str) -> str:
    """리포트 파일 위치 기준의 상대 링크. 산출물은 runs/ 안, 정책은 밖에 있다."""
    target = Path(stored)
    absolute = target if target.is_absolute() else PROJECT_ROOT / target
    return os.path.relpath(absolute, report_dir)


def read_owned(path: Path, profile_id: str, violations: list[dict[str, Any]]) -> dict[str, Any]:
    if not path.is_file():
        violations.append(
            violation("POLICY_FILE_MISSING", "BLOCKING", f"소유 정책이 없습니다: {path}")
        )
        return {}
    meta, body = split_front_matter(path.read_text(encoding="utf-8"))
    found = sections(body)
    if meta.get("id") != profile_id:
        violations.append(
            violation(
                "POLICY_ID_MISMATCH",
                "BLOCKING",
                f"프론트매터 id가 `{meta.get('id')}`인데 프로필 id는 `{profile_id}`입니다.",
            )
        )
    for name in REQUIRED_SECTIONS:
        if name not in found:
            violations.append(
                violation("POLICY_SECTION_MISSING", "BLOCKING", f"`## {name}` 섹션이 없습니다.")
            )
    labels = [
        match.group(1)
        for line in found.get("허용값", "").splitlines()
        if (match := LABEL_LINE.match(line.strip()))
    ]
    if not labels:
        violations.append(
            violation("POLICY_LABELS_EMPTY", "BLOCKING", "`## 허용값`에서 라벨을 읽지 못했습니다.")
        )
    return {
        "path": relative_or_absolute(path),
        "sha256": sha256(path),
        "version": meta.get("version"),
        "owner": meta.get("owner"),
        "updatedAt": meta.get("updatedAt"),
        "labels": labels,
        "sections": sorted(found),
    }


def read_precedents(directory: Path | None, profile_id: str, violations: list[dict[str, Any]]):
    if directory is None or not directory.is_dir():
        return []
    precedents: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.md")):
        meta, _ = split_front_matter(path.read_text(encoding="utf-8"))
        identifier = meta.get("id") or ""
        status = meta.get("status") or ""
        problems: list[str] = []
        if identifier != path.stem:
            problems.append(f"id `{identifier}`가 파일명 `{path.stem}`과 다릅니다")
        if meta.get("profile") != profile_id:
            problems.append(f"profile `{meta.get('profile')}`가 프로필 id와 다릅니다")
        if status not in PRECEDENT_STATUSES:
            problems.append(f"status `{status}`는 {sorted(PRECEDENT_STATUSES)} 중 하나여야 합니다")
        if status == "DECIDED":
            missing = [field for field in DECIDED_FIELDS if not meta.get(field)]
            if missing:
                problems.append(f"DECIDED인데 {', '.join(missing)}가 비어 있습니다")
        for problem in problems:
            violations.append(
                violation("PRECEDENT_MALFORMED", "BLOCKING", f"{path.name}: {problem}")
            )
        precedents.append(
            {
                "id": identifier or path.stem,
                "path": relative_or_absolute(path),
                "status": status,
                "answers": as_list(meta.get("answers")),
                "acknowledges": as_list(meta.get("acknowledges")),
                "decision": meta.get("decision") or None,
                "decidedBy": meta.get("decidedBy") or None,
                "decidedAt": meta.get("decidedAt") or None,
                "supersedes": meta.get("supersedes") or None,
                "sha256": sha256(path),
            }
        )
    return precedents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--index-file", type=Path)
    parser.add_argument("--report-file", type=Path)
    args = parser.parse_args()

    profile = load_profile(args.profile or default_profile())
    layer = policy_layer(profile)
    if layer is None:
        print(f"{profile['id']}: policy 블록이 없어 정책 레이어를 건너뜁니다.")
        return 0

    root = args.output_root.resolve() if args.output_root else output_root(profile)
    index_path = args.index_file.resolve() if args.index_file else root / "policy" / "policy-index.json"
    report_path = (
        args.report_file.resolve() if args.report_file else root / "reports" / "policy-status.md"
    )

    violations: list[dict[str, Any]] = []
    profile_id = str(profile["id"])
    owned = read_owned(layer["owned"], profile_id, violations)
    precedents = read_precedents(layer.get("precedents"), profile_id, violations)

    profile_labels = [str(item) for item in profile.get("labels", []) or []]
    policy_labels = owned.get("labels", [])
    for label in policy_labels:
        if label not in profile_labels:
            violations.append(
                violation(
                    "LABEL_NOT_IN_PROFILE",
                    "REVIEW",
                    f"정책 허용값 `{label}`이 프로필 labels에 없습니다.",
                )
            )
    for label in profile_labels:
        if policy_labels and label not in policy_labels:
            violations.append(
                violation(
                    "LABEL_NOT_IN_POLICY",
                    "REVIEW",
                    f"프로필 라벨 `{label}`이 정책 허용값에 없습니다.",
                )
            )

    questions_path = root / "reports" / "policy-questions.json"
    questions = json.loads(questions_path.read_text(encoding="utf-8")) if questions_path.is_file() else []
    question_ids = [str(item.get("id")) for item in questions if isinstance(item, dict)]
    answered: dict[str, list[str]] = {}
    resolved: set[str] = set()
    for precedent in precedents:
        for question_id in precedent["answers"]:
            answered.setdefault(question_id, []).append(precedent["id"])
            if precedent["status"] == "DECIDED":
                resolved.add(question_id)
            if question_id not in question_ids:
                violations.append(
                    violation(
                        "UNKNOWN_QUESTION",
                        "REVIEW",
                        f"{precedent['id']}가 없는 질문 `{question_id}`를 가리킵니다.",
                    )
                )
    for question_id in question_ids:
        if question_id not in answered:
            violations.append(
                violation(
                    "QUESTION_WITHOUT_PRECEDENT",
                    "REVIEW",
                    f"정책 질문 `{question_id}`에 대응하는 판례 파일이 없습니다.",
                )
            )

    acknowledged: dict[str, list[str]] = {}
    for precedent in precedents:
        for code in precedent["acknowledges"]:
            acknowledged.setdefault(code, []).append(precedent["id"])
    for item in violations:
        trackers = acknowledged.get(item["code"], [])
        item["tracked"] = bool(trackers)
        item["trackedBy"] = trackers

    blocking = [item for item in violations if item["severity"] == "BLOCKING"]
    untracked = [
        item for item in violations if item["severity"] == "REVIEW" and not item["tracked"]
    ]
    open_precedents = [item for item in precedents if item["status"] == "OPEN"]
    decided = [item for item in precedents if item["status"] == "DECIDED"]

    imported_path = layer.get("imported")
    index = {
        "schemaVersion": INDEX_SCHEMA,
        "profileId": profile_id,
        "generatedAt": datetime.now(UTC).isoformat(),
        "owned": owned,
        "imported": (
            {"path": relative_or_absolute(imported_path), "sha256": sha256(imported_path)}
            if imported_path is not None and imported_path.is_file()
            else None
        ),
        "precedents": precedents,
        "questionPrecedents": dict(sorted(answered.items())),
        "questionsWithoutPrecedent": sorted(
            item for item in question_ids if item not in answered
        ),
        "unresolvedQuestions": sorted(item for item in question_ids if item not in resolved),
        "counts": {
            "precedents": len(precedents),
            "decided": len(decided),
            "open": len(open_precedents),
            "questions": len(question_ids),
            "questionsWithPrecedent": len(answered),
            "questionsResolved": len(resolved),
            "blockingViolations": len(blocking),
            "untrackedReviewViolations": len(untracked),
        },
        "violations": violations,
    }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    def rows(items: list[dict[str, Any]]) -> str:
        if not items:
            return "- 없음"
        return "\n".join(
            f"- `{item['code']}` · {item['detail']}"
            + (f" (추적: {', '.join(item['trackedBy'])})" if item["trackedBy"] else "")
            for item in items
        )

    precedent_rows = (
        "\n".join(
            f"| [{item['id']}]({link_from(report_path.parent, item['path'])}) | {item['status']} | "
            f"{', '.join(item['answers']) or '-'} | {item['decision'] or '[미정]'} |"
            for item in precedents
        )
        or "| - | - | - | - |"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        f"""# {profile['displayName']} 정책 레이어 상태

- 소유 정책: [{owned.get('path', '없음')}]({link_from(report_path.parent, owned.get('path', '.'))}) (v{owned.get('version', '?')}, {owned.get('updatedAt', '?')})
- 허용값: {', '.join(f'`{label}`' for label in policy_labels) or '없음'}
- 판례: {len(precedents)}건 (확정 {len(decided)}건 · 열림 {len(open_precedents)}건)
- 정책 질문: {len(question_ids)}건 (판례 연결 {len(answered)}건 · 사람이 확정 {len(resolved)}건)

## 판례

| ID | 상태 | 답하는 질문 | 판정 |
|---|---|---|---|
{precedent_rows}

## 계약 위반 (사이클 중단)

{rows(blocking)}

## 추적되지 않은 검토 항목

{rows(untracked)}

추적되지 않은 항목은 아무도 모르는 정책 공백이다. 판례를 만들어 `acknowledges`에 코드를
적으면 "알고 남겨둔 것"으로 바뀐다. 공백 자체는 죄가 아니지만, 추적되지 않는 공백은 죄다.
""",
        encoding="utf-8",
    )

    summary_path = root / "run-summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if isinstance(summary, dict):
            summary["policyLayer"] = {
                "version": owned.get("version"),
                "labels": policy_labels,
                **index["counts"],
            }
            summary.setdefault("artifacts", {})["policyStatus"] = relative_or_absolute(report_path)
            summary.setdefault("artifacts", {})["policyIndex"] = relative_or_absolute(index_path)
            if "소유 정책 레이어" not in summary.setdefault("cycle", []):
                summary["cycle"].append("소유 정책 레이어")
            summary_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    print(json.dumps(index["counts"], ensure_ascii=False, sort_keys=True))
    for item in blocking:
        print(f"BLOCKING {item['code']}: {item['detail']}")
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
