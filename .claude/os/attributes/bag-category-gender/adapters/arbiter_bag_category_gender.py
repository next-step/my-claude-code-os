#!/usr/bin/env python3
"""가방 성별 정책을 큐 행에 기계적으로 적용하는 심판 술어.

공통 심판(arbitrate.py)은 라벨 비교만 한다. 이 파일만 가방을 안다.
`.claude/os/attributes/bag-category-gender/policy/policy.md`의 근거 우선순위를 그대로 옮긴 것이고,
새 판단을 넣지 않는다. 정책이 바뀌면 여기도 같이 바뀌어야 한다.
"""

from __future__ import annotations

from typing import Any


STRONG = "STRONG"
WEAK = "WEAK"
UNDETERMINED = "UNDETERMINED"
UNRESOLVABLE = "UNRESOLVABLE"

# 정책 1순위. 순서가 중요하다. "남녀공용"이 "공용"보다, 여성 토큰이 남성 토큰보다 먼저다.
DIRECT_TEXT: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("UNISEX", ("남녀공용", "유니섹스", "unisex", "남녀 공용", "공용")),
    ("FEMALE", ("여성용", "우먼즈", "우먼스", "women's", "womens", "for women", "여성 전용")),
    ("MALE", ("남성용", "맨즈", "men's", "mens", "for men", "남성 전용")),
)

FEMALE_EVIDENCE = ("여성", "우먼", "여자")
MALE_EVIDENCE = ("남성", "맨즈", "남자")
MIXED_EVIDENCE = ("남녀", "남성과 여성", "여성과 남성")


def _direct_text_label(product_name: str) -> tuple[str, str] | None:
    """정책 1순위: 대상 판매 가방을 직접 수식하는 성별 문구."""
    name = (product_name or "").lower()
    for label, tokens in DIRECT_TEXT:
        for token in tokens:
            if token.lower() in name:
                return label, token
    return None


def _evidence_label(evidence: str) -> str | None:
    """실행이 기록한 근거 문장이 가리키는 단일 성별."""
    text = (evidence or "").lower()
    if any(token in text for token in MIXED_EVIDENCE):
        return None
    has_female = any(token in text for token in FEMALE_EVIDENCE)
    has_male = any(token in text for token in MALE_EVIDENCE)
    if has_female and not has_male:
        return "FEMALE"
    if has_male and not has_female:
        return "MALE"
    return None


def _no_evidence(row: dict[str, Any]) -> bool:
    """정책 판정 불가 조건: 근거가 아예 없다."""
    return (
        row.get("decisionSource") == "NONE"
        and row.get("thumbnailFold") in (None, "", UNDETERMINED)
        and row.get("detailFold") in (None, "", UNDETERMINED)
        and not row.get("detailEvidence")
        and not row.get("textSignal")
    )


def policy_answer(row: dict[str, Any]) -> dict[str, Any]:
    """정책만 보고 이 상품의 답을 낸다. 골든셋과 실행 결과는 보지 않는다."""
    direct = _direct_text_label(str(row.get("productName") or ""))
    if direct:
        label, token = direct
        return {
            "label": label,
            "strength": STRONG,
            "rule": "P1_DIRECT_TEXT",
            "note": f"상품명에 직접 성별 문구 '{token}'이 있다. 1순위 근거는 이미지보다 우선한다.",
            "blockedBy": [],
        }

    if _no_evidence(row):
        return {
            "label": UNDETERMINED,
            "strength": STRONG,
            "rule": "P0_NO_EVIDENCE",
            "note": "근거가 없다. 정책은 근거 부족을 UNISEX로 대신하지 않는다.",
            "blockedBy": ["BG-0002"],
        }

    evidence_type = row.get("detailEvidenceType")
    if row.get("detailStatus") == "OK" and evidence_type in {"HUMAN", "TEXT", "MIXED"}:
        label = _evidence_label(str(row.get("detailEvidence") or ""))
        if label:
            if evidence_type == "TEXT":
                return {
                    "label": label,
                    "strength": STRONG,
                    "rule": "P1_DIRECT_TEXT",
                    "note": "실행이 직접 성별 문구를 1순위 근거로 기록했다.",
                    "blockedBy": [],
                }
            return {
                "label": label,
                "strength": WEAK,
                "rule": "P3_WEARER",
                "note": "3순위 착용자 근거뿐이다. BG-0001은 이 근거를 약한 것으로 본다.",
                "blockedBy": ["BG-0001"],
            }

    if evidence_type == "PRODUCT_ONLY":
        return {
            "label": UNRESOLVABLE,
            "strength": WEAK,
            "rule": "P2_COMBINED_DESIGN",
            "note": "2순위 결합 디자인은 두 묶음 이상이 겹치는지 이미지로 봐야 한다. 문자로 판정할 수 없다.",
            "blockedBy": [],
        }

    return {
        "label": UNRESOLVABLE,
        "strength": WEAK,
        "rule": "NO_APPLICABLE_RULE",
        "note": "이 스냅샷의 필드만으로는 정책의 어느 순위도 적용할 수 없다.",
        "blockedBy": [],
    }


# 큐 신호가 미결 판례에 걸려 있으면 심판이 그 사실을 함께 올린다.
SIGNAL_PRECEDENTS: dict[str, str] = {
    "GOLDEN_SOURCE_CONFLICT": "BG-0003",
    "GOLDEN_POLICY_VIOLATION_CANDIDATE": "BG-0001",
    "POLICY_RUNTIME_CONTRADICTION": "BG-0002",
    "GOLDEN_UNSUPPORTED_AGREEMENT": "BG-0002",
}
