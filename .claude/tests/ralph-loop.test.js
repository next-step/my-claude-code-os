/**
 * 랄프 루프(.claude/lib/ralph-loop.js, ralph-run.js)의 인수 테스트.
 *
 * AC-1~11·13~15는 가짜 fs·가짜 spawn으로 순수 로직만 본다. AC-12는 **실제 저장소**에
 * 커밋된 목표 정의를 대상으로 도는 회귀 테스트다(context-ab.test.js AC-11과 같은 성격).
 *
 * 이 루프는 한 번 돌 때마다 실비가 나가므로, 테스트가 실제 프로세스를 절대 띄우지 않게 한다.
 *
 * 실행: node --test .claude/tests/ralph-loop.test.js
 */
const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");

const {
  median,
  parseGoalSpec,
  measureResponse,
  aggregateProbes,
  computeNoiseBand,
  extractFromCommand,
  evaluateMetrics,
  isImprovement,
  decideNext,
  buildIterationPrompt,
  summarizeRun,
  editMirrorPath,
  rewritePatchPaths,
  DEFAULT_REPEATS,
} = require("../lib/ralph-loop.js");
const { planSessions, runLoop, parseArgv, collectPatch, NOTES_FILE } = require("../lib/ralph-run.js");

const PROJECT_DIR = path.resolve(__dirname, "..", "..");

/** 최소한으로 유효한 목표 정의. 각 테스트가 필요한 필드만 덮어쓴다. */
function goal(over = {}) {
  return {
    id: "demo",
    goal: "응답을 짧게 만든다",
    editable: [".claude/context/response-brevity.md"],
    probes: [{ id: "p1", prompt: "질문1" }, { id: "p2", prompt: "질문2" }],
    targets: [{ id: "chars", kind: "response", extract: "median_chars", op: "<=", relative_to_baseline: 0.5 }],
    guards: [{ id: "tests", kind: "command", cmd: "node --test x", extract: "fail", op: "==", absolute: 0 }],
    repeats: 3,
    max_iterations: 5,
    stall_after: 2,
    ...over,
  };
}

// --- 목표 정의 검증 ---

test("AC-1: max_iterations가 없으면 목표 정의를 거부한다 (상한 없는 루프는 만들지 않는다)", () => {
  const { max_iterations, ...noCap } = goal();
  assert.throws(() => parseGoalSpec(noCap), /max_iterations는 1 이상의 정수/);
  assert.throws(() => parseGoalSpec(goal({ max_iterations: 0 })), /max_iterations/);
});

test("AC-2: 화이트리스트 밖 필드나 오타 난 extract는 거부한다", () => {
  assert.throws(() => parseGoalSpec({ ...goal(), typo: 1 }), /알 수 없는 목표 필드/);
  assert.throws(
    () => parseGoalSpec(goal({ targets: [{ id: "x", kind: "response", extract: "mean_chars", op: "<=", absolute: 10 }] })),
    /알 수 없는 response extract/,
    "오타 난 지표는 값이 null로 나오고, null은 미달로 읽혀 루프가 상한까지 헛돈다",
  );
  assert.throws(
    () => parseGoalSpec(goal({ targets: [{ id: "x", kind: "response", extract: "max_chars", op: "<=", absolute: 10, relative_to_baseline: 0.5 }] })),
    /정확히 하나가 필요합니다/,
  );
});

test("AC-13: repeats를 생략하면 3이 채워지고, 대표값은 평균이 아니라 중앙값이다", () => {
  const { repeats, ...noRepeats } = goal();
  assert.strictEqual(parseGoalSpec(noRepeats).repeats, DEFAULT_REPEATS);
  assert.strictEqual(DEFAULT_REPEATS, 3, "중앙값을 쓰려면 홀수여야 한 번의 이상치가 대표값을 흔들지 않는다");
  // 평균이면 1000+1000+7000 / 3 = 3000. 중앙값은 1000이다.
  assert.strictEqual(median([1000, 1000, 7000]), 1000);
  const agg = aggregateProbes([
    { probeId: "p1", chars: 1000, lines: 10, citationCount: 1 },
    { probeId: "p1", chars: 1000, lines: 10, citationCount: 1 },
    { probeId: "p1", chars: 7000, lines: 70, citationCount: 1 },
  ]);
  assert.strictEqual(agg.median_chars, 1000);
  assert.strictEqual(agg.max_chars, 7000);
});

// --- 측정 ---

test("AC-3: measureResponse가 글자 수와 `파일:줄` 인용 수를 센다", () => {
  const m = measureResponse("근거는 `context-ab.js:89` 와 `OS.md:291` 입니다.\n둘째 줄.");
  assert.strictEqual(m.citationCount, 2);
  assert.strictEqual(m.lines, 2);
  assert.strictEqual(m.chars, [..."근거는 `context-ab.js:89` 와 `OS.md:291` 입니다.\n둘째 줄."].length);
  // 줄 번호가 없는 파일 이름은 인용으로 세지 않는다. 그냥 언급일 수 있다.
  assert.strictEqual(measureResponse("OS.md 를 보세요").citationCount, 0);
});

test("AC-14: 노이즈 폭은 과제 안에서 재고, 그 폭 안의 감소는 개선으로 세지 않는다", () => {
  // 과제 p1은 5000자대, p2는 1000자대다. 과제를 가로질러 재면 폭이 4200으로 과대평가된다.
  const runs = [
    { probeId: "p1", chars: 5000, lines: 1, citationCount: 1 },
    { probeId: "p1", chars: 5200, lines: 1, citationCount: 1 },
    { probeId: "p2", chars: 1000, lines: 1, citationCount: 1 },
    { probeId: "p2", chars: 1100, lines: 1, citationCount: 1 },
  ];
  assert.strictEqual(computeNoiseBand(runs), 200, "과제별 산포 중 최댓값을 쓴다");
  assert.strictEqual(isImprovement({ current: 2900, previous: 3000, noiseBand: 200 }), false);
  assert.strictEqual(isImprovement({ current: 2700, previous: 3000, noiseBand: 200 }), true);
});

test("AC-8: extractFromCommand가 TAP과 spec 리포터 양쪽에서 fail 수를 뽑는다", () => {
  const spec = { extract: "fail" };
  assert.strictEqual(extractFromCommand("# pass 10\n# fail 3\n", spec), 3);
  assert.strictEqual(extractFromCommand("ℹ pass 10\nℹ fail 0\n", spec), 0);
  assert.strictEqual(extractFromCommand({ stdout: "", stderr: "ℹ fail 2\n" }, spec), 2);
  assert.strictEqual(extractFromCommand("아무것도 없음", spec), null, "못 뽑으면 null이지 0이 아니다");
  assert.strictEqual(extractFromCommand({ exitCode: 1 }, { extract: "exit_code" }), 1);
});

// --- 판정 ---

test("AC-4: relative_to_baseline 0.5가 베이스라인 중앙값의 절반으로 환산된다", () => {
  const spec = parseGoalSpec(goal());
  const r = evaluateMetrics({
    targets: spec.targets, guards: [],
    values: { response: { median_chars: 2000 } },
    baseline: { response: { median_chars: 4000 } },
  });
  assert.strictEqual(r.targets[0].threshold, 2000);
  assert.strictEqual(r.targets[0].pass, true);
  const worse = evaluateMetrics({
    targets: spec.targets, guards: [],
    values: { response: { median_chars: 2001 } },
    baseline: { response: { median_chars: 4000 } },
  });
  assert.strictEqual(worse.targets[0].pass, false);
});

test("AC-5: target을 전부 달성해도 guard가 깨지면 met은 거짓이다", () => {
  const spec = parseGoalSpec(goal());
  const base = { response: { median_chars: 4000 } };
  const values = { response: { median_chars: 1000 }, command: { tests: 2 } };
  const r = evaluateMetrics({ targets: spec.targets, guards: spec.guards, values, baseline: base });
  assert.strictEqual(r.targetsMet, true);
  assert.strictEqual(r.met, false, "분량만 재는 루프는 아무 말도 안 하는 방향으로 최적화된다");
  assert.deepStrictEqual(r.guardBreaches, ["tests"]);
});

test("AC-5b: 측정에 실패해 값이 null이면 통과로 치지 않는다", () => {
  const spec = parseGoalSpec(goal());
  const r = evaluateMetrics({
    targets: spec.targets, guards: spec.guards,
    values: { response: {}, command: {} },
    baseline: { response: { median_chars: 4000 } },
  });
  assert.strictEqual(r.targets[0].pass, false, "못 잰 것을 통과로 읽으면 초록불이 품질 보증으로 둔갑한다");
  assert.strictEqual(r.met, false);
});

test("AC-6: stall_after 연속 미개선이면 stalled를 낸다", () => {
  const spec = parseGoalSpec(goal({ stall_after: 2 }));
  const bad = { met: false, targetsMet: false, guardBreaches: [] };
  const history = [
    { iteration: 1, evaluation: bad, primary: 3990, baselinePrimary: 4000 },
    { iteration: 2, evaluation: bad, primary: 3985, baselinePrimary: 4000 },
  ];
  assert.strictEqual(decideNext({ spec, history, noiseBand: 200 }).action, "stalled");
  // 노이즈 폭을 넘어 줄었으면 정체가 아니다.
  const moving = [
    { iteration: 1, evaluation: bad, primary: 3500, baselinePrimary: 4000 },
    { iteration: 2, evaluation: bad, primary: 3000, baselinePrimary: 4000 },
  ];
  assert.strictEqual(decideNext({ spec, history: moving, noiseBand: 200 }).action, "continue");
});

test("AC-7: 상한을 다 쓰면 exhausted를 내고, 달성하면 done을 낸다", () => {
  const spec = parseGoalSpec(goal({ max_iterations: 2, stall_after: 9 }));
  const bad = { met: false, targetsMet: false, guardBreaches: [] };
  const full = [
    { iteration: 1, evaluation: bad, primary: 3000, baselinePrimary: 4000 },
    { iteration: 2, evaluation: bad, primary: 2000, baselinePrimary: 4000 },
  ];
  assert.strictEqual(decideNext({ spec, history: full, noiseBand: 0 }).action, "exhausted");
  const won = [{ iteration: 1, evaluation: { met: true, targetsMet: true, guardBreaches: [] }, primary: 1000, baselinePrimary: 4000 }];
  assert.strictEqual(decideNext({ spec, history: won, noiseBand: 0 }).action, "done");
});

// --- 프롬프트와 요약 ---

test("AC-10: 이터레이션 프롬프트가 진행 노트를 먼저 읽으라고 지시한다", () => {
  const spec = parseGoalSpec(goal());
  const p = buildIterationPrompt({ spec, iteration: 3, last: null, notesPath: NOTES_FILE });
  assert.match(p, /이전 회차의 대화 기록은 남아 있지 않다/);
  assert.ok(p.indexOf(NOTES_FILE) < p.indexOf("## 목표"), "노트를 읽으라는 지시가 목표보다 앞에 있어야 한다");
  assert.match(p, /\.claude\/context\/response-brevity\.md/, "고쳐도 되는 파일 목록이 들어간다");
  assert.match(p, /guard가 하나라도 깨지면 실패/);
});

test("AC-11: summarizeRun 결과에 한계(caveat)가 실린다", () => {
  const spec = parseGoalSpec(goal());
  const s = summarizeRun({ spec, history: [], baseline: { response: { median_chars: 4000 } }, noiseBand: 0, decision: { action: "stalled", reason: "r" } });
  assert.match(s.caveat, /사람이 최종 패치를 읽고 판단/);
  assert.match(s.caveat, /훅이 없습니다/);
  assert.match(s.caveat, /노이즈 폭이 0/, "노이즈 폭 0은 정체 판정이 꺼졌다는 뜻이므로 반드시 말한다");
  assert.strictEqual(s.outcome, "stalled");
});

// --- 실행 계획과 안전장치 ---

test("AC-15: 이터레이션당 세션 수가 1 + 과제수 × repeats 와 정확히 같다", () => {
  const spec = parseGoalSpec(goal({ repeats: 3 }));
  const s = planSessions(spec);
  assert.strictEqual(s.baselineSessions, 6);
  assert.strictEqual(s.perIterationSessions, 1 + 2 * 3);
  assert.strictEqual(s.worstCaseSessions, 6 + 5 * 7);
});

test("AC-9: dry-run이 기본이고 이때 spawn은 0회다", () => {
  let spawnCalls = 0;
  let execCalls = 0;
  const spec = parseGoalSpec(goal());
  const out = runLoop({
    sourceDir: "/src",
    spec,
    root: "/runs",
    workDir: "/work/work",
    probeDir: "/work/probe",
    // dryRun 을 일부러 넘기지 않는다 — 기본값이 안전한 쪽인지가 이 AC의 요지다.
    fsImpl: { writeFileSync: () => { throw new Error("dry-run이 파일을 썼다"); }, mkdirSync: () => {}, existsSync: () => false },
    spawnImpl: () => { spawnCalls += 1; return { status: 0, stdout: "{}", stderr: "" }; },
    execImpl: () => { execCalls += 1; return { stdout: "", stderr: "", exitCode: 0 }; },
    log: () => {},
  });
  assert.strictEqual(spawnCalls, 0, "--go 없이는 절대 세션이 뜨지 않는다. 실비가 나가기 때문이다");
  assert.strictEqual(execCalls, 0);
  assert.strictEqual(out.dryRun, true);
  assert.strictEqual(out.sessions.worstCaseSessions, 41);
});

test("AC-9b: --go 없이 부른 main은 dry-run이고, --goal 없이는 즉시 실패한다", () => {
  assert.throws(() => parseArgv([]), /--goal/);
  assert.throws(() => parseArgv(["--goal", "g.json", "--없는옵션"]), /알 수 없는 옵션/);
  assert.strictEqual(parseArgv(["--goal", "g.json"]).go, false);
  assert.strictEqual(parseArgv(["--goal", "g.json", "--go"]).go, true);
});

// --- 여기부터 실제 저장소 회귀 ---

test("AC-12: 커밋된 brevity-50.json이 parseGoalSpec을 통과한다", () => {
  const raw = require(path.join(PROJECT_DIR, "experiments", "ralph", "goals", "brevity-50.json"));
  const spec = parseGoalSpec(raw);
  assert.strictEqual(spec.id, "brevity-50");
  assert.ok(spec.maxIterations >= 1, "상한이 있어야 한다");
  assert.ok(spec.guards.length >= 1, "품질 하한 없이 분량만 재면 루프가 침묵을 향해 최적화된다");
  const fs = require("node:fs");
  for (const rel of spec.editable) {
    assert.ok(fs.existsSync(path.join(PROJECT_DIR, rel)), `고칠 대상 파일이 없습니다: ${rel}`);
  }
});

test("AC-16: 최종 패치는 인덱스가 아니라 기준 커밋과 비교한다", () => {
  // 루프가 회차마다 커밋을 남기므로, `git diff --cached`로 뽑으면 마지막 커밋 직후라
  // 차이가 항상 0으로 나온다. 실제로 스모크 테스트에서 지표는 달성했는데 패치가 빈 파일이었다.
  const cmds = [];
  const exec = (cmd) => {
    cmds.push(cmd);
    return { stdout: cmd.startsWith("git diff --name-only") ? "" : cmd.startsWith("git diff") ? "diff --git a/x b/x\n" : "", stderr: "", exitCode: 0 };
  };
  const { patch } = collectPatch({ workDir: "/work", baseRef: "abc123", editable: ["a.md"], execImpl: exec });
  assert.match(patch, /^diff --git/);
  assert.ok(cmds.some((c) => c.startsWith("git diff abc123 HEAD --")), `기준 커밋과 비교해야 합니다. 실제 명령: ${JSON.stringify(cmds)}`);
  assert.ok(!cmds.some((c) => c.includes("--cached")), "인덱스와 비교하면 커밋 직후라 항상 비어 나온다");
});

test("AC-16b: 기준 커밋을 모르면 빈 패치 대신 이유를 남긴다", () => {
  const { patch } = collectPatch({ workDir: "/work", baseRef: null, editable: [], execImpl: () => ({ stdout: "", stderr: "", exitCode: 0 }) });
  assert.match(patch, /기준 커밋을 알 수 없어/, "빈 파일을 내놓으면 '바뀐 게 없다'로 잘못 읽힌다");
});

test("AC-17: 패치를 editable 범위로 한정하고, 사본에서 뺀 파일의 삭제를 범위 밖 변경으로 세지 않는다", () => {
  // 사본은 훅과 settings.json을 빼고 만들므로 git 입장에서 그 파일들은 '삭제'로 보인다.
  // 한정하지 않으면 패치에 훅 삭제가 전부 실려서, 적용하는 순간 훅이 사라진다.
  // 스모크 테스트에서 496KB짜리 삭제 패치가 나와 잡았다.
  const cmds = [];
  const exec = (cmd) => {
    cmds.push(cmd);
    if (cmd.startsWith("git diff --name-only")) {
      return { stdout: ".claude/context/a.md\n.claude/hooks/x.js\n.claude/settings.json\nOS.md\nRALPH-NOTES.md\n", stderr: "", exitCode: 0 };
    }
    return { stdout: cmd.startsWith("git diff") ? "diff --git a/a b/a\n" : "", stderr: "", exitCode: 0 };
  };
  const { patch, stray } = collectPatch({ workDir: "/work", baseRef: "base", editable: [".claude/context/a.md"], execImpl: exec });
  const diffCmd = cmds.find((c) => c.startsWith("git diff base HEAD --"));
  assert.ok(diffCmd.includes('"..claude/context/a.md"'.replace("..claude", ".claude")), `패치 범위가 editable로 한정돼야 합니다: ${diffCmd}`);
  assert.ok(!patch.includes("hooks"), "훅 삭제가 패치에 실리면 안 된다");
  assert.deepStrictEqual(stray, ["OS.md"], "뺀 파일과 노트는 범위 밖 변경이 아니지만, 진짜 범위 밖 변경은 이름을 남긴다");
});

test("AC-18: 기준 커밋은 저장소 HEAD가 아니라 사본을 만든 시점이다", () => {
  // 원본에 커밋 안 된 작업이 있으면, HEAD를 기준으로 쓸 때 그것까지 루프가 바꾼 것으로 잡혀
  // 최종 패치에 섞인다. 스모크 테스트에서 관계없는 파일 14개가 실제로 잡혔다.
  const cmds = [];
  const exec = (cmd) => {
    cmds.push(cmd);
    return { stdout: cmd.startsWith("git rev-parse") ? "basesha\n" : "", stderr: "", exitCode: 0 };
  };
  const noop = { existsSync: () => true, readFileSync: () => "", writeFileSync: () => {}, mkdirSync: () => {}, rmSync: () => {}, readdirSync: () => [], cpSync: () => {} };
  const spec = parseGoalSpec(goal());
  const { baseRef } = require("../lib/ralph-run.js").materializeCopies({
    sourceDir: "/src", workDir: "/w", probeDir: "/p", spec, fsImpl: noop, execImpl: exec,
  });
  assert.strictEqual(baseRef, "basesha");
  const commitIdx = cmds.findIndex((c) => c.includes("ralph base"));
  const revIdx = cmds.findIndex((c) => c.startsWith("git rev-parse"));
  assert.ok(commitIdx >= 0, `사본 상태를 먼저 커밋해야 합니다: ${JSON.stringify(cmds)}`);
  assert.ok(commitIdx < revIdx, "커밋이 rev-parse보다 앞서야 기준이 사본 시점이 된다");
});

test("AC-19: command 가드도 베이스라인 기준으로 걸 수 있다 (사본이 처음부터 빨간불인 경우)", () => {
  // 실제 실행(2026-09-11)에서 작업 사본의 테스트가 3개 깨진 채로 시작했다. 훅을 뺀 사본이라
  // `commit-habits.md`가 인용한 훅 파일이 사라지고 다이어그램 수치가 어긋난 탓이며, 목표와 무관하다.
  // `fail == 0`을 절대값으로 걸면 그 가드는 처음부터 만족될 수 없다.
  const spec = parseGoalSpec(goal({
    guards: [{ id: "tests", kind: "command", cmd: "node --test x", extract: "fail", op: "<=", relative_to_baseline: 1 }],
  }));
  const baseline = { response: { median_chars: 4000 }, command: { tests: 3 } };

  const same = evaluateMetrics({
    targets: spec.targets, guards: spec.guards,
    values: { response: { median_chars: 1000 }, command: { tests: 3 } }, baseline,
  });
  assert.strictEqual(same.guards[0].threshold, 3, "기준값은 베이스라인에서 온다");
  assert.deepStrictEqual(same.guardBreaches, [], "고치기 전과 같은 수면 깨뜨린 것이 아니다");
  assert.ok(same.met, "가드가 멀쩡하면 목표 달성이 성립한다");

  const worse = evaluateMetrics({
    targets: spec.targets, guards: spec.guards,
    values: { response: { median_chars: 1000 }, command: { tests: 4 } }, baseline,
  });
  assert.deepStrictEqual(worse.guardBreaches, ["tests"], "하나라도 더 깨지면 위반이다");
  assert.strictEqual(worse.met, false);
});

test("AC-20: 베이스라인에서 guard 명령을 재지 않으면 기준값이 서지 않는다", () => {
  const spec = parseGoalSpec(goal({
    guards: [{ id: "tests", kind: "command", cmd: "node --test x", extract: "fail", op: "<=", relative_to_baseline: 1 }],
  }));
  const ev = evaluateMetrics({
    targets: spec.targets, guards: spec.guards,
    values: { response: { median_chars: 1000 }, command: { tests: 0 } },
    baseline: { response: { median_chars: 4000 } },   // command 측정이 없다
  });
  assert.strictEqual(ev.guards[0].threshold, null, "기준을 모르면 null이어야 한다");
  assert.deepStrictEqual(ev.guardBreaches, ["tests"], "기준을 모르는 가드는 통과로 치지 않는다");
});

test("AC-21: 실제 실행이 베이스라인 guard를 먼저 재고 그 값을 기준으로 쓴다", () => {
  // 세션은 가짜, 명령은 항상 fail 2를 낸다. 고치기 전에도 2, 고친 뒤에도 2이므로 깨진 것이 없다.
  const calls = [];
  const fakeSpawn = () => ({
    status: 0,
    stdout: JSON.stringify({ is_error: false, num_turns: 1, duration_ms: 1, total_cost_usd: 0, result: "짧다 `a.md:1`", usage: {} }),
  });
  const fakeExec = (cmd) => {
    calls.push(cmd);
    if (cmd.includes("--test")) return { stdout: "ℹ pass 10\nℹ fail 2\n", stderr: "", exitCode: 1 };
    return { stdout: cmd.startsWith("git rev-parse") ? "basesha\n" : "", stderr: "", exitCode: 0 };
  };
  const files = {};
  const fs = {
    existsSync: (p) => p in files,
    readFileSync: (p) => files[p] ?? "",
    writeFileSync: (p, v) => { files[p] = v; },
    mkdirSync: () => {}, rmSync: () => {}, readdirSync: () => [], cpSync: () => {},
  };
  const spec = parseGoalSpec(goal({
    max_iterations: 1,
    targets: [{ id: "chars", kind: "response", extract: "median_chars", op: "<=", absolute: 10000 }],
    guards: [{ id: "tests", kind: "command", cmd: "node --test x", extract: "fail", op: "<=", relative_to_baseline: 1 }],
  }));
  const out = runLoop({
    sourceDir: "/src", spec, root: "/out", workDir: "/w", probeDir: "/p",
    dryRun: false, fsImpl: fs, spawnImpl: fakeSpawn, execImpl: fakeExec, log: () => {},
  });
  const testCalls = calls.filter((c) => c.includes("--test"));
  assert.ok(testCalls.length >= 2, `베이스라인과 이터레이션 양쪽에서 재야 합니다: ${testCalls.length}회`);
  const guard = out.history[0].evaluation.guards[0];
  assert.strictEqual(guard.threshold, 2, "기준값은 고치기 전에 잰 2여야 한다");
  assert.ok(guard.pass, "고치기 전과 같으면 통과여야 한다");
});

test("AC-22: 고칠 파일은 .claude 밖 작업본 경로로 옮겨 놓고, 그 경로를 프롬프트에 싣는다", () => {
  // 헤드리스 세션은 `.claude/**`를 민감 파일로 분류해 편집 승인 모드에서도 되묻고 멈춘다
  // (2026-09-11 실측). 루프에는 되물을 사람이 없으므로 그 자리에서 끝난다.
  assert.strictEqual(editMirrorPath(".claude/context/response-brevity.md"), "ralph-edit/claude__context__response-brevity.md");
  assert.strictEqual(editMirrorPath("docs/a.md"), "ralph-edit/docs__a.md");
  // 디렉터리가 다른 같은 이름이 겹치면 한쪽 변경이 조용히 사라진다.
  assert.notStrictEqual(editMirrorPath("a/x.md"), editMirrorPath("b/x.md"));

  const spec = parseGoalSpec(goal());
  const paths = spec.editable.map((p) => editMirrorPath(p));
  const prompt = buildIterationPrompt({ spec, iteration: 1, editablePaths: paths });
  assert.ok(prompt.includes(paths[0]), "작업본 경로가 프롬프트에 있어야 한다");
  assert.ok(!prompt.includes(`- ${spec.editable[0]}`), "원본 경로를 고치라고 시키면 안 된다");
});

test("AC-23: 최종 패치의 경로는 작업본이 아니라 원래 경로다", () => {
  // 되돌리지 않으면 저장소에 적용할 수 없는 패치가 나온다.
  const mirror = { "ralph-edit/claude__context__a.md": ".claude/context/a.md" };
  const raw = [
    "diff --git a/ralph-edit/claude__context__a.md b/ralph-edit/claude__context__a.md",
    "--- a/ralph-edit/claude__context__a.md",
    "+++ b/ralph-edit/claude__context__a.md",
    "+한 줄",
  ].join("\n");
  const out = rewritePatchPaths(raw, mirror);
  assert.ok(!out.includes("ralph-edit/"), `작업본 경로가 남으면 안 됩니다:\n${out}`);
  assert.strictEqual(out.split(".claude/context/a.md").length - 1, 4);

  const cmds = [];
  const exec = (cmd) => {
    cmds.push(cmd);
    if (cmd.startsWith("git diff --name-only")) return { stdout: "ralph-edit/claude__context__a.md\n.claude/context/a.md\n", stderr: "", exitCode: 0 };
    if (cmd.startsWith("git diff")) return { stdout: raw, stderr: "", exitCode: 0 };
    return { stdout: "", stderr: "", exitCode: 0 };
  };
  const { patch, stray } = collectPatch({
    workDir: "/w", baseRef: "base", editable: [".claude/context/a.md"], mirror, execImpl: exec,
  });
  assert.ok(patch.includes(".claude/context/a.md") && !patch.includes("ralph-edit/"), "패치 경로가 되돌아와야 한다");
  assert.ok(cmds.some((c) => c.includes('git diff base HEAD -- "ralph-edit/claude__context__a.md"')), `범위는 작업본이어야 합니다: ${JSON.stringify(cmds)}`);
  assert.deepStrictEqual(stray, [], "원본 경로가 그대로 있는 것은 범위 밖 변경이 아니다");
});

test("AC-24: 작업 세션에만 편집 승인 인자가 붙고, 측정 세션에는 붙지 않는다", () => {
  // 측정 세션까지 권한 설정을 바꾸면 재는 대상 자체가 평소 세션과 달라진다.
  const seen = [];
  const fakeSpawn = (cmd, args) => {
    seen.push(args);
    return { status: 0, stdout: JSON.stringify({ is_error: false, num_turns: 1, duration_ms: 1, total_cost_usd: 0, result: "짧다 `a.md:1`", usage: {} }) };
  };
  const exec = (cmd) => ({ stdout: cmd.startsWith("git rev-parse") ? "basesha\n" : "ℹ fail 0\n", stderr: "", exitCode: 0 });
  const files = {};
  const fs = {
    existsSync: (p) => p in files, readFileSync: (p) => files[p] ?? "", writeFileSync: (p, v) => { files[p] = v; },
    mkdirSync: () => {}, rmSync: () => {}, readdirSync: () => [], cpSync: () => {},
  };
  const spec = parseGoalSpec(goal({
    max_iterations: 1,
    targets: [{ id: "chars", kind: "response", extract: "median_chars", op: "<=", absolute: 10 }],
  }));
  runLoop({
    sourceDir: "/src", spec, root: "/out", workDir: "/w", probeDir: "/p",
    dryRun: false, fsImpl: fs, spawnImpl: fakeSpawn, execImpl: exec, log: () => {},
  });
  const withMode = seen.filter((a) => a.includes("--permission-mode"));
  assert.strictEqual(withMode.length, 1, `작업 세션 1개에만 붙어야 합니다: ${withMode.length}개`);
  assert.strictEqual(withMode[0][withMode[0].indexOf("--permission-mode") + 1], "acceptEdits");
});

test("AC-25: kind가 command인 target도 실제로 실행돼 값이 잡힌다", () => {
  // 회귀. 처음에는 명령을 돌리는 함수에 guards만 넘겨서, 명령 target을 쓴 목표 정의가
  // 스키마는 통과하면서 값이 영원히 null로 남았다. null은 통과로 치지 않으므로
  // 루프가 무엇을 해도 상한까지 돌다 exhausted로 끝났다 — context-slim-30 첫 실주행이
  // 14세션을 쓰고서야 이걸 드러냈다.
  const cmds = [];
  const exec = (cmd) => {
    cmds.push(cmd);
    if (cmd.startsWith("git rev-parse")) return { stdout: "basesha\n", stderr: "", exitCode: 0 };
    if (cmd.includes("budget-report")) return { stdout: "# import_chars 7000\n", stderr: "", exitCode: 0 };
    return { stdout: "ℹ fail 0\n", stderr: "", exitCode: 0 };
  };
  const fakeSpawn = () => ({
    status: 0,
    stdout: JSON.stringify({ is_error: false, num_turns: 1, duration_ms: 1, total_cost_usd: 0, result: "짧다 `a.md:1`", usage: {} }),
  });
  const files = {};
  const fs = {
    existsSync: (p) => p in files, readFileSync: (p) => files[p] ?? "", writeFileSync: (p, v) => { files[p] = v; },
    mkdirSync: () => {}, rmSync: () => {}, readdirSync: () => [], cpSync: () => {},
  };
  const spec = parseGoalSpec(goal({
    max_iterations: 1,
    targets: [{ id: "import_chars", kind: "command", cmd: "node budget-report.js", extract: "import_chars", op: "<=", absolute: 7600 }],
    guards: [],
  }));
  runLoop({
    sourceDir: "/src", spec, root: "/out", workDir: "/w", probeDir: "/p",
    dryRun: false, fsImpl: fs, spawnImpl: fakeSpawn, execImpl: exec, log: () => {},
  });

  assert.ok(cmds.some((c) => c.includes("budget-report")), `target 명령이 실행돼야 합니다: ${JSON.stringify(cmds)}`);
  const written = JSON.parse(files["/out/iteration-1/metrics.json"]);
  const t = written.evaluation.targets.find((x) => x.id === "import_chars");
  assert.strictEqual(t.value, 7000, "target 값이 잡혀야 합니다");
  assert.strictEqual(t.pass, true, "7000 <= 7600 이므로 통과해야 합니다");
});

test("AC-26: 명령 target도 베이스라인에서 재므로 relative_to_baseline을 쓸 수 있다", () => {
  // 베이스라인에서 안 재면 기준값이 서지 않아 배수 목표가 통째로 무력해진다 — AC-20의 target 판이다.
  let call = 0;
  const exec = (cmd) => {
    if (cmd.startsWith("git rev-parse")) return { stdout: "basesha\n", stderr: "", exitCode: 0 };
    if (cmd.includes("budget-report")) {
      call += 1;
      // 베이스라인 10000 → 회차 1에서 6000 (60%, 목표 70% 이하를 만족)
      return { stdout: `# import_chars ${call === 1 ? 10000 : 6000}\n`, stderr: "", exitCode: 0 };
    }
    return { stdout: "ℹ fail 0\n", stderr: "", exitCode: 0 };
  };
  const fakeSpawn = () => ({
    status: 0,
    stdout: JSON.stringify({ is_error: false, num_turns: 1, duration_ms: 1, total_cost_usd: 0, result: "짧다 `a.md:1`", usage: {} }),
  });
  const files = {};
  const fs = {
    existsSync: (p) => p in files, readFileSync: (p) => files[p] ?? "", writeFileSync: (p, v) => { files[p] = v; },
    mkdirSync: () => {}, rmSync: () => {}, readdirSync: () => [], cpSync: () => {},
  };
  const spec = parseGoalSpec(goal({
    max_iterations: 1,
    targets: [{ id: "import_chars", kind: "command", cmd: "node budget-report.js", extract: "import_chars", op: "<=", relative_to_baseline: 0.7 }],
    guards: [],
  }));
  runLoop({
    sourceDir: "/src", spec, root: "/out", workDir: "/w", probeDir: "/p",
    dryRun: false, fsImpl: fs, spawnImpl: fakeSpawn, execImpl: exec, log: () => {},
  });

  const baseline = JSON.parse(files["/out/baseline/metrics.json"]);
  assert.ok(baseline.guards.some((g) => g.id === "import_chars" && g.value === 10000), "베이스라인에서 target 명령을 재야 합니다");
  const t = JSON.parse(files["/out/iteration-1/metrics.json"]).evaluation.targets[0];
  assert.strictEqual(t.threshold, 7000, "기준값은 베이스라인 × 0.7 이어야 합니다");
  assert.strictEqual(t.pass, true);
});

test("AC-27: 세션이 실패한 측정은 집계에서 뺀다 — 오류 문자열이 '짧은 응답'으로 세어지면 안 된다", () => {
  // 분량을 줄이는 목표에서는 세션 실패가 개선처럼 보인다. 78자짜리 API 오류 문자열은
  // 완벽한 성적이 된다. context-slim-30 2회차 실주행이 실제로 여기 걸렸다.
  const agg = aggregateProbes([
    { probeId: "p1", chars: 5000, lines: 100, citationCount: 2, ok: true },
    { probeId: "p1", chars: 5200, lines: 104, citationCount: 2, ok: true },
    { probeId: "p1", chars: 78, lines: 1, citationCount: 0, ok: false },
  ]);
  assert.strictEqual(agg.runs, 2, "유효한 측정만 세어야 합니다");
  assert.strictEqual(agg.failedRuns, 1);
  assert.strictEqual(agg.attemptedRuns, 3);
  assert.strictEqual(agg.usable, true, "3회 중 2회 성공이면 과반이라 쓸 수 있습니다");
  assert.strictEqual(agg.median_chars, 5100, "78자가 섞이면 중앙값이 5000이 된다");
  assert.strictEqual(agg.min_citation_count, 2, "실패 측정의 인용 0이 섞이면 안 됩니다");
});

test("AC-28: ok 필드가 없는 측정은 유효로 본다 — 없는 것과 거짓은 다르다", () => {
  const agg = aggregateProbes([
    { probeId: "p1", chars: 100, lines: 2, citationCount: 1 },
    { probeId: "p1", chars: 300, lines: 6, citationCount: 1 },
  ]);
  assert.strictEqual(agg.runs, 2);
  assert.strictEqual(agg.failedRuns, 0);
  assert.strictEqual(agg.median_chars, 200);
});

test("AC-29: 한 과제의 측정이 과반 실패하면 지표를 통째로 null로 낸다", () => {
  // 남은 한 개의 중앙값을 대표값이라 부를 수 없다. null은 통과로 치지 않으므로
  // 못 잰 회차가 조용히 성공으로 넘어가지 않는다.
  const agg = aggregateProbes([
    { probeId: "p1", chars: 5000, lines: 100, citationCount: 2, ok: true },
    { probeId: "p1", chars: 78, lines: 1, citationCount: 0, ok: false },
    { probeId: "p1", chars: 78, lines: 1, citationCount: 0, ok: false },
  ]);
  assert.strictEqual(agg.usable, false);
  assert.strictEqual(agg.median_chars, null);
  assert.strictEqual(agg.median_citation_count, null);
  assert.strictEqual(agg.failedRuns, 2, "몇 개가 실패했는지는 그대로 남겨야 합니다");
});

test("AC-30: 과제 하나만 통째로 실패해도 전체를 못 쓴다고 본다", () => {
  // 과제가 빠지면 남은 과제의 값이 대표값이 되어 버린다. 과제마다 응답 길이가 원래
  // 다르므로(computeNoiseBand가 과제 안에서 재는 이유와 같다) 그 대표값은 의미가 없다.
  const agg = aggregateProbes([
    { probeId: "p1", chars: 5000, lines: 100, citationCount: 2, ok: true },
    { probeId: "p1", chars: 5200, lines: 104, citationCount: 2, ok: true },
    { probeId: "p2", chars: 78, lines: 1, citationCount: 0, ok: false },
    { probeId: "p2", chars: 78, lines: 1, citationCount: 0, ok: false },
  ]);
  assert.strictEqual(agg.usable, false);
  assert.strictEqual(agg.median_chars, null);
});

test("AC-31: 베이스라인을 못 재면 회차를 하나도 시작하지 않고 멈춘다", () => {
  // 배수 목표는 기준값이 없어 서지 않고 노이즈 폭도 못 구한다. 그런데도 상한까지
  // 돌면 회차마다 실비만 나간다 — 2회차 실주행이 그렇게 28세션을 태웠다.
  let sessions = 0;
  const fakeSpawn = () => {
    sessions += 1;
    return { status: 1, stdout: JSON.stringify({ is_error: true, num_turns: 1, duration_ms: 1, total_cost_usd: 0, result: "API Error: ENOTFOUND", usage: {} }) };
  };
  const exec = (cmd) => ({ stdout: cmd.startsWith("git rev-parse") ? "basesha\n" : "ℹ fail 0\n", stderr: "", exitCode: 0 });
  const files = {};
  const fs = {
    existsSync: (p) => p in files, readFileSync: (p) => files[p] ?? "", writeFileSync: (p, v) => { files[p] = v; },
    mkdirSync: () => {}, rmSync: () => {}, readdirSync: () => [], cpSync: () => {},
  };
  const spec = parseGoalSpec(goal({ max_iterations: 4 }));
  const { summary } = runLoop({
    sourceDir: "/src", spec, root: "/out", workDir: "/w", probeDir: "/p",
    dryRun: false, fsImpl: fs, spawnImpl: fakeSpawn, execImpl: exec, log: () => {},
  });

  assert.strictEqual(summary.outcome, "aborted", `베이스라인이 못 쓸 상태면 중단해야 합니다: ${summary.outcome}`);
  assert.strictEqual(summary.iterations, 0, "회차를 시작하면 안 됩니다");
  assert.strictEqual(sessions, spec.probes.length * spec.repeats, `베이스라인 세션만 띄워야 합니다: ${sessions}개`);
  assert.ok(files["/out/summary.json"], "summary.json은 남겨야 합니다");
});

test("AC-32: 명령 지표는 작업본을 옮겨 심은 뒤 측정 사본에서 잰다", () => {
  // 회귀. 옮겨 심기 전에 재면 작업 세션이 고친 내용을 못 보고 베이스라인과 같은 값이
  // 계속 나온다 — context-slim-30 3회차 실주행에서 import_chars가 두 회차 내내
  // 10,896에서 미동이 없었다. 순서와 대상 사본을 둘 다 잠근다.
  const order = [];
  const exec = (cmd, opts) => {
    if (cmd.startsWith("git rev-parse")) return { stdout: "basesha\n", stderr: "", exitCode: 0 };
    if (cmd.includes("budget-report")) order.push({ step: "measure", cwd: opts && opts.cwd });
    return { stdout: "# import_chars 100\nℹ fail 0\n", stderr: "", exitCode: 0 };
  };
  const fakeSpawn = () => ({
    status: 0,
    stdout: JSON.stringify({ is_error: false, num_turns: 1, duration_ms: 1, total_cost_usd: 0, result: "짧다 `a.md:1`", usage: {} }),
  });
  const files = { "/w/ralph-edit/claude__context__response-brevity.md": "줄인 내용" };
  const fs = {
    existsSync: (p) => p in files,
    readFileSync: (p) => files[p] ?? "",
    writeFileSync: (p, v) => { files[p] = v; if (p.startsWith("/p/")) order.push({ step: "sync", path: p }); },
    mkdirSync: () => {}, rmSync: () => {}, readdirSync: () => [], cpSync: () => {},
  };
  const spec = parseGoalSpec(goal({
    max_iterations: 1,
    targets: [{ id: "import_chars", kind: "command", cmd: "node budget-report.js", extract: "import_chars", op: "<=", absolute: 7600 }],
    guards: [],
  }));
  runLoop({
    sourceDir: "/src", spec, root: "/out", workDir: "/w", probeDir: "/p",
    dryRun: false, fsImpl: fs, spawnImpl: fakeSpawn, execImpl: exec, log: () => {},
  });

  const measures = order.filter((o) => o.step === "measure");
  assert.ok(measures.length >= 2, `베이스라인과 이터레이션에서 각각 재야 합니다: ${measures.length}회`);
  for (const m of measures) {
    assert.strictEqual(m.cwd, "/p", `측정 사본에서 재야 합니다: ${m.cwd}`);
  }
  // 이터레이션의 측정은 옮겨 심기 뒤에 와야 한다.
  const lastSync = order.map((o) => o.step).lastIndexOf("sync");
  const lastMeasure = order.map((o) => o.step).lastIndexOf("measure");
  assert.ok(lastSync < lastMeasure, `옮겨 심은 뒤에 재야 합니다: ${JSON.stringify(order.map((o) => o.step))}`);
});

test("AC-33: 회차마다 산출물 전문 사본과 루브릭을 남긴다", () => {
  // diff만 남기면 특정 회차의 전체 모습을 보려고 앞 회차를 되짚어 재구성해야 한다.
  const exec = (cmd) => ({ stdout: cmd.startsWith("git rev-parse") ? "basesha\n" : "ℹ fail 0\n", stderr: "", exitCode: 0 });
  const fakeSpawn = () => ({
    status: 0,
    stdout: JSON.stringify({ is_error: false, num_turns: 1, duration_ms: 1, total_cost_usd: 0, result: "짧다 `a.md:1`", usage: {} }),
  });
  // 사본 만들기는 cpSync가 하는데 가짜 fs는 아무것도 안 한다. 사본에 파일이 있는 상태를 직접 만든다.
  const body = "# 가\n- 근거: `a.js:1`\n- 한계를 말한다.\n";
  const files = { "/src/.claude/context/response-brevity.md": body, "/w/.claude/context/response-brevity.md": body };
  const fs = {
    existsSync: (p) => p in files,
    readFileSync: (p) => files[p] ?? "",
    writeFileSync: (p, v) => { files[p] = v; },
    mkdirSync: () => {}, rmSync: () => {}, readdirSync: () => [], cpSync: () => {},
  };
  const spec = parseGoalSpec(goal({ max_iterations: 1 }));
  runLoop({
    sourceDir: "/src", spec, root: "/out", workDir: "/w", probeDir: "/p",
    dryRun: false, fsImpl: fs, spawnImpl: fakeSpawn, execImpl: exec, log: () => {},
  });

  const rubricPath = Object.keys(files).find((p) => p.endsWith("iteration-1/rubric.json"));
  assert.ok(rubricPath, `루브릭을 남겨야 합니다: ${JSON.stringify(Object.keys(files))}`);
  const rubric = JSON.parse(files[rubricPath]);
  assert.equal(rubric.dimensions.length, 6, "여섯 차원을 남겨야 합니다");
  assert.ok(rubric.caveat.includes("종료 판정에 쓰이지 않는다"));
  assert.ok(Object.keys(files).some((p) => p.includes("iteration-1/snapshot/")), "전문 사본을 남겨야 합니다");

  const metrics = JSON.parse(files["/out/iteration-1/metrics.json"]);
  assert.ok(metrics.rubric, "metrics.json에도 루브릭이 실려야 합니다");
});

test("AC-34: 루브릭은 종료 판정에 쓰이지 않는다", () => {
  // 점수를 판정에 물리면 루프가 점수를 최적화한다. 이 저장소가 세 실험 연속으로
  // "채점 기준이 대상보다 부정확했다"를 겪은 뒤 일부러 뺀 결정이다.
  const exec = (cmd) => ({ stdout: cmd.startsWith("git rev-parse") ? "basesha\n" : "ℹ fail 0\n", stderr: "", exitCode: 0 });
  const fakeSpawn = () => ({
    status: 0,
    stdout: JSON.stringify({ is_error: false, num_turns: 1, duration_ms: 1, total_cost_usd: 0, result: "짧다 `a.md:1`", usage: {} }),
  });
  const body2 = "# 가\n- 근거: `a.js:1`\n";
  const files = { "/src/.claude/context/response-brevity.md": body2, "/w/.claude/context/response-brevity.md": body2 };
  const fs = {
    existsSync: (p) => p in files, readFileSync: (p) => files[p] ?? "", writeFileSync: (p, v) => { files[p] = v; },
    mkdirSync: () => {}, rmSync: () => {}, readdirSync: () => [], cpSync: () => {},
  };
  // target은 절대 통과할 수 없게 두고, 루브릭은 전부 1.0이 되게 둔다.
  const spec = parseGoalSpec(goal({
    max_iterations: 1,
    targets: [{ id: "chars", kind: "response", extract: "median_chars", op: "<=", absolute: 1 }],
    guards: [],
  }));
  const { summary } = runLoop({
    sourceDir: "/src", spec, root: "/out", workDir: "/w", probeDir: "/p",
    dryRun: false, fsImpl: fs, spawnImpl: fakeSpawn, execImpl: exec, log: () => {},
  });
  assert.notEqual(summary.outcome, "done", "루브릭이 좋아도 target을 못 채우면 done이 아니다");
  assert.ok(summary.trend[0].rubric, "그래도 추이에는 루브릭이 실린다");
});
