#!/usr/bin/env python3
"""정책 규칙 하나마다 브리프 한 장을 만든다. 판례가 다음 실행에 닿는 유일한 길이다.

## 왜 이 파일이 있는가

판독자는 정책 파일을 열지 않는다. 열면 판정 규칙(어느 근거면 어느 라벨인가)까지 읽고,
그러면 「무엇이 보이는가」를 답해야 할 눈이 「무엇이 답인가」를 먼저 정해 버린다.
그래서 호출자가 **근거 규칙만 발췌해** 넣어 준다 — 이 설계는 옳다.

문제는 그 발췌를 **사람이 손으로 떴다**는 것이다. 어느 파일에서 뜨는지 적힌 곳이 없었고,
실제로 2순위 묶음 표의 마지막 줄이 빠져 판독자가 그 묶음을 못 본 적이 있다.
**발췌에 없는 것은 판독자에게 존재하지 않는다.** 손으로 뜨는 한 그 사고는 다시 난다.

그리고 더 큰 구멍이 있었다. 사람이 판례로 답한 경계가 **판독자에게 한 번도 닿지 않았다.**
판례는 정책 폴더 안에서 문서로만 살아 있었고, 다음 실행은 그것을 모른 채 같은 경계에서
같은 실수를 했다. 판례가 자산이 되려면 **다음 판독이 그것을 읽어야 한다.**

이 스크립트가 둘을 함께 없앤다. 규칙마다 한 장을 굽는다.

| 브리프에 실리는 것 | 왜 |
|---|---|
| 그 규칙이 속한 정책 섹션 **통째로** | 자르지 않는다. 자를 자리가 없으면 잘리지 않는다 |
| 그 규칙에 걸린 판례의 질문과 답 | 사람이 정한 경계가 다음 판독에 닿는 자리 |
| 그 판례를 근거로 확정한 사례 몇 건 | 말이 아니라 실제로 어떻게 적용됐는가 |
| 정책 파일의 해시 | 이 브리프가 어느 정책에서 나왔는지 되짚는다 |

## 판례에는 두 종류가 있다

`applies` 프론트매터가 가른다. 이 구분이 없으면 판독자가 GT 판정 규칙을 읽는다.

| 값 | 뜻 | 판독자에게 |
|---|---|---|
| `EVIDENCE` | **무엇이 근거인가**의 경계 (몇 묶음이면 결합이 성립하는가) | 준다 |
| `RULING` | **근거가 이러할 때 무엇으로 정할 것인가**의 경계 (GT를 뒤집을 것인가) | 주지 않는다 |

선언하지 않으면 `RULING`으로 본다. 모르는 것을 판독자에게 주는 쪽이 안 주는 쪽보다 나쁘다.

속성을 모른다. 정책 인덱스가 낸 규칙 목록과 판례 목록, 그리고 결정 원장에서 파생된
판례별 사례집만 읽는다. 어느 규칙이 몇 순위인지, 무엇을 뜻하는지는 여기서 알지 않는다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from build_policy_index import sections, split_front_matter
from catalog_profile import (
    default_profile,
    load_profile,
    output_root,
    policy_layer,
    project_path,
    relative_or_absolute,
)

BRIEF_SCHEMA = "catalog-rule-brief-v1"
FOR_READERS = "EVIDENCE"
# 판례가 실제로 적용된 사례를 몇 건까지 싣는가. 전부 실으면 브리프가 사례집이 되고,
# 판독자는 규칙 대신 사례를 외운다 — 그러면 새 사례를 못 읽는다.
MAX_CASES = 5


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def short_hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    except OSError:
        return "없음"


def question_of(path: Path) -> str:
    """판례 본문의 첫 제목 아래 문단. 그 판례가 무엇을 묻는지 한 덩어리다.

    프론트매터의 `decision`은 답이고, 답만 주면 무엇에 대한 답인지 모른다.
    """
    try:
        _, body = split_front_matter(path.read_text(encoding="utf-8"))
    except OSError:
        return ""
    lines: list[str] = []
    started = False
    for line in body.splitlines():
        if line.startswith("# "):
            started = True
            continue
        if started and line.startswith("#"):
            break
        if started:
            lines.append(line)
    return "\n".join(lines).strip()


def cases_for(log: dict[str, Any], precedent_id: str) -> list[dict[str, Any]]:
    """이 판례를 근거로 사람이 확정한 사례들. 최근 것이 앞에 온다."""
    entries = (log.get("byPrecedent") or {}).get(precedent_id) or []
    ordered = sorted(entries, key=lambda row: str(row.get("reviewedAt") or ""), reverse=True)
    return ordered[:MAX_CASES]


def brief_text(
    rule: dict[str, Any],
    excerpt: str,
    precedents: list[dict[str, Any]],
    log: dict[str, Any],
    policy_path: Path,
) -> str:
    for_readers = [item for item in precedents if item["applies"] == FOR_READERS]
    decided = [item for item in for_readers if item["status"] == "DECIDED"]
    still_open = [item for item in for_readers if item["status"] != "DECIDED"]

    parts = [
        f"# {rule['id']}",
        "",
        f"> {rule['summary']}" if rule["summary"] else "",
        "",
        f"<!-- 기계가 만들었다. 고칠 곳은 {relative_or_absolute(policy_path)}와 판례 파일이다. -->",
        f"<!-- 정책 {relative_or_absolute(policy_path)}@{short_hash(policy_path)} -->",
        "",
        f"## 정책 원문 — `{rule['section']}`",
        "",
        "이 섹션을 통째로 싣는다. **줄여서 넘기지 않는다** — 발췌에 없는 것은 판독자에게",
        "존재하지 않고, 실제로 표의 마지막 줄이 빠져 판독이 어긋난 적이 있다.",
        "",
        excerpt.strip(),
        "",
    ]

    parts.append("## 사람이 답한 경계")
    parts.append("")
    if not decided:
        parts.append(
            "이 규칙 위에서 확정된 판례가 아직 없다. 정책 원문만으로 판독한다 — "
            "**없는 판례를 있는 것처럼 추측하지 않는다.**"
        )
        parts.append("")
    for item in decided:
        parts += [f"### {item['id']}", "", f"**질문** {item['question']}" if item["question"] else "",
                  "", f"**답** {item['decision']}", ""]
        if item["decidedBy"] or item["decidedAt"]:
            parts.append(f"확정 {item['decidedBy'] or '—'} · {item['decidedAt'] or '—'}")
            parts.append("")
        cases = cases_for(log, item["id"])
        if cases:
            parts.append("이 판례를 근거로 실제로 이렇게 정했다.")
            parts.append("")
            for case in cases:
                label = case.get("correctedLabel") or "라벨 유지"
                parts.append(f"- `{case.get('productKey')}` → {label} — {case.get('reason') or '사유 없음'}")
            parts.append("")

    # 이 규칙 위에서 판례 없이 내린 판단들. 쌓이면 사람이 같은 경계를 매번 혼자 다시 넘고
    # 있다는 뜻이고, 그것이 **다음에 판례를 열 자리**다. 판독자에게는 안 싣는다 —
    # 확정되지 않은 개별 판단은 근거 규칙이 아니라 아직 답이 아닌 것들이기 때문이다.
    orphan = (log.get("ruleWithoutPrecedent") or {}).get(rule["id"]) or []
    if orphan:
        parts += [
            "---",
            "",
            f"<!-- 이 규칙 위에서 판례 없이 내린 판단이 {len(orphan)}건 쌓였다."
            " 같은 경계를 사람이 매번 다시 넘고 있다는 뜻이므로 판례를 열 자리다."
            " 확정되지 않은 판단이라 판독자에게는 싣지 않는다. -->",
            "",
        ]

    if still_open:
        parts += [
            "## 아직 답이 없는 경계",
            "",
            "아래 질문은 열려 있다. **이 경계에 걸리면 값을 만들지 말고 그렇게 적는다.**",
            "열린 질문을 판독자가 자기 판단으로 닫으면, 그 판단이 판례를 대신하게 된다.",
            "",
        ]
        for item in still_open:
            parts.append(f"- **{item['id']}** — {item['question'].splitlines()[0] if item['question'] else '질문 본문 없음'}")
        parts.append("")

    held = [item for item in precedents if item["applies"] != FOR_READERS]
    if held:
        parts += [
            "---",
            "",
            f"<!-- 이 규칙에는 판정 경계 판례도 {len(held)}건 걸려 있다"
            f"({', '.join(item['id'] for item in held)}). 판독자에게는 싣지 않는다 —"
            " 무엇이 근거인가를 답할 눈이 무엇이 답인가를 먼저 정하기 때문이다. -->",
            "",
        ]
    return "\n".join(line for line in parts if line is not None) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()

    profile = load_profile(args.profile or default_profile())
    layer = policy_layer(profile)
    if layer is None:
        print(f"{profile['id']}: policy 블록이 없어 규칙 브리프를 건너뜁니다.")
        return 0

    root = args.output_root.resolve() if args.output_root else output_root(profile)
    index = read_json(root / "policy" / "policy-index.json", {})
    rules = (index.get("owned") or {}).get("rules") or []
    if not rules:
        print(f"{profile['id']}: 정책이 이름 붙인 규칙이 없어 브리프를 만들지 않습니다.")
        return 0

    policy_path = layer["owned"]
    _, body = split_front_matter(policy_path.read_text(encoding="utf-8"))
    section_text = sections(body)

    # 판례를 규칙으로 찾을 수 있게 펼친다. 이 대조가 없으면 브리프는 정책 발췌일 뿐이다.
    # 프론트매터는 정책 인덱스가 이미 읽었다. 여기서 다시 읽지 않는다 — 두 번 읽으면
    # 한쪽이 `DECIDED`로 보는 판례를 다른 쪽이 `OPEN`으로 본다. 본문만 파일에서 뜬다.
    by_id: dict[str, dict[str, Any]] = {}
    for item in index.get("precedents") or []:
        by_id[str(item["id"])] = {
            "id": str(item["id"]),
            "status": str(item.get("status") or ""),
            "rules": [str(value) for value in (item.get("rules") or [])],
            "applies": str(item.get("applies") or "RULING"),
            "decision": str(item.get("decision") or ""),
            "decidedBy": str(item.get("decidedBy") or ""),
            "decidedAt": str(item.get("decidedAt") or ""),
            "question": question_of(project_path(str(item.get("path") or ""))),
        }

    gt_path = project_path(str((profile.get("gt") or {}).get("path") or ""))
    log = read_json(gt_path.parent / "from-decisions" / "precedent-log.json", {}) if gt_path.name else {}

    out_dir = root / "policy" / "rule-briefs"
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.md"):
        stale.unlink()

    listed: list[dict[str, Any]] = []
    for rule in rules:
        rule_id = str(rule["id"])
        bound = [item for item in by_id.values() if rule_id in item["rules"]]
        excerpt = section_text.get(str(rule["section"]), "")
        path = out_dir / f"{rule_id}.md"
        path.write_text(brief_text(rule, excerpt, bound, log, policy_path), encoding="utf-8")
        listed.append({
            "rule": rule_id,
            "section": rule["section"],
            "summary": rule["summary"],
            "path": relative_or_absolute(path),
            "precedents": sorted(item["id"] for item in bound),
            # 판독자에게 넘길 수 있는 판례가 몇 건인가. 0이면 이 규칙은 아직 정책 원문뿐이다.
            "forReaders": sorted(item["id"] for item in bound if item["applies"] == FOR_READERS),
        })

    index_path = out_dir / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "schemaVersion": BRIEF_SCHEMA,
                "profileId": profile["id"],
                "builtAt": datetime.now(UTC).isoformat(),
                "policy": relative_or_absolute(policy_path),
                "policySha256": short_hash(policy_path),
                "note": "규칙 하나에 브리프 한 장. 판독자에게는 이 파일을 그대로 넘긴다 — 손으로 발췌하지 않는다.",
                "briefs": listed,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    summary_path = root / "run-summary.json"
    if summary_path.is_file():
        summary = read_json(summary_path, {})
        if isinstance(summary, dict):
            summary.setdefault("artifacts", {})["ruleBriefs"] = relative_or_absolute(index_path)
            # 루프의 건강. `readersCanLearnFrom`이 0이면 판례가 쌓여도 **다음 판독은
            # 아무것도 배우지 못한다** — 확정된 근거 판례가 아직 하나도 없다는 뜻이다.
            summary["precedentBriefs"] = {
                "rules": len(listed),
                "rulesWithPrecedent": sum(1 for item in listed if item["precedents"]),
                "readersCanLearnFrom": sum(1 for item in listed if item["forReaders"]),
            }
            if "규칙 브리프" not in summary.setdefault("cycle", []):
                summary["cycle"].append("규칙 브리프")
            summary_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    print(
        json.dumps(
            {
                "briefs": len(listed),
                "rulesWithPrecedent": sum(1 for item in listed if item["precedents"]),
                "rulesReadersCanLearnFrom": sum(1 for item in listed if item["forReaders"]),
                "index": relative_or_absolute(index_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
