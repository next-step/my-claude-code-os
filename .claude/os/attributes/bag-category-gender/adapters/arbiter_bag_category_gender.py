#!/usr/bin/env python3
"""가방 성별 정책을 큐 행에 기계적으로 적용하는 심판 술어.

공통 심판(arbitrate.py)은 라벨 비교만 한다. 이 파일만 가방을 안다.
`.claude/os/attributes/bag-category-gender/policy/policy.md`의 근거 우선순위를 그대로 옮긴 것이고,
새 판단을 넣지 않는다. 정책이 바뀌면 여기도 같이 바뀌어야 한다.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("프로젝트 루트(.claude를 가진 폴더)를 찾지 못했습니다.")


PROJECT_ROOT = _find_project_root()


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
MIXED_EVIDENCE = ("남녀", "남성과 여성", "여성과 남성", "남성·여성", "여성·남성")


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


def _mixed_wearer(evidence: str) -> bool:
    """정책 3순위: 남성과 여성이 같은 가방을 모두 착용했다.

    한쪽만 보이는 것은 촬영 컷 선택으로도 설명되지만 둘 다 보이는 것은 그렇지 않다.
    그래서 이 관측은 UNISEX의 적극적 근거이고, 단일 성별 착용자보다 강하다.
    """
    text = (evidence or "").lower()
    if any(token in text for token in MIXED_EVIDENCE):
        return True
    has_female = any(token in text for token in FEMALE_EVIDENCE)
    has_male = any(token in text for token in MALE_EVIDENCE)
    return has_female and has_male


def _no_evidence(row: dict[str, Any]) -> bool:
    """정책 판정 불가 조건: 근거가 아예 없다."""
    return (
        row.get("decisionSource") == "NONE"
        and row.get("thumbnailFold") in (None, "", UNDETERMINED)
        and row.get("detailFold") in (None, "", UNDETERMINED)
        and not row.get("detailEvidence")
        and not row.get("textSignal")
    )


sys.path.insert(0, str(Path(__file__).resolve().parent))
from label_precondition_rules import load as load_preconditions, verdict  # noqa: E402

# 감사와 **같은 함수**를 쓴다. 각자 적으면 갈라지고, 갈라지면 지적이 덮인다.
_PRECONDITIONS = load_preconditions()
_RULES_BY_LABEL = {str(rule.get("label")): rule for rule in _PRECONDITIONS.get("rules") or []}


def _category_denies(label: str, row: dict[str, Any]) -> bool:
    return verdict(label, row, _RULES_BY_LABEL) == "DENY"


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
            "blockedBy": [],
        }

    evidence_type = row.get("detailEvidenceType")
    if row.get("detailStatus") == "OK" and evidence_type in {"HUMAN", "TEXT", "MIXED"}:
        evidence_text = str(row.get("detailEvidence") or "")
        if _mixed_wearer(evidence_text):
            # 「남녀가 모두 착용」은 문자로 확인할 수 없는 주장이다. 한 문장이 두 가지를
            # 함께 주장하기 때문이다 — **두 성별이 관측됐다**는 것과 **그들이 대상과 같은
            # 가방을 들었다**는 것. 정규식은 어느 쪽도 보지 못하고 낱말만 본다.
            #
            # 2순위 결합 디자인을 «문자로 판정할 수 없다»로 둔 것과 같은 이유이고,
            # 여기서는 근거가 더 있다 — 이 주장으로 사람 GT를 뒤집자고 한 건을 사진으로
            # 되짚었더니 **6건 전부 무너졌다**(다른 컬러웨이, 가방 없는 배너, 반대로 읽힌 성별).
            # 그래서 STRONG을 주지 않는다. 지우지도 않는다 — 사진으로 보면 설 수도 있다.
            return {
                "label": UNRESOLVABLE,
                "strength": WEAK,
                "rule": "P3_MIXED_WEARER",
                "note": (
                    "실행이 「남녀가 모두 착용」이라 적었다. 그 문장은 두 성별 관측과 "
                    "대상 동일성을 함께 주장하는데 문자로는 어느 쪽도 확인할 수 없다. "
                    "이미지로 되짚어야 한다."
                ),
                "blockedBy": [],
            }
        label = _evidence_label(evidence_text)
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
                "note": "3순위 착용자 근거뿐이다. 이 근거만으로 골든셋을 뒤집을지는 판례가 답한다.",
                "blockedBy": [],
            }

    if evidence_type == "PRODUCT_ONLY":
        return {
            "label": UNRESOLVABLE,
            "strength": WEAK,
            "rule": "P2_COMBINED_DESIGN",
            "note": "2순위 결합 디자인은 두 묶음 이상이 겹치는지 이미지로 봐야 한다. 문자로 판정할 수 없다.",
            "blockedBy": [],
        }

    # 순위를 다 밟고도 답이 없을 때, 정책이 **아무 말도 안 한 것은 아니다.**
    # 「일반 토트·숄더·크로스백은 남녀 모두 쓸 수 있다는 상식만으로 UNISEX가 아니다」는
    # 이 자리에 대한 정책의 답이다. 이걸 빼 두면 GT와 실행이 나란히 UNISEX일 때
    # 심판이 «충돌 없음»을 내고, 둘이 함께 정책을 어긴 사실이 조용히 지나간다.
    if _category_denies("UNISEX", row):
        return {
            "label": UNDETERMINED,
            "strength": STRONG,
            "rule": "P0_CATEGORY_NOT_UNISEX",
            "note": (
                "정책이 이 계열을 «상식만으로 UNISEX가 아니다»로 명시했고, "
                "공용이라는 적극적 근거가 이 스냅샷에 없다."
            ),
            "blockedBy": [],
        }

    return {
        "label": UNRESOLVABLE,
        "strength": WEAK,
        "rule": "NO_APPLICABLE_RULE",
        "note": "이 스냅샷의 필드만으로는 정책의 어느 순위도 적용할 수 없다.",
        "blockedBy": [],
    }


# 큐 신호가 미결 판례에 걸려 있으면 심판이 그 사실을 함께 올린다. **여기는 비어 있다.**
#
# 전에는 이 표에 판례 ID가 적혀 있었다. 그러면 판례를 새로 써도 심판은 모르고, 판례를
# 닫아도 코드를 고쳐야 했다 — 판례가 자산이 아니라 코드의 상수였다. 지금은 판례 파일이
# `rule:`과 `signals:`로 스스로 걸리고, 엔진이 그 선언을 읽어 막는다.
#
# 이 자리를 지우지 않고 비워 두는 이유는, 어댑터가 **속성만 아는 이음**을 넣을 수 있어야
# 하기 때문이다. 정책 문장으로 표현되지 않는 이음이 생기면 여기 적는다.
SIGNAL_PRECEDENTS: dict[str, str] = {}
