/**
 * 시스템 루프 건강도 — 이미 돌고 있는 감사기들의 출력을 한자리에 모은다.
 *
 * 여기서 새로 재는 것은 거의 없다. `freshness.js`·`guideline-audit.js`·`context-inject.js`가
 * 이미 위반을 세고 있고, 실패 원장과 랄프 루프 결과는 훅과 러너가 이미 쌓아 뒀다.
 * 이 파일이 더하는 것은 **한 자리에 모으는 것과, 그 숫자가 무엇을 못 보는지 함께 내는 것**뿐이다.
 *
 * ## 점수를 이렇게 정의한 이유
 *
 * `1 − 위반/전체`의 "전체"를 **검사기가 실제로 보는 항목 수**로 못박는다. "나쁜 사례/전체"의
 * 전체를 '일어날 수 있는 모든 나쁜 일'로 읽으면 점수가 품질 보증처럼 보이는데, 그건 이 저장소가
 * 반복해 겪은 실패다(`OS.md` 2026-09-07 "검증기가 초록불이었는데도 틀렸다").
 * 그래서 `score`는 항상 `numerator`·`denominator`·`definition`과 함께 나가고,
 * 검사기가 아예 보지 않는 영역은 `blindSpots`로 따로 낸다. 점수가 1.00이어도 사각지대는 남는다.
 *
 * ## 스냅샷을 쌓지 않는 이유
 *
 * 추세를 자동으로 쌓으려면 훅이 파일을 써야 하는데, 그 파일이 `git status`에 잡히면
 * `big-change-commit-check.js`가 무한 재발동한다 — 이 저장소가 이미 두 번 겪은 버그다
 * (`.claude/context/hook-discipline.md`). 추세는 사람이 `docs/`에 남긴다.
 *
 * 순수 함수로 쓰고 `fs`는 옵션으로 주입받는다(`.claude/context/code-vs-instruction.md`).
 */
const nodeFs = require("node:fs");
const nodePath = require("node:path");

const { auditFreshness } = require("./freshness.js");
const { auditGuidelines } = require("./guideline-audit.js");
const { auditInjection } = require("./context-inject.js");
const { buildContextMap, summarizeBudget } = require("./context-map.js");

/** 검사기가 아예 보지 않는 영역. 점수가 1.00이어도 이건 그대로 남는다. */
const BLIND_SPOTS = [
  "지침을 실제로 지켰는가 — 마크다운 지시문은 테스트할 수 없다(code-vs-instruction.md).",
  "위임한 판단이 옳았는가 — 서브에이전트의 PASS/FAIL이 맞는지는 아무도 안 본다.",
  "검사기 자신의 결함 — 명령 target 미측정과 실패 세션 오집계는 둘 다 초록불 상태에서 사람이 찾았다.",
  "루프 단계 목록이 코드에 없다 — 위임 폭은 사람이 docs/loop-delegation.json에 적은 것을 그대로 읽는다.",
  "MCP 서버의 컨텍스트 비용은 미측정이라 세금 축에 들어가지 않는다.",
];

function readJson(filePath, fsImpl) {
  try {
    if (!fsImpl.existsSync(filePath)) return null;
    return JSON.parse(fsImpl.readFileSync(filePath, "utf8"));
  } catch {
    return null;
  }
}

/**
 * 실패 원장에서 두 가지를 센다.
 * - `unresolved`: 마지막 기록이 FAIL이면 지금 빨간불이다. 훅은 초록불로 돌아온 순간에만
 *   RESOLVED를 쓰므로(`atdd-failure-log.js`), 마지막 항목 하나만 보면 된다.
 * - `recurring`: 두 번 이상 깨진 AC. 한 번 깨진 것은 사고지만 반복은 구조 문제다.
 */
function readLedger(projectDir, fsImpl) {
  const ledger = readJson(nodePath.join(projectDir, ".claude", "atdd-failure-ledger.json"), fsImpl);
  const entries = ledger && Array.isArray(ledger.entries) ? ledger.entries : [];
  const byAc = {};
  for (const e of entries) {
    for (const t of e.failedTests || []) {
      const m = String(t).match(/AC-\d+/);
      if (m) byAc[m[0]] = (byAc[m[0]] || 0) + 1;
    }
  }
  const recurring = Object.entries(byAc).filter(([, n]) => n >= 2).map(([id, n]) => ({ id, count: n }));
  const last = entries.length ? entries[entries.length - 1] : null;
  return {
    entries: entries.length,
    unresolved: last ? last.status === "FAIL" : false,
    lastStatus: last ? last.status : null,
    recurring: recurring.sort((a, b) => b.count - a.count),
  };
}

/** 랄프 루프 실행 결과. runs/는 gitignore돼 있어 없을 수 있다 — 없으면 표본 0으로 낸다. */
function readRalphRuns(projectDir, fsImpl) {
  const root = nodePath.join(projectDir, "experiments", "ralph", "runs");
  const outcomes = [];
  try {
    if (!fsImpl.existsSync(root)) return { runs: 0, done: 0, outcomes };
    for (const name of fsImpl.readdirSync(root)) {
      const summary = readJson(nodePath.join(root, name, "summary.json"), fsImpl);
      if (summary && summary.outcome) outcomes.push({ goalId: summary.goalId || name, outcome: summary.outcome });
    }
  } catch {
    return { runs: 0, done: 0, outcomes };
  }
  return { runs: outcomes.length, done: outcomes.filter((o) => o.outcome === "done").length, outcomes };
}

/** 사람이 적은 위임 폭 루브릭. 없으면 축 자체를 `null`로 낸다 — 0으로 채우지 않는다. */
function readDelegation(projectDir, fsImpl) {
  const doc = readJson(nodePath.join(projectDir, "docs", "loop-delegation.json"), fsImpl);
  if (!doc || !Array.isArray(doc.stages) || doc.stages.length === 0) return null;
  const byOwner = {};
  for (const s of doc.stages) byOwner[s.owner] = (byOwner[s.owner] || 0) + 1;
  const humanOnly = doc.stages.filter((s) => s.owner === "human");
  return {
    stages: doc.stages.length,
    byOwner,
    humanOnly: humanOnly.map((s) => ({ id: s.id, name: s.name })),
    delegatedRatio: (doc.stages.length - humanOnly.length) / doc.stages.length,
    updatedAt: doc.updatedAt || null,
  };
}

/**
 * 네 축을 모으고 한 줄 점수를 낸다.
 *
 * 점수에 들어가는 것은 **위생 축뿐이다.** 신뢰도·자율성·세금은 분모가 성격이 달라서
 * 같은 비율로 섞으면 의미가 사라진다(재발 AC 1건과 낡은 수치 1건은 무게가 다르다).
 * 가중치를 정할 근거가 아직 없으므로 임의로 정하지 않고, 점수 밖에 원시 수치로 낸다.
 */
function auditLoopHealth({ projectDir, fsOverrides = {} } = {}) {
  const fsImpl = { ...nodeFs, ...fsOverrides };

  const fresh = auditFreshness({ projectDir, fsOverrides });
  const guide = auditGuidelines({ projectDir, fsOverrides });
  const inject = auditInjection({ projectDir, fsOverrides });

  const hygieneChecks = [
    // `registered`는 배열이 아니라 개수다. 등록부에 올라 실제로 대조된 수치의 수.
    { id: "freshness.stale", label: "문서에 박힌 수치가 낡음", violations: fresh.stale.length, checked: fresh.registered || 0 },
    // 아래 둘은 "몇 개를 훑었나"를 감사기가 내주지 않는다. 그래서 위반이 있을 때만 분모에
    // 들어간다 — 모르는 수를 지어내 분모를 부풀리면 점수가 실제보다 좋아 보인다.
    { id: "freshness.unregistered", label: "등록되지 않은 수치", violations: fresh.unregistered.length, checked: 0 },
    { id: "freshness.missingFile", label: "인용한 파일이 사라짐", violations: fresh.missingFile.length, checked: 0 },
    { id: "guideline.violations", label: "지침 상수 불일치·끊어진 인용", violations: (guide.violations || []).length, checked: ((guide.counts && guide.counts.constants) || 0) + ((guide.counts && guide.counts.topics) || 0) },
    { id: "inject.violations", label: "지침 등록 정합성", violations: (inject.violations || []).length, checked: (inject.counts && inject.counts.guidelines) || 0 },
  ];
  const violations = hygieneChecks.reduce((n, c) => n + c.violations, 0);
  // 분모는 "검사기가 실제로 본 항목 수"다. 위반이 있으면 그 위반도 본 항목이므로 함께 센다.
  const denominator = hygieneChecks.reduce((n, c) => n + Math.max(c.checked, c.violations), 0);

  const ledger = readLedger(projectDir, fsImpl);
  const ralph = readRalphRuns(projectDir, fsImpl);
  const delegation = readDelegation(projectDir, fsImpl);
  const budget = summarizeBudget(buildContextMap({ projectDir, fsOverrides }));

  return {
    score: {
      value: denominator === 0 ? null : Number(((denominator - violations) / denominator).toFixed(4)),
      numerator: denominator - violations,
      denominator,
      definition: "검사기가 실제로 본 항목 중 위반이 아닌 비율. '일어날 수 있는 모든 나쁜 일' 중의 비율이 아니다.",
    },
    axes: {
      hygiene: { checks: hygieneChecks, violations },
      reliability: ledger,
      autonomy: ralph,
      tax: { alwaysLoadedChars: budget.alwaysLoaded.total, onDemandChars: budget.onDemand.total, mcpUnmeasured: budget.unmeasured.mcpServerCount },
      coverage: delegation,
    },
    blindSpots: BLIND_SPOTS,
    caveat:
      "이 점수는 '검사기가 초록불이다'라는 뜻이지 '루프가 좋다'는 뜻이 아니다. "
      + "blindSpots에 적힌 것은 점수가 1.00이어도 그대로 남는다. "
      + (delegation ? "" : "위임 폭 루브릭(docs/loop-delegation.json)이 없어 coverage 축은 비어 있다. "),
  };
}

module.exports = { auditLoopHealth, readLedger, readRalphRuns, readDelegation, BLIND_SPOTS };
