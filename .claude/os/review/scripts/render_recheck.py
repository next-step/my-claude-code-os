#!/usr/bin/env python3
"""재판독 판정을 한 화면으로 만든다.

엔진 보고서는 **실행이 주장한 것**을 싣는다. 그게 그 보고서의 일이다.
그런데 그 주장이 재판독에서 반박된 뒤에도 화면이 그대로면, 사람은 반박이 있었다는 사실을
알 수 없다. 엔진은 심사를 모르므로(의존 방향) 그 화면에 재판독을 얹을 수 없다.
그래서 **심사가 자기 화면을 따로 낸다.**

한 줄에 둘을 나란히 놓는 것이 이 화면의 전부다 — 실행이 이 장면에 뭐라 적었는가,
재판독은 무엇을 보았는가. 숫자를 다시 세지 않고 `recheck.json`이 적어 둔 값만 그린다.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

VERDICT_LABEL = {
    "REFUTED": "반박됨",
    "CORROBORATED": "지지됨",
    "INCONCLUSIVE": "못 가름",
    "RE_READ": "다시 판독",
}
ACTION_LABEL = {
    "WITHDRAW": "권고 철회",
    "HOLD": "보류",
    "KEEP": "그대로",
    "MORE_EVIDENCE": "근거 추가",
}

STYLE = """
:root{--ink:#111;--muted:#666;--ghost:#999;--rule:#e3e3e3;--inset:#fafafa;--accent:#e5231b;--ok:#1449b8}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);
  font-family:'Gothic A1',-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo',sans-serif;
  font-size:15px;line-height:1.62;-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding:56px 28px 96px}
h1{font-size:30px;font-weight:800;letter-spacing:-.02em;margin:0 0 6px}
.sub{color:var(--muted);font-size:13.5px;margin:0 0 8px}
.mono{font-family:'IBM Plex Mono',ui-monospace,SFMono-Regular,monospace}
.warn{margin:22px 0 40px;padding:13px 16px;background:var(--inset);border-left:3px solid var(--accent);
  font-size:13.5px;color:#444}
.p{padding:34px 0 38px;border-top:1.5px solid var(--ink)}
.p-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:12px}
.p-head h2{font-size:19px;font-weight:700;margin:0}
.key{font-family:'IBM Plex Mono',monospace;font-size:11.5px;color:var(--ghost);letter-spacing:.04em}
.badge{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.09em;padding:3px 9px;
  border:1px solid var(--ink);text-transform:uppercase}
.badge.REFUTED{background:var(--accent);border-color:var(--accent);color:#fff}
.badge.CORROBORATED{background:var(--ok);border-color:var(--ok);color:#fff}
.badge.INCONCLUSIVE,.badge.RE_READ{background:#fff;color:var(--muted);border-color:var(--rule)}
.why{margin:14px 0 4px;font-size:14.5px}
.meta{font-size:12.5px;color:var(--ghost)}
table{width:100%;border-collapse:collapse;margin-top:18px;font-size:14px}
th{text-align:left;font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--ghost);
  font-weight:500;padding:0 12px 7px 0;border-bottom:1px solid var(--rule)}
td{padding:13px 12px 13px 0;border-bottom:1px solid var(--rule);vertical-align:top}
td.scene{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--muted);white-space:nowrap}
.said{color:var(--muted)}
.saw{font-weight:600}
.saw.diff{color:var(--accent)}
.agree{display:block;font-size:12px;color:var(--ghost);margin-top:2px}
.note{display:block;font-size:12.5px;color:var(--muted);margin-top:3px}
.cast{margin:16px 0 0;font-size:13px;color:var(--muted)}
.models{margin-top:10px;font-size:13.5px}
.models td.model{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--ink);white-space:nowrap}
.models td.value{font-weight:600}
.models td.off{color:var(--ghost);font-weight:400}
.none{padding:40px 0;color:var(--ghost)}
footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--rule);font-size:12px;color:var(--ghost)}
"""


def esc(value: Any) -> str:
    return html.escape(str(value or ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()

    run_root = args.run.resolve()
    source = run_root / "run-review" / "recheck.json"
    if not source.exists():
        print(f"recheck.json이 없다. 먼저 record_recheck.py를 돌려라: {source}")
        return 2
    record = json.loads(source.read_text(encoding="utf-8"))
    summary_path = run_root / "run-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}

    # 이 기록이 지금 실행 위에 서 있는가. 어긋나면 화면 맨 위에서 그렇게 말한다 —
    # 옛 실행의 판정을 지금 것처럼 읽으면 반박되지 않은 건을 반박된 것으로 본다.
    stale = bool(summary.get("generatedAt")) and summary.get("generatedAt") != record.get("basedOn")

    blocks: list[str] = []
    for product in record.get("products") or []:
        verdict = str(product.get("verdict") or "")
        rows = "".join(
            f'<tr><td class="scene">{esc(scene["sceneId"])}</td>'
            f'<td class="said">{esc(scene["judgeNote"]) or "—"}</td>'
            f'<td><span class="saw{" diff" if scene.get("reread") and scene.get("judgeNote") and scene["reread"] not in scene["judgeNote"] else ""}">'
            f'{esc(scene["reread"]) or "—"}</span>'
            + (f'<span class="agree">{esc(scene["agreement"])}</span>' if scene.get("agreement") else "")
            + (f'<span class="note">{esc(scene["note"])}</span>' if scene.get("note") else "")
            + "</td></tr>"
            for scene in product.get("scenes") or []
        )
        # 캐스팅을 장면 표보다 **앞에** 놓는다. 「두 종류가 모두 관측됨」은 사람이 둘이라는
        # 전제 위에 서 있어서, 그 전제가 무엇이었는지를 보기 전에 장면을 읽으면
        # 값만 놓고 다투게 된다. 전제가 먼저다.
        models = product.get("models") or []
        model_rows = "".join(
            f'<tr><td class="model">{esc(model.get("modelId"))}</td>'
            f'<td class="{"value" if model.get("observed") else "value off"}">'
            f'{esc(model.get("observed")) or "판독 안 함"}</td>'
            f'<td>{esc(model.get("targetContact")) or "—"}</td>'
            f'<td>{esc(model.get("presence") or model.get("faceVisibility")) or "—"}'
            + (f' · {esc(model.get("confidence"))}' if model.get("confidence") else "")
            + "</td>"
            f'<td class="scene">{esc(" ".join(model.get("scenes") or [])) or "—"}'
            # 축별 관찰. 값만 보이면 「왜 그렇게 읽었나」를 되짚을 수 없다 —
            # 한 축으로 확정한 판독이 화면에서 확정으로만 보이는 것이 그 사고였다.
            + "".join(
                f'<span class="note">{esc(axis)} · {esc(text)}</span>'
                for axis, text in sorted((model.get("observations") or {}).items())
                if text
            )
            + (f'<span class="note">기준 {esc(model.get("readFrom"))}</span>' if model.get("readFrom") else "")
            + (f'<span class="agree">{esc(model.get("agreement"))}</span>' if model.get("agreement") else "")
            + (f'<span class="note">{esc(model.get("note"))}</span>' if model.get("note") else "")
            + "</td></tr>"
            for model in models
        )
        cast = product.get("cast") or {}
        cast_note = " · ".join(
            part
            for part in (
                f'모델 없음 {" ".join(cast.get("noModelScenes") or [])}'
                if cast.get("noModelScenes")
                else "",
                f'미확정 {" ".join(cast.get("unsureScenes") or [])}'
                if cast.get("unsureScenes")
                else "",
            )
            if part
        )
        cast_block = (
            '<table class="models"><thead><tr><th>모델</th><th>관측값</th><th>대상 접촉</th>'
            "<th>얼굴</th><th>장면</th></tr></thead>"
            f"<tbody>{model_rows}</tbody></table>"
            + (f'<p class="cast">{esc(cast_note)}</p>' if cast_note else "")
            if models
            else ""
        )
        action = ACTION_LABEL.get(str(product.get("recommendation") or ""), "")
        blocks.append(
            f'<section class="p"><div class="p-head">'
            f'<h2>{esc(product.get("productName")) or esc(product.get("productKey"))}</h2>'
            f'<span class="key">{esc(product.get("productKey"))}</span>'
            f'<span class="badge {esc(verdict)}">{esc(VERDICT_LABEL.get(verdict, verdict))}</span>'
            + (f'<span class="badge">{esc(action)}</span>' if action else "")
            + "</div>"
            f'<p class="why">{esc(product.get("verdictReason"))}</p>'
            f'<p class="meta">판독자 {esc(product.get("readers"))}명 · {esc(product.get("basis"))}</p>'
            + cast_block
            + f'<table><thead><tr><th>장면</th><th>판독기가 적은 것</th><th>재판독이 본 것</th></tr></thead>'
            f"<tbody>{rows}</tbody></table></section>"
        )

    body = "".join(blocks) or '<p class="none">기록된 재판독이 없다.</p>'
    stale_note = (
        '<div class="warn"><b>이 판정은 지금 실행의 것이 아니다.</b> '
        "사이클이 다시 돌아 요약이 바뀌었다. 재판독을 다시 돌리기 전까지 이 화면을 근거로 쓰지 않는다.</div>"
        if stale
        else ""
    )
    document = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>재판독 판정 · 심사</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Gothic+A1:wght@400;500;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{STYLE}</style></head><body><div class="wrap">
<h1>재판독 판정</h1>
<p class="sub">실행이 근거로 든 장면을 다시 보고, 그 주장이 서는지 가른 결과다.</p>
<p class="sub mono">{esc(record.get("basedOn"))}</p>
{stale_note}
<div class="warn">{esc(record.get("note"))}
사람 판정 원장에 넣지 않는다 — 확정은 사람이 한다.</div>
{body}
<footer>심사는 읽기만 한다. 이 화면은 GT도 정책도 고치지 않는다.</footer>
</div></body></html>
"""
    target = run_root / "run-review" / "recheck.html"
    target.write_text(document, encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
