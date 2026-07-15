#!/usr/bin/env python3
"""airflow-os 컨텍스트 체계 다이어그램 생성기 (카드 스타일).

좌표를 직접 계산 → 절대배치 카드 + SVG 엣지 레이어 HTML → Chrome 스크린샷.
diagram 스킬 레시피를 따른다: 흰 시트, 세로 패널=계층, 흰 카드, 회색 직선 엣지.
결합이 다대다로 뭉치는 '워커→컨텍스트'는 선 대신 인라인 뱃지(B/T/R/I)로 표현한다.
"""

import html
from pathlib import Path

OUT_HTML = Path(__file__).resolve().parents[1] / "context_system.html"

# ── 캔버스 ────────────────────────────────────────────────────────────
SHEET_W, SHEET_H = 1392, 776
CARD_W_MAX, CARD_H, CARD_PAD = 340, 74, 20

# 4개 세로 패널 (x, width, 색점, 타이틀)
PANELS = [
    dict(key="human",   x=40,  w=180, tint="#f4f6f9", dot="#64748b", title="사람"),
    dict(key="skills",  x=290, w=320, tint="#f6f8fc", dot="#3b82f6", title="스킬"),
    dict(key="workers", x=640, w=320, tint="#f5faf6", dot="#16a34a", title="서브에이전트"),
    dict(key="context", x=990, w=362, tint="#f7f5fd", dot="#8b5cf6", title="컨텍스트"),
]
PANEL_TOP, PANEL_H = 150, 566

# ── 카드 정의: (col, cx_offset, cy, title, subtitle, tint, badges) ──────
# cy = 카드 세로 중심. 화살표 길이 최소화하려 공급원은 타깃 가운데 높이에 둔다.
PURPLE = "#f4f0fd"   # 오케스트레이터 강조
SLATE  = "#eef1f6"   # 사람 게이트

CARDS = {
    # 사람
    "req":   dict(col="human", cy=312, title="요청", sub="파이프라인 작업 의뢰", tint=SLATE),
    "ok":    dict(col="human", cy=560, title="승인", sub="유일한 수동 게이트", tint=SLATE),
    # 스킬 — audit/interview/pipeline을 요청(312) 기준 대칭으로
    "audit": dict(col="skills", cy=226, title="dag-audit", sub="진단·리뷰 (읽기 전용)"),
    "intv":  dict(col="skills", cy=312, title="interview", sub="신규 — 질문으로 설계도 합의"),
    "pipe":  dict(col="skills", cy=398, title="airflow-pipeline",
                  sub="오케스트레이터 · 설계→구현→테스트→리뷰 루프", tint=PURPLE),
    "lab":   dict(col="skills", cy=490, title="lab", sub="로컬 Airflow 3.2 검증 env"),
    "meta":  dict(col="skills", cy=580, title="OS 유지 스킬",
                  sub="lint · sync · retrospective · diagram"),
    # 워커 — pipeline(398) 기준 대칭
    "build": dict(col="workers", cy=318, title="dag-builder", sub="구현 — 설계도를 코드로"),
    "test":  dict(col="workers", cy=398, title="dag-tester", sub="파싱·구조 검증"),
    "rev":   dict(col="workers", cy=478, title="dag-reviewer", sub="컨벤션·안티패턴·진단"),
    # 컨텍스트 (badges = 이걸 읽는 워커/스킬)
    "spec":  dict(col="context", cy=222, title="dag-design-spec", sub="설계도 형식·필드",
                  badges="IBTR", cond="R"),
    "anti":  dict(col="context", cy=306, title="airflow-antipatterns", sub="top-level·멱등성 금지 패턴",
                  badges="IBR"),
    "know":  dict(col="context", cy=390, title="airflow3-knowledge", sub="버전 종속 지식",
                  badges="BR"),
    "plat":  dict(col="context", cy=474, title="platform", sub="XCom backend · 계보",
                  badges="BR"),
    "work":  dict(col="context", cy=558, title="workspace", sub="코드 위치 · 작업환경",
                  badges="BT"),
    "conv":  dict(col="context", cy=650, h=88, title="conventions/  ×8",
                  sub="naming · loading · operators · schedule",
                  sub2="defaults · reuse · dbt · airbyte",
                  badges="BR"),
}

# ── 엣지 (선): 인접 컬럼의 깔끔한 호출·라우팅만. 워커→컨텍스트는 뱃지로. ──
# (from, to, from_anchor, to_anchor)  anchor: r=오른변 l=왼변
EDGES = [
    ("req", "audit", "r", "l"),
    ("req", "intv",  "r", "l"),
    ("req", "pipe",  "r", "l"),
    ("pipe", "build", "r", "l"),
    ("pipe", "test",  "r", "l"),
    ("pipe", "rev",   "r", "l"),
]

BADGE_LABEL = {
    "B": "dag-builder", "T": "dag-tester", "R": "dag-reviewer", "I": "interview",
}


def panel(key):
    return next(p for p in PANELS if p["key"] == key)


def card_box(cid):
    c = CARDS[cid]
    p = panel(c["col"])
    h = c.get("h", CARD_H)
    w = min(CARD_W_MAX, p["w"] - 2 * CARD_PAD)
    x = p["x"] + (p["w"] - w) / 2
    y = c["cy"] - h / 2
    return x, y, w, h


def anchor(cid, side):
    x, y, w, h = card_box(cid)
    cy = y + h / 2
    return (x + w, cy) if side == "r" else (x, cy)


def edge_path(a, b):
    """짧은 수평 스텁으로 카드를 수평 진입·진출한 뒤 직선. 가파른 팬에서 흐물거림 방지."""
    (sx, sy), (tx, ty) = a, b
    stub = 16
    return f"M {sx} {sy} L {sx+stub} {sy} L {tx-stub} {ty} L {tx} {ty}"


def build():
    parts = []
    parts.append(f'<div class="page"><div class="sheet" style="width:{SHEET_W}px;height:{SHEET_H}px">')

    # 헤더
    parts.append(
        '<div class="head">'
        '<div class="h1">airflow-os 컨텍스트 체계</div>'
        '<div class="h2">사람은 요청·승인만 한다. 스킬이 워커를 <b>호출</b>(선)하고, '
        '워커는 공유 컨텍스트를 이름으로 <b>참조</b>(뱃지)한다 — 지식은 <code>.claude/context/</code> 한 곳.</div>'
        '<div class="rule"></div></div>'
    )

    # 패널
    for p in PANELS:
        parts.append(
            f'<div class="panel" style="left:{p["x"]}px;top:{PANEL_TOP}px;'
            f'width:{p["w"]}px;height:{PANEL_H}px;background:{p["tint"]}">'
            f'<div class="ptitle"><span class="dot" style="background:{p["dot"]}"></span>'
            f'{html.escape(p["title"])}</div></div>'
        )

    # 엣지 레이어 (카드 뒤)
    svg = [f'<svg class="edges" width="{SHEET_W}" height="{SHEET_H}">']
    svg.append(
        '<defs><marker id="arw" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M0,0 L10,5 L0,10 z" fill="#aab2be"/></marker></defs>'
    )
    for f, t, fa, ta in EDGES:
        d = edge_path(anchor(f, fa), anchor(t, ta))
        svg.append(f'<path d="{d}" fill="none" stroke="#aab2be" stroke-width="1.4" '
                   f'stroke-linejoin="round" marker-end="url(#arw)"/>')
    svg.append("</svg>")
    parts.append("".join(svg))

    # 카드
    for cid, c in CARDS.items():
        x, y, w, h = card_box(cid)
        tint = c.get("tint", "#ffffff")
        badges = ""
        if c.get("badges"):
            cond = c.get("cond", "")
            chips = "".join(
                f'<span class="bdg{" cond" if b in cond else ""}">{b}</span>'
                for b in c["badges"])
            badges = f'<span class="bdgs">{chips}</span>'
        sub = html.escape(c["sub"])
        if c.get("sub2"):
            sub += "<br>" + html.escape(c["sub2"])
        parts.append(
            f'<div class="card" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:{tint}">'
            f'<div class="ct">{html.escape(c["title"])}{badges}</div>'
            f'<div class="cs">{sub}</div></div>'
        )

    # 하단 범례 + 스탬프
    legend = (
        '<span class="sw" style="background:%s;border-color:#d9cffa"></span>오케스트레이터'
        '<span class="gap"></span>'
        '<span class="sw" style="background:%s;border-color:#d5dbe6"></span>사람 게이트'
        '<span class="gap"></span>'
        '<span class="ln"></span>호출·라우팅'
        '<span class="gap"></span>'
        '<span class="bdg">B</span><span class="bdg">T</span>'
        '<span class="bdg">R</span><span class="bdg">I</span>'
        '&nbsp;읽는 워커 (B 빌더 · T 테스터 · R 리뷰어 · I 인터뷰)'
        '<span class="gap"></span>'
        '<span class="bdg cond">R</span>&nbsp;테두리 = 조건부 주입(검증 모드에서만)'
    ) % (PURPLE, SLATE)
    parts.append(f'<div class="legend">{legend}</div>')
    parts.append('<div class="stamp">기준 2026-07-15 · .claude/ 로컬 자산 · 참조 관계 실측</div>')

    parts.append("</div></div>")
    return TEMPLATE.replace("__BODY__", "".join(parts))


TEMPLATE = """<!doctype html><html><head><meta charset="utf-8"><style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#eef1f5; font-family:-apple-system,'Helvetica Neue','Apple SD Gothic Neo',sans-serif; }
.page { padding:40px; display:inline-block; }
.sheet { position:relative; background:#fff; border-radius:24px;
  box-shadow:0 12px 40px rgba(30,40,60,.10); }
.head { position:absolute; left:40px; top:34px; right:40px; }
.h1 { font-size:30px; font-weight:700; color:#1e2633; letter-spacing:-.2px; }
.h2 { font-size:13.5px; color:#6b7686; margin-top:8px; line-height:1.55; max-width:1180px; }
.h2 b { color:#3a4557; font-weight:600; } .h2 code { color:#7c6bb0; font-size:12.5px; }
.rule { height:1px; background:#e9ecf2; margin-top:16px; }
.panel { position:absolute; border-radius:16px; }
.ptitle { position:absolute; left:18px; top:14px; font-size:11.5px; font-weight:700;
  letter-spacing:1.2px; color:#7a8496; text-transform:uppercase; display:flex; align-items:center; }
.dot { width:9px; height:9px; border-radius:50%; display:inline-block; margin-right:8px; }
.edges { position:absolute; left:0; top:0; pointer-events:none; }
.card { position:absolute; border-radius:12px; border:1px solid #e6e8ee;
  box-shadow:0 2px 6px rgba(30,40,60,.05); padding:13px 16px; }
.ct { font-size:15px; font-weight:600; color:#232b38; display:flex; align-items:center; }
.cs { font-size:11.5px; color:#8b93a3; margin-top:6px; line-height:1.4; }
.bdgs { margin-left:8px; display:inline-flex; gap:3px; }
.bdg { display:inline-flex; align-items:center; justify-content:center;
  min-width:15px; height:15px; padding:0 3px; border-radius:4px;
  background:#e3f2fd; color:#0284c7; font-size:9.5px; font-weight:700;
  font-family:ui-monospace,Menlo,monospace; }
.bdg.cond { background:#fff; box-shadow:inset 0 0 0 1px #86c5e6; }
.legend { position:absolute; left:40px; bottom:28px; font-size:11.5px; color:#6b7686;
  display:flex; align-items:center; }
.legend .sw { width:14px; height:14px; border-radius:4px; border:1px solid #ccc;
  display:inline-block; margin-right:7px; }
.legend .ln { width:22px; height:0; border-top:1.6px solid #aab2be; display:inline-block; margin-right:7px; }
.legend .gap { display:inline-block; width:22px; }
.legend .bdg { margin-right:2px; }
.stamp { position:absolute; right:40px; bottom:28px; font-size:11px; color:#a7b0be; }
</style></head><body>__BODY__</body></html>"""


if __name__ == "__main__":
    OUT_HTML.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT_HTML}")
