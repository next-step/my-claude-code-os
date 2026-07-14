export const meta = {
  name: 'implement-loop',
  description: 'Loop that builds a clickable paper-reproduction program (via /code-run) and scores it (via /score) against the paper\'s reported results, iterating in INDEPENDENT contexts until the score hits a threshold. A triage step judges complexity and picks the optimal number of build agents per loop, which fan out in parallel and are merged into one self-contained index.html. Learnings persist to LEARNINGS.md and feed the next loop. Analyzer/code/code-run agents also communicate through a shared CHANNEL.md blackboard. Realizes loop.txt: 클릭 실행 프로그램 · 점수화 · 점수 도달까지 루프 · 독립 컨텍스트 · 학습 인계 · 적정 에이전트 수 판단 후 병렬 · 에이전트 간 소통.',
  whenToUse: 'After /analyzer+/code produced output/<slug>/ for a paper, run this to build & self-improve a double-click-to-run reproduction until it scores >= threshold.',
  phases: [
    { title: 'Setup', detail: 'Resolve slug/threshold/maxIters/maxParallel, locate output/<slug>/' },
    { title: 'Triage', detail: 'Judge reproduction complexity → decide build-agent count + component split' },
    { title: 'Loop', detail: 'Per iteration (independent contexts): parallel component builds → merge → sync (analyzer/code answer code-run via CHANNEL.md) → score (incl. repo-fidelity: WebFetch real repo & compare) → distill learnings; stop at threshold' },
    { title: 'Report', detail: 'Summarize iterations, final score, app path' },
  ],
}

// ── config ──────────────────────────────────────────────────────────────────
// PORTABLE: ROOT defaults to '.' so the loop runs on any clone path.
// Args (object or JSON string): { slug, threshold?, maxIters?, maxParallel?, root? }.
let ARGS = args
if (typeof ARGS === 'string') {
  const t = ARGS.trim()
  if (t.startsWith('{') || t.startsWith('[')) { try { ARGS = JSON.parse(t) } catch (_) {} }
}
const isObj = typeof ARGS === 'object' && ARGS !== null
const ROOT = (isObj && ARGS.root) || '.'
const SLUG_RAW = typeof ARGS === 'string' ? ARGS : (isObj && ARGS.slug)
if (!SLUG_RAW) throw new Error('implement-loop: no paper slug provided (pass a slug string, or { slug, threshold?, maxIters?, maxParallel?, root? }). e.g. "liveedit_2606.26740"')
const SLUG = String(SLUG_RAW).replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 60)

const THRESHOLD = (isObj && ARGS.threshold) || 85
const MAX_ITERS = (isObj && ARGS.maxIters) || 4
const MAX_PARALLEL = (isObj && ARGS.maxParallel) || 4
// Optional externally-injected guidance for THIS run (e.g. verified corrections
// to apply). Appended to every build prompt and surfaced to score. Empty = none.
const NOTES = (isObj && ARGS.notes) || ''
const NOTE = NOTES ? `\n\n[이번 실행 반영 지침 — 최우선]\n${NOTES}` : ''
// 구현 매체: 'terminal' = 실제 실행되는 CLI/서버 프로젝트(모델·컴퓨트 태스크 기본),
//           'html' = 순수 클라이언트사이드 알고리즘일 때 자급식 실행 HTML.
const MEDIUM = ((isObj && ARGS.medium) || 'html').toLowerCase()

const SK = (n) => `${ROOT}/.claude/skills/${n}/SKILL.md`
const OUTDIR = `${ROOT}/output/${SLUG}`
const APP = `${OUTDIR}/app`
const P = (f) => `${APP}/${f}`
const B = (f) => `${APP}/_build/${f}` // scratch fragments from parallel component builds
const CHANNEL = `${OUTDIR}/CHANNEL.md` // shared blackboard: analyzer ↔ code ↔ code-run
const clamp = (n, lo, hi) => Math.max(lo, Math.min(n | 0 || lo, hi))
const M = { model: 'opus', effort: 'high' }
const M_LEARN = { model: 'opus', effort: 'medium' }

// Communication directive appended to every build prompt: read answers from
// analyzer/code, and post questions back to them when the paper materials are
// missing/contradictory/ambiguous (loop.txt 추가 요구: 에이전트 간 소통).
const CH = `\n[소통] ${CHANNEL} 를 Read로 먼저 읽어 analyzer/code가 남긴 답변(→ code-run RESOLVED)을 반영하라. 재현에 꼭 필요한데 분석/코드에 없거나 모순되거나 조건이 불명확한 정보가 있으면, 지어내지 말고 '## Q<n> [code-run → analyzer] (OPEN)' 또는 '## Q<n> [code-run → code] (OPEN)' 형식으로 ${CHANNEL} 끝에 append(기존 삭제 금지). 파일이 없으면 헤더와 함께 새로 만든다.`

// Structured score returned by each scoring pass. Mirrors /score's scorecard.json.
const SCORE_SCHEMA = {
  type: 'object',
  required: ['total', 'verdict', 'must_fix', 'learned'],
  properties: {
    total: { type: 'number' },
    verdict: { type: 'string', enum: ['PASS', 'FAIL'] },
    must_fix: { type: 'array', items: { type: 'string' } },
    learned: { type: 'array', items: { type: 'string' } },
  },
}

// Triage plan: how many build agents and how to split the app into components.
const PLAN_SCHEMA = {
  type: 'object',
  required: ['build_agents', 'components', 'rationale'],
  properties: {
    build_agents: { type: 'number' }, // 1..MAX_PARALLEL
    components: { type: 'array', items: { type: 'string' } }, // parallel-buildable aspect labels
    rationale: { type: 'string' },
  },
}

// ── Phase 1: Setup ───────────────────────────────────────────────────────────
phase('Setup')
log(`대상=output/${SLUG}/ · 목표점수=${THRESHOLD} · 최대루프=${MAX_ITERS} · 동시성상한=${MAX_PARALLEL} · 학습파일=output/${SLUG}/app/LEARNINGS.md`)

// ── Phase 2: Triage — judge complexity → optimal build-agent count + split ────
// Mirrors paper-os: gauge the reproduction task's complexity ONCE, then let every
// loop fan out that many parallel component builders. (Complexity of the paper
// doesn't change between loops; only the build content improves.)
phase('Triage')
const plan = await agent(
  `작업 디렉토리 ${ROOT}. 논문 ${SLUG} 의 **클릭 실행형 재현 프로그램(단일 자급식 index.html)** 을 만드는 작업의 복잡도를 산정하라.
${OUTDIR}/01_analysis.md 와 ${OUTDIR}/04_code.md 를 Read로 훑어라.
신호: 재현할 파이프라인 단계 수, 보고된 지표/벤치마크/성능테스트 수, 인터랙션 요소 수, 시각화 난이도.
규칙: 단순하면 build_agents=1, 복잡하면 최대 ${MAX_PARALLEL}까지. 2 이상이면 서로 겹치지 않게 병렬로 만들 수 있는 컴포넌트 라벨을 'components'에 그 개수만큼 제시하라.
좋은 분할 예: ["파이프라인 단계 애니메이션", "성능지표/벤치마크 패널", "인터랙션 토글+콘솔 로그 스트림", "레이아웃/정직성 배너/조립 스캐폴드"].
근거를 rationale에 적어라. 동시성 상한 ${MAX_PARALLEL} 초과 금지.`,
  { phase: 'Triage', schema: PLAN_SCHEMA, label: 'triage', model: 'opus', effort: 'medium' }
)
const nBuild = clamp(plan.build_agents || 1, 1, MAX_PARALLEL)
const components = (plan.components && plan.components.length ? plan.components : ['전체']).slice(0, nBuild)
log(`빌드 에이전트×${components.length} ${components.length > 1 ? '(병렬 컴포넌트→병합)' : '(단일 빌드)'} — ${plan.rationale}`)

// ── build stage: 1 agent, or N parallel component agents + a merge agent ──────
// loop.txt(추가 요구): "각 루프도 적정 에이전트 수를 판단해 병렬처리". N>1이면 컴포넌트별
// 병렬 빌더가 조각을 쓰고, 병합 에이전트가 하나의 자급식 index.html로 조립한다.
async function buildStage(i, prior) {
  // 터미널 매체: 단일 빌드로 실제 실행되는 runnable 프로젝트를 만든다(HTML 조각 병합 없음).
  if (MEDIUM === 'terminal') {
    return agent(
      `작업 디렉토리 ${ROOT}. ${SK('code-run')} 를 Read로 읽고 그 절차대로, 논문 ${SLUG} 의 **터미널에서 실제 실행되는 runnable 프로젝트**를 ${APP}/ 아래에 만들어라(개선하라).
${prior}
입력: ${OUTDIR}/01_analysis.md(방법·태스크·지표 정본), ${OUTDIR}/04_code.md(진입점·의존성·실구현 가능 범위).
산출: ${APP}/ 아래 — 진입 스크립트(예: main.py/cli.py)+핵심 구현 모듈+**버전 고정 requirements**(또는 package.json)+run.ps1/run.sh+README(복붙 설치→실행 명령·예시 입출력)+작은 샘플 입력(인자 없이도 동작). 그리고 ${OUTDIR}/05_run.md(실행 가이드)와 ${P('REPRODUCE.md')}(무엇을 실제 구현/실행했나 ↔ 논문 근거).
논문의 방법을 **실제 코드로 구현**하라(가능하면 실제 라이브러리/모델/알고리즘 호출; 시각화·대시보드가 목표 아님). 정말 못 구하는 부분(독점 가중치 등)만 라벨된 stand-in으로 두고 명시. 하드코딩된 결과·가짜 로그 금지.
이 환경에서 런타임이 되면 직접 실행해 로그를 남기고, 안 되면(스텁 python 등) 복붙 명령 + '사용자 실행 필요/미실행'으로 정직하게 표기.
끝나면 진입점 경로 + 복붙 실행 명령을 반환.` + CH + NOTE,
      { phase: `Iter${i}:build`, label: `build#${i}`, ...M }
    )
  }
  if (components.length <= 1) {
    return agent(
      `작업 디렉토리 ${ROOT}. ${SK('code-run')} 를 Read로 읽고 그 절차대로 논문 ${SLUG} 의 클릭 실행형 재현 프로그램을 만들어라(개선하라).
${prior}
입력: ${OUTDIR}/01_analysis.md(논문 보고값 정본), ${OUTDIR}/04_code.md.
산출: ${P('index.html')}(단일·자급식·더블클릭·외부요청0), ${P('REPRODUCE.md')}, ${OUTDIR}/05_run.md.
성능 테스트/벤치마크가 있으면 반드시 포함하고 화면 수치는 전부 논문 보고값으로 라벨링(지어내기 금지). 끝나면 index.html 경로와 개선점 반환.` + CH + NOTE,
      { phase: `Iter${i}:build`, label: `build#${i}`, ...M }
    )
  }
  // N개 컴포넌트 병렬 빌드 → 조각 파일
  await parallel(components.map((c, idx) => () =>
    agent(
      `작업 디렉토리 ${ROOT}. ${SK('code-run')} 의 원칙(자급식·클릭실행·논문 보고값만·정직성)에 따라, 논문 ${SLUG} 재현 프로그램의 **'${c}' 컴포넌트만** 만들어라.
${prior}
입력: ${OUTDIR}/01_analysis.md(논문 보고값 정본), ${OUTDIR}/04_code.md.
이 컴포넌트에 필요한 HTML 조각 + <style> 규칙 + <script> 로직을, 다른 컴포넌트와 충돌하지 않도록 **고유 접두사/네임스페이스**로 작성해 ${B(`part${idx}.md`)} 에 저장하라(코드블록으로). 외부 요청 금지(인라인/data URI). 이 컴포넌트가 재현하는 논문 보고값도 함께 적어라.` + CH + NOTE,
      { phase: `Iter${i}:build`, label: `build#${i}:${c}`, ...M }
    )))
  // 병합 → 단일 자급식 index.html
  return agent(
    `작업 디렉토리 ${ROOT}. ${SK('code-run')} 를 Read로 읽고, ${APP}/_build/part*.md 조각들을 모두 Read로 읽어 **하나의 자급식 ${P('index.html')}** 로 조립하라.
${prior}
요구: 단일 파일·외부요청0·더블클릭 실행·콘솔 에러 없음. 조각들의 style/script를 통합(중복·충돌 제거)하고, 상단 "실행" 버튼→파이프라인 재생→결과 패널이 매끄럽게 흐르게 하라. 정직성 배너와 원본 레포 링크 포함.
또한 ${P('REPRODUCE.md')}(재현항목↔논문 보고값 표)와 ${OUTDIR}/05_run.md(클릭 실행 가이드)를 발행하라. 병합 후 ${APP}/_build/ 조각 파일은 삭제. 끝나면 index.html 경로와 통합 결과를 반환.` + CH + NOTE,
    { phase: `Iter${i}:merge`, label: `build#${i}:merge`, ...M }
  )
}

// ── Phase 3: Loop — build(병렬) → score → learn, each INDEPENDENT context ─────
// loop.txt #4(독립 컨텍스트): 모든 agent() 호출이 새 subagent → 깨끗한 컨텍스트.
// loop.txt #5(학습 인계): distill 단계가 LEARNINGS.md에 누적, 다음 루프 빌더가 먼저 읽음.
// loop.txt #3(점수 도달까지): verdict PASS(total>=THRESHOLD) 즉시 종료.
phase('Loop')
const history = []
let passed = false
let last = null

for (let i = 1; i <= MAX_ITERS; i++) {
  const prior = i === 1
    ? `이번 실행의 첫 루프다. 이전 실행 산출물(${P('index.html')}·${P('LEARNINGS.md')}·${P('scorecard.json')}·${CHANNEL})이 이미 있으면 Read로 읽어 **처음부터 다시 만들지 말고 이어서 개선**하라(재실행일 수 있음). 위 [이번 실행 반영 지침]이 있으면 그것부터 반영.`
    : `이번은 ${i}번째 루프다. 직전 총점 ${last ? last.total : '?'}/100 (목표 ${THRESHOLD}). 반드시 ${P('LEARNINGS.md')} 와 ${P('scorecard.json')} 를 먼저 Read로 읽고, must_fix 항목부터 고쳐라.`

  // build (병렬 컴포넌트 → 병합, 또는 단일) — 각 조각도 독립 컨텍스트
  await buildStage(i, prior)

  // sync (독립 컨텍스트) — analyzer/code 역할로 code-run이 남긴 질문에 응답.
  // loop.txt 추가 요구(에이전트 간 소통): build가 CHANNEL에 남긴 OPEN 질문을
  //   논문/코드 근거로 해소해, 다음 루프 build가 반영하게 한다.
  await agent(
    `작업 디렉토리 ${ROOT}. 너는 이 논문의 **analyzer + code 역할**로서, 재현 빌더(code-run)의 질문에 답한다.
${CHANNEL} 를 Read로 읽어라(없으면 이번엔 할 일 없음). '[code-run → analyzer]' 또는 '[code-run → code]' 로 온 OPEN 질문 각각에 대해:
- ${OUTDIR}/01_analysis.md(논문 보고값 정본)와 ${OUTDIR}/04_code.md(저장소/실행 사실)를 근거로 답을 찾아,
- '## A<n> [analyzer → code-run] (RESOLVED Q<n>)' 또는 '## A<n> [code → code-run] (RESOLVED Q<n>)' 형식으로 ${CHANNEL} 끝에 append하고, 해당 Q의 (OPEN)을 (RESOLVED)로 바꿔라.
- 근거로도 확정 못 하면 '(RESOLVED: 원문 미보고)'로 정직하게 닫아라(지어내기 금지).
기존 내용 삭제 금지. 답변한 질문 수를 반환.`,
    { phase: `Iter${i}:sync`, label: `sync#${i}`, ...M_LEARN }
  )

  // score (독립 컨텍스트) — scorecard.json/md 기록 + 구조화 verdict 반환
  const score = await agent(
    `작업 디렉토리 ${ROOT}. ${SK('score')} 를 Read로 읽고 그 기준(총 100점, **6축 — 최우선 축은 실제 실행 구현(functional_reproduction, 25점), 실제 코드 대조(repo_fidelity, 20점) 포함**)에 따라 논문 ${SLUG} 의 산출물(${MEDIUM === 'terminal' ? `${APP}/ 아래 runnable 프로젝트 파일들` : P('index.html')})을 채점하라.
임계값 threshold=${THRESHOLD}. 현재 iteration=${i}. 구현 매체=${MEDIUM}.
**실제 실행 검증(최우선)**: ${MEDIUM === 'terminal'
      ? `${APP}/ 의 진입 스크립트·핵심 모듈 코드를 Read로 읽어, 논문 태스크와 방법이 하드코딩/가짜로그가 아니라 **실제 코드로 구현**됐는지, 복붙 명령으로 실행 시 실제 출력이 나오는 구조인지(의존성 고정·진입점·샘플 입력) 확인하고 functional_checks에 남겨라. 이 환경 런타임이 되면 실제 실행해 확인, 안 되면 runnable 구조로 판정하되 미실행 명시.`
      : `index.html의 JS 로직을 읽어 논문 태스크와 핵심 알고리즘이 하드코딩/애니메이션이 아니라 **실제 계산으로 구현**됐는지 확인하고 functional_checks에 남겨라.`}
정본은 ${OUTDIR}/01_analysis.md 이며, ${P('REPRODUCE.md')} 주장과 실제 코드를 대조하라. 실행 가능성은 ${MEDIUM === 'terminal' ? `requirements 버전 고정·진입점·run.*/README 명령·샘플 입력` : `index.html 자급식(외부 http/src/cdn/fetch 참조 검사)`}으로 판정.
**실제 코드 대조(repo_fidelity)**: 공식 저장소 URL(${OUTDIR}/01_analysis.md §8·${OUTDIR}/04_code.md·${P('REPRODUCE.md')}에서 확인)을 찾아, WebFetch로 레포 실제 소스(config yaml·진입 스크립트·추론 파이프라인·모델 소스)를 직접 읽어 앱이 주장한 코드 수준 값(예: chunk 크기·denoise step 리스트·prune 비율·마스크 식·베이스 모델)을 하나씩 검증하라. 필요하면 먼저 ToolSearch로 'select:WebFetch'를 로드. 대조 결과는 scorecard.json의 repo_checks에 파일·실제값·일치여부로 남겨라. WebFetch가 불가하면 그 사실을 명시하고 이 축을 추정으로 채우지 말 것.
${P('scorecard.json')}(iteration=${i}, threshold=${THRESHOLD} 기입)와 ${P('scorecard.md')} 를 Write로 저장하고, 구조화 결과(total/verdict/must_fix/learned)를 반환.`,
    { phase: `Iter${i}:score`, label: `score#${i}`, schema: SCORE_SCHEMA, ...M }
  )
  last = score
  history.push({ iter: i, total: score ? score.total : null, verdict: score ? score.verdict : null })
  log(`루프 ${i}/${MAX_ITERS}: ${score ? score.total : '?'}/100 → ${score ? score.verdict : 'ERROR'}${score && score.must_fix && score.must_fix.length ? ' · 미달: ' + score.must_fix.slice(0, 3).join('; ') : ''}`)

  // distill learnings → LEARNINGS.md (독립 컨텍스트, 인계용)
  if (score) {
    await agent(
      `작업 디렉토리 ${ROOT}. 논문 ${SLUG} 재현 루프의 **학습 로그**를 갱신하라(loop.txt: 배운 내용을 파일로 저장해 다음 루프가 참고).
${P('LEARNINGS.md')} 가 있으면 Read로 읽고 없으면 새로 만든다. 맨 위 한 줄 설명 뒤에, 이번 루프 섹션을 **누적 추가**하라(기존 섹션 삭제 금지):

## 루프 ${i} — 총점 ${score.total}/100 (${score.verdict})
- 이번에 배운 것: ${(score.learned || []).join(' / ') || '(없음)'}
- 다음 루프가 고칠 것(must_fix): ${(score.must_fix || []).join(' / ') || '(없음)'}

다음 루프 빌더가 이 파일만 읽어도 개선점을 알도록 재사용 가능한 교훈 위주로 간결히. 저장 후 경로 반환.`,
      { phase: `Iter${i}:learn`, label: `learn#${i}`, ...M_LEARN }
    )
  }

  if (score && score.verdict === 'PASS') { passed = true; log(`목표 점수 도달 (${score.total} ≥ ${THRESHOLD}) — 루프 종료`); break }
}

// ── Phase 4: Report ──────────────────────────────────────────────────────────
phase('Report')
if (!passed) log(`최대 루프(${MAX_ITERS}) 소진. 최고점 ${Math.max(...history.map(h => h.total || 0))}/100 (목표 ${THRESHOLD} 미달) — LEARNINGS.md에 다음 개선점 기록됨.`)

const rel = (f) => `output/${SLUG}/app/${f}`
return {
  slug: SLUG,
  threshold: THRESHOLD,
  build_agents: components.length,
  components,
  passed,
  iterations: history,
  final_total: last ? last.total : null,
  medium: MEDIUM,
  app: MEDIUM === 'terminal' ? `output/${SLUG}/app/ (README의 복붙 명령으로 실행)` : rel('index.html'),
  scorecard: rel('scorecard.json'),
  learnings: rel('LEARNINGS.md'),
  channel: `output/${SLUG}/CHANNEL.md`,
  open: MEDIUM === 'terminal'
    ? `cd output/${SLUG}/app && (pip install -r requirements.txt 후) python main.py --mode evaluate 등으로 실행 — README 참고.`
    : `output/${SLUG}/app/index.html 를 더블클릭해서 여세요.`,
}
