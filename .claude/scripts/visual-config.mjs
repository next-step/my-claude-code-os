// 시각 검증 "무대(stage)" 설정의 단일 이음새(seam).
//
// 촬영 스크립트가 demo-app 값을 하드코딩하지 않고 여기서 읽는다.
// 무대에 종속되는 값은 딱 둘 — dev 서버 주소(baseUrl)와 변형을 고립 렌더하는 경로(variantRoute).
//   - 무대가 이미 있는 프로젝트(demo-app, Storybook…) → 이 두 값만 바꾸면 "연결".
//   - 무대가 없는 프로젝트 → 온보딩(스캐폴드/어댑트)이 무대를 심고 이 설정을 발급 (OS.md 8단계).
//
// 설정 파일(.claude/visual.config.json)이 없으면 아래 기본값(=현재 demo-app 동작)을 쓴다.
//   → 설정이 없어도 절대 안 깨진다. demo-app 은 지금 그대로 동작한다.
import { readFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'

// 무설정 시 기본값 = 현재 demo-app 무대. 여기 있는 키만 config 로 덮을 수 있다.
const DEFAULTS = {
  baseUrl: 'http://localhost:5173',
  // 변형 하나를 고립 렌더해 여는 경로. {target} 은 레지스트리 키로 치환된다.
  //   demo-app: '/gallery?c={target}'   Storybook 예: '/iframe.html?id={target}'
  variantRoute: '/gallery?c={target}',
}

// cwd 에서 위로 올라가며 .claude/visual.config.json 을 찾는다(스크립트 cwd 가 하위 앱이어도 됨).
async function findConfig(startDir) {
  let dir = startDir
  for (let i = 0; i < 6; i++) {
    const p = join(dir, '.claude', 'visual.config.json')
    try {
      await readFile(p)
      return p
    } catch {
      /* 없으면 상위로 */
    }
    const parent = dirname(dir)
    if (parent === dir) break
    dir = parent
  }
  return null
}

export async function loadVisualConfig(cwd = process.cwd()) {
  const path = await findConfig(cwd)
  if (!path) return { ...DEFAULTS, _source: 'defaults' }
  const raw = JSON.parse(await readFile(path, 'utf8'))
  return { ...DEFAULTS, ...raw, _source: path }
}

// 변형 하나의 고립 렌더 URL 을 만든다. baseUrl 은 argv 로 덮을 수 있어 따로 받는다.
export function variantUrl(cfg, baseUrl, target) {
  return baseUrl + cfg.variantRoute.replace('{target}', target)
}
