#!/usr/bin/env node
/**
 * 네 단계를 순서대로 실행한다.
 *
 * 사용법:
 *   node ventures/coupang-shorts/bin/run.js                        (dry-run)
 *   node ventures/coupang-shorts/bin/run.js --go                   (설정된 검색어로 하루치)
 *   node ventures/coupang-shorts/bin/run.js --go --video <영상ID>   (한 편만)
 *
 * 단계 사이를 파일로 넘긴다. 각 단계가 느리고 실패 지점이 서로 달라서, 중간 산출물이
 * 남아야 앞 단계를 다시 돌리지 않고 이어서 재시도할 수 있다.
 *
 * 한 편이 실패해도 멈추지 않는다. 히트맵이 없는 영상이 섞여 있는 것이 정상이다.
 */
"use strict";

const path = require("node:path");
const { loadConfig, runDir, readJson, run, parseArgs, log } = require("./_shared.js");

const 노드 = process.execPath;
const BIN = __dirname;

/** 하위 단계를 별도 프로세스로 띄운다. 한 단계가 죽어도 전체가 죽지 않는다. */
function 단계실행(script, extraArgs) {
  const r = run(노드, [path.join(BIN, script), ...extraArgs], { timeoutMs: 1800000 });
  if (r.stdout) process.stdout.write(r.stdout);
  if (!r.ok && r.stderr) log(`  (${script} stderr) ${r.stderr.slice(0, 400)}`);
  return r.ok;
}

function main() {
  const args = parseArgs();
  const config = loadConfig("pipeline");
  const 공통 = args.go ? ["--go"] : [];
  if (args.fake) 공통.push("--fake");

  const 시작 = Date.now();
  log(`쇼츠 파이프라인 — ${args.dryRun ? "dry-run (실제로 돌리려면 --go)" : "실행"}`);

  let 대상 = [];

  if (args.video) {
    대상 = [args.video];
  } else {
    if (!단계실행("collect.js", 공통)) log("  수집 단계가 실패했지만 계속 간다");
    if (args.dryRun) {
      log("\n(dry-run) 수집 뒤 분석·렌더·수익화가 이어진다");
      return;
    }
    const 오늘 = new Date().toISOString().slice(0, 10);
    const 목록 = readJson(path.join(__dirname, "..", "runs", 오늘, "_collect", "candidates.json"));
    대상 = 목록 && 목록.candidates
      ? 목록.candidates.slice(0, config.output.dailyTarget).map((c) => c.videoId)
      : [];
    log(`\n오늘 처리할 영상 ${대상.length}편 (목표 ${config.output.dailyTarget}편)`);
  }

  const 성공 = [];
  const 실패 = [];

  for (const videoId of 대상) {
    const 영상인자 = [...공통, "--video", videoId];

    if (!단계실행("analyze.js", 영상인자)) { 실패.push([videoId, "분석"]); continue; }

    const plan = readJson(path.join(runDir(videoId), "plan.json"));
    if (!plan || !plan.segments || plan.segments.length === 0) {
      실패.push([videoId, `구간 없음 (${plan ? plan.reason : "분석 결과 없음"})`]);
      continue;
    }
    if (args.dryRun) { 성공.push(videoId); continue; }

    // 수익화를 렌더보다 먼저 돌린다. 화면에 박을 타이틀 문구를 수익화 단계가 만들기
    // 때문이다. 수익화는 렌더 결과에 기대는 것이 없어 순서를 바꿔도 안전하다.
    if (!단계실행("monetize.js", 영상인자)) { 실패.push([videoId, "수익화"]); continue; }
    if (!단계실행("render.js", 영상인자)) { 실패.push([videoId, "렌더"]); continue; }

    성공.push(videoId);
  }

  const 걸린시간 = Math.round((Date.now() - 시작) / 1000);
  log(`\n${"─".repeat(50)}`);
  log(`끝났다 — 성공 ${성공.length}편, 실패 ${실패.length}편, ${걸린시간}초`);
  for (const v of 성공) {
    log(`  ✓ ${v} → ${path.relative(process.cwd(), runDir(v))}`);
  }
  for (const [v, 이유] of 실패) log(`  ✗ ${v} — ${이유}`);

  if (성공.length > 0) {
    log("\n다음은 사람이 한다: 영상을 눈으로 확인하고, meta.json 의 문구로 업로드한다.");
    log("쿠팡 키가 없는 동안에는 설명의 링크 자리를 직접 채워야 한다 (SETUP.md 참고).");
  }
}

if (require.main === module) main();
module.exports = { main };
