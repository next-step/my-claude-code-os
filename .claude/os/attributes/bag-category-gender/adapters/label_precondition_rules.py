#!/usr/bin/env python3
"""정책의 «이 계열에는 이 라벨을 붙일 수 없다» 규칙을 읽고 적용하는 한 곳.

감사와 심판이 **같은 함수**를 쓴다. 각자 낱말을 적어 두면 조용히 갈라지고, 갈라지면
큐가 지목한 건을 심판이 「충돌 없음」으로 덮는다 — 실제로 그렇게 넷이 덮였다.

술어 파일이 정책을 이기지 않는다. 다투면 `policy/policy.md`가 정본이다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RULES_PATH = (
    Path(__file__).resolve().parent.parent / "policy" / "label-preconditions.json"
)


def load() -> dict[str, Any]:
    if not RULES_PATH.is_file():
        raise SystemExit(f"정책 술어 파일이 없습니다: {RULES_PATH}")
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def category_value(row: dict[str, Any], rule: dict[str, Any]) -> str:
    """이 규칙이 볼 분류 값. 기본은 **마지막 마디**다.

    경로 전체로 맞추면 부모 마디에 걸린다 — `가방>숄더백/쇼퍼백>쇼퍼백`이 부모의 «숄더»
    때문에 지목된 적이 있다. 정책이 말한 것은 **그 상품이 무엇인가**이지 어느 묶음에
    속하는가가 아니다.
    """
    raw = str(row.get(str(rule.get("matchField") or "")) or "")
    if not raw:
        return ""
    if str(rule.get("matchOn") or "leaf") == "leaf":
        return raw.split(">")[-1].strip()
    return raw


def match_tokens(entries: Any, value: str) -> str | None:
    """맞은 **정책 낱말**을 돌려준다. 맞은 분류 낱말이 아니라 정책 낱말이다 —
    지적을 읽는 사람이 정책의 어느 문장에 걸렸는지 바로 알아야 한다."""
    for entry in entries or []:
        for token in entry.get("categoryTokens") or []:
            if token and token in value:
                return str(entry.get("policyWord") or token)
    return None


def near_miss(row: dict[str, Any], rule: dict[str, Any]) -> dict[str, str] | None:
    """정책 낱말이 **마지막 마디 밖**에 있는가.

    `가방>숄더백/쇼퍼백>쇼퍼백`은 정책이 이름을 대지 않은 자리라 공백이 맞다. 그런데
    부모 마디에 「숄더」가 있고 상품명이 `DOT TOTE BAG`이다. 이런 건은 정책 한 줄이면
    갈리는 자리이므로, 공백 72건을 뭉뚱그리지 않고 **먼저 물을 것**으로 표시해 둔다.
    """
    leaf = category_value(row, rule)
    raw = str(row.get(str(rule.get("matchField") or "")) or "")
    parent = raw[: len(raw) - len(leaf)] if leaf and raw.endswith(leaf) else raw
    name = str(row.get("productName") or "")
    for side in ("allow", "deny"):
        for entry in rule.get(side) or []:
            for token in entry.get("categoryTokens") or []:
                if not token:
                    continue
                where = "분류의 상위 마디" if token in parent else ("상품명" if token in name else "")
                if where:
                    return {
                        "policyWord": str(entry.get("policyWord") or token),
                        "side": side,
                        "where": where,
                    }
    return None


def verdict(label: Any, row: dict[str, Any], rules_by_label: dict[str, Any]) -> str:
    rule = rules_by_label.get(str(label or ""))
    if not rule:
        return "PASS"
    value = category_value(row, rule)
    if not value:
        return "PASS"
    if match_tokens(rule.get("allow"), value):
        return "PASS"
    if match_tokens(rule.get("deny"), value):
        return "DENY"
    return "SILENT"
