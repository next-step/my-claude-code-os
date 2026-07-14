export const meta = {
  name: 'paper-prep',
  description: 'Prepare the substrate implement-loop needs for a paper: run analyzer → code so output/<slug>/01_analysis.md and 04_code.md (+04_runcard.md) exist. Lean alternative to the full paper-os when you only want to then run implement-loop (the scored, real-working-app loop).',
  whenToUse: 'Before implement-loop on a NEW paper: gives it 01_analysis.md + 04_code.md. Pass { link, slug }.',
  phases: [
    { title: 'Analyze', detail: 'analyzer skill → <slug>/01_analysis.md' },
    { title: 'Code', detail: 'code skill → <slug>/04_code.md + 04_runcard.md (finds & analyzes the official repo)' },
  ],
}

let ARGS = args
if (typeof ARGS === 'string') { const t = ARGS.trim(); if (t.startsWith('{')) { try { ARGS = JSON.parse(t) } catch (_) {} } }
const isObj = typeof ARGS === 'object' && ARGS !== null
const ROOT = (isObj && ARGS.root) || '.'
const LINK = (isObj && ARGS.link) || (typeof ARGS === 'string' ? ARGS : null)
if (!LINK) throw new Error('paper-prep: no paper link (pass { link, slug, root? })')
const SLUG = String((isObj && ARGS.slug) || 'paper').replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 60)
const SK = (n) => `${ROOT}/.claude/skills/${n}/SKILL.md`
const OUT = `${ROOT}/output/${SLUG}`
const M = { model: 'opus', effort: 'high' }

phase('Analyze')
const analysis = await agent(
  `작업 디렉토리 ${ROOT}. ${SK('analyzer')} 를 Read로 읽고 그 절차를 정확히 따라, 이 논문을 분석해 **${OUT}/01_analysis.md** 로 Write하라(상위 폴더 없으면 생성): ${LINK}
8개 섹션 모두 채우고, §6 실험/결과의 보고 지표(수치)와 §8 공식 코드 저장소 링크를 반드시 포함하라. 끝나면 파일 경로 + 한 줄 요약 + 공식 레포 URL을 반환.`,
  { phase: 'Analyze', label: 'analyzer', ...M }
)

phase('Code')
const code = await agent(
  `작업 디렉토리 ${ROOT}. ${SK('code')} 를 Read로 읽고 그 절차대로, 이 논문의 **공식 구현 저장소를 찾아 분석**해 **${OUT}/04_code.md** 와 소형 **${OUT}/04_runcard.md** 를 Write하라. 논문 분석은 ${OUT}/01_analysis.md 참고.
논문↔코드 매핑 표, 진입점, 핵심 하이퍼파라미터, 그리고 브라우저에서 **실제 구현 가능한 알고리즘 기여**(대형 학습 가중치가 아닌 자료구조/포맷/평가지표 등)와 **브라우저 불가로 stand-in이 필요한 부분**을 명확히 구분해 적어라(implement-loop의 '실제 동작 우선' 판단 근거). 끝나면 두 파일 경로 + 공식 레포 URL을 반환.`,
  { phase: 'Code', label: 'code', ...M }
)

return { slug: SLUG, link: LINK, analysis: `output/${SLUG}/01_analysis.md`, code: `output/${SLUG}/04_code.md`, runcard: `output/${SLUG}/04_runcard.md` }
