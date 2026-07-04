// 기준선(before)과 현재(after) 스크린샷을 변형마다 픽셀 비교한다. (시각 회귀의 "WHAT" 레이어)
//
// 역할 분담(OS.md): 이 스크립트는 "무엇이 바뀌었나"를 정밀하게 잰다 — 1px·미세 색차까지.
//   "그 변화가 진짜 문제냐(MATTER)"는 판정하지 않는다. 그건 AI 눈(visual-comparator)이 한다.
//   여기선 바뀐 변형을 추려 diff 이미지만 만들어, AI 가 "바뀐 것만" 보게 해 비용을 줄인다.
//
// 사용법: node scripts/regress-diff.mjs [target]
//   target 기본값: card  (screenshots/<target>/baseline/ 가 있어야 함 — snapshot-baseline 으로 생성)
// 산출물: screenshots/<target>/diff/<id>.png (바뀐 변형만), 마지막 줄에 JSON 요약(스킬이 파싱)
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from 'node:fs'
import { PNG } from 'pngjs'
import pixelmatch from 'pixelmatch'

const target = process.argv[2] || 'card'
const dir = `screenshots/${target}`
const baseDir = `${dir}/baseline`
const diffDir = `${dir}/diff`

if (!existsSync(baseDir)) {
  console.error(
    `기준선이 없다: ${baseDir} — 먼저 npm run baseline -- ${target} 로 before 를 박아라.`,
  )
  process.exit(1)
}

// 미세 색차도 잡아야 하므로 픽셀 민감도를 높게(threshold 낮게) 둔다.
// 안티앨리어싱 노이즈는 includeAA:false 로 무시 → "진짜 바뀐" 픽셀만 센다.
const PX_THRESHOLD = 0.05
// 이 비율 미만 차이는 렌더링 노이즈로 보고 "변화 없음"으로 친다(AI 호출 절약).
const NOISE_PERCENT = 0.02

const ids = readdirSync(baseDir)
  .filter((f) => f.endsWith('.png'))
  .map((f) => f.replace(/\.png$/, ''))

// 신규 변형 사각지대 방지: baseline 이후 *추가된* 변형(after 에만 존재)도 잡는다.
// 비교할 before 가 없으니 픽셀 diff 불가 — "신규"로 보고하고, 판정은 절대 판정(visual-judge)의 몫.
const afterIds = readdirSync(dir)
  .filter((f) => f.endsWith('.png'))
  .map((f) => f.replace(/\.png$/, ''))
const newIds = afterIds.filter((id) => !ids.includes(id))

mkdirSync(diffDir, { recursive: true })

const results = []
for (const id of newIds) {
  results.push({
    id,
    changed: true,
    newVariant: true,
    reason: '신규 변형 — baseline 없음(비교 불가). visual-judge 절대 판정 필요',
    diffPercent: null,
    diffImage: null,
  })
}
for (const id of ids) {
  const beforePath = `${baseDir}/${id}.png`
  const afterPath = `${dir}/${id}.png`

  if (!existsSync(afterPath)) {
    results.push({ id, changed: true, reason: 'after 스샷 없음(변형 삭제됨?)', diffPercent: null })
    continue
  }

  const before = PNG.sync.read(readFileSync(beforePath))
  const after = PNG.sync.read(readFileSync(afterPath))

  // 크기가 다르면 레이아웃/요소 크기가 바뀐 것 — 픽셀 비교 불가, 그 사실을 변화로 보고.
  if (before.width !== after.width || before.height !== after.height) {
    results.push({
      id,
      changed: true,
      dimensionMismatch: true,
      before: { w: before.width, h: before.height },
      after: { w: after.width, h: after.height },
      diffPercent: null,
      diffImage: null,
      reason: `요소 크기 변경 ${before.width}x${before.height} → ${after.width}x${after.height}`,
    })
    continue
  }

  const { width, height } = before
  const diff = new PNG({ width, height })
  const diffPixels = pixelmatch(before.data, after.data, diff.data, width, height, {
    threshold: PX_THRESHOLD,
    includeAA: false,
  })
  const diffPercent = Number(((diffPixels / (width * height)) * 100).toFixed(3))
  const changed = diffPercent >= NOISE_PERCENT

  let diffImage = null
  if (changed) {
    diffImage = `${diffDir}/${id}.png`
    writeFileSync(diffImage, PNG.sync.write(diff))
  }

  results.push({ id, changed, dimensionMismatch: false, diffPixels, diffPercent, diffImage })
}

const changed = results.filter((r) => r.changed)

// 갤러리 빌더·스킬이 다시 읽을 수 있게 저장한다. comparator 판정은 스킬이 여기에 verdict/note 로 머지한다.
writeFileSync(
  `${dir}/regress.json`,
  JSON.stringify({ target, total: results.length, changedCount: changed.length, results }, null, 2),
)

console.log(
  JSON.stringify(
    {
      ok: true,
      target,
      total: results.length,
      changedCount: changed.length,
      noiseThresholdPercent: NOISE_PERCENT,
      changed: changed.map((r) => ({
        id: r.id,
        diffPercent: r.diffPercent,
        dimensionMismatch: !!r.dimensionMismatch,
        reason: r.reason,
      })),
      results,
    },
    null,
    2,
  ),
)
