export const meta = {
  name: 'catalog-improvement-sweep',
  description: '워크리스트가 고른 GT 후보를 건마다 판정하고 반증까지 받은 뒤, 정책 군집을 한 문장 질문으로 바꾼다',
  phases: [
    { title: 'GT 건별 판정', detail: '후보 하나에 판정관 하나. 정책·큐·근거를 읽고 분류한다' },
    { title: 'GT 반증', detail: '같은 건을 반대편에서 다시 본다. GT를 유지할 근거를 찾는다' },
    { title: '정책 군집 질문', detail: '군집 하나에 정찰자 하나. 한 번 답하면 닫히는 질문으로 바꾼다' },
  ],
}

// 이 스크립트는 파일을 읽지 못한다(워크플로우 런타임 제약). 그래서 args는 포인터만 나르고,
// 본문은 각 에이전트가 워크리스트에서 직접 읽는다. 숫자를 세는 일은 이미 끝났다 —
// build_improvement_worklist.py가 세어 worklist.json에 적어 두었고, 여기서는 판단만 한다.
const PROFILE = args.profile
const RUN = args.run
const WORKLIST = args.worklist
const LABELS = (args.labels || []).join(' · ')
const GT = args.gt || []
const CLUSTERS = args.clusters || []

const COMMON = `
프로필: ${PROFILE}
run 폴더: ${RUN}
워크리스트: ${WORKLIST}
허용 라벨: ${LABELS}

읽기만 한다. 어떤 파일도 고치지 않고, 사람 판정 원장(review/decisions.json)에 남기지 않는다.
건수를 세지 않는다 — 영향 건수는 워크리스트가 이미 세어 두었다.
숫자를 옮겨 적지 말고, 관찰한 것과 그것이 어느 문장에서 나왔는지만 적는다.`

const GT_SCHEMA = {
  type: 'object',
  properties: {
    productKey: { type: 'string' },
    classification: {
      type: 'string',
      enum: ['GOLDEN_SUSPECT', 'POLICY_GAP', 'RUNTIME_CONTRADICTION', 'MODEL_ERROR', 'NEEDS_MORE_EVIDENCE'],
    },
    currentGoldLabel: { type: 'string' },
    proposedLabel: {
      type: 'string',
      description: '허용 라벨 중 하나. 현재 GT를 그대로 두자는 결론이면 현재 라벨을 적는다',
    },
    policySentence: {
      type: 'string',
      description: '이 제안을 지지하는 소유 정책의 문장이나 판례 id. 댈 수 없으면 빈 문자열로 둔다',
    },
    evidence: { type: 'array', items: { type: 'string' }, description: '관찰한 근거. 어디서 봤는지 포함' },
    missingEvidence: { type: 'array', items: { type: 'string' }, description: '이 스냅샷에 없어서 못 본 것' },
    question: { type: 'string', description: '사람이 한 문장으로 답할 질문' },
    confidence: { type: 'string', enum: ['HIGH', 'LOW'] },
  },
  required: ['productKey', 'classification', 'currentGoldLabel', 'proposedLabel', 'evidence', 'question', 'confidence'],
}

const REFUTE_SCHEMA = {
  type: 'object',
  properties: {
    productKey: { type: 'string' },
    verdict: { type: 'string', enum: ['GT_STANDS', 'GT_SUSPECT_CONFIRMED', 'INCONCLUSIVE'] },
    standingEvidence: { type: 'array', items: { type: 'string' }, description: '현재 GT를 유지할 근거' },
    weakestLink: { type: 'string', description: '앞 판정에서 가장 약한 고리 하나' },
    note: { type: 'string' },
  },
  required: ['productKey', 'verdict', 'weakestLink'],
}

const CLUSTER_SCHEMA = {
  type: 'object',
  properties: {
    clusterKey: { type: 'string' },
    defectType: { type: 'string', enum: ['GAP', 'MISTRANSLATION', 'WEAK_EVIDENCE', 'RUNTIME_MISMATCH'] },
    defectReason: { type: 'string' },
    boundary: { type: 'string', description: '어떤 조건의 상품에서 답이 안 나오는가. 상품 이름이 아니라 조건으로' },
    question: { type: 'string', description: '한 번 답하면 닫히는 한 문장' },
    options: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          choice: { type: 'string' },
          changes: { type: 'string' },
          cost: { type: 'string' },
        },
        required: ['choice', 'changes'],
      },
    },
    recommendation: { type: 'string' },
    rationale: { type: 'string' },
    counterExamples: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          productKey: { type: 'string' },
          currentGoldLabel: { type: 'string' },
          runLabel: { type: 'string' },
          whyDifferent: { type: 'string' },
        },
        required: ['productKey', 'whyDifferent'],
      },
    },
    duplicates: { type: 'string', description: '이 군집을 이미 덮는 판례 id나 질문 id. 없으면 빈 문자열' },
    unread: { type: 'array', items: { type: 'string' }, description: '읽지 못한 파일과 이유' },
  },
  required: ['clusterKey', 'defectType', 'boundary', 'question', 'options', 'recommendation'],
}

function adjudicatePrompt(item) {
  return `워크리스트 ${WORKLIST}의 gtCandidates에서 id=${item.id}인 항목 하나만 판정한다.
상품: ${item.productKey}${item.productName ? ` (${item.productName})` : ''}

그 항목의 queues가 가리키는 큐 파일에서 이 productKey의 행을 찾아 읽고, 프로필의 goal과
policy.owned·policy.precedents를 근거 우선순위 그대로 적용한다. 심판은 이 건을 "골든셋을 고친다"로
보았다. 그 판단을 이어받지 말고 처음부터 다시 가른다 — 심판은 라벨만 비교했고, 너는 근거를 읽는다.

사람이 확정한 GT를 뒤집자는 제안이므로 기준이 높다. 정책 문장을 댈 수 없으면
policySentence를 비우고 confidence를 LOW로 둔다. 근거가 스냅샷에 없으면 억지로 메우지 말고
NEEDS_MORE_EVIDENCE로 답한다.${COMMON}`
}

function refutePrompt(claim, item) {
  return `방금 다른 판정관이 상품 ${item.productKey}에 대해 아래와 같이 주장했다.

분류: ${claim.classification}
현재 GT: ${claim.currentGoldLabel} → 제안: ${claim.proposedLabel}
근거로 든 정책 문장: ${claim.policySentence || '(대지 못했다)'}
관찰 근거: ${(claim.evidence || []).join(' / ') || '(없음)'}

네 일은 이 주장을 확인해 주는 것이 아니라 **반증하는 것**이다. 현재 GT ${claim.currentGoldLabel}을
그대로 유지해야 할 근거를 소유 정책·판례·큐 행·GT 계보(lineage)에서 찾는다. 근거 우선순위가
더 높은 문장이 반대편을 지지하는지, 인용된 근거가 실제로 이 상품의 것인지, 계보가 이미 한 번
사람 손을 탔는지 본다. 찾지 못하면 GT_SUSPECT_CONFIRMED로 그렇게 답한다 — 억지로 반박하지 않는다.
확신이 서지 않으면 INCONCLUSIVE다.

너는 이미지를 열지 않는다. 사진을 봐야 갈리는 건이면 그 사실을 weakestLink에 적는다.
그 건은 이 워크플로우가 다루지 않는다 — 사진을 다시 받아 되짚는 절차로 넘어간다.${COMMON}`
}

function clusterPrompt(item) {
  return `워크리스트 ${WORKLIST}의 policyClusters에서 id=${item.id}인 군집 하나만 정찰한다.
군집 키: ${item.clusterKey} · 귀책: ${item.owner}

그 행의 queues와 sampleProductKeys로 실제 큐 행을 열어 반례를 고르고, blockedBy에 판례 id가
있으면 그 판례 파일을 먼저 읽는다. ${RUN}/reports/policy-questions.json에 이미 같은 질문이
있으면 새로 만들지 말고 그 id를 duplicates에 적는다.

경계는 상품 이름이 아니라 조건으로 쓴다. 조건으로 쓸 수 없으면 이 무리는 아직 군집이 아니라
사례 더미이고, boundary에 그렇게 적는다.${COMMON}`
}

log(`GT 후보 ${GT.length} · 정책 군집 ${CLUSTERS.length}. 상한 밖으로 밀린 것은 워크리스트의 excluded에 있다.`)

// 두 레인은 서로를 기다리지 않는다. 단위가 다르고(건 · 군집) 읽는 것도 다르므로
// 한쪽이 늦다고 다른 쪽을 멈출 이유가 없다. 레인 안에서도 배리어를 두지 않는다 —
// GT-01의 반증이 GT-04의 판정을 기다릴 필요가 없다.
const gtLane = pipeline(
  GT,
  (item) =>
    agent(adjudicatePrompt(item), {
      agentType: 'catalog-golden-adjudicator',
      label: `판정 ${item.id} ${item.productKey}`,
      phase: 'GT 건별 판정',
      schema: GT_SCHEMA,
    }),
  (claim, item) =>
    claim
      ? agent(refutePrompt(claim, item), {
          agentType: 'catalog-golden-adjudicator',
          label: `반증 ${item.id} ${item.productKey}`,
          phase: 'GT 반증',
          schema: REFUTE_SCHEMA,
        }).then((refutation) => ({ id: item.id, productKey: item.productKey, claim, refutation }))
      : null,
)

const policyLane = pipeline(CLUSTERS, (item) =>
  agent(clusterPrompt(item), {
    agentType: 'catalog-policy-cluster-scout',
    label: `군집 ${item.id} ${item.clusterKey}`,
    phase: '정책 군집 질문',
    schema: CLUSTER_SCHEMA,
  }).then((question) => (question ? { id: item.id, clusterKey: item.clusterKey, question } : null)),
)

const [gt, clusters] = await Promise.all([gtLane, policyLane])
const kept = gt.filter(Boolean)
const questions = clusters.filter(Boolean)
if (kept.length < GT.length || questions.length < CLUSTERS.length) {
  log(`돌아오지 못한 것: GT ${GT.length - kept.length}건 · 군집 ${CLUSTERS.length - questions.length}건. 보고서에 빈자리로 남는다.`)
}

return {
  schemaVersion: 'catalog-improvement-sweep-v1',
  worklist: WORKLIST,
  profile: PROFILE,
  run: RUN,
  gt: kept,
  clusters: questions,
}
