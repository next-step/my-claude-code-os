#!/usr/bin/env python3
"""GT 정정 후보 리포트를 무신사 스토어프론트 톤 아트보드로 짓는다.

머리에 아무것도 두지 않는다. 제목 다음이 바로 필터이고, 그 다음이 제안이다.
사용자가 2026-09-06 편집기에서 두 번에 걸쳐 지웠다 — 눈썹 라벨과 상단 요약 4칸
(고치자는 제안·인용된 장면·현재 GT 출처·소스가 갈린 건), 그리고 머리말 문단 전체.
"쓸데없는 정보". 이 화면이 묻는 것은 "이 GT가 틀렸나" 하나뿐이고, 리포트 자신을 설명하는
말과 리포트 자신을 세는 숫자는 그 답에 기여하지 않는다.

필터 칩의 개수는 남는다 — 무엇을 먼저 볼지 고르는 데 쓰인다.
「근거」 표시의 뜻을 풀어 주던 문장도 함께 사라졌다. 표시 자체로 읽힌다고 본 것이다.
"""
import html, json, pathlib

ROWS = json.loads(pathlib.Path('gt-rows.json').read_text(encoding='utf-8'))
E = lambda s: html.escape(str(s or ''), quote=True)

def kept_photos(row):
    return [p for p in row['plate'] if p['role'] == 'TARGET' or p['cited']]

blocks, search_index, meta = [], [], []
for idx, row in enumerate(ROWS, start=1):
    rid = f'r{idx}'
    photos = kept_photos(row)
    key_slug = row['productKey'].replace(':', '-')
    conflict = row.get('sourceConflict') or {}

    chips = []
    if conflict:
        chips.append('<span style="display:inline-flex;align-items:center;height:22px;padding:0 9px;'
                     'border:1px solid var(--accent);color:var(--accent);font-family:var(--mono);'
                     'font-size:10px;font-weight:600;letter-spacing:.1em">SOURCE CONFLICT</span>')
    for pid in row.get('blockedBy') or []:
        chips.append(f'<span style="display:inline-flex;align-items:center;height:22px;padding:0 9px;'
                     f'border:1px solid #E4E4E4;color:#767676;font-family:var(--mono);font-size:10px;'
                     f'font-weight:600;letter-spacing:.1em">{E(pid)}</span>')

    shots = []
    for pi, ph in enumerate(photos):
        pid = f'{rid}.p{pi}'
        cited = ph['cited']
        border = '2px solid var(--accent)' if cited else '1px solid #E4E4E4'
        tag = (f'<span style="position:absolute;top:0;left:0;z-index:2;padding:5px 9px 4px;'
               f'background:var(--accent);color:#fff;font-family:var(--mono);font-size:9.5px;'
               f'font-weight:700;letter-spacing:.14em">근거</span>') if cited else ''
        cap_color = 'var(--accent)' if cited else '#A3A3A3'
        shots.append(
            f'<figure style="{{{{{pid}.fig}}}}">'
            f'<button type="button" onClick="{{{{{pid}.tap}}}}" aria-label="{E(ph["caption"])} 크게 보기" '
            f'style="position:relative;display:block;width:100%;padding:0;border:{border};'
            f'background:#fff;cursor:zoom-in">'
            f'{tag}'
            f'<img src="{key_slug}-{pi}.jpg" alt="{E(ph["caption"])}" '
            f'style="display:block;width:100%;height:{{{{{pid}.h}}}};object-fit:var(--fit);background:#fff"></button>'
            f'<figcaption style="margin-top:9px;font-family:var(--mono);font-size:10px;'
            f'letter-spacing:.09em;color:{cap_color}">{E(ph["caption"])}</figcaption>'
            f'</figure>')

    rest = len(row['plate']) - len(photos)
    rest_line = (f'<p style="margin:18px 0 0;font-family:var(--mono);font-size:10.5px;letter-spacing:.07em;'
                 f'color:#A3A3A3">판독기가 본 사진 {len(row["plate"])}장 가운데 대표·인용 {len(photos)}장. '
                 f'나머지 {rest}장은 실제 리포트에서 펼친다</p>') if rest else ''

    conflict_row = ''
    if conflict:
        conflict_row = (
            '<div style="display:grid;grid-template-columns:104px minmax(0,1fr);gap:20px;'
            'padding:15px 0;border-top:1px solid #F0F0F0">'
            '<span style="font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.13em;'
            'color:#A3A3A3;padding-top:3px">갈린 GT</span>'
            f'<p style="margin:0;font-size:14.5px;line-height:1.75;color:#000">'
            f'<b style="font-weight:700">{E(conflict.get("canonical"))}</b> '
            f'<span style="font-family:var(--mono);font-size:11px;letter-spacing:.05em;color:#767676">'
            f'{E(conflict.get("canonicalSource"))}'
            f'{" · " + E(conflict.get("canonicalVersion")) if conflict.get("canonicalVersion") else ""}</span>'
            f' — 현재 GT와 갈린다. 어느 쪽을 정본으로 볼지가 먼저다.</p></div>')

    blocks.append(f'''
<sc-if value="{{{{{rid}.show}}}}" hint-placeholder-val="{{{{true}}}}">
<article style="padding:64px 0 72px;border-top:1px solid #000">
  <div style="display:grid;grid-template-columns:96px minmax(0,1fr);gap:0 32px;align-items:start">
    <span style="font-family:var(--mono);font-size:40px;font-weight:600;letter-spacing:-.03em;
                 line-height:.85;color:#E4E4E4;font-feature-settings:'tnum' 1">{idx:02d}</span>
    <div style="min-width:0">
      <div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;margin-bottom:14px">
        <a href="{E(row['url'])}" target="_blank" rel="noreferrer"
           style="font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:.1em;color:#000">{E(row['productKey'])} &#8599;</a>
        <span style="font-family:var(--mono);font-size:11px;letter-spacing:.07em;color:#A3A3A3">{E(row['brand'])} · {E(row['category'])}</span>
        {''.join(chips)}
      </div>
      <h3 style="margin:0 0 34px;font-size:26px;font-weight:700;letter-spacing:-.02em;line-height:1.3;color:#000">{E(row['productName'])}</h3>

      <div style="display:flex;flex-wrap:wrap;align-items:flex-end;gap:16px 44px;padding:26px 0;border-top:1px solid #000;border-bottom:1px solid #E4E4E4">
        <div style="min-width:0">
          <p style="margin:0 0 10px;font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.15em;color:#A3A3A3">현재 GT</p>
          <p style="margin:0;font-size:42px;font-weight:800;letter-spacing:-.03em;line-height:.95;color:#B8B8B8;
                    text-decoration:line-through;text-decoration-thickness:2px;font-feature-settings:'tnum' 1">{E(row['referenceLabel'])}</p>
          <p style="margin:12px 0 0;font-family:var(--mono);font-size:10.5px;letter-spacing:.05em;color:#767676">{E(row['goldSource'])}{" · " + E(row['gtReviewStatus']) if row.get('gtReviewStatus') else ""}</p>
        </div>
        <span aria-hidden="true" style="font-size:28px;line-height:1;color:#E4E4E4;padding-bottom:22px">&#10230;</span>
        <div style="min-width:0">
          <p style="margin:0 0 10px;font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.15em;color:var(--accent)">이렇게 고치자</p>
          <p style="margin:0;font-size:42px;font-weight:800;letter-spacing:-.03em;line-height:.95;color:var(--accent);font-feature-settings:'tnum' 1">{E(row['proposed'])}</p>
          <p style="margin:12px 0 0;font-family:var(--mono);font-size:10.5px;letter-spacing:.05em;color:#767676">정책이 낸 답 · {E(row['ruleId'] or '—')}</p>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:104px minmax(0,1fr);gap:20px;padding:19px 0;border-bottom:1px solid #F0F0F0">
        <span style="font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.13em;color:#A3A3A3;padding-top:3px">판독기</span>
        <p style="margin:0;font-size:15px;line-height:1.75;color:#000">{E(row['judgeText']) or '기록된 문장이 없다.'}</p>
      </div>
      <div style="display:grid;grid-template-columns:104px minmax(0,1fr);gap:20px;padding:19px 0">
        <span style="font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.13em;color:#A3A3A3;padding-top:3px">리뷰어</span>
        <p style="margin:0;font-size:15px;line-height:1.75;color:#767676">{E(row['reviewerText']) or '아직 가르지 않았다.'}</p>
      </div>
      {conflict_row}

      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:20px;margin-top:34px">
        {''.join(shots)}
      </div>
      {rest_line}
    </div>
  </div>
</article>
</sc-if>''')

    search_index.append({
        'id': rid,
        'q': ' '.join(str(x) for x in [row['productKey'], row['productName'], row['brand'],
                                       row['category'], row['referenceLabel'], row['proposed'],
                                       row['goldSource'], row['judgeText'], row['reviewerText']]).lower(),
        'proposed': row['proposed'],
        'conflict': bool(conflict),
        'photos': len(photos),
    })
    meta.append({'id': rid, 'n': len(photos)})

DATA_JS = json.dumps(search_index, ensure_ascii=False)

CONFLICTS = sum(1 for r in ROWS if r.get('sourceConflict'))  # 필터 칩 개수에만 쓴다

doc = f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;700;800&family=Gothic+A1:wght@400;500;700;800&family=IBM+Plex+Mono:wght@400;600;700&display=swap">
  <style>
    body {{ margin: 0; background: #fff; }}
    a {{ color: #000; text-decoration: none; border-bottom: 1px solid #C8C8C8; }}
    a:hover {{ color: var(--accent, #D62300); border-bottom-color: var(--accent, #D62300); }}
    button {{ font: inherit; color: inherit; }}
    ::selection {{ background: #000; color: #fff; }}
  </style>
</helmet>
<div style="{{{{rootStyle}}}}">
  <div style="max-width:1240px;margin:0 auto;padding:0 48px 120px">

    <header style="padding:88px 0 0">
      <h1 style="margin:0;font-size:78px;font-weight:800;letter-spacing:-.045em;line-height:.98;color:#000">GT 정정 후보</h1>

    </header>

    <div style="position:sticky;top:0;z-index:9;display:flex;flex-wrap:wrap;align-items:center;gap:10px;
                margin-top:56px;padding:16px 0;background:#fff;border-top:1px solid #000;border-bottom:1px solid #000">
      <button type="button" onClick="{{{{f.all}}}}" style="{{{{f.allStyle}}}}">전체 {len(ROWS)}</button>
      <button type="button" onClick="{{{{f.female}}}}" style="{{{{f.femaleStyle}}}}">여성으로 {sum(1 for r in ROWS if r['proposed'] == 'FEMALE')}</button>
      <button type="button" onClick="{{{{f.male}}}}" style="{{{{f.maleStyle}}}}">남성으로 {sum(1 for r in ROWS if r['proposed'] == 'MALE')}</button>
      <button type="button" onClick="{{{{f.conflict}}}}" style="{{{{f.conflictStyle}}}}">소스 충돌 {CONFLICTS}</button>
      <span style="flex:1 1 auto"></span>
      <input type="search" placeholder="상품명 · 키 · 브랜드 · GT 출처 · 사유" aria-label="검색" onInput="{{{{onQuery}}}}"
             style="min-width:260px;padding:9px 12px;border:1px solid #E4E4E4;background:#fff;
                    font-family:var(--mono);font-size:11.5px;letter-spacing:.04em;color:#000">
      <span style="font-family:var(--mono);font-size:11px;letter-spacing:.09em;color:#A3A3A3;font-feature-settings:'tnum' 1">{{{{shownLabel}}}}</span>
    </div>

    {''.join(blocks)}

    <sc-if value="{{{{noneShown}}}}" hint-placeholder-val="{{{{false}}}}">
      <p style="padding:120px 0;border-top:1px solid #000;text-align:center;font-family:var(--mono);
                font-size:12px;letter-spacing:.1em;color:#A3A3A3">조건에 맞는 제안이 없다</p>
    </sc-if>

    <footer style="margin-top:8px;padding:36px 0 0;border-top:2px solid #000;
                   font-family:var(--mono);font-size:10.5px;letter-spacing:.07em;color:#A3A3A3;line-height:2">
      원장 · runs/bag-category-gender/review/decisions.json<br>
      심판 추천 · runs/bag-category-gender/review/verdicts.jsonl
    </footer>
  </div>
</div>
</x-dc>
<script data-dc-script data-props='{{"accent":{{"editor":"color","default":"#D62300","options":["#D62300","#000000","#1D4ED8","#B08900"],"section":"색"}},"fit":{{"editor":"enum","options":["contain","cover"],"default":"contain","section":"사진"}},"$preview":{{"width":1240,"height":2400}}}}'>
const ROWS = {DATA_JS};

class Component extends DCLogic {{
  constructor(props) {{
    super(props);
    this.state = {{ filter: 'ALL', query: '', open: '' }};
  }}

  visible() {{
    const q = this.state.query.trim().toLowerCase();
    const f = this.state.filter;
    const hit = {{}};
    for (const row of ROWS) {{
      let ok = true;
      if (f === 'FEMALE' || f === 'MALE') ok = row.proposed === f;
      else if (f === 'CONFLICT') ok = row.conflict;
      if (ok && q) ok = row.q.includes(q);
      hit[row.id] = ok;
    }}
    return hit;
  }}

  chipStyle(active) {{
    const base = 'display:inline-flex;align-items:center;height:34px;padding:0 16px;'
      + "font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:.09em;cursor:pointer;"
      + 'transition:background .12s,color .12s,border-color .12s;';
    return active
      ? base + 'background:#000;border:1px solid #000;color:#fff;'
      : base + 'background:#fff;border:1px solid #E4E4E4;color:#767676;';
  }}

  renderVals() {{
    const accent = this.props.accent ?? '#D62300';
    const fit = this.props.fit ?? 'contain';
    const hit = this.visible();
    const shown = ROWS.filter((row) => hit[row.id]).length;
    const pick = (name) => () => this.setState({{ filter: name }});
    const vals = {{
      rootStyle: '--accent: ' + accent + '; --fit: ' + fit + ';'
        + " --mono: 'IBM Plex Mono', ui-monospace, 'SF Mono', monospace;"
        + " font-family: 'Archivo', 'Gothic A1', -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', sans-serif;"
        + ' color: #000; background: #fff; -webkit-font-smoothing: antialiased;',
      shownLabel: shown + ' / ' + ROWS.length,
      noneShown: shown === 0,
      onQuery: (ev) => this.setState({{ query: ev.target.value }}),
      f: {{
        all: pick('ALL'), female: pick('FEMALE'), male: pick('MALE'), conflict: pick('CONFLICT'),
        allStyle: this.chipStyle(this.state.filter === 'ALL'),
        femaleStyle: this.chipStyle(this.state.filter === 'FEMALE'),
        maleStyle: this.chipStyle(this.state.filter === 'MALE'),
        conflictStyle: this.chipStyle(this.state.filter === 'CONFLICT'),
      }},
    }};
    for (const row of ROWS) {{
      const entry = {{ show: hit[row.id] }};
      for (let i = 0; i < row.photos; i += 1) {{
        const key = row.id + ':' + i;
        const open = this.state.open === key;
        entry['p' + i] = {{
          fig: open ? 'margin:0;min-width:0;grid-column:1 / -1' : 'margin:0;min-width:0',
          h: open ? '720px' : '300px',
          tap: () => this.setState({{ open: open ? '' : key }}),
        }};
      }}
      vals[row.id] = entry;
    }}
    return vals;
  }}
}}
</script>
</body>
</html>
'''

pathlib.Path('Main.dc.html').write_text(doc, encoding='utf-8')
print('Main.dc.html', len(doc), 'bytes ·', len(ROWS), 'proposals ·',
      sum(len(kept_photos(r)) for r in ROWS), 'photos')
