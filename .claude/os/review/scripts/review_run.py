#!/usr/bin/env python3
"""엔진이 낸 run 하나를 심사한다 — 이 결과로 사람이 판정을 시작해도 되는가.

엔진을 import하지 않는다. 프로필도 어댑터도 읽지 않는다. 읽는 것은 `run-summary.json`과
그 파일이 `artifacts`로 선언한 경로뿐이다. 그래서 어떤 속성의 run이든 같은 코드가 본다.

쓰는 것은 `run-review/` 아래뿐이다. 엔진 산출물도 사람 판정 원장도 고치지 않는다.
읽기만 하는 쪽이 판정을 남기면, 다음 사람은 어느 숫자가 원본인지 알 수 없다.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "catalog-run-review-v1"
SUMMARY_NAME = "run-summary.json"
OUTPUT_DIRNAME = "run-review"
# 큐 계약. 이 다섯이 없으면 사람은 그 행을 판정할 수 없다.
QUEUE_CONTRACT = ("signal", "reason", "productKey", "referenceLabel", "observedLabel")
SAMPLE_LIMIT = 20
SEVERITY_ORDER = {"ERROR": 0, "WARN": 1, "INFO": 2}


def find_project_root(start: Path) -> Path:
    for parent in [start.resolve(), *start.resolve().parents]:
        if (parent / ".claude").is_dir():
            return parent
    raise SystemExit("프로젝트 루트(.claude를 가진 폴더)를 찾지 못했습니다.")


PROJECT_ROOT = find_project_root(Path(__file__))
RUNS_ROOT = PROJECT_ROOT / ".claude" / "os" / "runs"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def default_run() -> Path:
    """엔진이 프로필을 하나만 찾을 때 그것을 쓰듯, run이 하나뿐일 때만 그것을 쓴다."""
    found = sorted(run for run in RUNS_ROOT.glob("*") if (run / SUMMARY_NAME).is_file())
    if len(found) == 1:
        return found[0]
    if not found:
        raise SystemExit(f"{relative(RUNS_ROOT)} 아래에 {SUMMARY_NAME}을 가진 run이 없습니다.")
    names = ", ".join(run.name for run in found)
    raise SystemExit(f"run이 여럿입니다({names}). --run으로 하나를 지정하세요.")


class Review:
    """검사 하나가 무엇을 봤고 무엇을 못 봤는지까지 남긴다. 건너뛴 검사는 통과가 아니다."""

    def __init__(self, run: Path, summary: dict[str, Any]) -> None:
        self.run = run
        self.summary = summary
        self.artifacts = summary.get("artifacts") if isinstance(summary.get("artifacts"), dict) else {}
        self.findings: list[dict[str, Any]] = []
        self.checks: list[dict[str, Any]] = []

    def declared(self, key: str) -> Path | None:
        value = self.artifacts.get(key)
        if not isinstance(value, str) or not value:
            return None
        path = Path(value)
        return path if path.is_absolute() else (PROJECT_ROOT / path)

    def ran(self, check: str, looked_at: list[str]) -> None:
        self.checks.append({"check": check, "status": "RAN", "lookedAt": sorted(set(looked_at))})

    def skipped(self, check: str, reason: str) -> None:
        self.checks.append({"check": check, "status": "SKIPPED", "reason": reason})

    def find(
        self,
        check: str,
        severity: str,
        summary: str,
        *,
        count: int,
        pointer: str,
        sample: list[Any] | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.findings.append(
            {
                "check": check,
                "severity": severity,
                "summary": summary,
                "count": count,
                "pointer": pointer,
                "sample": (sample or [])[:SAMPLE_LIMIT],
                "detail": detail or {},
            }
        )


def queued_products(queue_dir: Path) -> dict[str, set[str]]:
    """같은 상품이 여러 큐에 있으면 한 건이다. 진행률을 만든 쪽과 같은 규칙으로 센다."""
    products: dict[str, set[str]] = {}
    for path in sorted(queue_dir.glob("*.jsonl")):
        for row in read_jsonl(path):
            key = str(row.get("productKey") or "")
            if key:
                products.setdefault(key, set()).add(str(row.get("signal") or path.stem))
    return products


def latest_decisions(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    decisions = ledger.get("decisions")
    if not isinstance(decisions, list):
        return {}
    latest: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        if isinstance(decision, dict) and decision.get("productKey"):
            latest[str(decision["productKey"])] = decision
    return latest


def check_declared_artifacts(review: Review) -> None:
    """선언한 산출물이 실제로 있는가. 없는 산출물을 가리키는 요약은 그 자체가 옛 실행의 것이다."""
    check = "ARTIFACT_DECLARED"
    if not review.artifacts:
        review.skipped(check, f"{SUMMARY_NAME}에 artifacts 선언이 없습니다.")
        return
    missing: list[str] = []
    for name in sorted(review.artifacts):
        path = review.declared(name)
        if path is None or not path.exists():
            missing.append(f"{name} → {review.artifacts[name]}")
        elif path.is_file() and path.stat().st_size == 0:
            missing.append(f"{name} → 비어 있음")
    review.ran(check, [relative(review.run / SUMMARY_NAME)])
    if missing:
        review.find(
            check,
            "ERROR",
            "요약이 선언한 산출물이 없거나 비어 있다. 이 요약은 지금 폴더의 것이 아니다.",
            count=len(missing),
            pointer=relative(review.run / SUMMARY_NAME),
            sample=missing,
        )


def check_queue_contract(review: Review, queue_dir: Path | None) -> None:
    """사람이 한 행을 판정하려면 다섯 필드가 있어야 한다. 근거 없는 행은 큐에 쌓일 뿐 판정되지 않는다."""
    check = "QUEUE_CONTRACT"
    if queue_dir is None or not queue_dir.is_dir():
        review.skipped(check, "queueDirectory가 선언되지 않았거나 폴더가 없습니다.")
        return
    broken: list[dict[str, Any]] = []
    rows = 0
    files = sorted(queue_dir.glob("*.jsonl"))
    for path in files:
        for index, row in enumerate(read_jsonl(path), start=1):
            rows += 1
            absent = [field for field in QUEUE_CONTRACT if not str(row.get(field) or "").strip()]
            if absent:
                broken.append({"file": path.name, "line": index, "missing": absent})
    review.ran(check, [relative(queue_dir)])
    if broken:
        review.find(
            check,
            "ERROR",
            "큐 계약 필드가 빈 행이 있다. 사람이 이 행을 판정할 수 없다.",
            count=len(broken),
            pointer=relative(queue_dir),
            sample=broken,
            detail={"queueFiles": len(files), "queueRows": rows},
        )


def check_progress_recount(
    review: Review,
    queue_dir: Path | None,
    decisions: dict[str, dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """요약이 말한 진행률을 산출물에서 다시 센다. 복사된 숫자는 조용히 틀린다."""
    check = "PROGRESS_RECOUNT"
    if queue_dir is None or not queue_dir.is_dir():
        review.skipped(check, "queueDirectory가 없어 다시 셀 수 없습니다.")
        return None
    products = queued_products(queue_dir)
    ledger = decisions or {}
    pending = sorted(key for key in products if key not in ledger)
    deferred = sorted(key for key in products if ledger.get(key, {}).get("decision") == "DEFERRED")
    adjudicated = sorted(
        key for key in products if key in ledger and ledger[key].get("decision") != "DEFERRED"
    )
    recount = {
        "queuedProducts": len(products),
        "adjudicatedProducts": len(adjudicated),
        "deferredProducts": len(deferred),
        "pendingProducts": len(pending),
    }
    review.ran(check, [relative(queue_dir)])

    claimed = review.summary.get("reviewProgress")
    if not isinstance(claimed, dict):
        review.find(
            check,
            "WARN",
            "요약에 reviewProgress가 없다. 사람 판정이 어디까지 왔는지 요약만 보고는 알 수 없다.",
            count=1,
            pointer=relative(review.run / SUMMARY_NAME),
        )
        return recount

    gaps = [
        {"field": field, "claimed": claimed.get(field), "recounted": value}
        for field, value in recount.items()
        if isinstance(claimed.get(field), int) and claimed[field] != value
    ]
    if not gaps:
        return recount

    generated_at = str(review.summary.get("generatedAt") or "")
    recorded_after = sorted(
        key
        for key, decision in ledger.items()
        if str(decision.get("reviewedAt") or "") > generated_at
    )
    if recorded_after:
        review.find(
            check,
            "WARN",
            "요약을 만든 뒤에 판정이 기록됐다. 진행률이 원장보다 옛것이다 — 사이클을 다시 돌려라.",
            count=len(recorded_after),
            pointer=relative(review.run / SUMMARY_NAME),
            sample=recorded_after,
            detail={"gaps": gaps},
        )
    else:
        review.find(
            check,
            "ERROR",
            "요약의 진행률과 산출물을 다시 센 값이 다르다. 둘은 서로 다른 실행의 것이다.",
            count=len(gaps),
            pointer=relative(review.run / SUMMARY_NAME),
            sample=gaps,
        )
    return recount


def check_verdict_coverage(
    review: Review, queue_dir: Path | None, verdicts: list[dict[str, Any]] | None
) -> None:
    """심판이 큐를 전부 훑었는가. 빠진 상품은 추천 없이 사람에게만 남는다."""
    check = "VERDICT_COVERAGE"
    if verdicts is None:
        review.skipped(check, "arbiterVerdicts가 선언되지 않았습니다. 심판 없는 프로필입니다.")
        return
    if queue_dir is None or not queue_dir.is_dir():
        review.skipped(check, "queueDirectory가 없어 대조할 대상이 없습니다.")
        return
    products = set(queued_products(queue_dir))
    judged = {str(row.get("productKey") or "") for row in verdicts}
    uncovered = sorted(products - judged)
    orphan = sorted(judged - products - {""})
    review.ran(check, [relative(queue_dir)])
    if uncovered:
        review.find(
            check,
            "ERROR",
            "큐에 있는데 심판 결과가 없는 상품이 있다. 심판이 이번 큐를 보지 않았다.",
            count=len(uncovered),
            pointer=str(review.artifacts.get("arbiterVerdicts")),
            sample=uncovered,
        )
    if orphan:
        review.find(
            check,
            "WARN",
            "큐에 없는 상품의 심판 결과가 남아 있다. 심판 결과가 옛 큐의 것이다.",
            count=len(orphan),
            pointer=str(review.artifacts.get("arbiterVerdicts")),
            sample=orphan,
        )


def check_review_load(
    review: Review,
    queue_dir: Path | None,
    verdicts: list[dict[str, Any]] | None,
    decisions: dict[str, dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """미판정 큐 안에서 지금 판정 가능한 건이 몇 건인가.

    사람의 시간이 가장 비싼 자원이다. 충돌이 아닌 건과 판례에 막힌 건이 큐에 섞여 있으면
    진행률은 정직해도 그 숫자가 가리키는 일은 정직하지 않다.
    """
    check = "REVIEW_LOAD"
    if verdicts is None or queue_dir is None or not queue_dir.is_dir():
        review.skipped(check, "심판 결과나 큐가 없어 판정 가능한 건을 가를 수 없습니다.")
        return None
    ledger = decisions or {}
    pending = {key for key in queued_products(queue_dir) if key not in ledger}
    by_product = {str(row.get("productKey") or ""): row for row in verdicts}
    no_conflict = sorted(key for key in pending if by_product.get(key, {}).get("owner") == "NONE")
    blocked: dict[str, list[str]] = {}
    for key in sorted(pending):
        for precedent in by_product.get(key, {}).get("blockedBy") or []:
            blocked.setdefault(str(precedent), []).append(key)
    blocked_keys = {key for keys in blocked.values() for key in keys}
    decidable = sorted(pending - set(no_conflict) - blocked_keys)
    load = {
        "pendingProducts": len(pending),
        "noConflictProducts": len(no_conflict),
        "blockedProducts": len(blocked_keys),
        "decidableNow": len(decidable),
        "blockedByPrecedent": {pid: len(keys) for pid, keys in sorted(blocked.items())},
    }
    review.ran(check, [relative(queue_dir), str(review.artifacts.get("arbiterVerdicts"))])
    if no_conflict:
        review.find(
            check,
            "WARN",
            "심판이 충돌 없음으로 본 상품이 미판정 큐에 남아 있다. 사람 시간이 여기에 쓰인다.",
            count=len(no_conflict),
            pointer=str(review.artifacts.get("arbiterVerdicts")),
            sample=no_conflict,
        )
    if blocked:
        review.find(
            check,
            "WARN",
            "미결 판례가 답해야 판정할 수 있는 상품이 있다. 건별 판정보다 판례가 먼저다.",
            count=len(blocked_keys),
            pointer=str(review.artifacts.get("arbiterVerdicts")),
            sample=[{"precedent": pid, "products": len(keys)} for pid, keys in sorted(blocked.items())],
            detail={"blockedByPrecedent": load["blockedByPrecedent"]},
        )
    return load


def check_ledger_alignment(
    review: Review, queue_dir: Path | None, decisions: dict[str, dict[str, Any]] | None
) -> None:
    """사람 판정이 이번 run의 근거 위에서 내려졌는가."""
    check = "LEDGER_ALIGNMENT"
    if decisions is None:
        review.skipped(check, "decisionLedger가 선언되지 않았습니다.")
        return
    if queue_dir is None or not queue_dir.is_dir():
        review.skipped(check, "queueDirectory가 없어 원장과 대조할 수 없습니다.")
        return
    products = queued_products(queue_dir)
    review.ran(check, [str(review.artifacts.get("decisionLedger")), relative(queue_dir)])
    stale = sorted(key for key in decisions if key not in products)
    if stale:
        review.find(
            check,
            "WARN",
            "큐에서 사라진 상품의 판정이 원장에 있다. 지우지 말고 왜 사라졌는지 확인한다.",
            count=len(stale),
            pointer=str(review.artifacts.get("decisionLedger")),
            sample=stale,
        )
    moved = [
        {
            "productKey": key,
            "decidedOn": sorted(decision.get("queueSignals") or []),
            "nowInQueueAs": sorted(products[key]),
        }
        for key, decision in sorted(decisions.items())
        if key in products and sorted(decision.get("queueSignals") or []) != sorted(products[key])
    ]
    if moved:
        review.find(
            check,
            "WARN",
            "판정할 때의 신호와 지금 큐의 신호가 다르다. 그 판정은 다른 근거 위에서 내려졌다.",
            count=len(moved),
            pointer=str(review.artifacts.get("decisionLedger")),
            sample=moved,
        )


def check_policy_layer(review: Review) -> None:
    """정책 공백이 추적되고 있는가. goal의 완료 조건이 0을 요구하는 항목이다."""
    check = "POLICY_TRACKING"
    layer = review.summary.get("policyLayer")
    if not isinstance(layer, dict):
        review.skipped(check, "policyLayer가 없습니다. 소유 정책이 없는 프로필입니다.")
        return
    review.ran(check, [relative(review.run / SUMMARY_NAME)])
    untracked = layer.get("untrackedReviewViolations")
    if isinstance(untracked, int) and untracked > 0:
        review.find(
            check,
            "ERROR",
            "어느 판례도 추적하지 않는 정책 위반이 있다. 답할 사람이 없는 공백이다.",
            count=untracked,
            pointer=str(review.artifacts.get("policyStatus") or relative(review.run / SUMMARY_NAME)),
        )
    blocking = layer.get("blockingViolations")
    if isinstance(blocking, int) and blocking > 0:
        review.find(
            check,
            "ERROR",
            "정책 레이어가 막은 위반이 남아 있다.",
            count=blocking,
            pointer=str(review.artifacts.get("policyStatus") or relative(review.run / SUMMARY_NAME)),
        )


def completion(review: Review, recount: dict[str, Any] | None) -> list[dict[str, Any]]:
    """goal.md의 완료 조건을 이 run에서 확인한다. 다시 센 값과 요약이 말한 값을 구분해 적는다."""
    layer = review.summary.get("policyLayer") if isinstance(review.summary.get("policyLayer"), dict) else {}
    rows: list[dict[str, Any]] = []
    if recount is not None:
        rows.append(
            {
                "condition": "큐에 쌓인 상품이 전부 한 번은 사람 판정을 거쳤다",
                "observed": recount["pendingProducts"],
                "met": recount["pendingProducts"] == 0,
                "source": "recount",
            }
        )
    for condition, field in (
        ("질문마다 답한 판례가 있다", "open"),
        ("추적되지 않는 공백이 없다", "untrackedReviewViolations"),
    ):
        if isinstance(layer.get(field), int):
            rows.append(
                {
                    "condition": condition,
                    "observed": layer[field],
                    "met": layer[field] == 0,
                    "source": SUMMARY_NAME,
                }
            )
    if isinstance(layer.get("questions"), int) and isinstance(layer.get("questionsResolved"), int):
        rows.append(
            {
                "condition": "정책 결함마다 답한 질문이 있다",
                "observed": layer["questions"] - layer["questionsResolved"],
                "met": layer["questions"] == layer["questionsResolved"],
                "source": SUMMARY_NAME,
            }
        )
    rows.append(
        {
            "condition": "GT 결함이 다음 스냅샷에 반영됐다",
            "observed": None,
            "met": None,
            "source": "다음 사이클과 비교해야 안다. 이번 run 하나로는 확인할 수 없다",
        }
    )
    return rows


def render_markdown(report: dict[str, Any]) -> str:
    verdict_line = {
        "PASS": "이 run으로 사람 판정을 시작해도 된다.",
        "WARN": "시작할 수 있지만, 먼저 읽어야 할 지적이 있다.",
        "FAIL": "이 run을 판정 근거로 쓰지 않는다. 아래를 고치고 사이클을 다시 돌린다.",
    }[report["verdict"]]
    lines = [
        f"# {report['runId']} · 실행 심사",
        "",
        f"- 판정: **{report['verdict']}** — {verdict_line}",
        f"- 본 요약: `{report['basedOn']['file']}` (생성 {report['basedOn']['generatedAt']})",
        f"- 심사 시각: {report['reviewedAt']}",
        "",
        "이 문서는 엔진 산출물을 **읽기만** 하고 다시 센 결과다. 여기 숫자의 출처는",
        "`run-review.json`이고, 사람 판정 원장은 이 심사로 바뀌지 않는다.",
        "",
        "## 지적",
        "",
    ]
    if not report["findings"]:
        lines += ["없음.", ""]
    else:
        lines += ["| 심각도 | 검사 | 건수 | 무엇이 |", "|---|---|---|---|"]
        for finding in report["findings"]:
            lines.append(
                f"| `{finding['severity']}` | `{finding['check']}` | {finding['count']} | {finding['summary']} |"
            )
        lines += ["", "근거는 `findings.jsonl`에 검사별로 있다. 각 행의 `pointer`가 원본 산출물이다.", ""]

    lines += ["## 검사", "", "| 검사 | 상태 | 비고 |", "|---|---|---|"]
    for check in report["checks"]:
        note = check.get("reason") or ", ".join(f"`{path}`" for path in check.get("lookedAt", []))
        lines.append(f"| `{check['check']}` | {check['status']} | {note} |")
    lines += ["", "**건너뛴 검사는 통과가 아니다.** 요약이 그 산출물을 선언하지 않았다는 뜻이다.", ""]

    if report.get("reviewLoad"):
        load = report["reviewLoad"]
        lines += [
            "## 지금 판정 가능한 건",
            "",
            "| 구분 | 건수 |",
            "|---|---|",
            f"| 미판정 | {load['pendingProducts']} |",
            f"| 심판이 충돌 없다고 본 것 | {load['noConflictProducts']} |",
            f"| 미결 판례에 막힌 것 | {load['blockedProducts']} |",
            f"| **지금 사람이 가를 수 있는 것** | **{load['decidableNow']}** |",
            "",
        ]

    lines += ["## 완료 조건", "", "| 조건 | 관측 | 충족 | 출처 |", "|---|---|---|---|"]
    for row in report["completion"]:
        met = {True: "예", False: "아니오", None: "측정 불가"}[row["met"]]
        observed = "—" if row["observed"] is None else row["observed"]
        lines.append(f"| {row['condition']} | {observed} | {met} | {row['source']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, help="심사할 run 폴더. 생략하면 run이 하나일 때만 그것을 쓴다")
    parser.add_argument("--strict", action="store_true", help="ERROR가 하나라도 있으면 1로 끝낸다")
    args = parser.parse_args()

    run = (args.run.resolve() if args.run else default_run())
    summary_path = run / SUMMARY_NAME
    if not summary_path.is_file():
        raise SystemExit(f"{relative(summary_path)}이 없습니다. 엔진 사이클을 먼저 돌리세요.")
    summary = read_json(summary_path)
    if not isinstance(summary, dict):
        raise SystemExit(f"{relative(summary_path)}: 객체가 아닙니다.")

    review = Review(run, summary)
    queue_dir = review.declared("queueDirectory")

    verdict_path = review.declared("arbiterVerdicts")
    verdicts = read_jsonl(verdict_path) if verdict_path and verdict_path.is_file() else None
    ledger_path = review.declared("decisionLedger")
    decisions = (
        latest_decisions(read_json(ledger_path))
        if ledger_path and ledger_path.is_file()
        else None
    )

    check_declared_artifacts(review)
    check_queue_contract(review, queue_dir)
    recount = check_progress_recount(review, queue_dir, decisions)
    check_verdict_coverage(review, queue_dir, verdicts)
    load = check_review_load(review, queue_dir, verdicts, decisions)
    check_ledger_alignment(review, queue_dir, decisions)
    check_policy_layer(review)

    review.findings.sort(key=lambda item: (SEVERITY_ORDER[item["severity"]], item["check"]))
    counts = {
        severity: sum(1 for item in review.findings if item["severity"] == severity)
        for severity in ("ERROR", "WARN", "INFO")
    }
    verdict = "FAIL" if counts["ERROR"] else ("WARN" if counts["WARN"] else "PASS")

    report = {
        "schemaVersion": SCHEMA,
        "runId": run.name,
        "reviewedAt": datetime.now(UTC).isoformat(),
        "basedOn": {
            "file": relative(summary_path),
            "generatedAt": summary.get("generatedAt"),
            "profileId": summary.get("profileId"),
        },
        "verdict": verdict,
        "findingCounts": counts,
        "findings": review.findings,
        "checks": review.checks,
        "recount": recount,
        "reviewLoad": load,
        "completion": completion(review, recount),
    }

    output_dir = run / OUTPUT_DIRNAME
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "findings.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in review.findings),
        encoding="utf-8",
    )
    (output_dir / "run-review.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "run-review.md").write_text(render_markdown(report), encoding="utf-8")

    print(
        json.dumps(
            {
                "verdict": verdict,
                "runId": report["runId"],
                "basedOn": report["basedOn"]["generatedAt"],
                "findingCounts": counts,
                "report": relative(output_dir / "run-review.md"),
                "json": relative(output_dir / "run-review.json"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 1 if (args.strict and counts["ERROR"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
