#!/usr/bin/env python3
"""판독자를 여러 번 불러 본 결과를 채점한다. 다수결로 접지 않는다.

한 번 잘 나온 것과 매번 잘 나오는 것은 다르다. 판독은 같은 사진에도 다른 답을 낼 수 있어서,
사례 하나를 한 번 맞힌 것으로는 「고쳤다」고 말할 수 없다. 그래서 같은 입력을 여러 번 넣고
**얼마나 자주 맞히는가**와 **답이 갈리는가**를 따로 낸다.

**갈린 답을 다수결로 합치지 않는다.** 3번 중 2번 맞혔다는 것과 3번 다 맞혔다는 것은
다른 사실이고, 앞은 그 사례가 판독기에게 아직 어렵다는 뜻이다. 합치면 그 사실이 지워진다.

기대값의 근거(`truthBasis`)를 함께 낸다. 근거의 종류가 다르면 틀렸을 때 뜻이 다르기 때문이다 —
사진에 찍힌 사실(`STRUCTURAL`)을 틀린 것은 사진을 못 본 것이고,
`CORROBORATED`를 틀린 것은 앞선 판독과 갈린 것이지 반드시 오답은 아니다.

review 패키지 규칙을 따른다 — `run-review/` 밖으로 쓰지 않는다.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def matches(expect: dict[str, Any], answer: dict[str, Any]) -> tuple[bool, list[str]]:
    """기대와 답이 맞는가. 어긋난 항목을 함께 돌려준다.

    `<필드>In` 키는 «이 중 하나면 된다»는 뜻이다. 착용과 휴대처럼 정책이 같이 세는 값이 있다.
    """
    misses: list[str] = []
    for key, wanted in expect.items():
        if key.endswith("In"):
            field = key[:-2]
            got = answer.get(field)
            if got not in wanted:
                misses.append(f"{field}={got!r} (기대 {wanted})")
            continue
        got = answer.get(key)
        if got != wanted:
            misses.append(f"{key}={got!r} (기대 {wanted!r})")
    return not misses, misses


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="runs/<프로필ID> 폴더")
    parser.add_argument("--cases", type=Path, required=True, help="시험 사례 JSON")
    parser.add_argument("--trials", type=Path, required=True, help="시행 기록 JSON")
    args = parser.parse_args()

    cases = {case["id"]: case for case in read_json(args.cases)["cases"]}
    trials = read_json(args.trials)["trials"]

    # 같은 사례를 고치기 전과 후에 각각 돌린다. 단계를 섞으면 «고쳐서 좋아졌다»가
    # «원래 그랬다»와 구분되지 않는다. 단계 이름을 안 주면 `final`로 본다.
    by_case: dict[tuple[str, str], list[dict[str, Any]]] = {}
    unknown: list[str] = []
    for trial in trials:
        case_id = str(trial.get("caseId") or "")
        if case_id not in cases:
            unknown.append(case_id)
            continue
        by_case.setdefault((case_id, str(trial.get("phase") or "final")), []).append(trial)

    results: list[dict[str, Any]] = []
    for (case_id, phase), runs in by_case.items():
        case = cases[case_id]
        hits = 0
        misses: list[str] = []
        signatures: Counter[str] = Counter()
        for trial in runs:
            answer = trial.get("answer") or {}
            ok, why = matches(case["expect"], answer)
            hits += 1 if ok else 0
            if why:
                misses.append(f"#{trial.get('run')}: " + " · ".join(why))
            # 답의 지문. 같은 사례를 여러 번 불렀을 때 답이 갈렸는지를 이걸로 본다.
            signatures[json.dumps(answer, ensure_ascii=False, sort_keys=True)] += 1
        results.append(
            {
                "caseId": case_id,
                "phase": phase,
                "agent": case["agent"],
                "truthBasis": case["truthBasis"],
                "runs": len(runs),
                "hits": hits,
                # 답이 몇 가지로 갈렸는가. 1이면 판독이 흔들리지 않았다는 뜻이다.
                "distinctAnswers": len(signatures),
                "misses": misses,
            }
        )

    # 갈려야 하는 짝. 같은 프레임의 두 사람이 같은 값으로 나오면 판독기가 한쪽으로 쏠린 것이다.
    contrasts: list[dict[str, Any]] = []
    seen: set[frozenset[str]] = set()
    for case_id, case in cases.items():
        other = case.get("contrastWith")
        if not other or other not in cases:
            continue
        pair = frozenset({case_id, other})
        if pair in seen:
            continue
        seen.add(pair)
        left = by_case.get((case_id, "final"), [])
        right = by_case.get((other, "final"), [])
        same = 0
        for a, b in zip(left, right):
            if (a.get("answer") or {}) == (b.get("answer") or {}):
                same += 1
        contrasts.append(
            {
                "pair": sorted(pair),
                "comparedRuns": min(len(left), len(right)),
                # 갈려야 하는데 같은 값이 나온 횟수. 0이 정상이다.
                "collapsed": same,
            }
        )

    record = {
        "schemaVersion": "catalog-reading-trials-v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "cases": str(args.cases),
        "note": "판독자 반복 호출 채점. 다수결로 합치지 않는다 — 갈린 사실을 그대로 남긴다.",
        "results": sorted(results, key=lambda item: (item["caseId"], item["phase"])),
        "contrasts": contrasts,
        "unknownCaseIds": sorted(set(unknown)),
    }
    out_dir = args.run.resolve() / "run-review"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "reading-trials.json"
    target.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(target)
    print(f"{'사례':<24} {'단계':<8} {'근거':<14} {'시행':>4} {'적중':>4} {'답 종류':>7}")
    for item in record["results"]:
        print(
            f"  {item['caseId']:<22} {item['phase']:<8} {item['truthBasis']:<14} "
            f"{item['runs']:>4} {item['hits']:>4} {item['distinctAnswers']:>7}"
        )
        for miss in item["misses"]:
            print(f"      어긋남 {miss}")
    for contrast in contrasts:
        state = "갈렸다" if contrast["collapsed"] == 0 else f"뭉갬 {contrast['collapsed']}회"
        print(f"  대비 {' ↔ '.join(contrast['pair'])}: {state}")
    if record["unknownCaseIds"]:
        print(f"  모르는 사례 id: {', '.join(record['unknownCaseIds'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
