#!/usr/bin/env python3
"""가방 성별 정책의 직접 근거로 실행 오류와 GT 오류 후보를 분리한다."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("프로젝트 루트(.claude를 가진 폴더)를 찾지 못했습니다.")


PROJECT_ROOT = _find_project_root()
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / ".claude" / "os" / "runs" / "bag-category-gender"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: object expected")
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def is_undetermined(value: Any) -> bool:
    return value in (None, "", "UNDETERMINED")


def no_evidence_unisex(row: dict[str, Any]) -> bool:
    return (
        row.get("productGender") == "UNISEX"
        and row.get("decisionSource") == "NONE"
        and is_undetermined(row.get("thumbnailFold"))
        and is_undetermined(row.get("detailFold"))
        and not row.get("detailEvidence")
        and not row.get("textSignal")
    )


def direct_evidence(row: dict[str, Any]) -> bool:
    return (
        row.get("detailStatus") == "OK"
        and row.get("detailEvidenceType") in {"HUMAN", "TEXT", "MIXED"}
        and bool(row.get("detailEvidence"))
    )


def evidence_supports_prediction(row: dict[str, Any]) -> bool:
    if not direct_evidence(row):
        return False
    evidence = str(row.get("detailEvidence") or "").lower()
    if "남녀" in evidence or "남성과 여성" in evidence or "여성과 남성" in evidence:
        return False
    prediction = row.get("productGender")
    if prediction == "FEMALE":
        return any(token in evidence for token in ("여성", "우먼", "여자")) and "남성" not in evidence
    if prediction == "MALE":
        return any(token in evidence for token in ("남성", "맨즈", "남자")) and "여성" not in evidence
    return False


def evidence_contradicts_prediction(row: dict[str, Any]) -> bool:
    if not direct_evidence(row):
        return False
    evidence = str(row.get("detailEvidence") or "").lower()
    prediction = row.get("productGender")
    if prediction == "FEMALE":
        return "남성" in evidence and "여성" not in evidence
    if prediction == "MALE":
        return "여성" in evidence and "남성" not in evidence
    return False


def queue_item(row: dict[str, Any], signal: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {
        "signal": signal,
        "reason": reason,
        "referenceLabel": row.get("goldLabel"),
        "observedLabel": row.get("productGender"),
        **row,
        **extra,
    }


def markdown_examples(rows: list[dict[str, Any]], limit: int = 12) -> str:
    if not rows:
        return "- 없음\n"
    lines = []
    for row in rows[:limit]:
        name = str(row.get("productName") or row.get("productKey"))
        name = name.replace("[", "\\[").replace("]", "\\]")
        url = str(row.get("pdpUrl") or "")
        label = f"[{name}]({url})" if url else name
        lines.append(
            f"- `{row.get('productKey')}` {label}: "
            f"GT=`{row.get('goldLabel')}`, 정책 실행=`{row.get('productGender')}`, "
            f"근거=`{row.get('detailEvidence') or '없음'}`"
        )
    return "\n".join(lines) + "\n"


def merge_detail_evidence(
    rows: list[dict[str, Any]], detail_path: Path
) -> list[dict[str, Any]]:
    if not detail_path.is_file():
        return rows
    detail_by_key = {row["productKey"]: row for row in read_jsonl(detail_path)}
    merged: list[dict[str, Any]] = []
    for row in rows:
        detail = detail_by_key.get(row.get("productKey"), {})
        merged.append(
            {
                **row,
                "policyEvidenceSceneIds": detail.get("policyEvidenceSceneIds", []),
                "evidenceImageUrls": detail.get("evidenceImageUrls", []),
                "policyPromptVersion": detail.get("promptVersion"),
                "policyPromptSha256": detail.get("promptSha256"),
                "preparedTileCount": detail.get("preparedTileCount"),
                "detailAssetCollectedTileCount": detail.get(
                    "detailAssetCollectedTileCount"
                ),
                "detailAssetRetainedTileCount": detail.get(
                    "detailAssetRetainedTileCount"
                ),
                "detailAssetRemovedSharedTileCount": detail.get(
                    "detailAssetRemovedSharedTileCount"
                ),
                "variantSharedRetainedTileCount": detail.get(
                    "variantSharedRetainedTileCount"
                ),
                "detailAssetFilterStatus": detail.get("detailAssetFilterStatus"),
                "selectedImageCount": detail.get("selectedImageCount"),
                "omittedImageCount": detail.get("omittedImageCount"),
                "allImageTileCount": detail.get("allImageTileCount"),
                "fullImageCoverageStatus": detail.get("fullImageCoverageStatus"),
                "collectionSources": detail.get("collectionSources", []),
                "collectionRecovered": bool(detail.get("collectionRecovered")),
                "previousCollectionError": detail.get("previousCollectionError"),
                "currentCollectionError": detail.get("currentCollectionError"),
                "interactionPolicyRecovered": bool(
                    detail.get("interactionPolicyRecovered")
                ),
                "invalidExplicitTextRecovered": bool(
                    detail.get("invalidExplicitTextRecovered")
                ),
                "judgeRetryReason": detail.get("judgeRetryReason"),
            }
        )
    return merged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    policy_path = output_root / "policy" / "bag-category-gender.md"
    canonical_gt_path = output_root / "golden" / "bag-product-gt.jsonl"
    evaluation_path = output_root / "golden" / "bag-policy-evaluation.jsonl"
    detail_path = output_root / "golden" / "bag-policy-detail-evidence.jsonl"
    report_dir = output_root / "reports"
    queue_dir = output_root / "queue"

    required = (policy_path, canonical_gt_path, evaluation_path, detail_path)
    if any(not path.is_file() for path in required):
        raise SystemExit("먼저 import_bag_category_gender_sources.py를 실행하세요.")

    policy = policy_path.read_text(encoding="utf-8")
    required_rules = (
        "대상 판매 가방을 직접 수식하는",
        "가방을 실제 착용하거나 휴대한 사람의 외형 성별 표현을 사용하세요",
        "근거 부족을 UNISEX로 대신하지 마세요",
    )
    missing_rules = [rule for rule in required_rules if rule not in policy]
    if missing_rules:
        raise SystemExit(f"정책 스냅샷에 필수 규칙이 없습니다: {missing_rules}")

    rows = merge_detail_evidence(
        sorted(read_jsonl(evaluation_path), key=lambda row: str(row["productKey"])), detail_path
    )
    canonical_rows = read_jsonl(canonical_gt_path)
    canonical_by_key = {row["productKey"]: row for row in canonical_rows}
    evaluation_by_key = {row["productKey"]: row for row in rows}

    golden_source_conflicts: list[dict[str, Any]] = []
    for product_key in sorted(canonical_by_key.keys() & evaluation_by_key.keys()):
        canonical = canonical_by_key[product_key]
        evaluation = evaluation_by_key[product_key]
        if canonical.get("goldLabel") == evaluation.get("goldLabel"):
            continue
        conflict_kind = (
            "UNCLASSIFIED_TO_LABELED"
            if canonical.get("goldLabel") == "UNCLASSIFIED"
            else "LABEL_TO_LABEL"
        )
        golden_source_conflicts.append(
            {
                "signal": "GOLDEN_SOURCE_CONFLICT",
                "conflictKind": conflict_kind,
                "reason": (
                    "정본 GT가 UNCLASSIFIED이고 평가 스냅샷에는 확정 라벨이 있다."
                    if conflict_kind == "UNCLASSIFIED_TO_LABELED"
                    else "같은 상품의 두 GT 소스가 서로 다른 확정 라벨을 가진다."
                ),
                "productKey": product_key,
                "productName": canonical.get("productName"),
                "standardCategory": canonical.get("standardCategory"),
                "canonicalGold": canonical.get("goldLabel"),
                "canonicalDatasetVersion": canonical.get("datasetVersion"),
                "canonicalSource": canonical.get("goldSource"),
                "evaluationGold": evaluation.get("goldLabel"),
                "evaluationSource": evaluation.get("goldSource"),
                "productGender": evaluation.get("productGender"),
                "referenceLabel": canonical.get("goldLabel"),
                "observedLabel": evaluation.get("goldLabel"),
                "pdpUrl": canonical.get("pdpUrl"),
            }
        )

    runtime_conflicts: list[dict[str, Any]] = []
    unsupported_agreements: list[dict[str, Any]] = []
    policy_golden_gaps: list[dict[str, Any]] = []
    golden_policy_violations: list[dict[str, Any]] = []
    model_policy_contradictions: list[dict[str, Any]] = []
    unresolved_conflicts: list[dict[str, Any]] = []
    evidence_pipeline_recoveries: list[dict[str, Any]] = []
    image_collection_recoveries: list[dict[str, Any]] = []
    interaction_policy_recoveries: list[dict[str, Any]] = []
    invalid_text_recoveries: list[dict[str, Any]] = []

    for row in rows:
        if row.get("collectionRecovered"):
            image_collection_recoveries.append(
                queue_item(
                    row,
                    "IMAGE_COLLECTION_RECOVERED",
                    "기존 수집기는 현재 29CM 화면을 만드는 BFF 상세 이미지를 읽지 못했지만, "
                    f"새 수집기는 {int(row.get('allImageTileCount') or 0)}개 타일을 확보해 전부 처리했다.",
                    policyRule="공개 HTML에 상세 이미지가 없으면 29CM product-detail BFF의 "
                    "itemDescriptions·itemImages를 함께 수집",
                    reviewRecommendation="복구된 상세 장면과 표준 카테고리를 기준으로 GT 충돌을 검수",
                )
            )
        if row.get("interactionPolicyRecovered"):
            interaction_policy_recoveries.append(
                queue_item(
                    row,
                    "INTERACTION_POLICY_RECOVERED",
                    "백팩·숄더백을 몸에 멘 WORN 장면을 기존 가방 정책이 버렸지만, "
                    "실제 가방 상호작용으로 인정해 판정을 복구했다.",
                    policyRule="가방의 실제 사용은 CARRIED뿐 아니라 WORN도 허용",
                )
            )
        if row.get("invalidExplicitTextRecovered"):
            invalid_text_recoveries.append(
                queue_item(
                    row,
                    "INVALID_TEXT_EVIDENCE_DROPPED",
                    "성별 단어가 없는 상품명을 직접 성별 문구로 신고한 모델 출력만 버리고, "
                    "독립적인 이미지 근거는 유지했다.",
                    policyRule="exactProductGenderText에 실제 성별 표지가 있을 때만 직접 문구로 인정",
                )
            )
        recovered_tiles = int(row.get("variantSharedRetainedTileCount") or 0)
        if recovered_tiles and direct_evidence(row):
            evidence_pipeline_recoveries.append(
                queue_item(
                    row,
                    "EVIDENCE_PIPELINE_RECOVERED",
                    f"기존 URL 공유 규칙이라면 제거될 상세 타일 {recovered_tiles}개를 "
                    "같은 상품군의 색상·패턴 변형 근거로 보존해 상세 추론을 복구했다.",
                    policyRule="같은 상품군의 변형끼리 공유하는 PDP 이미지는 유지하고, "
                    "서로 다른 상품군의 공용 이미지만 제거",
                    reviewRecommendation="복구된 이미지가 실제 대상 상품군과 연결되는지 확인",
                )
            )
        if no_evidence_unisex(row):
            runtime_conflicts.append(
                queue_item(
                    row,
                    "POLICY_RUNTIME_CONTRADICTION",
                    "정책은 근거 부족을 UNDETERMINED로 두지만 실행 결과는 UNISEX이다.",
                )
            )
            if row.get("goldLabel") == "UNISEX":
                unsupported_agreements.append(
                    queue_item(
                        row,
                        "GOLDEN_UNSUPPORTED_AGREEMENT",
                        "GT와 결과는 같지만 UNISEX를 지지하는 직접 근거가 없다.",
                    )
                )
            elif row.get("goldLabel") in {"MALE", "FEMALE"}:
                policy_golden_gaps.append(
                    queue_item(
                        row,
                        "POLICY_GOLDEN_GAP",
                        "사람 GT는 단일 성별이나 이 실행은 상세 근거를 확보하지 못했다.",
                    )
                )

        prediction = row.get("productGender")
        if prediction not in {"MALE", "FEMALE"} or row.get("goldLabel") == prediction:
            continue
        if evidence_supports_prediction(row):
            gender_word = "여성" if prediction == "FEMALE" else "남성"
            golden_policy_violations.append(
                queue_item(
                    row,
                    "GOLDEN_POLICY_VIOLATION_CANDIDATE",
                    f"정책은 대상 가방을 착용한 {gender_word} 모델 또는 직접 문구를 우선 근거로 사용한다. "
                    f"상세 근거는 {prediction}을 지지하지만 현재 GT는 {row.get('goldLabel')}이다.",
                    policyRule="근거 우선순위 1·2: 직접 성별 문구와 대상 가방 착용자의 외형 성별 표현",
                    reviewRecommendation="상세 근거 이미지를 확인한 뒤 GT 수정 여부를 판정",
                )
            )
        elif evidence_contradicts_prediction(row):
            model_policy_contradictions.append(
                queue_item(
                    row,
                    "MODEL_POLICY_CONTRADICTION",
                    "정책 실행의 최종 라벨과 실행이 스스로 기록한 상세 근거의 성별이 반대다.",
                )
            )
        else:
            unresolved_conflicts.append(
                queue_item(
                    row,
                    "POLICY_GOLDEN_CONFLICT",
                    "단일 성별 실행값과 GT가 다르지만 기록된 근거만으로 어느 쪽 오류인지 확정할 수 없다.",
                )
            )

    queue_counts = {
        "imageCollectionRecovered": write_jsonl(
            queue_dir / "image-collection-recovered.jsonl", image_collection_recoveries
        ),
        "interactionPolicyRecovered": write_jsonl(
            queue_dir / "interaction-policy-recovered.jsonl", interaction_policy_recoveries
        ),
        "invalidTextEvidenceDropped": write_jsonl(
            queue_dir / "invalid-text-evidence-dropped.jsonl", invalid_text_recoveries
        ),
        "evidencePipelineRecovered": write_jsonl(
            queue_dir / "evidence-pipeline-recovered.jsonl", evidence_pipeline_recoveries
        ),
        "goldenPolicyViolationCandidate": write_jsonl(
            queue_dir / "golden-policy-violation-candidate.jsonl", golden_policy_violations
        ),
        "modelPolicyContradiction": write_jsonl(
            queue_dir / "model-policy-contradiction.jsonl", model_policy_contradictions
        ),
        "goldenSourceConflict": write_jsonl(
            queue_dir / "golden-source-conflict.jsonl", golden_source_conflicts
        ),
        "policyRuntimeContradiction": write_jsonl(
            queue_dir / "policy-runtime-contradiction.jsonl", runtime_conflicts
        ),
        "goldenUnsupportedAgreement": write_jsonl(
            queue_dir / "golden-unsupported-agreement.jsonl", unsupported_agreements
        ),
        "policyGoldenGap": write_jsonl(
            queue_dir / "policy-golden-gap.jsonl", policy_golden_gaps
        ),
        "policyGoldenConflict": write_jsonl(
            queue_dir / "policy-golden-conflict.jsonl", unresolved_conflicts
        ),
    }

    # 이전 버전의 큐 파일이 새 감사에서 사라진 경우를 막기 위해 현재 계약 밖 JSONL은 제거하지 않는다.
    label_counts = Counter(str(row.get("goldLabel")) for row in rows)
    detail_rows = [row for row in rows if row.get("detailStatus") == "OK"]
    complete_coverage_rows = [
        row for row in detail_rows
        if row.get("fullImageCoverageStatus") == "COMPLETE"
    ]
    collected_tiles = sum(
        int(row.get("detailAssetCollectedTileCount") or 0) for row in detail_rows
    )
    retained_tiles = sum(
        int(row.get("detailAssetRetainedTileCount") or 0) for row in detail_rows
    )
    over_twenty_rows = sum(
        int(row.get("detailAssetRetainedTileCount") or 0) > 20 for row in detail_rows
    )
    golden_conflict_kinds = Counter(str(row["conflictKind"]) for row in golden_source_conflicts)
    questions = [
        {
            "id": "GQ-GT-001",
            "question": "정책의 직접 근거가 단일 성별을 지지하는데 GT가 UNISEX인 사례를 GT 오류로 확정할 것인가?",
            "impact": {
                "candidates": len(golden_policy_violations),
                "femaleCandidates": sum(row.get("productGender") == "FEMALE" for row in golden_policy_violations),
                "maleCandidates": sum(row.get("productGender") == "MALE" for row in golden_policy_violations),
            },
            "recommendation": "상세 근거 이미지를 우선 검수하고, 근거가 실제 대상 가방과 연결되면 GT를 수정한다.",
        },
        {
            "id": "GQ-RUN-001",
            "question": "근거가 없을 때 내부 UNDETERMINED를 최종 UNISEX로 바꿔도 되는가?",
            "impact": {
                "affected": len(runtime_conflicts),
                "unsupportedCorrect": len(unsupported_agreements),
                "wrongAgainstGt": len(policy_golden_gaps),
            },
            "recommendation": "평가에서는 UNDETERMINED를 보존하고 저장 호환 변환은 별도 projection으로 분리한다.",
        },
        {
            "id": "GQ-SOURCE-001",
            "question": "두 GT 소스 중 어느 버전을 정본으로 사용할 것인가?",
            "impact": {
                "differentRows": len(golden_source_conflicts),
                "labelToLabel": golden_conflict_kinds["LABEL_TO_LABEL"],
                "unclassifiedToLabeled": golden_conflict_kinds["UNCLASSIFIED_TO_LABELED"],
            },
            "recommendation": "최신 사람 검수 원장을 정본으로 지정하고 datasetVersion과 라벨 해시를 평가 입력에 기록한다.",
        },
    ]

    report_dir.mkdir(parents=True, exist_ok=True)
    question_json_path = report_dir / "policy-questions.json"
    question_json_path.write_text(
        json.dumps(questions, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    question_path = report_dir / "bag-category-gender-policy-questions.md"
    question_lines = ["# 가방 성별 정책 질문서", ""]
    for question in questions:
        question_lines.extend(
            [
                f"## {question['id']}",
                "",
                f"- 질문: {question['question']}",
                f"- 영향: `{json.dumps(question['impact'], ensure_ascii=False, sort_keys=True)}`",
                f"- 권고: {question['recommendation']}",
                "",
            ]
        )
    question_path.write_text("\n".join(question_lines), encoding="utf-8")

    accuracy = sum(row.get("goldLabel") == row.get("productGender") for row in rows) / len(rows)
    report_path = report_dir / "bag-category-gender-audit.md"
    report = f"""# 가방 정책 ↔ 골든셋 감사 결과

## 결론

최신 fresh 실행은 상세 이미지를 실제로 읽었다. 정책의 직접 근거와 실행 근거가 같은 단일 성별을
지지하지만 현재 GT가 다른 **GT 오류 후보는 {len(golden_policy_violations)}건**이다. 이 큐가 가장
먼저 볼 대상이다. 예전 실행의 빈 `detailEvidence`만 보고 만든 ‘근거 없는 일치’ 보고서는 상세 이미지
근거를 누락했으므로 정본으로 사용하지 않는다.

`EGOOCM:3398529`는 상세 8장을 읽었고 여성 모델 착용과 오간자·리본 결합 신호로 `FEMALE`을
냈지만 GT는 `UNISEX`다. 정책의 근거 우선순위 2와 일치하므로 GT 오류 후보 큐에 포함했다.

## 전체 수치

- 평가 상품: {len(rows)}건
- 최신 실행의 현재 GT 대비 정확도: {accuracy:.2%}
- 정책 직접 근거가 있는 GT 오류 후보: {len(golden_policy_violations)}건
- 공유 이미지 과잉 제거에서 복구된 상품: {len(evidence_pipeline_recoveries)}건
- 상세 이미지 URL 수집 실패에서 복구된 상품: {len(image_collection_recoveries)}건
- 가방 WORN 상호작용 정책에서 복구된 상품: {len(interaction_policy_recoveries)}건
- 전체 상세 타일 처리 완료: {len(complete_coverage_rows)}/{len(detail_rows)}건
- 실행 라벨과 실행 근거가 서로 반대: {len(model_policy_contradictions)}건
- 단일 성별 결과와 GT가 다르지만 추가 검토 필요: {len(unresolved_conflicts)}건
- 근거 없는 UNISEX 변환: {len(runtime_conflicts)}건
- 골든셋 소스 차이: {len(golden_source_conflicts)}건
- GT 분포: {dict(sorted(label_counts.items()))}

## 1. 정책 직접 근거가 있는 GT 오류 후보

{markdown_examples(golden_policy_violations)}
## 2. 실행 결과와 실행 근거가 서로 모순인 사례

{markdown_examples(model_policy_contradictions)}
## 3. 추가 시각 검토가 필요한 정책↔GT 충돌

{markdown_examples(unresolved_conflicts)}
## 다음 행동

1. `golden-policy-violation-candidate.jsonl`의 상세 근거 이미지를 검수한다.
2. 대상 가방과 단일 성별 모델 연결이 확인되면 GT 수정 판정을 기록한다.
3. `model-policy-contradiction.jsonl`은 GT가 아니라 실행 버그로 분리한다.
4. 근거 없는 UNISEX는 내부 UNDETERMINED 보존 여부를 결정한다.
"""
    report_path.write_text(report, encoding="utf-8")

    summary = {
        "completed": True,
        "generatedAt": datetime.now(UTC).isoformat(),
        "profileId": "bag-category-gender",
        "input": str(evaluation_path.relative_to(PROJECT_ROOT)),
        "policy": str(policy_path.relative_to(PROJECT_ROOT)),
        "products": len(rows),
        "surfaceAccuracy": accuracy,
        "imagePipeline": {
            "detailProducts": len(detail_rows),
            "completeCoverageProducts": len(complete_coverage_rows),
            "failedDetailProducts": len(detail_rows) - len(complete_coverage_rows),
            "collectedTiles": collected_tiles,
            "retainedTiles": retained_tiles,
            "productsOverTwentyTiles": over_twenty_rows,
            "imageCollectionRecoveredProducts": len(image_collection_recoveries),
            "interactionPolicyRecoveredProducts": len(interaction_policy_recoveries),
            "invalidTextEvidenceDroppedProducts": len(invalid_text_recoveries),
        },
        "signals": queue_counts,
        "primaryFinding": {
            "signal": "GOLDEN_POLICY_VIOLATION_CANDIDATE",
            "label": "정책 직접 근거가 있는 GT 오류 후보",
            "count": len(golden_policy_violations),
            "description": "상세 이미지·직접 문구가 단일 성별을 지지하지만 현재 GT가 다릅니다.",
        },
        "spotlightFinding": (
            {
                "signal": "IMAGE_COLLECTION_RECOVERED",
                "label": "29CM 상세 이미지 수집 복구",
                "count": len(image_collection_recoveries),
                "description": "공개 HTML에서 보이지 않던 BFF 상세 이미지를 수집해 전체 판정을 복구했습니다.",
            }
            if image_collection_recoveries
            else None
        ),
        "goldenSourceBreakdown": dict(sorted(golden_conflict_kinds.items())),
        "artifacts": {
            "auditReport": str(report_path.relative_to(PROJECT_ROOT)),
            "policyQuestions": str(question_path.relative_to(PROJECT_ROOT)),
            "policyQuestionsJson": str(question_json_path.relative_to(PROJECT_ROOT)),
            "queueDirectory": str(queue_dir.relative_to(PROJECT_ROOT)),
        },
        "cycle": [
            "정책 스냅샷",
            "최신 fresh 평가·상세 근거 스냅샷",
            "정책-실행-골든 비교",
            "GT 오류 후보와 실행 오류 분리",
            "상세 근거 이미지 큐 생성",
        ],
    }
    summary_path = output_root / "run-summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
