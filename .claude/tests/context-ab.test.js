const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");

const {
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
} = require("../lib/context-ab.js");
const { maskSecrets, runMatrix, loadConfig } = require("../lib/context-ab-run.js");

/**
 * 메모리 파일시스템. 이 하네스는 한 번 돌 때마다 실비가 나가므로,
 * 테스트가 실제 파일시스템이나 실제 프로세스를 절대 건드리지 않게 한다.
 */
function fakeFs(files = {}) {
  const map = new Map(Object.entries(files).map(([k, v]) => [path.resolve(k), v]));
  const norm = (p) => path.resolve(p);
  const impl = {
    writes: map,
    existsSync: (p) => map.has(norm(p)) || [...map.keys()].some((k) => k.startsWith(`${norm(p)}${path.sep}`)),
    readFileSync: (p) => {
      const v = map.get(norm(p));
      if (v === undefined) throw new Error(`ENOENT: ${p}`);
      return v;
    },
    writeFileSync: (p, data) => map.set(norm(p), String(data)),
    mkdirSync: () => {},
    rmSync: (p, opts = {}) => {
      const target = norm(p);
      for (const key of [...map.keys()]) {
        if (key === target || (opts.recursive && key.startsWith(`${target}${path.sep}`))) map.delete(key);
      }
    },
    readdirSync: (p) => {
      const prefix = `${norm(p)}${path.sep}`;
      const names = new Set();
      for (const key of map.keys()) {
        if (key.startsWith(prefix)) names.add(key.slice(prefix.length).split(path.sep)[0]);
      }
      return [...names].sort();
    },
    cpSync: (src, dest, opts = {}) => {
      const from = `${norm(src)}${path.sep}`;
      for (const [key, value] of [...map.entries()]) {
        if (!key.startsWith(from)) continue;
        if (opts.filter && !opts.filter(key)) continue;
        map.set(path.join(norm(dest), key.slice(from.length)), value);
      }
    },
  };
  return impl;
}

const ARM_A = { name: "armA", label: "주입됨", guidelines: "all", registered: true, hooks: false, git: false };
const ARM_C = { name: "armC", label: "지침 없음", guidelines: [], registered: false, hooks: false, git: false };

// --- 팔 스펙 ---

test("AC-1: 알 수 없는 필드나 빠진 플래그가 있는 팔 정의는 거부한다", () => {
  assert.throws(() => parseArmSpec({ ...ARM_A, typo: 1 }), /알 수 없는 팔 필드/);
  const { git, ...noGit } = ARM_A;
  assert.throws(() => parseArmSpec(noGit), /git는 boolean/);
  assert.throws(() => parseArmSpec({ ...ARM_A, name: "arm A" }), /팔 이름/);
  // 파일이 하나도 없는데 등록만 하겠다는 조합은 끊어진 등록만 남긴다.
  assert.throws(() => parseArmSpec({ ...ARM_C, registered: true }), /끊어진 등록/);
});

test("AC-1b: guidelines와 registered는 별개 축이다 — 둘 다 스펙에 남는다", () => {
  // 두 축을 합치면 실험 1이 겪은 통제 누수(등록만 지웠는데 팔이 파일을 발견함)를 다시 하게 된다.
  const spec = parseArmSpec({ ...ARM_A, registered: false });
  assert.strictEqual(spec.guidelines, "all");
  assert.strictEqual(spec.registered, false);
});

// --- 레지스트리 재작성 ---

const INDEX = ["# 레지스트리", "", "설명 문장 @는 아니다", "@alpha.md", "@beta.md", ""].join("\n");

test("AC-2: 지침이 없는 팔은 index.md의 @ 줄이 0개가 된다", () => {
  const out = rewriteRegistry(INDEX, []);
  assert.strictEqual(out.split(/\r?\n/).filter((l) => /^@/.test(l.trim())).length, 0);
  assert.match(out, /# 레지스트리/); // 산문은 남는다 — 팔끼리 다른 것이 등록만이어야 한다
});

test("AC-3: 등록만 지운 팔에서도 지침 파일은 디스크에 남는다", () => {
  const spec = parseArmSpec({ ...ARM_A, registered: false });
  const plan = planArmTree(spec, ["index.md", "README.md", "alpha.md", "beta.md"]);
  assert.deepStrictEqual(plan.keepGuidelines, ["alpha.md", "beta.md"]);
  assert.deepStrictEqual(plan.deleteGuidelines, []);
  assert.deepStrictEqual(plan.registryKeep, []); // 등록만 사라진다
});

test("AC-3b: 지침 없는 팔은 파일까지 지운다", () => {
  const plan = planArmTree(parseArmSpec(ARM_C), ["index.md", "README.md", "alpha.md", "beta.md"]);
  assert.deepStrictEqual(plan.keepGuidelines, []);
  assert.deepStrictEqual(plan.deleteGuidelines, ["alpha.md", "beta.md"]);
});

test("AC-3c: index.md와 README.md는 지침으로 세지 않는다", () => {
  const plan = planArmTree(parseArmSpec(ARM_A), ["index.md", "README.md", "alpha.md"]);
  assert.deepStrictEqual(plan.keepGuidelines, ["alpha.md"]);
});

// --- 사본 계획 ---

test("AC-4: .git과 훅은 스펙대로 제외된다 (훅 등록부까지 함께)", () => {
  const off = planArmTree(parseArmSpec(ARM_A), ["alpha.md"]);
  assert.ok(off.excludes.includes(".git"), "git:false면 .git을 뺀다 — gitStatus 누수(실험 3) 때문");
  assert.ok(off.excludes.includes(".claude/hooks"));
  // 훅 디렉터리만 지우고 settings.json을 남기면 매 이벤트마다 실행 실패가 난다.
  assert.ok(off.excludes.includes(".claude/settings.json"));

  const on = planArmTree(parseArmSpec({ ...ARM_A, hooks: true, git: true }), ["alpha.md"]);
  assert.ok(!on.excludes.includes(".git"));
  assert.ok(!on.excludes.includes(".claude/hooks"));
});

test("AC-4b: 존재하지 않는 지침을 지정하면 missing으로 드러낸다", () => {
  const spec = parseArmSpec({ ...ARM_A, guidelines: ["없는파일.md"] });
  assert.deepStrictEqual(planArmTree(spec, ["alpha.md"]).missing, ["없는파일.md"]);
});

// --- 헤드리스 출력 파싱 ---

const REAL_SHAPE = JSON.stringify({
  is_error: false,
  num_turns: 12,
  duration_ms: 1643,
  duration_api_ms: 2441,
  total_cost_usd: 0.0758,
  session_id: "abc",
  result: "ok",
  usage: { input_tokens: 2, output_tokens: 4, cache_read_input_tokens: 10126, cache_creation_input_tokens: 6973 },
});

test("AC-5: 실제 출력 스키마에서 지표를 꺼낸다 (2026-09-07 관측 기준)", () => {
  const p = parseHeadlessResult(REAL_SHAPE);
  assert.strictEqual(p.ok, true);
  assert.strictEqual(p.numTurns, 12);
  assert.strictEqual(p.costUsd, 0.0758);
  assert.strictEqual(p.cacheReadTokens, 10126);
});

test("AC-5b: 필드가 빠지거나 JSON이 깨져도 예외 없이 null을 채우고 원본을 보존한다", () => {
  // CLI 출력 스키마는 우리 것이 아니다. 버전이 오르면 바뀔 수 있으므로 러너가 죽으면 안 된다.
  const partial = parseHeadlessResult('{"result":"hi"}');
  assert.strictEqual(partial.durationMs, null);
  assert.strictEqual(partial.numTurns, null);
  assert.strictEqual(partial.result, "hi");

  const broken = parseHeadlessResult("not json");
  assert.strictEqual(broken.ok, false);
  assert.ok(broken.parseError);
  assert.strictEqual(broken.raw, null);
});

test("AC-5c: total_tokens는 캐시 읽기·생성까지 합산한다", () => {
  const t = toTimingRecord(parseHeadlessResult(REAL_SHAPE));
  assert.strictEqual(t.total_tokens, 2 + 4 + 10126 + 6973);
  assert.strictEqual(t.total_duration_seconds, 1.6);
});

// --- 채점 ---

test("AC-6: 채점되지 않은 항목이 남아 있으면 마감을 거부한다", () => {
  const skeleton = buildGradingSkeleton([{ id: "R1", text: "무언가" }, { id: "R2", text: "다른 것" }]);
  assert.strictEqual(skeleton.expectations[0].passed, null);
  assert.strictEqual(skeleton.status, "pending");
  assert.throws(() => finalizeGrading(skeleton), /채점되지 않은 항목 2개/);

  // 절반만 채워도 여전히 거부한다 — 미채점을 0점이나 만점으로 뭉개면
  // '테스트 0개를 전부 통과로 읽는' 것과 같은 사고가 난다.
  skeleton.expectations[0].passed = true;
  assert.throws(() => finalizeGrading(skeleton), /채점되지 않은 항목 1개/);
});

test("AC-7: pass_rate 계산과 필드명이 aggregate_benchmark.py 계약과 맞는다", () => {
  const skeleton = buildGradingSkeleton([
    { id: "R1", text: "a" },
    { id: "R2", text: "b" },
    { id: "R3", text: "c" },
  ]);
  skeleton.expectations.forEach((e, i) => {
    e.passed = i < 2;
  });
  const done = finalizeGrading(skeleton, "human");
  assert.deepStrictEqual(done.summary, { passed: 2, failed: 1, total: 3, pass_rate: 0.67 });
  // 뷰어와 집계기가 text/passed/evidence 라는 이름에 의존한다.
  assert.deepStrictEqual(Object.keys(done.expectations[0]).sort(), ["evidence", "passed", "text"]);
  assert.match(done.expectations[0].text, /^R1: /);
});

test("AC-7b: 미채점 실행은 집계 게이트에서 걸린다", () => {
  // 키가 없으면 집계기는 pass_rate를 조용히 0.0으로 채운다 — '채점 안 함'이 '전부 실패'로 둔갑한다.
  const pending = { path: "/r/a/grading.json", grading: buildGradingSkeleton([{ id: "R1", text: "t" }]) };
  const graded = { path: "/r/b/grading.json", grading: finalizeGrading(
    (() => { const g = buildGradingSkeleton([{ id: "R1", text: "t" }]); g.expectations[0].passed = true; return g; })()
  ) };
  assert.strictEqual(verifyGrading([pending, graded]).ok, false);
  assert.deepStrictEqual(verifyGrading([pending, graded]).pending, ["/r/a/grading.json"]);
  assert.strictEqual(verifyGrading([graded]).ok, true);
  assert.strictEqual(graded.grading.status, "graded");
});

// --- 경로·계획 ---

test("AC-8: 실행 경로에 run-* 계층이 있다 (없으면 집계기가 조용히 건너뛴다)", () => {
  const p = runDirPath("/root", { iteration: 1, evalName: "skill-draft", arm: "armA", run: 2 });
  assert.strictEqual(p, path.join("/root", "iteration-1", "eval-skill-draft", "armA", "run-2"));
});

test("AC-8b: planMatrix가 팔×이벌×반복을 빠짐없이 펼친다", () => {
  const plan = planMatrix({
    arms: [{ name: "armA" }, { name: "armC" }],
    evals: [{ id: 0, eval_name: "e1", prompt: "p1" }, { id: 1, eval_name: "e2", prompt: "p2" }],
    repeats: 2,
    iteration: 1,
    root: "/root",
  });
  assert.strictEqual(plan.length, 8);
  assert.strictEqual(new Set(plan.map((s) => s.dir)).size, 8);
});

// --- 러너 ---

function armTree() {
  return {
    "/src/.claude/context/index.md": INDEX,
    "/src/.claude/context/alpha.md": "지침 A",
    "/src/.claude/context/beta.md": "지침 B",
    "/src/.claude/hooks/h.js": "// hook",
    "/src/.claude/settings.json": "{}",
    "/src/.git/config": "[core]",
    "/src/CLAUDE.md": "@.claude/context/index.md\n",
  };
}

test("AC-9: 가짜 spawn으로 실행 횟수가 팔×이벌×반복과 정확히 같다", () => {
  const fs = fakeFs(armTree());
  const calls = [];
  const spawn = (cmd, args, opts) => {
    calls.push({ cmd, cwd: opts.cwd });
    return { status: 0, stdout: REAL_SHAPE, stderr: "" };
  };
  const out = runMatrix({
    sourceDir: "/src",
    workDir: "/work",
    root: "/runs",
    arms: [parseArmSpec(ARM_A), parseArmSpec(ARM_C)],
    evals: [{ id: 0, eval_name: "e1", prompt: "p1", rubric: [{ id: "R1", text: "t" }] }],
    repeats: 2,
    dryRun: false,
    fsImpl: fs,
    spawnImpl: spawn,
    log: () => {},
  });
  assert.strictEqual(calls.length, 4);
  assert.strictEqual(out.results.filter((r) => r.ok).length, 4);
  assert.ok(calls.every((c) => c.cmd === "claude"));
});

test("AC-9b: 실행마다 timing.json·grading.json 골격·응답이 남는다", () => {
  const fs = fakeFs(armTree());
  runMatrix({
    sourceDir: "/src",
    workDir: "/work",
    root: "/runs",
    arms: [parseArmSpec(ARM_A)],
    evals: [{ id: 0, eval_name: "e1", prompt: "p1", rubric: [{ id: "R1", text: "t" }] }],
    repeats: 1,
    dryRun: false,
    fsImpl: fs,
    spawnImpl: () => ({ status: 0, stdout: REAL_SHAPE, stderr: "" }),
    log: () => {},
  });
  const base = path.resolve("/runs/iteration-1/eval-e1/armA/run-1");
  assert.ok(fs.writes.has(path.join(base, "timing.json")));
  assert.ok(fs.writes.has(path.join(base, "outputs/response.txt")));
  const grading = JSON.parse(fs.writes.get(path.join(base, "grading.json")));
  assert.strictEqual(grading.expectations[0].passed, null, "채점은 사람이 한다 — 러너가 미리 채우지 않는다");
  // summary 키를 null로 두면 aggregate_benchmark.py:130이 None에 .get을 걸어 죽는다.
  assert.strictEqual("summary" in grading, false);
  assert.strictEqual(grading.status, "pending");
});

test("AC-9c: 팔 사본에 그 팔의 상시 로드 실측치가 기록된다", () => {
  // 실험 1의 핵심 발견("6,830자를 더 지고도 입력 토큰을 12만 개 덜 썼다")이 이 수치 없이는 안 나온다.
  const fs = fakeFs(armTree());
  runMatrix({
    sourceDir: "/src",
    workDir: "/work",
    root: "/runs",
    arms: [parseArmSpec(ARM_A), parseArmSpec(ARM_C)],
    evals: [{ id: 0, eval_name: "e1", prompt: "p1", rubric: [] }],
    repeats: 1,
    dryRun: false,
    fsImpl: fs,
    spawnImpl: () => ({ status: 0, stdout: REAL_SHAPE, stderr: "" }),
    log: () => {},
  });
  const a = JSON.parse(fs.writes.get(path.resolve("/work/armA/arm.json")));
  const c = JSON.parse(fs.writes.get(path.resolve("/work/armC/arm.json")));
  assert.ok(a.budget.alwaysLoaded.total > c.budget.alwaysLoaded.total, "주입된 팔이 더 많이 지고 시작해야 한다");
  // 사본에서 지침 파일이 실제로 사라졌는지도 함께 본다.
  assert.strictEqual(fs.writes.has(path.resolve("/work/armC/.claude/context/alpha.md")), false);
  assert.strictEqual(fs.writes.has(path.resolve("/work/armA/.claude/context/alpha.md")), true);
});

test("AC-9d: 훅과 .git은 사본에 복사되지 않는다", () => {
  const fs = fakeFs(armTree());
  runMatrix({
    sourceDir: "/src", workDir: "/work", root: "/runs",
    arms: [parseArmSpec(ARM_A)],
    evals: [{ id: 0, eval_name: "e1", prompt: "p1", rubric: [] }],
    repeats: 1, dryRun: false, fsImpl: fs,
    spawnImpl: () => ({ status: 0, stdout: REAL_SHAPE, stderr: "" }),
    log: () => {},
  });
  assert.strictEqual(fs.writes.has(path.resolve("/work/armA/.claude/hooks/h.js")), false);
  assert.strictEqual(fs.writes.has(path.resolve("/work/armA/.git/config")), false);
});

test("AC-10: dry-run이 기본이고 이때 spawn은 0회다", () => {
  let calls = 0;
  const out = runMatrix({
    sourceDir: "/src",
    workDir: "/work",
    root: "/runs",
    arms: [parseArmSpec(ARM_A), parseArmSpec(ARM_C)],
    evals: [{ id: 0, eval_name: "e1", prompt: "p1", rubric: [] }],
    repeats: 2,
    // dryRun 을 일부러 넘기지 않는다 — 기본값이 안전한 쪽인지가 이 AC의 요지다.
    fsImpl: fakeFs(armTree()),
    spawnImpl: () => {
      calls += 1;
      return { status: 0, stdout: "{}", stderr: "" };
    },
    log: () => {},
  });
  assert.strictEqual(calls, 0);
  assert.strictEqual(out.dryRun, true);
  assert.strictEqual(out.plan.length, 4);
});

test("AC-10b: 응답을 남길 때 명백한 시크릿 접두사는 가린다", () => {
  // 길이 컷·마스킹까지만 한다. 완전한 비식별화는 약속하지 않는다(sensitive-info.md).
  const masked = maskSecrets("키는 sk-abcdefgh12345678 이고 ghp_zzzzzzzzzzzz 도 있다");
  assert.ok(!masked.includes("abcdefgh12345678"));
  assert.match(masked, /masked/);
});

// --- 실제 저장소 회귀 감시 ---

test("AC-11: 커밋된 experiments/context-ab 설정이 스키마를 통과한다", () => {
  const configDir = path.resolve(__dirname, "..", "..", "experiments", "context-ab");
  const { arms, evals } = loadConfig(configDir);
  assert.ok(arms.length >= 3, "주입·미주입·부재 3팔이 있어야 두 축(A↔B, B↔C)을 가를 수 있다");
  assert.ok(evals.every((e) => Array.isArray(e.rubric) && e.rubric.length > 0), "루브릭 없는 과제는 채점할 수 없다");
  // 팔끼리 달라야 하는 것은 지침 구성뿐이다. 훅·.git 설정이 팔마다 다르면 통제가 샌다.
  assert.strictEqual(new Set(arms.map((a) => `${a.hooks}/${a.git}`)).size, 1);
});
