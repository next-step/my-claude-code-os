#!/usr/bin/env python3
# 수용 기준이 "테스트로 옮겨 적을 수 있는 문장"인지 기계적으로 채점한다.
# feature-loop 오케스트레이터의 1구간(기획) 관문.
#
# 표준 라이브러리만 쓴다 — 기준 하나 검사하려고 의존성을 설치하게 만들지 않는다.
#
# 이 스크립트는 문장의 **형식**만 본다. 내용이 맞는지는 판정하지 않는다.
#   형식 판정 → 이 스크립트 (사람 없이 갈린다, 재현성이 있다)
#   내용 판정 → 사람의 승인 (그 기준이 정말 필요한 기준인가)
# 둘을 섞으면 채점기가 자연어 판정으로 미끄러진다. OS.md 4절 규칙 7.
#
# "형식만 본다"는 것은 한계다. 통과한 기준이 좋은 기준이라는 보장은 없다.
# 다만 떨어진 기준은 확실히 테스트로 옮길 수 없다. 관문의 값은 그쪽에 있다.
#
# 입력 : 수용 기준이 목록(- 또는 1.)으로 적힌 파일, 또는 - 로 stdin
# 출력 : 기준별 PASS/FAIL + 기록 한 줄. --json 으로 기계용 출력.
# 종료 : 0 전부 통과 / 1 하나라도 실패 / 2 읽을 수 없음·기준을 찾지 못함

import argparse
import json
import re
import sys

MIN_LEN, MAX_LEN = 10, 200

# 판정을 사람에게 되돌리는 말들. 이 단어가 있으면 테스트로 옮길 수 없다.
VAGUE = [
    "적절히", "적절한", "적당히", "적당한", "알맞게", "알맞은",
    "잘 ", "좋게", "좋은", "나쁘지", "빠르게", "빨리", "신속",
    "쉽게", "쉬운", "간단히", "간편", "편하게", "편리",
    "효율적", "최적화", "최적의", "개선하", "향상",
    "사용자 친화", "직관적", "자연스럽", "부드럽", "매끄럽",
    "안정적", "유연하", "확장 가능",
    "필요시", "필요하면", "가능하면", "되도록", "대체로", "어느 정도",
    "충분히", "많이", "적게", "다양한", "여러 가지", "등등", "기타",
]

# 검증 가능한 기대값의 신호. 숫자거나 아래 중 하나는 있어야 한다.
CONCRETE = [
    "절반", "두 배", "세 배", "배로", "없다", "없음", "없어야", "있다", "있음", "있어야",
    "이상", "이하", "초과", "미만", "같다", "동일", "다르다", "포함", "제외",
    "첫", "마지막", "최대", "최소", "전부", "모든", "각", "빈 ", "참", "거짓",
    "true", "false", "null", "성공", "실패", "거절", "허용", "차단",
]

# 서술형 종결. 기준은 문장이어야 한다. 명사구는 테스트로 옮길 수 없다.
ENDINGS = ("다", "다.", "함", "함.", "된다", "된다.", "한다", "한다.", "이다", "이다.")


def dwidth(text):
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def pad(text, width):
    return text + " " * max(0, width - dwidth(text))


def clip(text, limit=54):
    out = ""
    for ch in text:
        if dwidth(out) + dwidth(ch) > limit:
            return out + "…"
        out += ch
    return out


# ------------------------------------------------------------------ 검사 항목
# 판정함수는 (통과여부, 고칠 것)을 돌려준다.
# 고칠 것 문장은 "다음에 무엇을 하라"까지 말해야 한다. OS.md 6절 요건 3.

def check_length(c):
    n = len(c)
    if n < MIN_LEN:
        return False, f"{n}자다. 조건과 기대값이 들어간 문장으로 다시 써라"
    if n > MAX_LEN:
        return False, f"{n}자다. {MAX_LEN}자를 넘으면 기준 여러 개가 섞인 것이다. 쪼개라"
    return True, ""


def check_vague(c):
    hits = [w for w in VAGUE if w in c]
    if hits:
        return False, (f"판정을 사람에게 되돌리는 말이 있다: {', '.join(hits[:3])} → "
                       "그 말이 뜻하는 값을 숫자·상태로 바꿔 적어라")
    return True, ""


def check_concrete(c):
    if re.search(r"\d", c):
        return True, ""
    if any(w in c for w in CONCRETE):
        return True, ""
    return False, ("검증 가능한 기대값이 없다. 숫자·날짜·상태(있다/없다/포함/제외/이상 등) 중 "
                   "하나로 기대값을 적어라")


def check_single(c):
    n = len(re.findall(r"(그리고|및 |또한|, 그리고)", c))
    if n >= 2:
        return False, f"접속어가 {n}번 나온다. 검증 대상이 여러 개다. 기준을 쪼개라"
    return True, ""


def check_sentence(c):
    body = c.rstrip()
    if not body.endswith(ENDINGS):
        return False, ("서술형으로 끝나지 않는다(명사구는 테스트로 옮길 수 없다). "
                       "'~한다 / ~된다 / ~이다'로 끝내라")
    return True, ""


CHECKS = [
    ("length", "길이", check_length),
    ("vague", "모호어 없음", check_vague),
    ("concrete", "검증 가능한 기대값", check_concrete),
    ("single", "검증 대상 하나", check_single),
    ("sentence", "서술형 문장", check_sentence),
]


def extract(text):
    """목록 항목만 수용 기준으로 본다. 제목·설명 줄은 무시한다."""
    out = []
    for line in text.splitlines():
        m = re.match(r"^\s*(?:[-*+]|\d+\.)\s+(.*\S)\s*$", line)
        if m:
            item = m.group(1).strip()
            # 체크박스 표기는 벗겨낸다
            item = re.sub(r"^\[[ xX]\]\s*", "", item)
            if item:
                out.append(item)
    return out


def lint(text, source):
    criteria = extract(text)
    results = []
    for c in criteria:
        checks = []
        for cid, label, fn in CHECKS:
            ok, hint = fn(c)
            checks.append({"id": cid, "label": label, "ok": ok, "hint": hint})
        results.append({
            "criterion": c,
            "checks": checks,
            "ok": all(k["ok"] for k in checks),
        })
    return {"source": source, "count": len(criteria), "results": results,
            "passed": sum(1 for r in results if r["ok"])}


def render(report):
    lines = [f"수용 기준 검사 · {report['source']}"]
    if not report["count"]:
        lines.append("  수용 기준을 찾지 못했다 — '- ' 또는 '1. ' 목록으로 적어라")
        return "\n".join(lines)

    width = max(dwidth(l) for _, l, _ in CHECKS)
    for i, r in enumerate(report["results"], 1):
        mark = "PASS" if r["ok"] else "FAIL"
        lines.append(f"  {mark}  {i}. {clip(r['criterion'])}")
        for k in r["checks"]:
            if not k["ok"]:
                lines.append(f"          {pad(k['label'], width)}  → {k['hint']}")
    verdict = "PASS" if report["passed"] == report["count"] else "FAIL"
    lines.append("")
    # 기록 한 줄 — 루프마다 추적할 수 있게. OS.md 6절 요건 4.
    lines.append(f"기록: criteria {verdict} {report['passed']}/{report['count']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description="수용 기준이 테스트로 옮겨 적을 수 있는 문장인지 채점한다.")
    ap.add_argument("path", help="수용 기준 파일 경로 (- 를 주면 stdin)")
    ap.add_argument("--json", action="store_true", help="JSON으로 출력")
    args = ap.parse_args()

    if args.path == "-":
        text, source = sys.stdin.read(), "stdin"
    else:
        try:
            with open(args.path, encoding="utf-8") as f:
                text = f.read()
            source = args.path
        except OSError as e:
            print(f"읽을 수 없다: {e}", file=sys.stderr)
            return 2

    report = lint(text, source)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render(report))

    if not report["count"]:
        return 2
    return 0 if report["passed"] == report["count"] else 1


if __name__ == "__main__":
    sys.exit(main())
