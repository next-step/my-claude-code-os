#!/usr/bin/env python3
"""컨텍스트 주입 A/B — sketch.md 를 assertion으로 기계 채점해 grading.json 생성.
모든 assertion은 grep 가능(객관). ON(주입)=컨벤션 준수 기대, OFF(대조)=일반 FastAPI 기대."""
import json, re, os, glob

WS = os.path.dirname(os.path.abspath(__file__))
IT = os.path.join(WS, "iteration-1")

def snip(text, pat, n=60):
    m = re.search(pat, text)
    if not m: return "미발견"
    s = max(0, m.start()-10); e = min(len(text), m.end()+n)
    return text[s:e].replace("\n", " ").strip()[:90]

def grade(text, eval_id):
    ex = []
    # A1: AppError 또는 팩토리 *_error()
    p = bool(re.search(r'AppError', text) or re.search(r'\w+_error\s*\(', text))
    ex.append({"text": "AppError(또는 팩토리 *_error())로 실패를 표현", "passed": p,
               "evidence": snip(text, r'AppError|\w+_error\s*\(') if p else "AppError/팩토리 미발견"})
    # A2: errorCode 바디
    p = "errorCode" in text
    ex.append({"text": "응답 바디가 errorCode+message 형식(detail 아님)", "passed": p,
               "evidence": snip(text, r'errorCode') if p else "errorCode 미발견(FastAPI 기본 detail 추정)"})
    # A3: raw HTTPException 을 raise 하지 않음
    viol = re.search(r'raise\s+HTTPException', text)
    ex.append({"text": "raw HTTPException을 실패의 1차 메커니즘으로 쓰지 않음", "passed": not viol,
               "evidence": ("raise HTTPException 사용: " + snip(text, r'raise\s+HTTPException')) if viol else "raise HTTPException 없음"})
    # A4: 레이어 2개+
    layers = [w for w in ("controller", "service", "repository") if re.search(w, text, re.I)]
    p = len(layers) >= 2
    ex.append({"text": "controller/service/repository 레이어 분리 반영", "passed": p,
               "evidence": "레이어 언급: " + (", ".join(layers) if layers else "없음")})
    # A5: 한국어
    p = bool(re.search(r'[가-힣]', text))
    ex.append({"text": "한국어 docstring/주석 존재", "passed": p,
               "evidence": snip(text, r'[가-힣][^\n]{0,30}') if p else "한글 미발견"})
    # A6: eval-2 보안 동일 처리
    if eval_id == 2:
        p = bool("INVALID_CREDENTIALS" in text or re.search(r'구분(하지 ?않|없이|하지않)|동일하게|같은 (실패|응답|메시지|에러|오류)|indistinguishable|same (error|response|message)', text, re.I))
        ex.append({"text": "보안: 아이디없음·비번불일치를 구분않고 동일 실패(INVALID_CREDENTIALS류)", "passed": p,
                   "evidence": snip(text, r'INVALID_CREDENTIALS|구분|동일하게|같은') if p else "구분 없는 동일 처리 신호 미발견"})
    passed = sum(1 for e in ex if e["passed"]); total = len(ex)
    return {"expectations": ex, "summary": {"passed": passed, "failed": total-passed, "total": total,
            "pass_rate": round(passed/total, 4)}}

rows = []
for ed in sorted(glob.glob(os.path.join(IT, "eval-*"))):
    eval_id = int(os.path.basename(ed).split("-")[1])
    for cfg in ("with_skill", "without_skill"):
        for rd in sorted(glob.glob(os.path.join(ed, cfg, "run-*"))):
            sk = os.path.join(rd, "outputs", "sketch.md")
            if not os.path.exists(sk):
                print("MISSING:", sk); continue
            text = open(sk, encoding="utf-8", errors="replace").read()
            g = grade(text, eval_id)
            json.dump(g, open(os.path.join(rd, "grading.json"), "w"), ensure_ascii=False, indent=2)
            rows.append((f"eval-{eval_id}", cfg, os.path.basename(rd), g["summary"]["pass_rate"]))

print(f"graded {len(rows)} runs")
for r in rows: print(f"  {r[0]:8} {r[1]:14} {r[2]:6} pass_rate={r[3]}")
