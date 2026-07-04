// 시각 검증 "무대(stage)" 설정의 단일 이음새(seam).
//
// 촬영 스크립트·스킬이 demo-app 값을 하드코딩하지 않고 여기서 읽는다.
// 무대에 종속되는 값은 딱 둘 — dev 서버 주소(baseUrl)와 변형을 고립 렌더하는 경로(variantRoute).
//   - 무대가 이미 있는 프로젝트(demo-app, Storybook…) → 이 두 값만 바꾸면 "연결".
//   - 무대가 없는 프로젝트 → 온보딩(스캐폴드/어댑트)이 무대를 심고 이 설정을 발급 (OS.md 8단계).
//
// 견고성 약속: 설정이 없거나 · 깨졌거나 · 값이 이상해도 절대 크래시하지 않는다 —
// 기본값(=현재 demo-app 동작)으로 폴백하고 stderr 로만 경고한다.
//
// CLI 모드(스킬용): node .claude/scripts/visual-config.mjs <target>
//   → 그 변형의 고립 렌더 URL 한 줄 출력. 인자 없으면 설정 JSON 출력.
import { readFile, stat } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

// 무설정 시 기본값 = 현재 demo-app 무대. 여기 있는 키만 config 로 덮을 수 있다.
const DEFAULTS = {
  baseUrl: 'http://localhost:5173',
  // 변형 하나를 고립 렌더해 여는 경로. {target} 은 레지스트리 키로 치환된다.
  //   demo-app: '/gallery?c={target}'   Storybook 예: '/iframe.html?id={target}'
  variantRoute: '/gallery?c={target}',
}

const exists = (p) => stat(p).then(() => true, () => false)

// cwd 에서 위로 올라가며 .claude/visual.config.json 을 찾는다(스크립트 cwd 가 하위 앱이어도 됨).
// git 루트(.git 있는 디렉터리)에서 멈춘다 — 조상(홈·부모 리포)의 남의 config 를 집지 않는다.
async function findConfig(startDir) {
  let dir = startDir
  for (let i = 0; i < 6; i++) {
    const p = join(dir, '.claude', 'visual.config.json')
    if (await exists(p)) return p
    if (await exists(join(dir, '.git'))) break // 리포 경계 — 이 위는 남의 땅
    const parent = dirname(dir)
    if (parent === dir) break
    dir = parent
  }
  return null
}

export async function loadVisualConfig(cwd = process.cwd()) {
  const path = await findConfig(cwd)
  if (!path) return { ...DEFAULTS, _source: 'defaults' }
  let raw
  try {
    raw = JSON.parse(await readFile(path, 'utf8'))
  } catch (e) {
    console.error(`[visual-config] ${path} 파싱 실패 — 기본값으로 폴백: ${e.message}`)
    return { ...DEFAULTS, _source: 'defaults (config 깨짐)' }
  }
  const cfg = { ...DEFAULTS, ...raw, _source: path }
  delete cfg.$comment // 문서용 키가 설정으로 새지 않게
  // 값 검증 — 이상하면 그 키만 기본값으로 되돌린다 (전체 폴백보다 관대하게)
  if (typeof cfg.baseUrl !== 'string' || !/^https?:\/\//.test(cfg.baseUrl)) {
    console.error(`[visual-config] baseUrl 이상(${cfg.baseUrl}) — 기본값 사용`)
    cfg.baseUrl = DEFAULTS.baseUrl
  }
  if (typeof cfg.variantRoute !== 'string' || !cfg.variantRoute.includes('{target}')) {
    console.error(`[visual-config] variantRoute 에 {target} 토큰 없음(${cfg.variantRoute}) — 기본값 사용 (없으면 모든 변형이 같은 URL 로 찍히는 사고)`)
    cfg.variantRoute = DEFAULTS.variantRoute
  }
  return cfg
}

// 변형 하나의 고립 렌더 URL 을 만든다. baseUrl 은 argv 로 덮을 수 있어 따로 받는다.
export function variantUrl(cfg, baseUrl, target) {
  return baseUrl + cfg.variantRoute.replace('{target}', target)
}

// CLI 모드 — 스킬(마크다운)이 URL 을 하드코딩하지 않고 얻는 통로.
if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const cfg = await loadVisualConfig()
  const target = process.argv[2]
  console.log(target ? variantUrl(cfg, cfg.baseUrl, target) : JSON.stringify(cfg, null, 2))
}
