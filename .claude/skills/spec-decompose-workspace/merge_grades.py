#!/usr/bin/env python3
"""기계 채점(A1/A4) + 블라인드 채점(A2/A3/A5/A6)을 run별 grading.json으로 합친다.

블라인드 채점 결과는 `sample-X` 라벨로 되어 있어서, `blind_mapping.json`으로
원래 run 경로를 되찾아야 한다. 매핑을 여기서만 여는 이유는 채점자에게
팔 정보를 주지 않기 위해서다 — 실험 3에서 오염이 난 곳이 채점자가 아니라
결과를 정리하는 호출자 층이었다는 기록(docs/context-ab-test.md:154)을 따랐다.

사용법: python3 merge_grades.py <iteration-dir>
"""
import json
import sys
from pathlib import Path

ASSERTION_TEXT = {}


def load_texts(it: Path):
    for eval_dir in sorted(it.glob("eval-*")):
        meta = json.loads((eval_dir / "eval_metadata.json").read_text(encoding="utf-8"))
        ASSERTION_TEXT[eval_dir.name] = {a["id"]: a["text"] for a in meta["assertions"]}


def main() -> int:
    it = Path(sys.argv[1])
    load_texts(it)
    mech = json.loads((it / "mechanical_grades.json").read_text(encoding="utf-8"))
    mapping = json.loads((it / "blind_mapping.json").read_text(encoding="utf-8"))

    # sample 라벨 -> run 경로. 역방향으로 뒤집어 run별 블라인드 점수를 모은다.
    blind_by_run = {}
    for blind_key, run_key in mapping.items():
        eval_name, label = blind_key.split("/")
        gfile = it / "blind" / eval_name / "grades.json"
        if not gfile.exists():
            print(f"ERROR: {gfile} 없음 — 블라인드 채점이 끝나지 않았다")
            return 1
        grades = json.loads(gfile.read_text(encoding="utf-8"))
        if label not in grades:
            print(f"ERROR: {gfile} 에 {label} 없음")
            return 1
        blind_by_run[run_key] = grades[label]

    written = 0
    for run_key, mech_res in mech.items():
        eval_name = run_key.split("/")[0]
        texts = ASSERTION_TEXT[eval_name]
        blind_res = blind_by_run.get(run_key)
        if blind_res is None:
            print(f"ERROR: {run_key} 블라인드 결과 없음")
            return 1

        expectations = []
        for aid in ("A1", "A2", "A3", "A4", "A5", "A6"):
            src = mech_res.get(aid) or blind_res.get(aid)
            if src is None:
                print(f"ERROR: {run_key} 의 {aid} 판정 없음")
                return 1
            expectations.append({
                "id": aid,
                "text": texts[aid],
                "passed": bool(src["passed"]),
                "evidence": src.get("evidence", ""),
            })

        passed = sum(1 for e in expectations if e["passed"])
        total = len(expectations)
        grading = {
            "summary": {
                "pass_rate": round(passed / total, 4),
                "passed": passed,
                "failed": total - passed,
                "total": total,
            },
            "expectations": expectations,
        }
        dest = it / run_key / "grading.json"
        dest.write_text(json.dumps(grading, ensure_ascii=False, indent=2), encoding="utf-8")
        written += 1
        print(f"{run_key}: {passed}/{total}")
    print(f"\ngrading.json {written}개 작성")
    return 0


if __name__ == "__main__":
    sys.exit(main())
