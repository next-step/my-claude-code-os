// 지정한 URL을 열어 컴포넌트(또는 전체 페이지) 스크린샷을 찍어 저장한다.
//
// 사용법:
//   node scripts/screenshot.mjs <출력경로.png> [URL] [선택자]
//   - URL    기본값: .claude/visual.config.json 의 baseUrl (없으면 http://localhost:5173)
//   - 선택자 기본값: [data-testid="demo-button"]  ('page' 를 주면 전체 페이지)
//
// 예) node scripts/screenshot.mjs screenshots/before.png
//     node scripts/screenshot.mjs screenshots/full.png http://localhost:5173 page
import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import { dirname } from 'node:path'
import { loadVisualConfig } from '../../.claude/scripts/visual-config.mjs'

const cfg = await loadVisualConfig()
const outPath = process.argv[2]
const url = process.argv[3] || cfg.baseUrl
const selector = process.argv[4] || '[data-testid="demo-button"]'

if (!outPath) {
  console.error('출력 경로를 첫 번째 인자로 넘겨주세요. 예: screenshots/before.png')
  process.exit(1)
}

await mkdir(dirname(outPath), { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({
  viewport: { width: 800, height: 600 },
  deviceScaleFactor: 1, // 화면 배율 고정 — 전/후 픽셀 비교 일관성 확보
})

await page.goto(url, { waitUntil: 'networkidle' })

if (selector === 'page') {
  await page.screenshot({ path: outPath })
} else {
  const el = page.locator(selector)
  await el.waitFor({ state: 'visible' })
  await el.screenshot({ path: outPath })
}

await browser.close()
console.log(JSON.stringify({ ok: true, outPath, url, selector }))
