/**
 * 컨텍스트 A/B 실험의 순수 로직.
 *
 * `docs/context-ab-test.md`에 기록된 실험 1~3은 결론이 값졌지만 **재현이 불가능했다** —
 * 팔(arm) 사본과 실행 스크립트가 /tmp에 있어 커밋되지 않았기 때문이다. 이 파일은 그
 * 구멍을 메우려고 만들었다. 팔을 어떻게 가를지, 결과를 어떻게 읽을지를 코드로 고정한다.
 *
 * 부작용(파일 복사·프로세스 실행)은 여기 없다 — `context-ab-run.js`가 담당한다.
 * 여기 있는 함수는 전부 순수 함수이고 `fs`는 옵션으로 주입받는다
 * (`context-map.js`·`context-inject.js`와 같은 습관). 실제 실행 없이,
 * 그래서 실비 없이 테스트하기 위해서다.
 */
const path = require("node:path");
const { parseImportLines } = require("./context-map.js");

/** 팔 스펙에서 허용하는 필드. 오타를 조용히 무시하면 통제가 새므로 화이트리스트로 막는다. */
const ARM_FIELDS = new Set(["name", "label", "guidelines", "registered", "hooks", "git", "note"]);

/**
 * 어느 팔에서나 사본에 넣지 않는 것들.
 * - node_modules: 크고 실험과 무관하다.
 * - .claude/sessions: 세션 훅의 런타임 상태. 사본에 들어가면 남의 세션 기록을 물고 시작한다.
 * - experiments/context-ab/runs: 실행 결과. 사본이 자기 결과를 다시 품는 재귀를 막는다.
 */
const ALWAYS_EXCLUDE = ["node_modules", ".claude/sessions", "experiments/context-ab/runs"];

/**
 * 팔 정의를 검증해 정규화한다.
 *
 * `guidelines`(디스크에 파일을 남길 것인가)와 `registered`(index.md에 @로 등록할 것인가)를
 * **일부러 따로 둔다.** 실험 1이 2팔에서 3팔로 늘어난 이유가 정확히 이것이다 —
 * 등록만 지우고 파일을 남겼더니 그 팔이 저장소를 뒤져 지침을 **발견**했고 통제가 샜다
 * (docs/context-ab-test.md '설계' 절). 두 축을 합치면 그 실수를 다시 하게 된다.
 *
 * @param {object} raw 팔 정의 한 개
 * @returns {{name:string,label:string,guidelines:"all"|string[],registered:boolean,hooks:boolean,git:boolean,note:string}}
 */
function parseArmSpec(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new TypeError("팔 정의는 객체여야 합니다");
  }
  for (const key of Object.keys(raw)) {
    if (!ARM_FIELDS.has(key)) {
      throw new TypeError(`알 수 없는 팔 필드: ${key} (허용: ${[...ARM_FIELDS].join(", ")})`);
    }
  }
  if (typeof raw.name !== "string" || !/^[A-Za-z0-9_-]+$/.test(raw.name)) {
    throw new TypeError("팔 이름은 영숫자·하이픈·밑줄만 쓸 수 있습니다 (디렉터리 이름이 됩니다)");
  }
  const guidelines = raw.guidelines;
  const guidelinesOk =
    guidelines === "all" ||
    (Array.isArray(guidelines) && guidelines.every((g) => typeof g === "string" && g.endsWith(".md")));
  if (!guidelinesOk) {
    throw new TypeError(`${raw.name}: guidelines는 "all" 이거나 .md 파일명 배열이어야 합니다`);
  }
  for (const flag of ["registered", "hooks", "git"]) {
    if (typeof raw[flag] !== "boolean") {
      throw new TypeError(`${raw.name}: ${flag}는 boolean 이어야 합니다 (생략 불가 — 기본값을 숨기면 팔이 무엇인지 읽어서 알 수 없습니다)`);
    }
  }
  if (guidelines !== "all" && guidelines.length === 0 && raw.registered) {
    throw new TypeError(`${raw.name}: 지침 파일이 하나도 없는데 registered:true 입니다 — 끊어진 등록만 남습니다`);
  }
  return {
    name: raw.name,
    label: typeof raw.label === "string" ? raw.label : raw.name,
    guidelines: guidelines === "all" ? "all" : [...guidelines],
    registered: raw.registered,
    hooks: raw.hooks,
    git: raw.git,
    note: typeof raw.note === "string" ? raw.note : "",
  };
}

/**
 * `index.md`의 `@` 등록 줄을 팔에 맞게 재작성한다.
 * 산문은 건드리지 않는다 — 레지스트리 파일의 설명문까지 지우면 팔끼리 다른 것이
 * 지침 등록만이 아니게 되어 통제가 하나 더 샌다.
 *
 * @param {string} indexText 원본 index.md 전문
 * @param {string[]} keepNames 남길 등록 대상 파일명 (예: ["a.md"]) — 빈 배열이면 전부 제거
 */
function rewriteRegistry(indexText, keepNames) {
  if (typeof indexText !== "string") return "";
  const keep = new Set(keepNames || []);
  const lines = indexText.split(/\r?\n/);
  const kept = lines.filter((line) => {
    const imports = parseImportLines(line);
    if (imports.length === 0) return true; // @ 줄이 아니다 — 그대로 둔다
    return keep.has(path.basename(imports[0]));
  });
  return kept.join("\n");
}

/**
 * 이 팔의 사본을 어떻게 만들지 계획한다. 실제 복사·삭제는 하지 않는다.
 *
 * 훅을 뺄 때 `.claude/hooks/`만 지우면 `settings.json`에 등록은 남아 매 이벤트마다
 * 실행 실패가 난다. 그래서 등록부(`settings*.json`)까지 함께 뺀다.
 *
 * `.git`을 빼는 것은 취향이 아니라 실험 3의 발견 때문이다 — gitStatus(최근 커밋 5개)가
 * 세션 시작 시 주입되고 서브에이전트까지 상속된다. 팔끼리 커밋 로그가 다르면
 * 지침이 아니라 커밋 로그를 비교하게 된다.
 *
 * @param {object} spec parseArmSpec 결과
 * @param {string[]} guidelineNames `.claude/context/`에 실재하는 지침 파일명 목록
 */
function planArmTree(spec, guidelineNames) {
  const all = (guidelineNames || []).filter((n) => n !== "index.md" && n !== "README.md");
  const keepGuidelines = spec.guidelines === "all" ? [...all] : all.filter((n) => spec.guidelines.includes(n));
  const missing = spec.guidelines === "all" ? [] : spec.guidelines.filter((n) => !all.includes(n));

  const excludes = [...ALWAYS_EXCLUDE];
  if (!spec.git) excludes.push(".git");
  if (!spec.hooks) excludes.push(".claude/hooks", ".claude/settings.json", ".claude/settings.local.json");

  return {
    arm: spec.name,
    excludes,
    keepGuidelines,
    deleteGuidelines: all.filter((n) => !keepGuidelines.includes(n)),
    // 등록은 "남긴 파일 중에서만" 가능하다. registered:false면 전부 등록 해제한다.
    registryKeep: spec.registered ? keepGuidelines : [],
    missing,
  };
}

/**
 * `claude -p --output-format json` 출력에서 지표를 꺼낸다.
 *
 * **방어적으로 읽는다.** CLI 출력 스키마는 우리 것이 아니라서 버전이 오르면 바뀔 수 있다.
 * 없는 키는 null로 두고 원본(raw)을 통째로 보존한다 — 나중에 "그때 뭐가 나왔더라"를
 * 다시 물을 수 있어야 하기 때문이다. 2026-09-07 관측 기준 실제 키:
 * duration_ms · duration_api_ms · num_turns · total_cost_usd · usage.{input,output,
 * cache_read_input,cache_creation_input}_tokens · result · is_error · session_id.
 */
function parseHeadlessResult(text) {
  let raw = null;
  let parseError = null;
  try {
    raw = JSON.parse(typeof text === "string" ? text : "");
  } catch (err) {
    parseError = err.message;
  }
  const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);
  const usage = (raw && typeof raw.usage === "object" && raw.usage) || {};
  return {
    ok: parseError === null && raw !== null && raw.is_error !== true,
    parseError,
    isError: raw ? raw.is_error === true : null,
    result: raw && typeof raw.result === "string" ? raw.result : null,
    sessionId: raw && typeof raw.session_id === "string" ? raw.session_id : null,
    durationMs: num(raw && raw.duration_ms),
    durationApiMs: num(raw && raw.duration_api_ms),
    numTurns: num(raw && raw.num_turns),
    costUsd: num(raw && raw.total_cost_usd),
    inputTokens: num(usage.input_tokens),
    outputTokens: num(usage.output_tokens),
    cacheReadTokens: num(usage.cache_read_input_tokens),
    cacheCreationTokens: num(usage.cache_creation_input_tokens),
    raw,
  };
}

/**
 * 집계기(skill-creator의 aggregate_benchmark.py)가 먹는 timing.json 모양으로 바꾼다.
 * total_tokens는 입력 계열을 전부 합친다 — 캐시 읽기·생성도 실제로 낸 비용이다.
 */
function toTimingRecord(parsed) {
  const sum = [parsed.inputTokens, parsed.outputTokens, parsed.cacheReadTokens, parsed.cacheCreationTokens]
    .filter((v) => typeof v === "number")
    .reduce((a, b) => a + b, 0);
  return {
    total_tokens: sum,
    duration_ms: parsed.durationMs,
    total_duration_seconds: parsed.durationMs === null ? null : Math.round(parsed.durationMs / 100) / 10,
    num_turns: parsed.numTurns,
    total_cost_usd: parsed.costUsd,
    input_tokens: parsed.inputTokens,
    output_tokens: parsed.outputTokens,
    cache_read_input_tokens: parsed.cacheReadTokens,
    cache_creation_input_tokens: parsed.cacheCreationTokens,
  };
}

/**
 * 채점 골격을 만든다. `passed`는 일부러 null로 둔다 — 사람이 채우기 전에는
 * "아직 안 봤다"와 "보고 통과시켰다"가 구별돼야 한다.
 *
 * 자동 채점을 코드로 굳히지 않는 이유: docs/context-ab-test.md가 **세 실험 연속으로
 * 자동 채점이 대상보다 부정확했다**고 기록했다(R7↔R10 충돌, "언급"과 "지적" 미구분,
 * 신호를 잘못된 층에 검). 정규식은 무엇을 볼지 미리 정한 만큼만 본다.
 */
function buildGradingSkeleton(rubric) {
  const items = Array.isArray(rubric) ? rubric : [];
  return {
    // `summary` 키를 **아예 두지 않는다.** null로 두면 aggregate_benchmark.py의
    // `grading.get("summary", {}).get(...)`(:130)가 None에 .get을 걸어 죽는다.
    // 대신 status로 미채점을 표시하고, 집계 전에 verifyGrading()이 막는다 —
    // 키가 없을 때 집계기는 pass_rate를 조용히 0.0으로 채우기 때문이다.
    status: "pending",
    expectations: items.map((item) => ({
      // 필드명 text/passed/evidence 는 aggregate_benchmark.py와 뷰어가 의존하는 계약이다.
      text: item.id ? `${item.id}: ${item.text}` : String(item.text || ""),
      passed: null,
      evidence: "",
    })),
    graded_by: null,
  };
}

/**
 * 채점을 마감해 summary를 계산한다.
 * 미채점 항목이 남아 있으면 **예외를 던진다.** 채점 안 한 항목을 0점이나 만점으로
 * 뭉개면 "테스트 0개를 전부 통과로 읽는" 것과 같은 사고가 난다
 * (docs/context-ab-test.md의 C팔이 정확히 그 사례다).
 */
function finalizeGrading(grading, gradedBy) {
  const expectations = (grading && grading.expectations) || [];
  const pending = expectations.filter((e) => typeof e.passed !== "boolean");
  if (pending.length > 0) {
    throw new Error(
      `채점되지 않은 항목 ${pending.length}개가 남아 있습니다: ${pending.map((e) => e.text).join(" / ")}`
    );
  }
  const passed = expectations.filter((e) => e.passed === true).length;
  const total = expectations.length;
  return {
    ...grading,
    status: "graded",
    summary: {
      passed,
      failed: total - passed,
      total,
      pass_rate: total === 0 ? 0 : Math.round((passed / total) * 100) / 100,
    },
    graded_by: gradedBy || grading.graded_by || "human",
  };
}

/**
 * 채점이 끝났는지 판정한다. 집계 전에 이 게이트를 통과해야 한다.
 *
 * 미채점 grading.json에는 `summary`가 없고, 집계기는 없는 값을 **조용히 0.0으로** 채운다
 * (aggregate_benchmark.py:130). 그러면 "채점 안 함"이 "전부 실패"로 둔갑한 표가 나온다 —
 * 테스트 0개를 초록불로 읽는 것과 정확히 같은 형태의 사고다.
 *
 * @param {Array<{path:string,grading:object}>} loaded 읽어 온 grading.json 목록
 */
function verifyGrading(loaded) {
  const pending = (loaded || []).filter((entry) => {
    const g = entry.grading || {};
    if (g.status === "graded" && g.summary) return false;
    return true;
  });
  return { ok: pending.length === 0, total: (loaded || []).length, pending: pending.map((e) => e.path) };
}

/**
 * 실행 결과가 놓일 경로. `run-<n>` 계층이 반드시 있어야 한다 —
 * aggregate_benchmark.py는 `run-*`가 하나도 없는 디렉터리를 설정(config)으로 치지 않고
 * **경고 없이 건너뛴다**(aggregate_benchmark.py:101). 이 저장소의
 * spec-decompose-workspace가 집계되지 않는 이유가 정확히 그것이다.
 */
function runDirPath(root, { iteration, evalName, arm, run }) {
  return path.join(root, `iteration-${iteration}`, `eval-${evalName}`, arm, `run-${run}`);
}

/**
 * 팔×이벌×반복의 실행 계획을 펼친다. 실행하지 않는다 — dry-run이 이 목록을 보여준다.
 */
function planMatrix({ arms, evals, repeats, iteration, root }) {
  const plan = [];
  for (const evalSpec of evals) {
    for (const arm of arms) {
      for (let run = 1; run <= repeats; run += 1) {
        plan.push({
          evalId: evalSpec.id,
          evalName: evalSpec.eval_name,
          arm: arm.name,
          run,
          prompt: evalSpec.prompt,
          dir: runDirPath(root, { iteration, evalName: evalSpec.eval_name, arm: arm.name, run }),
        });
      }
    }
  }
  return plan;
}

/**
 * 비용 어림. 실측 기준값을 인자로 받는다 — 모델과 과제에 따라 자릿수가 달라지므로
 * 코드에 숫자를 박아 두면 금방 거짓말이 된다.
 * (2026-09-07 관측: 한 문장 프롬프트 1회에 $0.076. 실제 과제는 이보다 훨씬 크다.)
 */
function estimateCost(plan, perRunUsd) {
  const unit = typeof perRunUsd === "number" ? perRunUsd : null;
  return { runs: plan.length, perRunUsd: unit, totalUsd: unit === null ? null : Math.round(plan.length * unit * 100) / 100 };
}

module.exports = {
  ALWAYS_EXCLUDE,
  parseArmSpec,
  rewriteRegistry,
  planArmTree,
  parseHeadlessResult,
  toTimingRecord,
  buildGradingSkeleton,
  finalizeGrading,
  verifyGrading,
  runDirPath,
  planMatrix,
  estimateCost,
};
