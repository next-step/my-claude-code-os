#!/usr/bin/env node
/**
 * 3단계: 렌더. 구간을 내려받아 세로형 쇼츠로 만든다.
 *
 * 사용법:
 *   node ventures/coupang-shorts/bin/render.js --video 5GTAp_RMEHc --go
 *
 * 원본 전체를 받지 않고 구간만 받는다. 10분짜리를 통째로 받으면 수백 MB 인데
 * 실제로 쓰는 것은 1분이 안 되기 때문이다.
 *
 * ffmpeg 는 `config/pipeline.json` 의 ffmpegPath 를 쓴다. Homebrew 의 ffmpeg 9.0.1 에는
 * drawtext·subtitles 필터가 없어 자막과 출처 표기를 입힐 수 없다.
 */
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { loadConfig, runDir, readJson, run, resolveFfmpeg, parseArgs, log, step } = require("./_shared.js");
const { buildSectionDownloadArgs } = require("../lib/ytdlp-cmd.js");
const { buildRenderPlan } = require("../lib/ffmpeg-cmd.js");

/** 구간 하나를 렌더한다. */
function renderSegment({ plan, seg, config, ffmpeg, dir }) {
  const 원본틀 = path.join(dir, `src${seg.rank}.%(ext)s`);
  const 원본 = path.join(dir, `src${seg.rank}.mp4`);

  if (!fs.existsSync(원본)) {
    const dl = run("yt-dlp", buildSectionDownloadArgs({
      videoId: plan.videoId,
      startSec: seg.startSec,
      endSec: seg.endSec,
      outputPath: 원본틀,
      maxHeight: config.render.maxHeight,
    }), { timeoutMs: 600000 });

    if (!dl.ok || !fs.existsSync(원본)) {
      return { ok: false, reason: `내려받기 실패: ${(dl.stderr || dl.error || "").slice(0, 150)}` };
    }
  }

  // 구간만 받았으므로 잘린 파일 안에서의 시각은 0부터다. 앞뒤 여유 1초를 건너뛴다.
  const 여유 = seg.startSec > 1 ? 1 : seg.startSec;
  const 출력 = path.join(dir, `short${seg.rank}.mp4`);

  const 출처 = plan.channelTitle
    ? `원본: ${plan.channelTitle}  https://youtu.be/${plan.videoId}`
    : `원본: https://youtu.be/${plan.videoId}`;

  const p = buildRenderPlan({
    inputPath: 원본,
    outputPath: 출력,
    startSec: 여유,
    endSec: 여유 + seg.durationSec,
    subtitlePath: config.render.subtitles === false ? undefined : seg.subtitlePath || undefined,
    attributionText: 출처,
    attributionTextPath: path.join(dir, `attr${seg.rank}.txt`),
    mode: config.render.mode,
    width: config.render.width,
    height: config.render.height,
    fps: config.render.fps,
    crf: config.render.crf,
    preset: config.render.preset,
    fontFile: config.render.fontFile,
  });

  // 순수 함수가 "무엇을 써야 하는지" 알려 준 파일들을 여기서 실제로 쓴다.
  for (const f of p.sidecarFiles) fs.writeFileSync(f.path, f.content, "utf-8");

  const r = run(ffmpeg, p.args, { timeoutMs: 600000 });
  if (!r.ok || !fs.existsSync(출력)) {
    return { ok: false, reason: `ffmpeg 실패 (${r.status}): ${(r.stderr || r.error || "").slice(0, 200)}` };
  }

  const 크기 = fs.statSync(출력).size;
  return { ok: true, outputPath: 출력, bytes: 크기 };
}

function main() {
  const args = parseArgs();
  const config = loadConfig("pipeline");
  const ffmpeg = resolveFfmpeg(config);

  if (!args.video) {
    log("  --video <영상ID> 가 필요하다");
    return;
  }

  const dir = runDir(args.video);
  const plan = readJson(path.join(dir, "plan.json"));

  step(3, `렌더 — ${args.video}`);

  if (!plan || !plan.segments || plan.segments.length === 0) {
    log("  분석 결과가 없다. 먼저 analyze.js 를 돌린다");
    return;
  }

  if (args.dryRun) {
    log("  (dry-run) 실제로 렌더하려면 --go 를 붙인다");
    log(`  ffmpeg: ${ffmpeg}`);
    for (const s of plan.segments) {
      log(`  · ${s.rank}위 ${s.startSec}s~${s.endSec}s (${s.durationSec}초), 자막 ${s.subtitleLineCount}줄`);
    }
    return;
  }

  for (const seg of plan.segments) {
    const r = renderSegment({ plan, seg, config, ffmpeg, dir });
    if (!r.ok) {
      log(`  ✗ ${seg.rank}위 실패 — ${r.reason}`);
      continue;
    }
    log(`  ✓ ${seg.rank}위 → ${path.relative(process.cwd(), r.outputPath)} (${(r.bytes / 1048576).toFixed(1)}MB)`);
  }
}

if (require.main === module) main();
module.exports = { main, renderSegment };
