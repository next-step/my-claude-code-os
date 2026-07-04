// 촬영·측정 결과(measurements.json)와 AI 눈 판단(ai-notes.json)을 모아
// 한 페이지 격자 갤러리(index.html)를 만든다. (OS.md 5단계)
//
// 모델(OS.md): 코드는 사실(수치 + overflow 판정)만, AI 가 맥락으로 최종 판정.
//   "코드는 통과/수치만인데 AI 가 잡은" 칸이 곧 AI 눈의 가치다 → 빨간 테두리로 강조.
//
// 사용법: node scripts/build-gallery.mjs [target] [--open]
//   target  기본값: card
//   --open  생성 후 기본 브라우저로 연다
// 입력:  screenshots/<target>/measurements.json (필수)
//        screenshots/<target>/ai-notes.json     (선택) { "<id>": { "level": "ok|warn|error", "note": "..." } }
// 산출물: screenshots/<target>/index.html
import { readFile, writeFile } from 'node:fs/promises'
import { spawn } from 'node:child_process'
import { resolve } from 'node:path'

const args = process.argv.slice(2)
const shouldOpen = args.includes('--open')
const target = args.find((a) => a !== '--open') || 'card'
const dir = `screenshots/${target}`

let measurements
try {
  measurements = JSON.parse(await readFile(`${dir}/measurements.json`, 'utf8'))
} catch {
  console.error(`${dir}/measurements.json 없음/깨짐 — 먼저 촬영하라: npm run capture -- ${target}`)
  process.exit(1)
}
let aiNotes = {}
try {
  aiNotes = JSON.parse(await readFile(`${dir}/ai-notes.json`, 'utf8'))
} catch {
  // 아직 AI 판단이 없으면 빈 칸
}

const BADGE = { ok: '✅ 정상', warn: '⚠️ 주의', error: '🟥 깨짐' }
const BADGE_BG = { ok: '#dcfce7', warn: '#fef9c3', error: '#fee2e2' }
const FLAG_COLOR = { warn: '#a16207', error: '#b91c1c' }
const RANK = { ok: 0, warn: 1, error: 2 }
// AI 판정 줄에서는 체크 이모지(✅)가 "맞음"처럼 보여 헷갈리므로, 색 텍스트만 쓴다
const LEVEL_WORD = { ok: '정상', warn: '주의', error: '깨짐' }
const LEVEL_COLOR = { ok: '#475569', warn: '#a16207', error: '#b91c1c' }
// 채점표용 — 등급은 색 동그라미(레벨 표시), 채점(맞음/틀림)만 ✅/❌ 로 구분
const TABLE_BADGE = { ok: '🟢 정상', warn: '🟡 주의', error: '🔴 깨짐' }

const esc = (s) =>
  String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])

const cards = measurements
  .map((m) => {
    const ai = aiNotes[m.id]
    const aiLevel = ai?.level
    const aiCaughtMore = aiLevel && RANK[aiLevel] > RANK[m.level]
    const expected = m.expected
    const aiHit = aiLevel ? aiLevel === expected : null
    const aiMissed = aiHit === false // AI 가 정답을 못 맞힌 칸 (사각지대)

    const flags = m.flags.length
      ? m.flags.map((f) => `<li style="color:${FLAG_COLOR[f.level]}">${esc(f.text)}</li>`).join('')
      : '<li style="color:#16a34a">overflow 없음 (코드가 단정할 깨짐 없음)</li>'

    const metaBits = [
      m.minContrast != null ? `최저대비 ${m.minContrast}:1` : '',
      m.anyOverImage ? '이미지 위 글자(측정불가)' : '',
      m.opacity < 1 ? `opacity ${m.opacity}` : '',
    ]
      .filter(Boolean)
      .map((t) => `<span>${esc(t)}</span>`)
      .join('')

    // 채점 행 (시험 채점표의 결과 줄)
    const scoreRow =
      aiHit === null
        ? `<div class="srow result pending"><span class="lbl">채점</span><span class="val">AI 판단 대기</span></div>`
        : aiHit
          ? `<div class="srow result hit"><span class="lbl">채점</span><span class="val">✅ 맞음</span></div>`
          : `<div class="srow result miss"><span class="lbl">채점</span><span class="val">❌ 틀림</span></div>`

    const explain = ai
      ? `<p class="ai-explain${aiCaughtMore ? ' win' : ''}${aiMissed ? ' miss' : ''}">💬 ${esc(ai.note)}</p>`
      : `<p class="ai-explain pending">💬 에이전트가 이미지를 보고 채움</p>`

    const tagLine = aiCaughtMore
      ? `<p class="tag win">⚡ 코드는 수치만 쟀는데, AI 눈이 더 잡아냄</p>`
      : aiMissed
        ? `<p class="tag miss">🕳 AI 눈이 정답을 놓친 사각지대</p>`
        : ''

    const frame = aiMissed ? ' missed' : aiCaughtMore ? ' highlight' : ''

    return `
    <figure class="card${frame}">
      <div class="shot"><img src="${esc(m.image)}" alt="${esc(m.label)}" /></div>
      <figcaption>
        <strong class="title">${esc(m.label)}</strong>
        <div class="score-table">
          <div class="srow"><span class="lbl">정답 (이래야 함)</span><span class="val">${TABLE_BADGE[expected] ?? expected}</span></div>
          <div class="srow"><span class="lbl">AI 답</span><span class="val">${aiLevel ? TABLE_BADGE[aiLevel] : '—'}</span></div>
          ${scoreRow}
        </div>
        ${explain}
        ${tagLine}
        <details class="code-detail">
          <summary>코드 측정 (사실만 · 참고) — 판정 ${TABLE_BADGE[m.level]}</summary>
          <ul class="flags">${flags}</ul>
          ${metaBits ? `<div class="meta">${metaBits}</div>` : ''}
        </details>
      </figcaption>
    </figure>`
  })
  .join('\n')

const codeCounts = measurements.reduce((a, m) => ((a[m.level] = (a[m.level] || 0) + 1), a), {})
const divergences = measurements.filter((m) => {
  const al = aiNotes[m.id]?.level
  return al && RANK[al] > RANK[m.level]
}).length

const total = measurements.length
const aiScored = measurements.filter((m) => aiNotes[m.id]?.level).length
const aiHits = measurements.filter((m) => aiNotes[m.id]?.level === m.expected).length
const codeHits = measurements.filter((m) => m.level === m.expected).length
const pct = (n, d) => (d ? Math.round((n / d) * 100) : 0)
const aiScore = pct(aiHits, total)
const codeScore = pct(codeHits, total)

const html = `<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${esc(target)} 변형 갤러리 — 시각 검증</title>
<style>
  :root { font-family: system-ui, sans-serif; color: #0f172a; }
  body { margin: 0; padding: 32px; background: #f1f5f9; }
  h1 { margin: 0 0 4px; font-size: 22px; }
  .sub { margin: 0 0 16px; color: #64748b; font-size: 14px; }
  .summary { margin: 0 0 24px; font-size: 14px; }
  .summary span { margin-right: 14px; }
  .scoreboard { display: flex; gap: 16px; margin: 0 0 20px; flex-wrap: wrap; }
  .score { display: flex; align-items: center; gap: 12px; padding: 14px 18px; border-radius: 12px; background: #fff; border: 1px solid #e2e8f0; min-width: 200px; }
  .score .n { font-size: 30px; font-weight: 800; line-height: 1; }
  .score .l { font-size: 13px; color: #475569; line-height: 1.35; }
  .score .l small { color: #94a3b8; }
  .score-ai { border-color: #3b82f6; } .score-ai .n { color: #2563eb; }
  .score-code .n { color: #64748b; }
  .score-div { border-color: #22c55e; } .score-div .n { color: #16a34a; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }
  .card { margin: 0; background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; }
  .card.highlight { border: 2px solid #22c55e; box-shadow: 0 0 0 4px #dcfce7; }
  .card.missed { border: 2px solid #ef4444; box-shadow: 0 0 0 4px #fee2e2; }
  .shot { background: #f8fafc; display: flex; justify-content: center; padding: 16px; border-bottom: 1px solid #f1f5f9; }
  .shot img { max-width: 100%; height: auto; display: block; }
  figcaption { padding: 14px 16px 14px; }
  .title { display: block; font-size: 15px; font-weight: 700; }
  /* 채점표 — 정답 / AI 답 / 채점 을 세로 정렬해 한눈에 비교 */
  .score-table { margin: 10px 0 0; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
  .srow { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 7px 11px; font-size: 13px; }
  .srow + .srow { border-top: 1px solid #f1f5f9; }
  .srow .lbl { color: #64748b; }
  .srow .val { font-weight: 600; white-space: nowrap; }
  .srow.result .val { font-weight: 800; }
  .srow.result.hit { background: #f0fdf4; } .srow.result.hit .val { color: #16a34a; }
  .srow.result.miss { background: #fef2f2; } .srow.result.miss .val { color: #dc2626; }
  .srow.result.pending { background: #f8fafc; } .srow.result.pending .val { color: #94a3b8; font-weight: 600; }
  .ai-explain { margin: 10px 0 0; font-size: 12.5px; line-height: 1.55; color: #475569; background: #f8fafc; border-radius: 6px; padding: 8px 10px; }
  .ai-explain.win { background: #f0fdf4; }
  .ai-explain.miss { background: #fef2f2; }
  .ai-explain.pending { color: #94a3b8; }
  .tag { margin: 8px 0 0; font-size: 12px; font-weight: 700; }
  .tag.win { color: #15803d; }
  .tag.miss { color: #b91c1c; }
  .code-detail { margin: 10px 0 0; font-size: 12px; color: #64748b; border-top: 1px dashed #e2e8f0; padding-top: 8px; }
  .code-detail summary { cursor: pointer; color: #475569; font-size: 12px; }
  .code-detail ul.flags { margin: 8px 0 0; padding-left: 18px; line-height: 1.6; }
  .code-detail .meta { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
  .code-detail .meta span { font-size: 11px; color: #475569; background: #f1f5f9; border-radius: 6px; padding: 2px 6px; font-variant-numeric: tabular-nums; }
</style>
</head>
<body>
  <h1>${esc(target)} 변형 갤러리 — 시각 검증</h1>
  <p class="sub">변형마다 <b>정답(이래야 함)</b>을 정해두고, <b>AI가 그림만 보고</b> 같은 판정을 내는지 <b>채점</b>합니다. <b style="color:#16a34a">초록 테두리</b> = AI가 코드보다 더 잡은 칸(AI 강점) · <b style="color:#dc2626">빨간 테두리</b> = AI가 정답을 놓친 칸(사각지대).</p>
  <div class="scoreboard">
    <div class="score score-ai">
      <div class="n">${aiScore}점</div>
      <div class="l">AI 자체 분별 점수<br><small>정답 ${aiHits}/${total} 일치 (${aiScored}개 판정)</small></div>
    </div>
    <div class="score score-code">
      <div class="n">${codeScore}점</div>
      <div class="l">코드 점수<br><small>정답 ${codeHits}/${total} 일치 (overflow만 판정)</small></div>
    </div>
    <div class="score score-div">
      <div class="n">${divergences}개</div>
      <div class="l">코드는 수치만,<br>AI 가 잡은 칸 ⚡</div>
    </div>
  </div>
  <p class="summary">
    <span>코드 분포: ✅ ${codeCounts.ok || 0} · 🟥 ${codeCounts.error || 0}</span>
    <span style="color:#94a3b8">총 ${measurements.length}개</span>
  </p>
  <div class="grid">
${cards}
  </div>
</body>
</html>
`

const outPath = `${dir}/index.html`
await writeFile(outPath, html)

if (shouldOpen) {
  const cmd =
    process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'start' : 'xdg-open'
  spawn(cmd, [resolve(outPath)], { stdio: 'ignore', detached: true, shell: process.platform === 'win32' }).unref()
}

console.log(
  JSON.stringify(
    {
      ok: true,
      target,
      out: outPath,
      opened: shouldOpen,
      variants: total,
      aiScore: `${aiScore}점 (${aiHits}/${total})`,
      codeScore: `${codeScore}점 (${codeHits}/${total})`,
      divergences,
    },
    null,
    2,
  ),
)
