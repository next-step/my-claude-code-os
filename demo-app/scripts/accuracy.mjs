// AI 눈 판정을 "정답(expected)"에 대고 채점한다 — 자기일관성이 아니라 정확도(PASS^N).
//
// 왜: confidence.json 의 agreement(일치율)는 "N번이 서로 얼마나 일치하나"(자기일관성)일 뿐,
//     "정답과 맞았나"(정확도)가 아니다. 그래서 일치율 100%인데 확신에 차서 '틀린' 사각지대
//     (예: 고립 크림 tone-c 를 N번 모두 '정상'으로 오판)를 못 드러낸다.
//     이 스크립트가 confidence.json 의 votes 를 measurements.json 의 expected 에 대고 채점해
//     그 사각지대를 숫자로 드러낸다. 채점 규칙은 build-gallery 와 동일한 완전일치(level === expected).
//
// 사용법:
//   node scripts/accuracy.mjs [target]                 정확도 계산 → accuracy.json 기록 + 표 출력
//   node scripts/accuracy.mjs [target] --save <label>  현재 accuracy 를 마일스톤으로 고정
//   node scripts/accuracy.mjs [target] --vs <label>    현재 vs 저장된 마일스톤 비교(델타)
//   target 기본값: card
//
// 산출물: screenshots/<target>/accuracy.json                 (작업용·재생성됨 → git 무시)
//         accuracy-history/<target>/<label>.json             (--save 마일스톤 → git 추적, 주차 전/후 보고용)
import { readFile, writeFile, mkdir } from 'node:fs/promises'

const LEVELS = ['ok', 'warn', 'error']

function parseArgs(argv) {
  const rest = argv.slice(2)
  const target = rest[0] && !rest[0].startsWith('--') ? rest.shift() : 'card'
  let save = null
  let vs = null
  for (let i = 0; i < rest.length; i++) {
    if (rest[i] === '--save') save = rest[++i]
    else if (rest[i] === '--vs') vs = rest[++i]
  }
  return { target, save, vs }
}

async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf-8'))
}

function pct(n, d) {
  return d ? Math.round((n / d) * 1000) / 10 : 0
}

// confidence.json(votes) + measurements(expected) → 변형별 정확도 + 요약.
function score(confidence, measurements) {
  const expectedById = new Map(measurements.map((m) => [m.id, m.expected]))
  const variants = {}
  let majorityCorrect = 0
  let votesTotal = 0
  let votesForExpectedTotal = 0
  const misses = []

  for (const [id, c] of Object.entries(confidence)) {
    const expected = expectedById.get(id)
    if (!expected) continue // measurements 에 없는 변형은 채점 불가 — 건너뛴다.
    const votes = c.votes || {}
    const n = c.n || Object.values(votes).reduce((a, b) => a + b, 0)
    const votesForExpected = votes[expected] || 0
    const correct = c.majority === expected
    const passN = n ? Math.round((votesForExpected / n) * 100) / 100 : 0

    variants[id] = { expected, majority: c.majority, correct, passN, n, votesForExpected }
    if (correct) majorityCorrect++
    else misses.push(id)
    votesTotal += n
    votesForExpectedTotal += votesForExpected
  }

  const total = Object.keys(variants).length
  const summary = {
    total,
    majorityCorrect,
    majorityAccuracy: pct(majorityCorrect, total), // 다수결이 정답과 맞은 변형 비율(%)
    voteAccuracy: pct(votesForExpectedTotal, votesTotal), // 개별 표 단위 정답률(%) = 기대 PASS 확률
    misses, // 다수결이 틀린 변형(사각지대 후보)
  }
  return { summary, variants }
}

const LEVEL_KR = { ok: '정상', warn: '주의', error: '깨짐' }

function renderTable(acc) {
  const rows = Object.entries(acc.variants).map(([id, v]) => {
    const mark = v.correct ? '✅' : '❌'
    const passPct = Math.round(v.passN * 100)
    return `| ${id} | ${LEVEL_KR[v.expected]} | ${LEVEL_KR[v.majority] ?? v.majority} | ${mark} | ${v.votesForExpected}/${v.n} (${passPct}%) |`
  })
  const s = acc.summary
  return [
    `🎯 정확도 채점 (정답 대비, N회 블라인드)`,
    ``,
    `| 변형 | 정답 | 다수결 | 정답일치 | PASS^N |`,
    `|------|------|--------|----------|--------|`,
    ...rows,
    ``,
    `다수결 정답률: ${s.majorityCorrect}/${s.total} (${s.majorityAccuracy}%)  ·  표 단위 정답률: ${s.voteAccuracy}%`,
    s.misses.length ? `사각지대(다수결 오답): ${s.misses.join(', ')}` : `사각지대 없음 — 전건 정답`,
  ].join('\n')
}

function renderCompare(cur, base, label) {
  const ids = new Set([...Object.keys(cur.variants), ...Object.keys(base.variants)])
  const rows = []
  for (const id of ids) {
    const a = base.variants[id]
    const b = cur.variants[id]
    const was = a ? (a.correct ? '✅' : '❌') : '—'
    const now = b ? (b.correct ? '✅' : '❌') : '—'
    let move = ''
    if (a && b && a.correct !== b.correct) move = b.correct ? ' ⬆︎ 개선' : ' ⬇︎ 후퇴'
    if (was !== now || move) rows.push(`| ${id} | ${was} → ${now} |${move} |`)
  }
  const dMaj = cur.summary.majorityAccuracy - base.summary.majorityAccuracy
  const sign = dMaj > 0 ? '+' : ''
  return [
    `🔀 정확도 비교 — 현재 vs "${label}"`,
    ``,
    rows.length ? `| 변형 | ${label} → 현재 | 변화 |` : `변형별 정답일치 변동 없음.`,
    ...(rows.length ? [`|------|------|------|`, ...rows] : []),
    ``,
    `다수결 정답률: ${base.summary.majorityAccuracy}% → ${cur.summary.majorityAccuracy}% (${sign}${Math.round(dMaj * 10) / 10}%p)`,
  ].join('\n')
}

async function main() {
  const { target, save, vs } = parseArgs(process.argv)
  const dir = `screenshots/${target}`

  let confidence, measurements
  try {
    confidence = await readJson(`${dir}/confidence.json`)
  } catch {
    console.error(`confidence.json 이 없다: ${dir} — 먼저 visual-confidence 로 N회 판정을 돌려라.`)
    process.exit(1)
  }
  try {
    measurements = await readJson(`${dir}/measurements.json`)
  } catch {
    console.error(`measurements.json 이 없다: ${dir} — 먼저 npm run capture -- ${target} 를 돌려라.`)
    process.exit(1)
  }

  // 마일스톤은 screenshots/(git 무시) 밖의 추적되는 위치에 둔다 — 주차 전/후 보고용으로 보존돼야 하므로.
  const histDir = `accuracy-history/${target}`

  const acc = score(confidence, measurements)
  await writeFile(`${dir}/accuracy.json`, JSON.stringify(acc, null, 2) + '\n')

  // 비교 모드: 저장된 마일스톤과 델타.
  if (vs) {
    let base
    try {
      base = await readJson(`${histDir}/${vs}.json`)
    } catch {
      console.error(`마일스톤이 없다: ${histDir}/${vs}.json — --save ${vs} 로 먼저 고정해라.`)
      process.exit(1)
    }
    console.log(renderCompare(acc, base, vs))
    return
  }

  // 저장 모드: 현재 정확도를 마일스톤으로 고정.
  if (save) {
    await mkdir(histDir, { recursive: true })
    await writeFile(`${histDir}/${save}.json`, JSON.stringify(acc, null, 2) + '\n')
    console.log(renderTable(acc))
    console.log(`\n📌 마일스톤 고정: ${histDir}/${save}.json (git 추적)`)
    return
  }

  console.log(renderTable(acc))
}

main()
