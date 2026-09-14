#!/usr/bin/env node
/**
 * 랄프 루프 러너 — 부작용 담당(파일 복사·프로세스 실행).
 *
 * 판정·파싱·계산은 전부 `ralph-loop.js`(순수)에 있다. 여기는 그 결과를 디스크와 프로세스에
 * 옮기는 일만 한다. `fs`·`spawn`·`exec`·`now`를 주입받으므로 실제 실행 없이 테스트할 수 있다 —
 * 이 루프는 한 번 돌 때마다 실비가 나가서, 테스트가 실행을 건드리면 안 된다.
 *
 * 기본은 dry-run이다. 실제 호출은 `--go`를 명시해야 일어난다(`context-ab-run.js`와 같은 규약).
 *
 * ## 사본을 둘로 나누는 이유
 * 작업 사본에는 `.git`이 있고 측정 사본에는 없다. 회차마다 커밋이 쌓이면 gitStatus(최근 커밋)가
 * 세션 시작 시 주입되므로, 측정 세션이 지침이 아니라 커밋 로그에 반응하게 된다 —
 * `context-ab.js:101`이 실험 3에서 겪었다고 적어 둔 누수와 정확히 같다. 그래서 회차마다
 * `editable` 파일만 작업 사본에서 측정 사본으로 옮겨 심고, 측정은 항상 커밋 로그가 없는
 * 사본에서 한다.
 *
 * 사용:
 *   node .claude/lib/ralph-run.js --goal experiments/ralph/goals/brevity-50.json
 *   node .claude/lib/ralph-run.js --goal experiments/ralph/goals/brevity-50.json --go
 */
const nodeFs = require("node:fs");
const nodePath = require("node:path");
const { spawnSync: nodeSpawnSync } = require("node:child_process");

const { maskSecrets, materializeArm, runOnce } = require("./context-ab-run.js");
const { parseArmSpec, toTimingRecord, estimateCost } = require("./context-ab.js");
const {
  parseGoalSpec,
  measureResponse,
  aggregateProbes,
  computeNoiseBand,
  extractFromCommand,
  evaluateMetrics,
  decideNext,
  buildIterationPrompt,
  summarizeRun,
  editMirrorPath,
  rewritePatchPaths,
} = require("./ralph-loop.js");

/**
 * 작업 세션에만 붙이는 인자.
 *
 * 측정 세션에는 붙이지 않는다. 측정은 평소 세션이 어떻게 답하는지를 재는 것이므로,
 * 권한 설정이 평소와 달라지면 재는 대상 자체가 달라진다.
 */
const WORK_SESSION_ARGS = ["--permission-mode", "acceptEdits"];

/** 진행 노트 파일명. 이터레이션 사이에 정보가 넘어가는 유일한 통로다. */
const NOTES_FILE = "RALPH-NOTES.md";

/**
 * 범위 밖 변경을 셀 때 무시할 경로.
 * 사본을 만들 때 일부러 뺀 것들이라 git 입장에서는 삭제로 보인다. 루프가 만진 것이 아니다.
 */
const PATCH_IGNORE = [".claude/hooks", ".claude/settings.json", ".claude/settings.local.json", ".claude/sessions", "node_modules", NOTES_FILE];

/** 작업 사본: `.git`을 남겨 회차마다 커밋을 쌓고, 마지막에 패치를 뽑는다. 훅은 뺀다. */
const WORK_ARM = { name: "work", label: "랄프 작업 사본", guidelines: "all", registered: true, hooks: false, git: true, note: "" };
/** 측정 사본: `.git`을 뺀다. 커밋 로그가 측정에 새는 것을 막기 위해서다. */
const PROBE_ARM = { name: "probe", label: "랄프 측정 사본", guidelines: "all", registered: true, hooks: false, git: false, note: "" };

/** 셸 명령 1회. guard 지표용. 던지지 않고 결과를 담아 돌려준다. */
function nodeExecSync(cmd, { cwd, timeoutMs = 600000 } = {}) {
  const proc = nodeSpawnSync(cmd, { cwd, shell: true, encoding: "utf8", timeout: timeoutMs, maxBuffer: 64 * 1024 * 1024 });
  return { stdout: proc.stdout || "", stderr: proc.stderr || "", exitCode: proc.status };
}

function ensureDir(dir, fsImpl) {
  fsImpl.mkdirSync(dir, { recursive: true });
}

function writeFile(filePath, body, fsImpl) {
  ensureDir(nodePath.dirname(filePath), fsImpl);
  fsImpl.writeFileSync(filePath, body);
}

/** 목표 정의 파일을 읽어 검증한다. */
function loadGoal(goalPath, fsImpl = nodeFs) {
  const raw = JSON.parse(fsImpl.readFileSync(goalPath, "utf8"));
  return parseGoalSpec(raw);
}

/**
 * 작업 사본과 측정 사본을 만든다.
 *
 * 진행 노트는 작업 사본 안에만 두고, 사본의 `.git/info/exclude`에 등록해 최종 패치에
 * 섞이지 않게 한다. 노트는 루프의 작업 기록이지 저장소에 반영할 변경이 아니다.
 */
function materializeCopies({ sourceDir, workDir, probeDir, spec, fsImpl = nodeFs, execImpl = nodeExecSync }) {
  const work = materializeArm(parseArmSpec(WORK_ARM), { sourceDir, destDir: workDir, fsImpl });
  const probe = materializeArm(parseArmSpec(PROBE_ARM), { sourceDir, destDir: probeDir, fsImpl });

  const notesPath = nodePath.join(workDir, NOTES_FILE);
  if (!fsImpl.existsSync(notesPath)) {
    writeFile(notesPath, `# 랄프 루프 진행 노트 (${spec.id})\n\n목표: ${spec.goal}\n\n아직 시도한 것이 없습니다.\n`, fsImpl);
  }
  const excludePath = nodePath.join(workDir, ".git", "info", "exclude");
  try {
    const prev = fsImpl.existsSync(excludePath) ? fsImpl.readFileSync(excludePath, "utf8") : "";
    if (!prev.includes(NOTES_FILE)) writeFile(excludePath, `${prev}\n${NOTES_FILE}\n`, fsImpl);
  } catch (err) {
    // .git이 없거나 읽을 수 없어도 루프는 돈다. 패치에 노트가 섞일 뿐이다.
  }
  // 고칠 파일의 작업본을 평범한 경로에 깔아 둔다. 이유는 `editMirrorPath`의 주석에 있다.
  // 기준 커밋보다 먼저 깔아야 작업본을 만든 것 자체가 최종 패치에 잡히지 않는다.
  const mirror = {};
  for (const rel of spec.editable) {
    const mirrorRel = editMirrorPath(rel);
    mirror[mirrorRel] = rel;
    const from = nodePath.join(workDir, rel);
    if (fsImpl.existsSync(from)) {
      writeFile(nodePath.join(workDir, mirrorRel), fsImpl.readFileSync(from, "utf8"), fsImpl);
    }
  }

  // 사본을 만든 **지금 이 상태**를 커밋해 기준으로 삼는다.
  //
  // 저장소 HEAD를 그대로 기준으로 쓰면 안 된다. 원본에 커밋 안 된 작업이 있으면 그것까지
  // 루프가 바꾼 것으로 잡혀 최종 패치에 섞인다 — 사람이 진행 중이던 무관한 변경을 루프
  // 결과로 오인해 적용하게 된다. 스모크 테스트에서 실제로 관계없는 파일 14개가 잡혔다.
  let baseRef = null;
  execImpl('git add -A && git commit -q --allow-empty -m "ralph base"', { cwd: workDir });
  const head = execImpl("git rev-parse HEAD", { cwd: workDir });
  if (head.exitCode === 0) baseRef = (head.stdout || "").trim() || null;

  return { work, probe, notesPath, baseRef, mirror };
}

/**
 * 작업 사본에서 고친 파일만 측정 사본으로 옮겨 심는다.
 *
 * `mirror`를 주면 작업본 경로에서 읽어 **원래 경로**에 심는다. 측정 세션은 지침이 원래
 * 자리에 있어야 그것을 지침으로 읽으므로, 작업본 경로 그대로 두면 측정이 성립하지 않는다.
 */
function syncEditable({ workDir, probeDir, editable, mirror = null, fsImpl = nodeFs }) {
  const copied = [];
  const pairs = mirror ? Object.entries(mirror) : editable.map((rel) => [rel, rel]);
  for (const [fromRel, toRel] of pairs) {
    const from = nodePath.join(workDir, fromRel);
    const to = nodePath.join(probeDir, toRel);
    if (!fsImpl.existsSync(from)) {
      // 이터레이션이 파일을 지웠을 수 있다. 그러면 측정 사본에서도 지운다.
      fsImpl.rmSync(to, { force: true });
      continue;
    }
    writeFile(to, fsImpl.readFileSync(from, "utf8"), fsImpl);
    copied.push(toRel);
  }
  return copied;
}

/** 측정 세션을 과제 수 × repeats 만큼 돌리고 잰다. */
function runProbes({ probeDir, probes, repeats, model, outDir = null, spawnImpl = nodeSpawnSync, fsImpl = nodeFs }) {
  const runs = [];
  for (const probe of probes) {
    for (let k = 1; k <= repeats; k += 1) {
      const started = Date.now();
      const { parsed, exitCode, stderr } = runOnce({ armDir: probeDir, prompt: probe.prompt, model, spawnImpl });
      const text = parsed.result || "";
      const measured = measureResponse(text);
      const record = {
        probeId: probe.id,
        run: k,
        ...measured,
        ok: parsed.ok,
        exitCode,
        wallMs: Date.now() - started,
        timing: toTimingRecord(parsed),
      };
      runs.push(record);
      if (outDir) {
        writeFile(nodePath.join(outDir, `${probe.id}-run-${k}.json`), `${JSON.stringify(record, null, 2)}\n`, fsImpl);
        writeFile(nodePath.join(outDir, `${probe.id}-run-${k}.txt`), maskSecrets(text), fsImpl);
        if (stderr) writeFile(nodePath.join(outDir, `${probe.id}-run-${k}.stderr.txt`), maskSecrets(stderr), fsImpl);
      }
    }
  }
  return runs;
}

/**
 * `kind: "command"`인 지표를 작업 사본 안에서 돌린다.
 *
 * **targets와 guards를 함께 받아야 한다.** 처음에는 guard만 받았는데, `parseMetricSpec`은
 * target에도 `kind: "command"`를 허용한다. 그래서 명령 target을 쓴 목표 정의는 스키마는
 * 통과하면서 값이 영원히 `null`로 남았고, `null`은 통과로 치지 않으므로(`ralph-loop.js`의
 * evaluateMetrics) 루프가 무엇을 해도 상한까지 돌다 `exhausted`로 끝났다. 실제로
 * context-slim-30 첫 실주행이 여기 걸려 14세션을 쓰고서야 드러났다.
 * 지표를 못 재는 것보다 나쁜 것은, 못 쟀다는 사실이 미달과 구분되지 않는 것이다.
 */
function runCommandMetrics({ workDir, metrics, execImpl = nodeExecSync }) {
  const values = {};
  const details = [];
  for (const m of metrics.filter((x) => x.kind === "command")) {
    const out = execImpl(m.cmd, { cwd: workDir });
    const value = extractFromCommand(out, m);
    values[m.id] = value;
    details.push({ id: m.id, cmd: m.cmd, exitCode: out.exitCode, value });
  }
  return { values, details };
}

/** 실행 계획. dry-run이 이 숫자를 보여준다. */
function planSessions(spec) {
  const perProbeSet = spec.probes.length * spec.repeats;
  return {
    probes: spec.probes.length,
    repeats: spec.repeats,
    baselineSessions: perProbeSet,
    perIterationSessions: 1 + perProbeSet,
    maxIterations: spec.maxIterations,
    worstCaseSessions: perProbeSet + spec.maxIterations * (1 + perProbeSet),
  };
}

/**
 * 최종 패치를 뽑는다. 실패해도 루프 결과를 버리지 않는다.
 *
 * 두 가지를 반드시 지킨다.
 *
 * ① **기준 커밋(`baseRef`)과 비교한다.** 루프가 회차마다 커밋을 남기므로, 인덱스나 워킹트리와
 *    비교하면 마지막 커밋 직후라 차이가 항상 0으로 나온다. 스모크 테스트에서 이 실수를 잡았다 —
 *    지표는 목표를 달성했는데 패치는 빈 파일이었다.
 *
 * ② **패치를 `editable` 경로로 한정한다.** 사본은 훅과 `settings.json`을 빼고 만들었으므로
 *    git 입장에서 그 파일들은 **삭제된 것**으로 보인다. 한정하지 않으면 패치에 훅 삭제가 전부
 *    실려서, 적용하는 순간 훅이 사라진다. 스모크 테스트에서 496KB짜리 삭제 패치가 나와 잡았다.
 *
 * 범위 밖에서 바뀐 것이 있으면 지우지 않고 `stray`로 이름만 돌려준다 — 조용히 버리면
 * 루프가 무엇을 더 만졌는지 사람이 알 수 없다.
 */
function collectPatch({ workDir, baseRef = null, editable = [], mirror = null, execImpl = nodeExecSync }) {
  // 작업본 경로에서 뽑은 뒤 원래 경로로 되돌린다. 안 되돌리면 사람이 적용할 수 없는 패치가 나온다.
  const scopePaths = mirror ? Object.keys(mirror) : editable;
  try {
    execImpl('git add -A && git commit -q --allow-empty -m "ralph final"', { cwd: workDir });
    if (!baseRef) {
      return { patch: "# 기준 커밋을 알 수 없어 패치를 뽑지 못했습니다. 작업 사본에 .git이 있는지 확인하세요.", stray: [] };
    }
    const scope = scopePaths.map((p) => `"${p}"`).join(" ");
    const out = execImpl(`git diff ${baseRef} HEAD -- ${scope}`, { cwd: workDir });
    const raw = out.exitCode === 0 ? out.stdout : `# git diff 실패 (exit ${out.exitCode})\n${out.stderr}`;
    const patch = mirror ? rewritePatchPaths(raw, mirror) : raw;

    const names = execImpl(`git diff --name-only ${baseRef} HEAD`, { cwd: workDir });
    const changed = (names.stdout || "").split("\n").map((x) => x.trim()).filter(Boolean);
    // 원본 경로가 그대로 있는 것은 정상이다. 작업 세션은 작업본만 고치기 때문이다.
    const inScope = new Set([...scopePaths, ...editable]);
    const stray = changed.filter((f) => !inScope.has(f) && !PATCH_IGNORE.some((pre) => f === pre || f.startsWith(`${pre}/`)));
    return { patch, stray };
  } catch (err) {
    return { patch: `# 패치를 뽑지 못했습니다: ${err.message}`, stray: [] };
  }
}

/**
 * 루프 본체.
 *
 * `dryRun`의 기본값이 true인 것이 이 함수의 가장 중요한 성질이다. 인자를 깜빡해도
 * 세션이 뜨지 않는다 — 테스트 AC-9가 이걸 잠근다.
 */
function runLoop({
  sourceDir,
  spec,
  root,
  workDir,
  probeDir,
  model = null,
  perRunUsd = null,
  dryRun = true,
  fsImpl = nodeFs,
  spawnImpl = nodeSpawnSync,
  execImpl = nodeExecSync,
  log = console.log,
}) {
  const sessions = planSessions(spec);
  const estimate = estimateCost({ length: sessions.worstCaseSessions }, perRunUsd);

  log(`목표: ${spec.id} — ${spec.goal}`);
  log(`측정 과제 ${sessions.probes}개 × 반복 ${sessions.repeats}회`);
  log(`베이스라인 ${sessions.baselineSessions}개 세션, 이터레이션당 ${sessions.perIterationSessions}개 세션(작업 1 + 측정 ${sessions.probes * sessions.repeats})`);
  log(`상한 ${sessions.maxIterations}회를 다 쓰면 최대 ${sessions.worstCaseSessions}개 세션`);
  log(`예상 비용: ${estimate.totalUsd === null ? "단가 미지정(--per-run-usd)" : `약 $${estimate.totalUsd}`}`);

  if (dryRun) {
    log("\n[dry-run] 아무것도 실행하지 않았습니다. 실제로 돌리려면 --go 를 붙이세요.");
    return { dryRun: true, sessions, estimate, history: [], summary: null };
  }

  const useModel = model || spec.model;
  const { baseRef, mirror } = materializeCopies({ sourceDir, workDir, probeDir, spec, fsImpl, execImpl });
  const editablePaths = Object.keys(mirror);

  // --- 베이스라인 ---
  log("\n[베이스라인] 고치기 전 상태를 잽니다.");
  const baselineRuns = runProbes({
    probeDir, probes: spec.probes, repeats: spec.repeats, model: useModel,
    outDir: nodePath.join(root, "baseline", "probes"), spawnImpl, fsImpl,
  });
  const baselineAgg = aggregateProbes(baselineRuns);
  const noiseBand = computeNoiseBand(baselineRuns);
  // guard 명령도 고치기 전에 한 번 잰다. 작업 사본은 훅을 뺀 상태라 목표와 무관하게
  // 이미 깨져 있는 테스트가 있고, 그 상태를 모르면 가드가 처음부터 빨간불이 된다.
  // 베이스라인도 이터레이션과 **같은 사본에서** 잰다. 다른 곳에서 재면 사본 구성 차이가
  // 그대로 차이로 잡혀 relative_to_baseline이 엉뚱한 값을 기준으로 삼는다.
  const baselineGuards = runCommandMetrics({ workDir: probeDir, metrics: [...spec.targets, ...spec.guards], execImpl });
  const baseline = { response: baselineAgg, command: baselineGuards.values };
  writeFile(
    nodePath.join(root, "baseline", "metrics.json"),
    `${JSON.stringify({ ...baselineAgg, noiseBand, guards: baselineGuards.details }, null, 2)}\n`,
    fsImpl,
  );
  if (baselineAgg.failedRuns > 0) {
    log(`베이스라인 측정 ${baselineAgg.attemptedRuns}회 중 ${baselineAgg.failedRuns}회가 실패했습니다(세션 오류).`);
  }
  // 베이스라인을 못 재면 그 뒤가 전부 무의미하다. 배수 목표는 기준값이 없어 서지 않고,
  // 노이즈 폭도 못 구해 정체 판정이 꺼진다. 그런데도 루프는 상한까지 돌면서 회차마다
  // 실비를 쓴다 — 2회차 실주행이 정확히 그렇게 28세션을 태웠다. 여기서 끊는다.
  if (!baselineAgg.usable) {
    const reason = `베이스라인 측정이 과반 실패했습니다(${baselineAgg.attemptedRuns}회 중 ${baselineAgg.failedRuns}회 실패). `
      + "기준값이 서지 않아 이 뒤의 회차는 전부 무의미하므로 시작하지 않습니다. "
      + "세션 오류 원문은 baseline/probes/*.txt 에 있습니다.";
    log(`중단: ${reason}`);
    const summary = summarizeRun({ spec, history: [], baseline, noiseBand, decision: { action: "aborted", reason } });
    writeFile(nodePath.join(root, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`, fsImpl);
    return summary;
  }
  log(`베이스라인 중앙값 ${baselineAgg.median_chars}자, 최대 ${baselineAgg.max_chars}자, 노이즈 폭 ${noiseBand}자`);
  for (const d of baselineGuards.details) {
    log(`베이스라인 guard ${d.id}: ${d.value ?? "측정 실패"}${d.value ? " — 고치기 전부터 이 값입니다" : ""}`);
  }

  const baselinePrimaryKey = spec.targets[0].extract;
  const baselinePrimary = baselineAgg[baselinePrimaryKey] ?? null;

  // --- 이터레이션 ---
  const history = [];
  let decision = decideNext({ spec, history, noiseBand });
  while (decision.action === "continue") {
    const iteration = history.length + 1;
    const iterDir = nodePath.join(root, `iteration-${iteration}`);
    const last = history.length > 0 ? history[history.length - 1].evaluation : null;
    const prompt = buildIterationPrompt({ spec, iteration, last, notesPath: NOTES_FILE, editablePaths });
    writeFile(nodePath.join(iterDir, "prompt.txt"), prompt, fsImpl);

    log(`\n[이터레이션 ${iteration}/${spec.maxIterations}] 작업 세션을 띄웁니다.`);
    const started = Date.now();
    const work = runOnce({ armDir: workDir, prompt, model: useModel, extraArgs: WORK_SESSION_ARGS, spawnImpl });
    writeFile(nodePath.join(iterDir, "work-response.txt"), maskSecrets(work.parsed.result || ""), fsImpl);
    if (work.stderr) writeFile(nodePath.join(iterDir, "work-stderr.txt"), maskSecrets(work.stderr), fsImpl);
    execImpl(`git add -A && git commit -q -m "ralph ${spec.id} iteration ${iteration}" --allow-empty`, { cwd: workDir });

    // **순서가 중요하다.** 작업 세션은 `ralph-edit/` 작업본만 고치므로, 옮겨 심기 전의
    // 사본에는 원본이 그대로 있다. 그 상태에서 명령 지표를 돌리면 고친 내용을 못 보고
    // 베이스라인과 같은 값이 계속 나온다 — context-slim-30 3회차 실주행이 여기 걸려
    // `import_chars`가 두 회차 내내 10,896에서 미동이 없었다.
    // 그래서 먼저 옮겨 심고, 측정 사본에서 잰다. 명령 지표와 측정 세션이 같은 상태를 본다.
    syncEditable({ workDir, probeDir, editable: spec.editable, mirror, fsImpl });
    const guardRun = runCommandMetrics({ workDir: probeDir, metrics: [...spec.targets, ...spec.guards], execImpl });

    log(`[이터레이션 ${iteration}] 측정 세션 ${sessions.probes * sessions.repeats}개를 띄웁니다.`);
    const runs = runProbes({
      probeDir, probes: spec.probes, repeats: spec.repeats, model: useModel,
      outDir: nodePath.join(iterDir, "probes"), spawnImpl, fsImpl,
    });
    const agg = aggregateProbes(runs);
    const evaluation = evaluateMetrics({
      targets: spec.targets, guards: spec.guards,
      values: { response: agg, command: guardRun.values }, baseline,
    });
    const primary = agg[baselinePrimaryKey] ?? null;
    writeFile(nodePath.join(iterDir, "metrics.json"), `${JSON.stringify({ aggregate: agg, guards: guardRun.details, evaluation }, null, 2)}\n`, fsImpl);
    writeFile(nodePath.join(iterDir, "timing.json"), `${JSON.stringify({ work: toTimingRecord(work.parsed), wall_ms: Date.now() - started, exit_code: work.exitCode }, null, 2)}\n`, fsImpl);

    history.push({ iteration, evaluation, primary, baselinePrimary });
    for (const r of evaluation.targets) {
      log(`  target ${r.id}: ${r.value ?? "측정 실패"} (목표 ${r.op} ${r.threshold ?? "?"}) → ${r.pass ? "통과" : "미달"}`);
    }
    for (const r of evaluation.guards) {
      log(`  guard  ${r.id}: ${r.value ?? "측정 실패"} (기준 ${r.op} ${r.threshold ?? "?"}) → ${r.pass ? "통과" : "깨짐"}`);
    }
    decision = decideNext({ spec, history, noiseBand });
    log(`  → ${decision.action}: ${decision.reason}`);
  }

  const summary = summarizeRun({ spec, history, baseline, noiseBand, decision });
  writeFile(nodePath.join(root, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`, fsImpl);
  const { patch, stray } = collectPatch({ workDir, baseRef, editable: spec.editable, mirror, execImpl });
  writeFile(nodePath.join(root, "final.patch"), patch, fsImpl);
  summary.strayChanges = stray;
  writeFile(nodePath.join(root, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`, fsImpl);
  if (fsImpl.existsSync(nodePath.join(workDir, NOTES_FILE))) {
    writeFile(nodePath.join(root, NOTES_FILE), fsImpl.readFileSync(nodePath.join(workDir, NOTES_FILE), "utf8"), fsImpl);
  }

  log(`\n결과: ${summary.outcome} — ${summary.reason}`);
  log(`패치: ${nodePath.join(root, "final.patch")} (자동 적용하지 않습니다. 읽고 사람이 적용합니다.)`);
  if (stray.length > 0) log(`범위 밖 변경 ${stray.length}건 — 패치에 넣지 않았습니다: ${stray.join(", ")}`);
  log(`한계: ${summary.caveat}`);
  return { dryRun: false, sessions, estimate, history, summary };
}

function parseArgv(argv) {
  const opts = { goal: null, go: false, maxIterations: null, workDir: null, root: null, model: null, perRunUsd: null };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--goal") opts.goal = argv[++i];
    else if (a === "--go") opts.go = true;
    else if (a === "--max-iterations") opts.maxIterations = Number(argv[++i]);
    else if (a === "--work-dir") opts.workDir = argv[++i];
    else if (a === "--root") opts.root = argv[++i];
    else if (a === "--model") opts.model = argv[++i];
    else if (a === "--per-run-usd") opts.perRunUsd = Number(argv[++i]);
    else throw new Error(`알 수 없는 옵션: ${a}`);
  }
  if (!opts.goal) throw new Error("--goal <목표 정의 JSON 경로> 가 필요합니다");
  return opts;
}

function main(argv, { fsImpl = nodeFs, spawnImpl = nodeSpawnSync, execImpl = nodeExecSync, log = console.log, cwd = process.cwd() } = {}) {
  const opts = parseArgv(argv);
  const spec = loadGoal(nodePath.resolve(cwd, opts.goal), fsImpl);
  if (opts.maxIterations) spec.maxIterations = opts.maxIterations;

  const base = opts.workDir || nodePath.join(process.env.TMPDIR || "/tmp", `ralph-${spec.id}-${process.pid}`);
  return runLoop({
    sourceDir: cwd,
    spec,
    root: opts.root || nodePath.join(cwd, "experiments", "ralph", "runs", spec.id),
    workDir: nodePath.join(base, "work"),
    probeDir: nodePath.join(base, "probe"),
    model: opts.model,
    perRunUsd: opts.perRunUsd !== null ? opts.perRunUsd : spec.perRunUsdEstimate,
    dryRun: !opts.go,
    fsImpl,
    spawnImpl,
    execImpl,
    log,
  });
}

if (require.main === module) {
  try {
    main(process.argv.slice(2));
  } catch (err) {
    console.error(`실패: ${err.message}`);
    process.exitCode = 1;
  }
}

module.exports = {
  NOTES_FILE, WORK_ARM, PROBE_ARM,
  loadGoal, materializeCopies, syncEditable, runProbes, runCommandMetrics,
  planSessions, collectPatch, runLoop, parseArgv, main, PATCH_IGNORE,
};
