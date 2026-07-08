export const meta = {
  name: 'paper-os',
  description: 'Paper-analysis OS: given a paper link, gauge complexity, decide optimal agent count per stage, run analyzer→detail→code→run→design→html with feedback gates. Outputs are organized per paper under output/<slug>/.',
  whenToUse: 'User provides a paper link and wants the full end-to-end paper-analysis pipeline run automatically.',
  phases: [
    { title: 'Triage', detail: 'Fetch the link, measure complexity, decide agent counts + paper slug' },
    { title: 'Intent', detail: 'Load <slug>/00_intent.md (from /interview) so stages honor user intent' },
    { title: 'Analyze', detail: 'analyzer skill → <slug>/01_analysis.md (gated)' },
    { title: 'Detail', detail: 'detail skill → <slug>/03_detail.md (parallel by concept on complex papers)' },
    { title: 'Code', detail: 'code skill → <slug>/04_code.md (parallel by module on large repos)' },
    { title: 'Run', detail: 'code-run skill → <slug>/05_run.md' },
    { title: 'Design', detail: 'mydesign skill → <slug>/design.css' },
    { title: 'Render', detail: 'html skill → <slug>/report.html' },
  ],
}

// ── config ──────────────────────────────────────────────────────────────────
// PORTABLE: ROOT defaults to '.' (the session working directory) so the OS runs
// on any PC / any clone path. Override via args object { link, root, maxParallel }.
// Some launch paths deliver `args` as a JSON string instead of a parsed object
// (observed with scriptPath invocation in this environment). Normalize so an
// object-shaped string ('{...}') becomes a real object; a bare URL string stays a string.
let ARGS = args
if (typeof ARGS === 'string') {
  const t = ARGS.trim()
  if (t.startsWith('{') || t.startsWith('[')) { try { ARGS = JSON.parse(t) } catch (_) {} }
}
const isObj = typeof ARGS === 'object' && ARGS !== null
const ROOT = (isObj && ARGS.root) || '.'
const SK = (n) => `${ROOT}/.claude/skills/${n}/SKILL.md`
// Custom .claude/agents/* are NOT resolvable inside the workflow runtime, so each
// stage runs on the default workflow agent and is told to READ its SKILL.md.

const LINK = typeof ARGS === 'string' ? ARGS : (isObj && ARGS.link)
const MAX_PARALLEL = (isObj && ARGS.maxParallel) || 5
if (!LINK) throw new Error('paper-os: no paper link provided in args (pass a URL string, or { link, root?, maxParallel? })')

// ── A/B knobs (used by /ab-test) ────────────────────────────────────────────
// context: path (relative to ROOT) of a background-knowledge file to inject into
//   every content stage — e.g. 'CONTEXT.md'. Null = don't inject (baseline arm).
// tag: arm label appended to the output folder so A/B runs don't clobber
//   (output/<slug>__A vs output/<slug>__B). Null = plain output/<slug>.
const CTX_FILE = (isObj && ARGS.context) || null
const TAG = (isObj && ARGS.tag) ? String(ARGS.tag).replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 24) : null

// ── per-stage model / reasoning-effort policy ───────────────────────────────
// 모든 단계는 Opus로 돌고, 단계가 요구하는 사고량에 따라 reasoning effort만 차등한다.
// 재튜닝은 여기 한 곳만 고치면 된다 — 아래 모든 agent() 호출이 M(stage)로 이 값을 끌어 쓴다.
// 대화형 .claude/agents/*.md 프론트매터에도 model:opus를 맞춰두었으나, effort 차등은
// 워크플로 런타임 전용이라(agent 프론트매터엔 effort 필드가 없음) 실질 적용은 여기서 일어난다.
const POLICY = {
  triage:  { model: 'opus', effort: 'medium' },
  analyze: { model: 'opus', effort: 'high'   },
  detail:  { model: 'opus', effort: 'medium' },
  code:    { model: 'opus', effort: 'high'   },
  run:     { model: 'opus', effort: 'high'   },
  design:  { model: 'opus', effort: 'medium' },
  render:  { model: 'opus', effort: 'low'    },
  gate:    { model: 'opus', effort: 'medium' },
}
const M = (k) => POLICY[k] || {}

// Per-paper output dir. Assigned after Triage produces a filesystem-safe slug.
// Every stage writes under OUTDIR so each paper gets its own self-contained folder.
let OUTDIR = `${ROOT}/output/_pending`
const P = (f) => `${OUTDIR}/${f}`

const GATE_SCHEMA = {
  type: 'object',
  required: ['verdict', 'score', 'must_fix'],
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'FAIL'] },
    score: { type: 'number' },
    must_fix: { type: 'array', items: { type: 'string' } },
    path: { type: 'string' },
  },
}

const PLAN_SCHEMA = {
  type: 'object',
  required: ['complexity', 'detail_agents', 'code_agents', 'rationale', 'concepts', 'modules', 'slug'],
  properties: {
    complexity: { type: 'string', enum: ['low', 'medium', 'high'] },
    detail_agents: { type: 'number' },
    code_agents: { type: 'number' },
    concepts: { type: 'array', items: { type: 'string' } },
    modules: { type: 'array', items: { type: 'string' } },
    slug: { type: 'string' }, // filesystem-safe paper folder name, e.g. liveedit_2606.26740
    rationale: { type: 'string' },
  },
}

// ── helper: run a stage, gate it, retry once on FAIL ────────────────────────
// Each gated stage has its own per-stage feedback skill: feedback-<stageName>
// (feedback-analysis / feedback-detail / feedback-code / feedback-run / feedback-html).
// Falls back to the generic `feedback` skill only for stages without a dedicated one.
async function gated(stageName, file, runStage) {
  const FB = ['analysis', 'detail', 'code', 'run', 'html'].includes(stageName)
    ? SK('feedback-' + stageName)
    : SK('feedback')
  let out = await runStage()
  let gate = await agent(
    `${ROOT} 작업 디렉토리에서, ${FB} 파일을 Read로 읽고 그 체크리스트에 따라 '${stageName}' 단계 산출물 ${file} 을 검증하라. ${OUTDIR}/feedback_${stageName}.md 로 저장하고 구조화 결과(verdict/score/must_fix/path)를 반환.`,
    { phase: 'Gate:' + stageName, schema: GATE_SCHEMA, label: `gate:${stageName}`, ...M('gate') }
  )
  if (gate && gate.verdict === 'FAIL') {
    log(`[${stageName}] FAIL (${gate.score}/10) → 재시도: ${gate.must_fix.join('; ')}`)
    out = await runStage(gate.must_fix)
    gate = await agent(
      `${ROOT} 에서 ${FB} 를 읽고 '${stageName}' 재검증: ${file}. 직전 지적사항: ${gate.must_fix.join('; ')}. 구조화 결과 반환.`,
      { phase: 'Gate:' + stageName, schema: GATE_SCHEMA, label: `gate:${stageName}:retry`, ...M('gate') }
    )
  }
  return { out, gate }
}

// ── Phase 1: Triage — complexity + agent counts + paper slug ────────────────
phase('Triage')
const plan = await agent(
  `다음 논문 링크를 WebFetch로 가볍게 훑어 복잡도를 산정하라: ${LINK}
신호: 길이/섹션 수, 수식·정리 밀도, 서브시스템/모듈 수, 코드 저장소 규모, 실험 수.
규칙:
- low → detail_agents=1, code_agents=1
- medium → detail_agents=2~3, code_agents=1
- high → detail_agents=3~5, code_agents=2~4
detail은 'concepts'(개념 그룹 라벨 배열)로, code는 'modules'(모듈 라벨 배열)로 분할 단위를 제시.
'slug'은 이 논문의 폴더명으로 쓸 파일시스템 안전 문자열(영문소문자/숫자/._-만, 예: liveedit_2606.26740)로 지어라.
단, output/ 아래에 이 논문의 00_intent.md 가 이미 있으면(Glob으로 확인) 그 폴더명을 slug으로 그대로 재사용하라(/interview가 만든 의도 파일과 폴더를 일치시키기 위함).
동시성 상한 ${MAX_PARALLEL}을 넘기지 말 것. 근거를 rationale에 적어라.`,
  { phase: 'Triage', schema: PLAN_SCHEMA, label: 'triage', ...M('triage') }
)
const nDetail = Math.max(1, Math.min(plan.detail_agents || 1, MAX_PARALLEL))
const nCode = Math.max(1, Math.min(plan.code_agents || 1, MAX_PARALLEL))
const SLUG = String(plan.slug || 'paper').replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 60) || 'paper'
const FOLDER = `${SLUG}${TAG ? '__' + TAG : ''}`  // A/B arm gets its own folder
OUTDIR = `${ROOT}/output/${FOLDER}`
log(`복잡도=${plan.complexity} · detail×${nDetail} · code×${nCode} · 폴더=output/${FOLDER} — ${plan.rationale}`)

// ── Phase: Intent — honor the /interview spec if one exists ─────────────────
// The /interview skill (run interactively BEFORE this workflow) writes
// output/<slug>/00_intent.md. Stages read it and let it override skill defaults.
phase('Intent')
// CTX: A/B background-knowledge preamble. Only present when args.context is set
// (Arm A of an /ab-test run). Appended to every content-stage prompt via INTENT.
const CTX = CTX_FILE
  ? `\n\n[배경지식] 시작 전 ${ROOT}/${CTX_FILE} 파일이 있으면 Read로 읽어 이 프로젝트의 의도·이력·규약을 배경지식으로 참고하라(현재 논문 산출물 생성이 최우선이며, 배경지식은 보조적 참고용일 뿐 그대로 베끼지 말 것).`
  : ''
const INTENT = `\n\n[의도 우선] 시작 전 ${P('00_intent.md')} 파일이 있으면 Read로 먼저 읽고, 거기 적힌 대상/실행위치/실행주체/성공기준·해당 단계 지침을 스킬 기본값보다 우선 적용하라. 없으면 스킬 기본값대로 진행.` + CTX
log(`의도 파일(있으면 적용): output/${FOLDER}/00_intent.md${CTX_FILE ? ` · 배경지식 주입: ${CTX_FILE}` : ''}`)

// ── Phase 2: Analyze (single, gated) ────────────────────────────────────────
phase('Analyze')
const analysis = await gated('analysis', P('01_analysis.md'), (fixes) =>
  agent(
    `작업 디렉토리 ${ROOT}. ${SK('analyzer')} 를 Read로 읽고 그 절차를 정확히 따라, 이 논문을 분석해 ${P('01_analysis.md')} 를 Write로 생성하라(상위 폴더 없으면 생성): ${LINK}` +
      (fixes ? `\n이전 피드백 반영: ${fixes.join('; ')}` : '') +
      `\n끝나면 파일 경로 + 제목 + 한 줄 요약 + 공식 코드 저장소 링크(있으면)를 반환.` + INTENT,
    { phase: 'Analyze', label: 'analyzer', ...M('analyze') }
  )
)

// ── Phase 3: Detail (split by concept on complex papers, then merge) ─────────
phase('Detail')
const conceptLabels = (plan.concepts && plan.concepts.length ? plan.concepts : ['전체']).slice(0, nDetail)
let detailRun
if (conceptLabels.length <= 1) {
  detailRun = (fixes) => agent(
    `${ROOT} 에서 ${SK('detail')} 를 읽고 그 절차대로 ${P('01_analysis.md')} 를 풀어 ${P('03_detail.md')} 를 생성하라.` +
      (fixes ? `\n이전 피드백: ${fixes.join('; ')}` : '') + INTENT,
    { phase: 'Detail', label: 'detail', ...M('detail') })
} else {
  detailRun = async () => {
    await parallel(conceptLabels.map((c, i) => () =>
      agent(`${ROOT} 에서 ${SK('detail')} 의 방식대로 '${c}' 개념만 상세 해설하여 ${P(`03_detail_part${i}.md`)} 로 저장.`,
        { phase: 'Detail', label: `detail:${c}`, ...M('detail') })))
    return agent(`${OUTDIR}/03_detail_part*.md 들을 Read로 모두 읽어 하나로 병합·정리해 ${P('03_detail.md')} 생성(중복 제거, 목차 추가). 병합 후 03_detail_part*.md 중간 파일은 삭제하라.`,
      { phase: 'Detail', label: 'detail:merge', ...M('detail') })
  }
}
const detail = await gated('detail', P('03_detail.md'), detailRun)

// ── Phase 4: Code (split by module on large repos, then merge) ───────────────
phase('Code')
const moduleLabels = (plan.modules && plan.modules.length ? plan.modules : ['전체']).slice(0, nCode)
let codeRun
if (moduleLabels.length <= 1) {
  codeRun = (fixes) => agent(
    `${ROOT} 에서 ${SK('code')} 를 읽고 그 절차대로 구현 저장소를 찾아 분석하고 ${P('04_code.md')} 를 생성하라. 논문 분석은 ${P('01_analysis.md')} 참고.` +
      (fixes ? `\n이전 피드백: ${fixes.join('; ')}` : '') + INTENT,
    { phase: 'Code', label: 'code', ...M('code') })
} else {
  codeRun = async () => {
    await parallel(moduleLabels.map((m, i) => () =>
      agent(`${ROOT} 에서 ${SK('code')} 방식대로 구현 저장소에서 '${m}' 모듈/하위시스템만 분석하여 ${P(`04_code_part${i}.md`)} 저장. 단서는 ${P('01_analysis.md')}.`,
        { phase: 'Code', label: `code:${m}`, ...M('code') })))
    return agent(`${OUTDIR}/04_code_part*.md 들을 Read로 읽어 병합해 ${P('04_code.md')} 생성(논문↔코드 매핑 표 통합). ` +
      `또한 ${SK('code')} 의 '실행 카드 스키마'를 따라 실행 사실만 추린 소형 ${P('04_runcard.md')}(≤ ~1,800자)를 반드시 함께 발행하라(단일 코드 에이전트 경로와 동일하게 — code-run 다운스트림이 이 카드만 읽음). ` +
      `병합 후 04_code_part*.md 중간 파일은 삭제하라. 끝나면 ${P('04_code.md')} 와 ${P('04_runcard.md')} 경로를 보고.`,
      { phase: 'Code', label: 'code:merge', ...M('code') })
  }
}
const code = await gated('code', P('04_code.md'), codeRun)

// ── Phase 5: Run ────────────────────────────────────────────────────────────
phase('Run')
const run = await gated('run', P('05_run.md'), (fixes) =>
  agent(`${ROOT} 에서 ${SK('code-run')} 를 읽고 그 절차대로 ${P('05_run.md')} 를 생성하라. 기본은 원본 레포를 사용자가 자기 터미널에서 돌릴 복붙 명령 블록+가이드이며, 클로드가 직접 실행하지 않는다(스킬 규칙 준수). 근거는 소형 실행 카드 ${P('04_runcard.md')} 를 우선 읽어라(없을 때만 ${P('04_code.md')} 전체로 폴백 — 컨텍스트 절감).` +
    (fixes ? `\n이전 피드백: ${fixes.join('; ')}` : '') + INTENT,
    { phase: 'Run', label: 'code-run', ...M('run') }))

// ── Phase 6: Design ─────────────────────────────────────────────────────────
phase('Design')
const design = await agent(
  `${ROOT} 에서 ${SK('mydesign')} 를 읽고 그 절차대로 ${P('design.css')} 를 생성(순백·고대비·720px 규약).`,
  { phase: 'Design', label: 'mydesign', ...M('design') })

// ── Phase 7: Render ─────────────────────────────────────────────────────────
phase('Render')
const html = await gated('html', P('report.html'), (fixes) =>
  agent(`${ROOT} 에서 ${SK('html')} 를 읽고 그 절차대로 ${P('01_analysis.md')}, ${P('03_detail.md')}, ${P('04_code.md')} 와 ${P('design.css')} 를 합쳐 자급식(인라인 CSS) ${P('report.html')} 생성.` +
    (fixes ? `\n이전 피드백: ${fixes.join('; ')}` : '') + INTENT,
    { phase: 'Render', label: 'html', ...M('render') }))

// ── Summary ─────────────────────────────────────────────────────────────────
const rel = (f) => `output/${FOLDER}/${f}`
return {
  link: LINK,
  slug: SLUG,
  tag: TAG,
  context: CTX_FILE,
  folder: `output/${FOLDER}/`,
  plan: { complexity: plan.complexity, detail_agents: nDetail, code_agents: nCode, rationale: plan.rationale },
  gates: {
    analysis: analysis.gate && analysis.gate.verdict,
    detail: detail.gate && detail.gate.verdict,
    code: code.gate && code.gate.verdict,
    run: run.gate && run.gate.verdict,
    html: html.gate && html.gate.verdict,
  },
  outputs: [
    rel('01_analysis.md'), rel('03_detail.md'), rel('04_code.md'),
    rel('05_run.md'), rel('design.css'), rel('report.html'), rel('run/'),
  ],
  final: rel('report.html'),
}
