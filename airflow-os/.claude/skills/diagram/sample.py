#!/usr/bin/env python3
"""diagram 스킬 — 카드 스타일 완성본의 복사 시작점(제네릭 템플릿).

새 다이어그램은 이 파일을 diagrams/src/build_<이름>.py 로 복사한 뒤
PANELS / CARDS / EDGES 세 곳만 바꾼다. 스타일(TEMPLATE·헬퍼)은 손대지 않는다.
내용은 전부 플레이스홀더 — 특정 자원 이름을 여기 박지 않는다(닳는다).

레시피: 좌표를 직접 계산 → 절대배치 카드 + SVG 엣지 레이어 HTML → Chrome 스크린샷.
  python3 이파일.py
  # 창은 콘텐츠(시트+여백)에 맞춘다: --window-size=(SHEET_W+80),(SHEET_H+80)
  chrome --headless --screenshot=out.png \
    --window-size=1310,680 --force-device-scale-factor=2 --hide-scrollbars file://.../out.html
"""

import html
from pathlib import Path

OUT_HTML = Path(__file__).with_name("sample.html")   # 복사 후엔 diagrams/ 아래로 바꾼다

# ── 캔버스 ────────────────────────────────────────────────────────────
SHEET_W, SHEET_H = 1230, 600
CARD_W_MAX, CARD_H, CARD_PAD = 280, 64, 20

# 세로 패널 = 계층 (x, width, 색점, 타이틀). 종착 컬럼은 화살표 없이 섬으로 둔다.
PANELS = [
    dict(key="in",   x=40,  w=160, tint="#f4f6f9", dot="#64748b", title="진입"),
    dict(key="orch", x=270, w=260, tint="#f6f8fc", dot="#3b82f6", title="오케스트레이터"),
    dict(key="work", x=600, w=260, tint="#f5faf6", dot="#16a34a", title="워커"),
    dict(key="res",  x=930, w=260, tint="#f7f5fd", dot="#8b5cf6", title="자원"),
]
PANEL_TOP, PANEL_H = 150, 360

# ── 카드: cy = 세로 중심. 공급원은 타깃들의 세로 중앙에 둬 대칭 팬을 만든다. ──
PURPLE = "#f4f0fd"   # 강조 틴트는 한 종류만 (오케스트레이터)
SLATE  = "#eef1f6"   # 진입/게이트

CARDS = {
    "req":  dict(col="in",   cy=330, title="요청", sub="진입 지점", tint=SLATE),
    "orch": dict(col="orch", cy=330, title="라우터",
                 sub="오케스트레이터 · 워커를 호출", tint=PURPLE),
    "wa":   dict(col="work", cy=250, title="워커 A", sub="역할 설명 한 줄"),
    "wb":   dict(col="work", cy=330, title="워커 B", sub="역할 설명 한 줄"),
    "wc":   dict(col="work", cy=410, title="워커 C", sub="역할 설명 한 줄"),
    # 공유 자원 (badges = 이 자원을 읽는 워커). 다대다는 선 대신 뱃지로.
    "rx":   dict(col="res",  cy=250, title="자원 X", sub="여러 워커가 참조", badges="AB"),
    "ry":   dict(col="res",  cy=330, title="자원 Y", sub="한 워커만 참조", badges="A"),
    "rz":   dict(col="res",  cy=410, title="자원 Z  ×N",
                 sub="N개 팬아웃은 대표 하나로 접는다", badges="ABC"),
}

# ── 엣지(선): 인접 컬럼의 깔끔한 호출만. 다대다 참조는 뱃지로. ──
# (from, to, from_anchor, to_anchor)  anchor: r=오른변 l=왼변
EDGES = [
    ("req", "orch", "r", "l"),
    ("orch", "wa", "r", "l"),
    ("orch", "wb", "r", "l"),
    ("orch", "wc", "r", "l"),
]

BADGE_LABEL = {"A": "워커 A", "B": "워커 B", "C": "워커 C"}


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
    """짧은 수평 스텁으로 카드를 수평 진출·진입한 뒤 직선 — 가파른 팬에서 흐물거림 방지."""
    (sx, sy), (tx, ty) = a, b
    stub = 16
    return f"M {sx} {sy} L {sx+stub} {sy} L {tx-stub} {ty} L {tx} {ty}"


def build():
    parts = []
    parts.append(f'<div class="page"><div class="sheet" style="width:{SHEET_W}px;height:{SHEET_H}px">')

    parts.append(
        '<div class="head">'
        '<div class="h1">제목 — 무엇의 지도인가</div>'
        '<div class="h2">부제 한 줄: 기준 시점·생략한 사실을 여기 밝힌다. '
        '스킬 레시피대로 <b>실측한 사실만</b> 그린다.</div>'
        '<div class="rule"></div></div>'
    )

    for p in PANELS:
        parts.append(
            f'<div class="panel" style="left:{p["x"]}px;top:{PANEL_TOP}px;'
            f'width:{p["w"]}px;height:{PANEL_H}px;background:{p["tint"]}">'
            f'<div class="ptitle"><span class="dot" style="background:{p["dot"]}"></span>'
            f'{html.escape(p["title"])}</div></div>'
        )

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

    for cid, c in CARDS.items():
        x, y, w, h = card_box(cid)
        tint = c.get("tint", "#ffffff")
        badges = ""
        if c.get("badges"):
            chips = "".join(f'<span class="bdg">{b}</span>' for b in c["badges"])
            badges = f'<span class="bdgs">{chips}</span>'
        sub = html.escape(c["sub"])
        if c.get("sub2"):
            sub += "<br>" + html.escape(c["sub2"])
        parts.append(
            f'<div class="card" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:{tint}">'
            f'<div class="ct">{html.escape(c["title"])}{badges}</div>'
            f'<div class="cs">{sub}</div></div>'
        )

    legend = (
        '<span class="sw" style="background:%s;border-color:#d9cffa"></span>강조(한 종류만)'
        '<span class="gap"></span>'
        '<span class="ln"></span>호출·라우팅'
        '<span class="gap"></span>'
        '<span class="bdg">A</span><span class="bdg">B</span><span class="bdg">C</span>'
        '&nbsp;이 자원을 읽는 워커 (A 워커 A · B 워커 B · C 워커 C)'
    ) % (PURPLE,)
    parts.append(f'<div class="legend">{legend}</div>')
    parts.append('<div class="stamp">기준 YYYY-MM-DD · 출처·실측 범위</div>')

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
