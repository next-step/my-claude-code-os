#!/usr/bin/env python3
"""회고 1건을 기록으로 저장한다 (append-only). portfolio-retrospect 스킬의 기록 담당.

설계(OS.md "기록 방식 A"):
- 원본 분석 기록은 status 만 갱신(update_status.py)하고, *회고 자체*(토론 경위·종목별 평가·
  튜닝안)는 여기 별도 파일에 남긴다. → 원본은 예측 박제, 회고는 평가 누적으로 역할이 갈린다.
- 과거 회고는 절대 덮어쓰지 않는다. 같은 날 또 돌리면 -2, -3 … 새 파일.
- 저장 위치: 프로젝트 내 data/retros/YYYY-MM-DD-retro[-N].md
- 형식: frontmatter(집계, 기계가 읽음) + 본문(토론·평가·튜닝안, 사람이 읽음).

입력 JSON(stdin 또는 argv[1]) — 메인 에이전트가 토론을 끝내고 조립해 넘긴다:
{
  "retro_date": "2026-07-07",                 # 생략 시 오늘
  "as_of": "2026-07-07",                      # 사실 판정 기준일(evaluate_records 의 as_of)
  "summary": {"total":5,"hit_target":2,"stopped":1,"watching":2,"avg_actual_return_pct":6.3},
  "rounds": 3,                                # 실제로 돈 토론 라운드 수
  "converged": true,                          # 수렴해서 멈췄나(false면 5R 상한 도달)
  "evaluations": [                            # 종목별 사실 + 한 줄 평가
    {"name":"기아","status":"hit_target","actual_return_pct":14.2,
     "comment":"지지선 진입 타이밍이 적중"}
  ],
  "debate": [                                 # 토론 경위(라운드별 핵심)
    {"round":1,"note":"기술적·펀더멘털 합의, 거시 vs 회의론자 충돌(운 논쟁)"},
    {"round":2,"note":"회의론자 표본부족 지적 수용 → 임계값 변경 보류로 합의"}
  ],
  "consensus": ["...합의된 결론..."],
  "open_issues": ["...끝내 미합의로 남긴 쟁점(있으면)..."],
  "tuning": [                                 # 다음 추천/분석에 반영할 제안(실제 수정은 사람 승인)
    {"target":"score_stocks.py","change":"부채비율 컷 150%→130%","why":"손절난 종목이 모두 고부채"}
  ]
}
출력: {"saved": "data/retros/..."} JSON
"""
from __future__ import annotations
import datetime
import json
import os
import sys

RETRO_DIR = os.path.join(os.getcwd(), "data", "retros")


def _target_path(retro_date: str) -> str:
    os.makedirs(RETRO_DIR, exist_ok=True)
    base = os.path.join(RETRO_DIR, f"{retro_date}-retro")
    path = f"{base}.md"
    n = 2
    while os.path.exists(path):            # append-only: 기존 회고 보존
        path = f"{base}-{n}.md"
        n += 1
    return path


def _yaml_scalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def render(data: dict, retro_date: str) -> str:
    s = data.get("summary", {})
    evals = data.get("evaluations", [])
    debate = data.get("debate", [])

    # --- frontmatter (집계) ---
    fm = ["---", f"retro_date: {retro_date}",
          f"as_of: {_yaml_scalar(data.get('as_of', retro_date))}",
          f"rounds: {_yaml_scalar(data.get('rounds', 0))}",
          f"converged: {_yaml_scalar(bool(data.get('converged', False)))}",
          "summary:"]
    for k in ("total", "hit_target", "stopped", "watching", "avg_actual_return_pct"):
        if s.get(k) is not None:
            fm.append(f"  {k}: {_yaml_scalar(s[k])}")
    fm.append("---")

    # --- 본문 ---
    body = [f"\n# 📒 회고 — {retro_date} (기준일 {data.get('as_of', retro_date)})\n"]

    body.append("## 성적표 (사실 — 스크립트 판정)")
    body.append(f"- 평가 {s.get('total','?')}건: "
                f"목표달성 {s.get('hit_target',0)} · 손절 {s.get('stopped',0)} · "
                f"관찰중 {s.get('watching',0)}"
                + (f" · 평균 실현수익률 {s['avg_actual_return_pct']}%"
                   if s.get('avg_actual_return_pct') is not None else ""))
    if evals:
        body += ["\n| 종목 | status | 실현수익률 | 한 줄 평가 |",
                 "|------|--------|-----------|-----------|"]
        for e in evals:
            r = e.get("actual_return_pct")
            r = f"{r:+g}%" if isinstance(r, (int, float)) else "—"
            body.append(f"| {e.get('name','')} | {e.get('status','')} | {r} | {e.get('comment','')} |")

    if debate:
        body.append("\n## 전문가 토론 경위")
        body.append(f"- 총 {data.get('rounds', len(debate))}라운드, "
                    + ("수렴 후 종료" if data.get("converged") else "상한(5R) 도달 — 미합의 잔존"))
        for d in debate:
            body.append(f"  - R{d.get('round','?')}: {d.get('note','')}")

    if data.get("consensus"):
        body.append("\n## 합의된 결론")
        body += [f"- {c}" for c in data["consensus"]]

    if data.get("open_issues"):
        body.append("\n## 미해결 쟁점 (다음 회고로 이월)")
        body += [f"- {c}" for c in data["open_issues"]]

    tuning = data.get("tuning", [])
    body.append("\n## 튜닝 제안 (다음 추천/분석 반영 — ⚠️ 실제 수정은 사람 승인)")
    if tuning:
        for t in tuning:
            body.append(f"- **{t.get('target','')}**: {t.get('change','')} "
                        f"— {t.get('why','')}")
    else:
        body.append("- (이번 회고에서 도출된 변경 없음 — 기준 유지)")

    body += ["\n## ⚠️ 유의",
             "- 회고는 과거 예측을 *평가*할 뿐, 원본 분석의 진입/목표/손절·근거는 수정하지 않는다(예측 박제).",
             "- status 사실 판정은 스크립트(현재가 대조), 해석·튜닝안은 전문가 토론+사람 판단의 결과다.",
             "- 튜닝안은 제안이며, 스크립트 상수/문서의 실제 변경은 사람이 승인 후 반영한다."]
    return "\n".join(fm) + "\n" + "\n".join(body) + "\n"


def main() -> int:
    raw = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else sys.stdin.read()
    data = json.loads(raw)
    retro_date = data.get("retro_date") or datetime.date.today().isoformat()
    path = _target_path(retro_date)
    with open(path, "w", encoding="utf-8") as f:
        f.write(render(data, retro_date))
    print(json.dumps({"saved": os.path.relpath(path, os.getcwd())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
