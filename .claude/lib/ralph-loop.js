/**
 * 랄프 루프의 순수 로직.
 *
 * 랄프 루프는 "목표에 닿을 때까지 같은 프롬프트를 새 컨텍스트로 다시 던지는" 기법이다.
 * 이 저장소의 기존 루프(06단계 TDD 재시도 등)와 다른 점은 두 가지다 — 이터레이션이
 * 대화를 이어받지 않고 매번 0에서 시작한다는 것, 그리고 종료를 사람이 아니라 **측정값**이
 * 정한다는 것이다.
 *
 * ## 이 파일이 판정하는 것
 *   ① 목표 달성 — targets가 전부 목표값에 닿았는가
 *   ② 품질 하한 — guards가 하나도 깨지지 않았는가
 *   ③ 진전 여부 — 노이즈 폭을 **넘어서** 좋아졌는가
 *   ④ 종료 시점 — done / stalled / exhausted 중 무엇인가
 *
 * ## 이 파일이 판정하지 **못하는** 것
 * 응답이 짧아지면서 실제로 쓸모가 줄었는지는 재지 못한다. guards는 인용 개수와 셸 명령
 * 결과만 본다. 자동 채점을 종료 판정에 물리지 않는 이유는 `.claude/context/context-experiment.md`에
 * 있다 — 이 저장소는 세 실험 연속으로 채점 기준이 대상보다 부정확했고, 그런 기준을 루프에
 * 물리면 루프가 잘못된 기준을 최적화한다. 최종 판단은 사람이 패치를 읽고 한다.
 *
 * 부작용(파일 복사·프로세스 실행)은 여기 없다 — `ralph-run.js`가 담당한다.
 * 여기 함수는 전부 순수 함수다(`context-ab.js`와 같은 습관). 실제 실행 없이,
 * 그래서 실비 없이 테스트하기 위해서다.
 *
 * .claude/tests/ralph-loop.test.js 가 이 파일의 인수기준을 검증한다.
 */

/** 목표 정의에서 허용하는 필드. 오타를 조용히 무시하면 통제가 새므로 화이트리스트로 막는다. */
const GOAL_FIELDS = new Set([
  "id", "goal", "editable", "probes", "targets", "guards",
  "repeats", "max_iterations", "stall_after", "model", "per_run_usd_estimate", "note",
]);

/** 지표 하나에서 허용하는 필드. */
const METRIC_FIELDS = new Set(["id", "kind", "extract", "op", "absolute", "relative_to_baseline", "cmd", "note"]);

/**
 * 측정 세션의 응답에서 뽑을 수 있는 값. 여기 없는 이름을 쓰면 목표 정의가 거부된다 —
 * 오타 난 지표는 값이 null로 나오고, null은 "달성 못 함"으로 읽혀 루프가 상한까지 헛돈다.
 */
const RESPONSE_EXTRACTS = new Set([
  "median_chars", "max_chars", "min_chars", "spread_chars",
  "median_lines", "max_lines", "min_citation_count", "median_citation_count",
]);

const OPS = {
  "<=": (a, b) => a <= b,
  ">=": (a, b) => a >= b,
  "<": (a, b) => a < b,
  ">": (a, b) => a > b,
  "==": (a, b) => a === b,
};

/**
 * 반복 측정 기본값을 3으로 둔 이유.
 *
 * 같은 지침·같은 과제로 돌려도 응답 글자 수는 실행마다 달라진다. 1회 측정을 기본으로 두면
 * 그 한계를 기본으로 삼는 셈이다(`context-ab.js`가 반복 기본값을 2로 둔 것과 같은 판단).
 * 여기서 2가 아니라 3인 이유는 대표값으로 **중앙값**을 쓰기 때문이다 — 짝수면 중앙값이
 * 두 값의 평균이 되어, 한 번의 이상치가 다시 대표값을 흔든다.
 */
const DEFAULT_REPEATS = 3;

/** `파일:줄` 인용. 이 저장소의 explanation-style.md가 요구하는 근거 형식이다. */
const CITATION = /[\w./-]+\.(?:md|js|json|mmd|svg|py|ts)(?::\d+)/g;

/** 정렬해서 가운데 값. 짝수면 두 값의 평균을 반올림한다. */
function median(numbers) {
  const xs = (numbers || []).filter((n) => typeof n === "number" && Number.isFinite(n)).sort((a, b) => a - b);
  if (xs.length === 0) return null;
  const mid = Math.floor(xs.length / 2);
  return xs.length % 2 === 1 ? xs[mid] : Math.round((xs[mid - 1] + xs[mid]) / 2);
}

/** 지표 하나를 검증해 정규화한다. */
function parseMetricSpec(raw, role) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new TypeError(`${role} 항목은 객체여야 합니다`);
  }
  for (const key of Object.keys(raw)) {
    if (!METRIC_FIELDS.has(key)) throw new TypeError(`알 수 없는 지표 필드: ${key}`);
  }
  if (typeof raw.id !== "string" || raw.id.length === 0) throw new TypeError(`${role}.id는 문자열이어야 합니다`);
  if (raw.kind !== "response" && raw.kind !== "command") {
    throw new TypeError(`${raw.id}: kind는 "response" 또는 "command"여야 합니다`);
  }
  if (!Object.prototype.hasOwnProperty.call(OPS, raw.op)) {
    throw new TypeError(`${raw.id}: op는 ${Object.keys(OPS).join(" ")} 중 하나여야 합니다`);
  }
  if (typeof raw.extract !== "string" || raw.extract.length === 0) {
    throw new TypeError(`${raw.id}: extract가 필요합니다`);
  }
  if (raw.kind === "response" && !RESPONSE_EXTRACTS.has(raw.extract)) {
    throw new TypeError(`${raw.id}: 알 수 없는 response extract "${raw.extract}"`);
  }
  if (raw.kind === "command" && (typeof raw.cmd !== "string" || raw.cmd.length === 0)) {
    throw new TypeError(`${raw.id}: kind가 command면 cmd가 필요합니다`);
  }
  const hasAbs = typeof raw.absolute === "number";
  const hasRel = typeof raw.relative_to_baseline === "number";
  // 둘 다 주면 어느 쪽이 이기는지가 정의에서 안 보인다. 하나만 받는다.
  if (hasAbs === hasRel) {
    throw new TypeError(`${raw.id}: absolute 또는 relative_to_baseline 중 정확히 하나가 필요합니다`);
  }
  return {
    id: raw.id,
    kind: raw.kind,
    extract: raw.extract,
    op: raw.op,
    absolute: hasAbs ? raw.absolute : null,
    relativeToBaseline: hasRel ? raw.relative_to_baseline : null,
    cmd: raw.kind === "command" ? raw.cmd : null,
    note: typeof raw.note === "string" ? raw.note : "",
  };
}

/**
 * 목표 정의를 검증해 정규화한다.
 *
 * `max_iterations`를 필수로 두는 이유: `OS.md:291`이 "무한히 시도하는 AI보다 빨리 손드는
 * AI가 낫다"고 적어 뒀다. 랄프 루프는 그 판단의 예외이지 폐기가 아니다. 상한을 생략 가능하게
 * 두면 예외가 기본이 된다.
 */
function parseGoalSpec(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new TypeError("목표 정의는 객체여야 합니다");
  }
  for (const key of Object.keys(raw)) {
    if (!GOAL_FIELDS.has(key)) throw new TypeError(`알 수 없는 목표 필드: ${key}`);
  }
  if (typeof raw.id !== "string" || !/^[A-Za-z0-9_-]+$/.test(raw.id)) {
    throw new TypeError("id는 파일·디렉터리 이름이 되므로 영숫자와 _-만 씁니다");
  }
  if (typeof raw.goal !== "string" || raw.goal.trim().length === 0) {
    throw new TypeError(`${raw.id}: goal은 한 문장 이상이어야 합니다`);
  }
  if (!Array.isArray(raw.editable) || raw.editable.length === 0) {
    throw new TypeError(`${raw.id}: editable에 고칠 파일을 최소 하나 적어야 합니다`);
  }
  if (!Array.isArray(raw.probes) || raw.probes.length === 0) {
    throw new TypeError(`${raw.id}: probes에 측정 과제를 최소 하나 적어야 합니다`);
  }
  for (const p of raw.probes) {
    if (!p || typeof p.id !== "string" || typeof p.prompt !== "string" || p.prompt.length === 0) {
      throw new TypeError(`${raw.id}: probe는 {id, prompt}여야 합니다`);
    }
  }
  if (!Array.isArray(raw.targets) || raw.targets.length === 0) {
    throw new TypeError(`${raw.id}: targets에 달성 지표를 최소 하나 적어야 합니다`);
  }
  if (typeof raw.max_iterations !== "number" || !Number.isInteger(raw.max_iterations) || raw.max_iterations < 1) {
    throw new TypeError(`${raw.id}: max_iterations는 1 이상의 정수여야 합니다 (상한 없는 루프는 만들지 않습니다)`);
  }
  const repeats = raw.repeats === undefined ? DEFAULT_REPEATS : raw.repeats;
  if (!Number.isInteger(repeats) || repeats < 1) {
    throw new TypeError(`${raw.id}: repeats는 1 이상의 정수여야 합니다`);
  }
  const stallAfter = raw.stall_after === undefined ? raw.max_iterations : raw.stall_after;
  if (!Number.isInteger(stallAfter) || stallAfter < 1) {
    throw new TypeError(`${raw.id}: stall_after는 1 이상의 정수여야 합니다`);
  }
  const targets = raw.targets.map((t) => parseMetricSpec(t, "targets"));
  const guards = (raw.guards || []).map((g) => parseMetricSpec(g, "guards"));
  const ids = [...targets, ...guards].map((m) => m.id);
  if (new Set(ids).size !== ids.length) throw new TypeError(`${raw.id}: 지표 id가 중복됩니다`);

  return {
    id: raw.id,
    goal: raw.goal.trim(),
    editable: [...raw.editable],
    probes: raw.probes.map((p) => ({ id: p.id, prompt: p.prompt })),
    targets,
    guards,
    repeats,
    maxIterations: raw.max_iterations,
    stallAfter,
    model: typeof raw.model === "string" ? raw.model : null,
    perRunUsdEstimate: typeof raw.per_run_usd_estimate === "number" ? raw.per_run_usd_estimate : null,
    note: typeof raw.note === "string" ? raw.note : "",
  };
}

/**
 * 응답 하나를 잰다.
 *
 * 글자 수는 `String.length`(UTF-16 단위)가 아니라 코드포인트로 센다. 한글은 둘이 같지만
 * 이모지에서 갈라지고, 갈라지면 "3000자"가 사람이 세는 3000자와 달라진다.
 */
function measureResponse(text) {
  const s = typeof text === "string" ? text : "";
  return {
    chars: [...s].length,
    lines: s.length === 0 ? 0 : s.split("\n").length,
    citationCount: (s.match(CITATION) || []).length,
    boldCount: (s.match(/\*\*[^*\n]+\*\*/g) || []).length,
  };
}

/**
 * 측정 세션 여러 개를 집계한다.
 *
 * 대표값은 평균이 아니라 **중앙값**이다. 한 번 유난히 긴 응답이 나와도 판정이 통째로
 * 흔들리지 않게 하기 위해서다.
 *
 * @param {Array<{probeId:string, chars:number, lines:number, citationCount:number}>} runs
 */
function aggregateProbes(runs) {
  const attempted = Array.isArray(runs) ? runs : [];
  // `ok === false`는 세션이 실패했다는 뜻이다(API 오류, 타임아웃). 그 응답 본문은
  // 오류 문자열이라 "아주 짧은 응답"으로 집계된다. **분량을 줄이는 목표에서는 그것이
  // 개선처럼 보인다** — 네트워크가 끊긴 것을 목표 달성으로 보고하게 된다.
  // 실제로 context-slim-30 두 번째 실주행이 여기 걸렸다: 6회 중 4회가 78자짜리
  // `API Error: ENOTFOUND`였는데 분량 가드가 초록불을 냈다.
  // `ok`가 아예 없는 측정은 옛 형식이므로 유효로 본다 — 없는 것과 거짓은 다르다.
  const list = attempted.filter((r) => r && r.ok !== false);
  const failedRuns = attempted.length - list.length;
  const chars = list.map((r) => r.chars);
  const lines = list.map((r) => r.lines);
  const cites = list.map((r) => r.citationCount);
  const byProbe = {};
  for (const r of list) {
    const key = r.probeId || "(unknown)";
    (byProbe[key] = byProbe[key] || []).push(r.chars);
  }
  // 한 과제의 측정이 과반 실패하면 그 과제는 사실상 못 잰 것이다. 남은 한두 개의
  // 중앙값을 대표값이라 부를 수 없으므로, 지표를 통째로 null로 낸다. null은 통과로
  // 치지 않으므로(evaluateMetrics) 못 잰 회차가 조용히 성공으로 넘어가지 않는다.
  const attemptedByProbe = {};
  for (const r of attempted) {
    const key = (r && r.probeId) || "(unknown)";
    attemptedByProbe[key] = (attemptedByProbe[key] || 0) + 1;
  }
  const usable = list.length > 0
    && Object.entries(attemptedByProbe).every(([k, n]) => ((byProbe[k] || []).length * 2) >= n);
  const num = (v) => (usable ? v : null);

  return {
    runs: list.length,
    attemptedRuns: attempted.length,
    failedRuns,
    usable,
    median_chars: num(median(chars)),
    max_chars: num(chars.length ? Math.max(...chars) : null),
    min_chars: num(chars.length ? Math.min(...chars) : null),
    spread_chars: num(chars.length ? Math.max(...chars) - Math.min(...chars) : null),
    median_lines: num(median(lines)),
    max_lines: num(lines.length ? Math.max(...lines) : null),
    min_citation_count: num(cites.length ? Math.min(...cites) : null),
    median_citation_count: num(median(cites)),
    byProbe: Object.fromEntries(Object.entries(byProbe).map(([k, v]) => [k, { runs: v.length, median: median(v), spread: Math.max(...v) - Math.min(...v) }])),
  };
}

/**
 * 노이즈 폭을 구한다 — 아무것도 안 고쳤을 때 글자 수가 흔들리는 범위다.
 *
 * **과제를 가로질러 재지 않고 과제 안에서 잰다.** 과제가 다르면 응답 길이도 원래 다르다.
 * 그 차이까지 노이즈로 세면 폭이 과대평가되어 진짜 개선까지 묻힌다. 그래서 과제별 산포를
 * 구한 뒤 그중 가장 큰 값을 쓴다.
 *
 * repeats가 1이면 산포가 0으로 나온다. 그때는 모든 변화가 개선으로 세지므로 정체 판정이
 * 사실상 꺼진다 — `summarizeRun`이 이 사실을 한계로 함께 낸다.
 */
function computeNoiseBand(baselineRuns) {
  const agg = aggregateProbes(baselineRuns);
  const spreads = Object.values(agg.byProbe).map((p) => p.spread);
  return spreads.length === 0 ? 0 : Math.max(...spreads);
}

/**
 * 셸 명령 출력에서 숫자를 뽑는다.
 *
 * `node --test` 요약 파싱은 `.claude/hooks/atdd-failure-log.js:24`의 정규식을 그대로 쓴다.
 * TAP 리포터(`# fail 3`)와 spec 리포터(`ℹ fail 3`) 양쪽을 지원한다.
 */
function extractFromCommand(output, spec) {
  const isObj = output && typeof output === "object";
  if (spec.extract === "exit_code") {
    return isObj && typeof output.exitCode === "number" ? output.exitCode : null;
  }
  const text = typeof output === "string"
    ? output
    : `${(isObj && output.stdout) || ""}\n${(isObj && output.stderr) || ""}`;
  const m = text.match(new RegExp(`^[^\\S\\n]*(?:#|ℹ)[^\\S\\n]*${spec.extract}[^\\S\\n]+(\\d+)`, "m"));
  return m ? Number(m[1]) : null;
}

/** 지표가 볼 값을 꺼낸다. response는 집계 결과에서, command는 실행 결과에서 온다. */
function resolveValue(spec, values) {
  const bag = spec.kind === "command" ? (values && values.command) || {} : (values && values.response) || {};
  const key = spec.kind === "command" ? spec.id : spec.extract;
  const v = bag[key];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** 목표값을 절대값으로 환산한다. relative_to_baseline은 베이스라인 대표값에 곱한다. */
/**
 * 기준선. `absolute`면 그 값이고, `relative_to_baseline`이면 베이스라인 측정값에 배수를 곱한다.
 *
 * command 지표에 베이스라인을 허용하는 이유: 작업 사본은 훅을 뺀 상태라 목표와 무관하게
 * 이미 깨져 있는 테스트가 있다. `fail == 0`을 절대값으로 걸면 그 가드는 처음부터
 * 만족될 수 없어서, "망가뜨리지 마라"가 아니라 "시작부터 실패"가 된다.
 * 배수 1을 주면 "고치기 전보다 더 깨뜨리지 마라"가 된다.
 */
function thresholdOf(spec, baseline) {
  if (spec.absolute !== null) return spec.absolute;
  const bag = spec.kind === "command" ? (baseline && baseline.command) : (baseline && baseline.response);
  const key = spec.kind === "command" ? spec.id : spec.extract;
  const base = bag ? bag[key] : null;
  if (typeof base !== "number" || !Number.isFinite(base)) return null;
  return Math.round(base * spec.relativeToBaseline);
}

/**
 * 목표 달성 여부와 품질 하한 위반을 판정한다.
 *
 * **guard가 하나라도 깨지면 target을 전부 달성했어도 `met`은 거짓이다.** 분량만 재는 루프는
 * "아무 말도 안 하는" 방향으로 최적화되기 때문이다.
 *
 * 값이 null이면(측정 실패, 명령 실패, 오타 난 extract) 통과로 치지 않는다. 못 잰 것을
 * 통과로 읽으면 초록불이 품질 보증으로 둔갑한다.
 */
function evaluateMetrics({ targets = [], guards = [], values = {}, baseline = null }) {
  const judge = (spec) => {
    const value = resolveValue(spec, values);
    const threshold = thresholdOf(spec, baseline);
    const pass = value !== null && threshold !== null && OPS[spec.op](value, threshold);
    return { id: spec.id, kind: spec.kind, extract: spec.extract, op: spec.op, value, threshold, pass };
  };
  const t = targets.map(judge);
  const g = guards.map(judge);
  const breaches = g.filter((r) => !r.pass).map((r) => r.id);
  return {
    met: t.length > 0 && t.every((r) => r.pass) && breaches.length === 0,
    targetsMet: t.length > 0 && t.every((r) => r.pass),
    targets: t,
    guards: g,
    guardBreaches: breaches,
  };
}

/**
 * 진전이 있었는가.
 *
 * "직전보다 줄었는가"가 아니라 "**노이즈 폭을 넘어서** 줄었는가"로 묻는다. 그렇지 않으면
 * 아무것도 안 고친 이터레이션도 절반의 확률로 개선으로 세어져, 정체 판정이 영원히
 * 초기화된다. 루프는 상한까지 헛돌고 실비만 나간다.
 */
function isImprovement({ current, previous, noiseBand = 0 }) {
  if (typeof current !== "number" || typeof previous !== "number") return false;
  return previous - current > noiseBand;
}

/**
 * 다음에 무엇을 할지 정한다.
 *
 * @param {object} args
 * @param {object} args.spec parseGoalSpec 결과
 * @param {Array<{iteration:number, evaluation:object, primary:number|null}>} args.history
 * @param {number} args.noiseBand
 * @returns {{action:"continue"|"done"|"stalled"|"exhausted", reason:string}}
 */
function decideNext({ spec, history = [], noiseBand = 0 }) {
  const last = history[history.length - 1];
  if (last && last.evaluation && last.evaluation.met) {
    return { action: "done", reason: `이터레이션 ${last.iteration}에서 targets를 전부 달성했고 guard도 깨지지 않았습니다.` };
  }
  if (history.length >= spec.maxIterations) {
    return { action: "exhausted", reason: `상한 ${spec.maxIterations}회를 다 썼습니다. 사람에게 인계합니다.` };
  }
  // 뒤에서부터 "개선 아님"이 몇 번 연속인지 센다. 베이스라인과의 비교까지 포함한다.
  let stalled = 0;
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const cur = history[i].primary;
    const prev = i === 0 ? (history[i].baselinePrimary ?? null) : history[i - 1].primary;
    if (isImprovement({ current: cur, previous: prev, noiseBand })) break;
    stalled += 1;
  }
  if (stalled >= spec.stallAfter) {
    return { action: "stalled", reason: `노이즈 폭(${noiseBand}자)을 넘는 개선이 ${stalled}회 연속 없었습니다. 사람에게 인계합니다.` };
  }
  return { action: "continue", reason: `이터레이션 ${history.length + 1}회차로 넘어갑니다.` };
}

/**
 * 이터레이션에 줄 프롬프트를 만든다.
 *
 * 컨텍스트가 매번 0에서 시작하는데도 루프가 앞으로 나아가는 유일한 이유가 이 프롬프트와
 * 진행 노트 파일이다. 그래서 노트를 **먼저 읽으라**는 지시를 맨 앞에 둔다 — 뒤에 두면
 * 세션이 노트를 읽기 전에 파일부터 고치기 시작한다.
 */
/**
 * 작업 사본에서 고칠 파일을 놓아 둘 자리.
 *
 * 헤드리스 세션은 `.claude/**`를 민감 파일로 분류해서, 편집 승인이 자동으로 서는 모드에서도
 * 사람에게 되묻고 멈춘다(2026-09-11 실측). 루프의 작업 세션은 되물을 사람이 없으므로 그 자리에서
 * 끝난다. 그래서 고칠 파일의 작업용 자리를 평범한 경로로 옮긴다 — 보호 자체를 끄지 않고,
 * 측정 직전과 최종 패치에서 원래 경로로 되돌린다.
 *
 * 경로 구분자를 `__`로 접는 이유는 서로 다른 디렉터리의 같은 파일명이 겹치지 않게 하기 위해서다.
 */
function editMirrorPath(original, dir = "ralph-edit") {
  // 앞의 점을 떼는 이유: 안 떼면 작업본이 숨김 파일이 되어 사람이 사본을 들여다볼 때 안 보인다.
  const flat = String(original).replace(/^\.+/, "").replace(/^\//, "").replace(/\//g, "__");
  return `${dir}/${flat}`;
}

/** 작업용 자리로 뽑힌 패치를 원래 경로로 되돌린다. 안 되돌리면 저장소에 적용할 수 없다. */
function rewritePatchPaths(patch, mapping = {}) {
  let out = typeof patch === "string" ? patch : "";
  // 긴 경로부터 바꿔야 짧은 경로가 접두사로 걸려 먼저 치환되는 일이 없다.
  const pairs = Object.entries(mapping).sort((a, b) => b[0].length - a[0].length);
  for (const [mirror, original] of pairs) out = out.split(mirror).join(original);
  return out;
}

function buildIterationPrompt({ spec, iteration, last = null, notesPath = "RALPH-NOTES.md", editablePaths = null }) {
  const paths = editablePaths || spec.editable;
  const lines = [];
  lines.push(`너는 자동 반복 루프의 ${iteration}회차다. 이전 회차의 대화 기록은 남아 있지 않다.`);
  lines.push(`가장 먼저 \`${notesPath}\`를 읽어라. 지금까지 무엇을 시도했고 무엇이 안 통했는지가 거기 있다.`);
  lines.push("");
  lines.push(`## 목표`);
  lines.push(spec.goal);
  lines.push("");
  lines.push(`## 고쳐도 되는 파일 (이 목록 밖은 건드리지 마라)`);
  for (const f of paths) lines.push(`- ${f}`);
  if (editablePaths) {
    lines.push("");
    lines.push("이 경로들이 이번 회차의 작업본이다. 루프가 측정 직전에 원래 자리로 옮겨 심는다. 원본 경로를 따로 찾아 고치지 마라 — 그쪽 변경은 측정에도 최종 패치에도 반영되지 않는다.");
  }
  lines.push("");
  lines.push(`## 어떻게 채점되는가`);
  for (const t of spec.targets) {
    lines.push(`- [target] ${t.id}: ${t.extract} ${t.op} ${t.absolute !== null ? t.absolute : `베이스라인 × ${t.relativeToBaseline}`}`);
  }
  for (const g of spec.guards) {
    lines.push(`- [guard] ${g.id}: ${g.extract} ${g.op} ${g.absolute}${g.cmd ? ` (명령: ${g.cmd})` : ""}`);
  }
  lines.push("");
  lines.push("target을 달성해도 guard가 하나라도 깨지면 실패로 친다.");
  if (last) {
    lines.push("");
    lines.push(`## 직전 회차 측정값`);
    for (const r of [...last.targets, ...last.guards]) {
      lines.push(`- ${r.id}: ${r.value === null ? "측정 실패" : r.value} (목표 ${r.op} ${r.threshold === null ? "?" : r.threshold}) → ${r.pass ? "통과" : "미달"}`);
    }
  }
  lines.push("");
  lines.push(`## 이번 회차에 할 일`);
  lines.push(`1. \`${notesPath}\`를 읽고 이미 시도해 실패한 방법을 반복하지 마라.`);
  lines.push("2. 목표에 가까워지도록 위 파일을 고쳐라. 한 번에 하나씩 바꿔야 무엇이 효과가 있었는지 알 수 있다.");
  lines.push(`3. 마지막에 \`${notesPath}\`에 이번에 무엇을 왜 바꿨는지 3줄 이내로 덧붙여라. 기존 내용은 지우지 마라.`);
  lines.push("4. 측정은 네가 하지 않는다. 루프가 별도 세션으로 잰다.");
  return lines.join("\n");
}

/**
 * 최종 보고용 요약.
 *
 * 반환값에 `caveat`을 반드시 싣는다 — `guideline-audit.js`·`freshness.js`와 같은 이유다.
 * 초록불을 품질 보증으로 읽는 것이 이 저장소가 반복해 겪은 실패다.
 */
function summarizeRun({ spec, history = [], baseline = null, noiseBand = 0, decision = null }) {
  const trend = history.map((h) => ({
    iteration: h.iteration,
    primary: h.primary,
    targetsMet: h.evaluation ? h.evaluation.targetsMet : null,
    guardBreaches: h.evaluation ? h.evaluation.guardBreaches : [],
  }));
  const caveats = [
    "목표 달성은 '지표가 목표값에 닿았다'는 뜻이지 '결과가 좋아졌다'는 뜻이 아닙니다. 응답이 짧아지면서 쓸모가 줄었는지는 사람이 최종 패치를 읽고 판단해야 합니다.",
    "작업 사본에는 훅이 없습니다. 훅이 관여하는 동작은 이 루프 안에서 재현되지 않습니다.",
  ];
  if (spec.repeats < 3) {
    caveats.push(`repeats가 ${spec.repeats}입니다. 노이즈 폭이 과소평가되어 우연한 변동이 개선으로 세어질 수 있습니다.`);
  }
  if (noiseBand === 0) {
    caveats.push("노이즈 폭이 0으로 나왔습니다. 모든 변화가 개선으로 세어지므로 정체 판정이 사실상 꺼져 있습니다.");
  }
  const failed = baseline && baseline.response ? baseline.response.failedRuns || 0 : 0;
  if (failed > 0) {
    caveats.push(`베이스라인 측정 ${baseline.response.attemptedRuns}회 중 ${failed}회가 세션 오류로 실패해 집계에서 제외했습니다. 남은 표본이 적을수록 기준값이 흔들립니다.`);
  }
  return {
    goalId: spec.id,
    outcome: decision ? decision.action : "unknown",
    reason: decision ? decision.reason : "",
    iterations: history.length,
    maxIterations: spec.maxIterations,
    baseline: baseline && baseline.response ? baseline.response : null,
    noiseBand,
    trend,
    caveat: caveats.join(" "),
  };
}

module.exports = {
  GOAL_FIELDS,
  METRIC_FIELDS,
  RESPONSE_EXTRACTS,
  DEFAULT_REPEATS,
  median,
  parseMetricSpec,
  parseGoalSpec,
  measureResponse,
  aggregateProbes,
  computeNoiseBand,
  extractFromCommand,
  resolveValue,
  thresholdOf,
  evaluateMetrics,
  isImprovement,
  decideNext,
  buildIterationPrompt,
  editMirrorPath,
  rewritePatchPaths,
  summarizeRun,
};
