#!/usr/bin/env node
/**
 * 컨텍스트 A/B 실험 러너 — 부작용 담당(파일 복사·프로세스 실행).
 *
 * 판정·파싱·계산은 전부 `context-ab.js`(순수)에 있다. 여기는 그 결과를 디스크와
 * 프로세스에 옮기는 일만 한다. `fs`·`spawn`·`now`를 주입받으므로 실제 실행 없이
 * 테스트할 수 있다 — 이 하네스는 한 번 돌 때마다 실비가 나가서, 테스트가 실행을
 * 건드리면 안 된다.
 *
 * 기본은 dry-run이다. 실제 호출은 `--go`를 명시해야 일어난다.
 * 훅이 아니라 사람이 부르는 도구이므로 막지 않고 되묻는 대신, 기본값을 안전한 쪽에 둔다.
 *
 * 사용:
 *   node .claude/lib/context-ab-run.js --config experiments/context-ab
 *   node .claude/lib/context-ab-run.js --config experiments/context-ab --go --arms armC --repeats 1
 */
const nodeFs = require("node:fs");
const nodePath = require("node:path");
const { spawnSync: nodeSpawnSync } = require("node:child_process");

const {
  parseArmSpec,
  rewriteRegistry,
  planArmTree,
  parseHeadlessResult,
  toTimingRecord,
  buildGradingSkeleton,
  verifyGrading,
  planMatrix,
  estimateCost,
} = require("./context-ab.js");
const { buildContextMap, summarizeBudget } = require("./context-map.js");

/** 시크릿 접두사만 가린다. 완전한 비식별화는 약속하지 않는다(.claude/context/sensitive-info.md). */
function maskSecrets(text) {
  if (typeof text !== "string") return "";
  return text.replace(/\b(sk-|ghp_|AKIA)[A-Za-z0-9_\-]{8,}/g, (m) => `${m.slice(0, 4)}…[masked]`);
}

/**
 * 팔 사본을 실제로 만든다.
 *
 * 사본은 저장소 **밖**(스크래치패드)에 만든다. 저장소 안에 두면 매 실행마다 git status가
 * 달라져 big-change-commit-check.js·os-retro-check.js가 무한 재발동한다 —
 * .gitignore가 같은 사고를 이미 네 번 기록해 뒀다.
 */
function materializeArm(spec, { sourceDir, destDir, fsImpl = nodeFs }) {
  const contextDir = nodePath.join(sourceDir, ".claude", "context");
  const guidelineNames = fsImpl.existsSync(contextDir)
    ? fsImpl.readdirSync(contextDir).filter((n) => n.endsWith(".md"))
    : [];
  const plan = planArmTree(spec, guidelineNames);
  if (plan.missing.length > 0) {
    throw new Error(`${spec.name}: 존재하지 않는 지침을 지정했습니다 — ${plan.missing.join(", ")}`);
  }

  fsImpl.rmSync(destDir, { recursive: true, force: true });
  const absExcludes = plan.excludes.map((rel) => nodePath.join(sourceDir, rel));
  fsImpl.cpSync(sourceDir, destDir, {
    recursive: true,
    filter: (src) => !absExcludes.some((ex) => src === ex || src.startsWith(`${ex}${nodePath.sep}`)),
  });

  const destContext = nodePath.join(destDir, ".claude", "context");
  for (const name of plan.deleteGuidelines) {
    fsImpl.rmSync(nodePath.join(destContext, name), { force: true });
  }
  const indexPath = nodePath.join(destContext, "index.md");
  if (fsImpl.existsSync(indexPath)) {
    const rewritten = rewriteRegistry(fsImpl.readFileSync(indexPath, "utf8"), plan.registryKeep);
    fsImpl.writeFileSync(indexPath, rewritten);
  }

  // 이 팔이 실제로 얼마를 지고 시작하는지 재서 기록한다. 결과 해석에 반드시 필요하다 —
  // 실험 1의 핵심 발견("6,830자를 더 지고도 입력 토큰을 12만 개 덜 썼다")이 이 수치 없이는 나오지 않는다.
  let budget = null;
  try {
    budget = summarizeBudget(buildContextMap({ projectDir: destDir, fsOverrides: fsImpl }));
  } catch (err) {
    budget = { error: err.message };
  }

  const record = { spec, plan, budget, materializedAt: new Date().toISOString() };
  fsImpl.writeFileSync(nodePath.join(destDir, "arm.json"), `${JSON.stringify(record, null, 2)}\n`);
  return record;
}

/** 팔 사본 안에서 헤드리스 세션 1회. 실패해도 던지지 않고 결과에 담아 돌려준다. */
function runOnce({ armDir, prompt, model, extraArgs = [], spawnImpl = nodeSpawnSync, timeoutMs = 900000 }) {
  const args = ["-p", prompt, "--output-format", "json"];
  if (model) args.push("--model", model);
  args.push(...extraArgs);
  const proc = spawnImpl("claude", args, {
    cwd: armDir,
    encoding: "utf8",
    timeout: timeoutMs,
    maxBuffer: 64 * 1024 * 1024,
  });
  const parsed = parseHeadlessResult(proc.stdout);
  return { parsed, exitCode: proc.status, stderr: (proc.stderr || "").slice(0, 4000) };
}

/**
 * 팔×이벌×반복을 돈다.
 *
 * 반복 기본값을 2로 둔 이유: 기존 실험이 팔당 1~2회만 돌리고 "루브릭 1~2점 차이는
 * 노이즈일 수 있다"를 스스로 한계로 적었다. 1을 기본값으로 두면 그 한계를 기본으로 삼는 셈이다.
 */
function runMatrix({
  sourceDir,
  workDir,
  root,
  arms,
  evals,
  repeats = 2,
  iteration = 1,
  model = null,
  dryRun = true,
  perRunUsd = null,
  fsImpl = nodeFs,
  spawnImpl = nodeSpawnSync,
  log = console.log,
}) {
  const plan = planMatrix({ arms, evals, repeats, iteration, root });
  const estimate = estimateCost(plan, perRunUsd);

  log(`팔 ${arms.length} × 이벌 ${evals.length} × 반복 ${repeats} = 실행 ${plan.length}회`);
  for (const arm of arms) {
    log(`  · ${arm.name} (${arm.label}) — 지침 ${arm.guidelines === "all" ? "전체" : `${arm.guidelines.length}개`}, 등록 ${arm.registered ? "함" : "안 함"}, 훅 ${arm.hooks ? "유지" : "제거"}, .git ${arm.git ? "유지" : "제거"}`);
  }
  if (estimate.totalUsd !== null) log(`예상 비용: 약 $${estimate.totalUsd} (건당 $${estimate.perRunUsd} 가정)`);

  if (dryRun) {
    log("\n[dry-run] 아무것도 실행하지 않았습니다. 실제로 돌리려면 --go 를 붙이세요.");
    return { dryRun: true, plan, estimate, results: [] };
  }

  const armDirs = {};
  for (const arm of arms) {
    const destDir = nodePath.join(workDir, arm.name);
    log(`[팔 준비] ${arm.name} → ${destDir}`);
    const record = materializeArm(arm, { sourceDir, destDir, fsImpl });
    armDirs[arm.name] = destDir;
    const total = record.budget && record.budget.alwaysLoaded ? record.budget.alwaysLoaded.total : "?";
    log(`           상시 로드 ${total}자`);
  }

  const results = [];
  for (const step of plan) {
    fsImpl.mkdirSync(nodePath.join(step.dir, "outputs"), { recursive: true });
    log(`[실행] ${step.evalName} / ${step.arm} / run-${step.run}`);
    const started = Date.now();
    const { parsed, exitCode, stderr } = runOnce({ armDir: armDirs[step.arm], prompt: step.prompt, model, spawnImpl });
    const wallMs = Date.now() - started;

    const evalSpec = evals.find((e) => e.eval_name === step.evalName);
    const write = (rel, data) => fsImpl.writeFileSync(nodePath.join(step.dir, rel), data);

    write("outputs/response.txt", maskSecrets(parsed.result || ""));
    write("outputs/raw.json", `${JSON.stringify(parsed.raw, null, 2)}\n`);
    if (stderr) write("outputs/stderr.txt", maskSecrets(stderr));
    write("timing.json", `${JSON.stringify({ ...toTimingRecord(parsed), wall_ms: wallMs, exit_code: exitCode }, null, 2)}\n`);
    write("grading.json", `${JSON.stringify(buildGradingSkeleton(evalSpec && evalSpec.rubric), null, 2)}\n`);
    fsImpl.writeFileSync(
      nodePath.join(step.dir, "..", "..", "eval_metadata.json"),
      `${JSON.stringify({ eval_id: step.evalId, eval_name: step.evalName, prompt: step.prompt, assertions: (evalSpec && evalSpec.rubric) || [] }, null, 2)}\n`
    );

    results.push({ ...step, ok: parsed.ok, exitCode, costUsd: parsed.costUsd, durationMs: parsed.durationMs });
    if (!parsed.ok) log(`  ⚠️ 실패 — exit ${exitCode}${parsed.parseError ? ` / ${parsed.parseError}` : ""}`);
  }

  const spent = results.map((r) => r.costUsd).filter((v) => typeof v === "number").reduce((a, b) => a + b, 0);
  log(`\n완료 ${results.filter((r) => r.ok).length}/${results.length} · 실제 비용 $${Math.round(spent * 100) / 100}`);
  log("다음: 응답을 읽고 grading.json 의 passed 를 채운 뒤 집계하세요. 채점 전 pass_rate 는 존재하지 않습니다.");
  return { dryRun: false, plan, estimate, results };
}

/**
 * 실행 결과 트리를 훑어 grading.json 을 전부 모은다. 집계 전 게이트의 입력이다.
 */
function collectGrading(root, fsImpl = nodeFs) {
  const found = [];
  const walk = (dir) => {
    if (!fsImpl.existsSync(dir)) return;
    for (const name of fsImpl.readdirSync(dir)) {
      const full = nodePath.join(dir, name);
      if (name === "grading.json") {
        let grading = null;
        try {
          grading = JSON.parse(fsImpl.readFileSync(full, "utf8"));
        } catch (err) {
          grading = { parseError: err.message };
        }
        found.push({ path: full, grading });
      } else if (!name.includes(".")) {
        walk(full);
      }
    }
  };
  walk(root);
  return found;
}

/** `--config` 디렉터리에서 arms.json·evals.json 을 읽어 검증한다. */
function loadConfig(configDir, fsImpl = nodeFs) {
  const read = (name) => JSON.parse(fsImpl.readFileSync(nodePath.join(configDir, name), "utf8"));
  const armsRaw = read("arms.json");
  const evalsRaw = read("evals.json");
  const arms = (armsRaw.arms || []).map(parseArmSpec);
  if (arms.length === 0) throw new Error("arms.json 에 팔이 없습니다");
  const names = new Set(arms.map((a) => a.name));
  if (names.size !== arms.length) throw new Error("팔 이름이 중복됩니다");
  const evals = evalsRaw.evals || [];
  if (evals.length === 0) throw new Error("evals.json 에 과제가 없습니다");
  for (const e of evals) {
    if (!e.eval_name || !e.prompt) throw new Error(`이벌에 eval_name/prompt 가 없습니다: ${JSON.stringify(e).slice(0, 80)}`);
  }
  return { arms, evals, meta: { arms: armsRaw, evals: evalsRaw } };
}

function parseArgv(argv) {
  const opts = { config: null, go: false, verify: false, arms: null, evals: null, repeats: null, iteration: 1, model: null, workDir: null, perRunUsd: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    const next = () => argv[(i += 1)];
    if (a === "--config") opts.config = next();
    else if (a === "--go") opts.go = true;
    else if (a === "--verify") opts.verify = true;
    else if (a === "--arms") opts.arms = next().split(",").map((s) => s.trim()).filter(Boolean);
    else if (a === "--evals") opts.evals = next().split(",").map((s) => s.trim()).filter(Boolean);
    else if (a === "--repeats") opts.repeats = Number(next());
    else if (a === "--iteration") opts.iteration = Number(next());
    else if (a === "--model") opts.model = next();
    else if (a === "--work-dir") opts.workDir = next();
    else if (a === "--per-run-usd") opts.perRunUsd = Number(next());
    else throw new Error(`알 수 없는 옵션: ${a}`);
  }
  return opts;
}

function main(argv, { fsImpl = nodeFs, spawnImpl = nodeSpawnSync, log = console.log, cwd = process.cwd() } = {}) {
  const opts = parseArgv(argv);
  if (!opts.config) throw new Error("--config <디렉터리> 가 필요합니다");
  const configDir = nodePath.resolve(cwd, opts.config);
  const { arms, evals, meta } = loadConfig(configDir, fsImpl);

  if (opts.verify) {
    const root = nodePath.join(configDir, "runs", `iteration-${opts.iteration}`);
    const check = verifyGrading(collectGrading(root, fsImpl));
    log(`채점 확인: ${check.total - check.pending.length}/${check.total} 완료`);
    for (const p of check.pending) log(`  · 미채점 ${nodePath.relative(cwd, p)}`);
    if (!check.ok) {
      log("\n집계하면 안 됩니다 — 집계기는 채점 안 된 실행의 pass_rate를 조용히 0.0으로 채웁니다.");
      process.exitCode = 1;
    }
    return check;
  }
  const selected = opts.arms ? arms.filter((a) => opts.arms.includes(a.name)) : arms;
  if (selected.length === 0) throw new Error(`--arms 로 고른 팔이 없습니다: ${opts.arms}`);
  const selectedEvals = opts.evals ? evals.filter((e) => opts.evals.includes(e.eval_name)) : evals;
  if (selectedEvals.length === 0) throw new Error(`--evals 로 고른 과제가 없습니다: ${opts.evals}`);

  const workDir = opts.workDir
    ? nodePath.resolve(cwd, opts.workDir)
    : nodePath.join(process.env.TMPDIR || "/tmp", `context-ab-arms-${process.pid}`);

  return runMatrix({
    sourceDir: cwd,
    workDir,
    root: nodePath.join(configDir, "runs"),
    arms: selected,
    evals: selectedEvals,
    repeats: opts.repeats || meta.evals.repeats || 2,
    iteration: opts.iteration,
    model: opts.model || meta.evals.model || null,
    dryRun: !opts.go,
    perRunUsd: opts.perRunUsd !== null ? opts.perRunUsd : meta.evals.per_run_usd_estimate || null,
    fsImpl,
    spawnImpl,
    log,
  });
}

module.exports = { maskSecrets, materializeArm, runOnce, runMatrix, loadConfig, collectGrading, parseArgv, main };

if (require.main === module) {
  try {
    main(process.argv.slice(2));
  } catch (err) {
    console.error(`오류: ${err.message}`);
    process.exit(1);
  }
}
