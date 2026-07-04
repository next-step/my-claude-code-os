// 갤러리의 모든 변형을 순회하며 (1) 요소 스크린샷을 찍고 (2) "사실"만 측정한다.
// (OS.md 2~3단계) — 컴포넌트 종류와 무관하게 동작한다.
//
// 철학(OS.md): 코드는 사실만 잰다. 판정은 (맥락 무관 깨짐인 overflow 를 빼면) 하지 않는다.
//   - 코드가 단정하는 깨짐: 내용 넘침(잘림) 뿐 — 어떤 컴포넌트/상황에서도 깨짐.
//   - 대비·opacity·색·크기는 *수치*로만 댄다. "그게 문제냐"는 AI 가 맥락 보고 판정.
//   - 글자가 이미지 위에 있으면 대비는 코드로 측정 불가 → AI 눈으로 넘긴다.
//
// 사용법: node scripts/capture-variants.mjs [target] [baseURL]
//   target  기본값: card   (레지스트리 키 — variantRoute 로 연다)
//   baseURL 기본값: .claude/visual.config.json 의 baseUrl (없으면 http://localhost:5173)
// 무대(URL) 종속은 config seam 으로 뺐다 — OS.md "이식성" 참조.
// 산출물: screenshots/<target>/<id>.png, screenshots/<target>/measurements.json
import { chromium } from 'playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import { loadVisualConfig, variantUrl } from '../../.claude/scripts/visual-config.mjs'

const cfg = await loadVisualConfig()
const target = process.argv[2] || 'card'
const baseURL = process.argv[3] || cfg.baseUrl
const url = variantUrl(cfg, baseURL, target)
const outDir = `screenshots/${target}`
await mkdir(outDir, { recursive: true })

function parseRGB(s) {
  const m = s && s.match(/rgba?\(([^)]+)\)/)
  if (!m) return null
  const [r, g, b, a = '1'] = m[1].split(',').map((v) => parseFloat(v))
  return { r, g, b, a: parseFloat(a) }
}
function toHex(s) {
  const c = parseRGB(s)
  if (!c) return null
  const h = (n) => Math.round(n).toString(16).padStart(2, '0')
  return `#${h(c.r)}${h(c.g)}${h(c.b)}`
}
function luminance({ r, g, b }) {
  const f = (v) => {
    const x = v / 255
    return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
}
function contrast(fg, bg, fgOpacity = 1) {
  const f = parseRGB(fg)
  const b = parseRGB(bg)
  if (!f || !b) return null
  const a = f.a * fgOpacity
  const comp = { r: f.r * a + b.r * (1 - a), g: f.g * a + b.g * (1 - a), b: f.b * a + b.b * (1 - a) }
  const L1 = luminance(comp)
  const L2 = luminance(b)
  const [hi, lo] = L1 > L2 ? [L1, L2] : [L2, L1]
  return Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100
}

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 900, height: 700 }, deviceScaleFactor: 1 })
try {
  await page.goto(url, { waitUntil: 'networkidle', timeout: 15_000 })
} catch (e) {
  await browser.close()
  console.error(`${url} 접속 실패 — dev 서버가 떠 있나? (npm run dev)\n원인: ${e.message}`)
  process.exit(1)
}

const ids = await page.$$eval('[data-variant-id]', (els) =>
  els.map((e) => e.getAttribute('data-variant-id')),
)
if (ids.length === 0) {
  await browser.close()
  console.error(
    `변형 0개: ${url} 에 [data-variant-id] 가 없다 — 대상 키 "${target}" 가 레지스트리에 등록됐는지 확인 (visual-list / visual-add).`,
  )
  process.exit(1)
}

const measurements = []
for (const id of ids) {
  const wrapper = page.locator(`[data-variant-id="${id}"]`)
  const comp = wrapper.locator(':scope > *:first-child') // 컴포넌트 루트 (태그 무관)
  await comp.screenshot({ path: `${outDir}/${id}.png` })

  const label = await wrapper.evaluate((w) => w.querySelector(':scope > span')?.textContent ?? '')
  const expected = await wrapper.evaluate((w) => w.getAttribute('data-expected') ?? 'ok')

  const raw = await comp.evaluate((root) => {
    // 직접 텍스트를 가진(=자식이 아니라 자기 자신이 글자를 가진) 보이는 요소들
    const hasDirectText = (n) =>
      [...n.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim())
    const visible = (n) => n.getClientRects().length > 0
    const candidates = [root, ...root.querySelectorAll('*')].filter(
      (n) => n instanceof HTMLElement && hasDirectText(n) && visible(n),
    )

    // 텍스트 요소의 "유효 배경" — 위로 올라가며 첫 불투명 배경색을 찾는다
    const effectiveBg = (node) => {
      let cur = node
      while (cur && cur !== document.documentElement) {
        const c = getComputedStyle(cur).backgroundColor
        const m = c.match(/rgba?\(([^)]+)\)/)
        if (m) {
          const p = m[1].split(',').map(parseFloat)
          const a = p[3] === undefined ? 1 : p[3]
          if (a > 0) return c
        }
        cur = cur.parentElement
      }
      return 'rgb(255, 255, 255)'
    }

    const overlap = (a, b) =>
      a && b && !(a.right <= b.left || a.left >= b.right || a.bottom <= b.top || a.top >= b.bottom)
    const imgs = [...root.querySelectorAll('img')]

    const texts = candidates.map((t) => {
      const rect = t.getBoundingClientRect()
      return {
        text: t.textContent.trim().slice(0, 24),
        truncated: t.scrollWidth > t.clientWidth + 1,
        fontSize: parseFloat(getComputedStyle(t).fontSize),
        color: getComputedStyle(t).color,
        bg: effectiveBg(t),
        overImage: imgs.some((im) => overlap(im.getBoundingClientRect(), rect)),
      }
    })

    return {
      overflowY: root.scrollHeight > root.clientHeight + 1,
      overflowX: root.scrollWidth > root.clientWidth + 1,
      opacity: parseFloat(getComputedStyle(root).opacity),
      rootBg: getComputedStyle(root).backgroundColor,
      texts,
    }
  })

  // 텍스트별 대비 계산 (이미지 위 글자는 측정 불가)
  const texts = raw.texts.map((t) => ({
    text: t.text,
    truncated: t.truncated,
    fontSize: t.fontSize,
    color: toHex(t.color),
    bg: toHex(t.bg),
    overImage: t.overImage,
    contrast: t.overImage ? null : contrast(t.color, t.bg, raw.opacity),
  }))
  const measured = texts.filter((t) => t.contrast != null)
  const minContrast = measured.length ? Math.min(...measured.map((t) => t.contrast)) : null
  const anyOverImage = texts.some((t) => t.overImage)
  const anyTruncated = texts.some((t) => t.truncated)

  // ── 코드가 *단정하는* 깨짐: overflow 만 (맥락 무관) ──
  const flags = []
  if (raw.overflowY || raw.overflowX)
    flags.push({ level: 'error', text: '내용 넘쳐 잘림(overflow)' })

  // ── 판정이 아니라 *사실/정보*로만 (AI 가 맥락 판정) ──
  const notes = []
  if (minContrast != null) notes.push(`최저 대비 ${minContrast}:1 (판정은 AI 맥락)`)
  if (anyTruncated) notes.push('텍스트 말줄임/잘림 있음')
  if (raw.opacity < 1) notes.push(`opacity ${raw.opacity}`)
  if (anyOverImage) notes.push('글자가 이미지 위 — 코드 대비 측정 불가, AI 눈 확인 필요')

  const level = flags.some((f) => f.level === 'error') ? 'error' : 'ok' // 코드는 overflow 만 판정

  measurements.push({
    id,
    label,
    expected,
    image: `${id}.png`,
    overflowY: raw.overflowY,
    overflowX: raw.overflowX,
    opacity: raw.opacity,
    rootBg: toHex(raw.rootBg),
    minContrast,
    anyOverImage,
    anyTruncated,
    texts,
    flags,
    notes,
    level,
  })
}

await browser.close()
await writeFile(`${outDir}/measurements.json`, JSON.stringify(measurements, null, 2))
console.log(
  JSON.stringify(
    {
      ok: true,
      target,
      count: measurements.length,
      summary: measurements.map((m) => ({ id: m.id, codeLevel: m.level, minContrast: m.minContrast })),
    },
    null,
    2,
  ),
)
