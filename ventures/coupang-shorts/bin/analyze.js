#!/usr/bin/env node
/**
 * 2단계: 분석. 히트맵과 자막을 받아 쇼츠로 쓸 구간을 고른다.
 *
 * 사용법:
 *   node ventures/coupang-shorts/bin/analyze.js --video 5GTAp_RMEHc --go
 *
 * 히트맵은 공식 API 에 없는 값이라 yt-dlp 가 플레이어 내부 응답에서 긁어 온다.
 * 나오지 않는 영상이 있고, 그때는 이유를 적고 건너뛴다 — 한 편 때문에 멈추지 않는다.
 */
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { loadConfig, runDir, readJson, writeJson, run, parseArgs, log, step } = require("./_shared.js");
const { buildHeatmapArgs, buildSubtitleArgs, buildMetadataArgs, FIELD_SEP } = require("../lib/ytdlp-cmd.js");
const { parseHeatmapOutput } = require("../lib/heatmap.js");
const { selectSegments } = require("../lib/segment.js");
const { parseVtt, snapToCues, sliceCues, toSrt } = require("../lib/subtitle.js");

/**
 * 이 영상의 제목과 채널명을 구한다.
 *
 * 먼저 collect.js 가 남긴 후보 목록을 보고, 없으면 yt-dlp 로 직접 가져온다.
 * 직접 가져오는 경로가 필요한 이유: --video 로 한 편만 분석할 때 collect 를 거치지
 * 않는데, 그러면 제목이 비어 검색어가 브랜드명만 남고 출처 표기도 만들 수 없다.
 * 실제로 그렇게 실패하는 것을 보고 넣었다.
 */
function 메타데이터(videoId) {
  const 오늘 = new Date().toISOString().slice(0, 10);
  const p = path.join(__dirname, "..", "runs", 오늘, "_collect", "candidates.json");
  const 목록 = readJson(p);
  const 찾음 = 목록 && 목록.candidates ? 목록.candidates.find((c) => c.videoId === videoId) : null;
  if (찾음 && 찾음.title) return 찾음;

  const r = run("yt-dlp", buildMetadataArgs(videoId), { timeoutMs: 180000 });
  if (!r.ok) return { videoId, title: "", channelTitle: "", viewCount: null, durationSec: null };

  const [id, duration, viewCount, channel, uploadDate, ...rest] = r.stdout.trim().split(FIELD_SEP);
  return {
    videoId: id || videoId,
    title: rest.join(FIELD_SEP).trim(),
    channelTitle: channel === "NA" ? "" : (channel || ""),
    viewCount: Number(viewCount) || null,
    durationSec: Number(duration) || null,
    uploadDate: uploadDate || null,
  };
}

function analyzeOne(videoId, config, args) {
  const dir = runDir(videoId);

  // 히트맵
  const h = run("yt-dlp", buildHeatmapArgs(videoId), { timeoutMs: 180000 });
  if (!h.ok) {
    return { videoId, heatmapAvailable: false, reason: `yt-dlp 실패: ${(h.stderr || h.error || "").slice(0, 150)}`, segments: [] };
  }

  const heatmap = parseHeatmapOutput(h.stdout);
  if (!heatmap.available) {
    return { videoId, heatmapAvailable: false, reason: heatmap.reason, segments: [] };
  }

  // 자막. 없어도 계속 간다 — 자막은 있으면 좋은 것이지 필수가 아니다.
  let cues = [];
  const subOut = path.join(dir, "sub.%(ext)s");
  const s = run("yt-dlp", buildSubtitleArgs(videoId, subOut, config.subtitle.lang), { timeoutMs: 180000 });
  if (s.ok) {
    const vtt = path.join(dir, `sub.${config.subtitle.lang}.vtt`);
    if (fs.existsSync(vtt)) cues = parseVtt(fs.readFileSync(vtt, "utf-8"));
  }

  // 구간 선정
  const { segments, skipped } = selectSegments(heatmap.buckets, config.segment);
  if (skipped) {
    return { videoId, heatmapAvailable: true, reason: skipped, segments: [], cueCount: cues.length };
  }

  // 경계를 자막 경계로 옮기고, 구간별 자막을 SRT 로 뽑는다.
  const 다듬은구간 = segments.map((seg) => {
    // 길이 제약을 함께 넘긴다. 넘기지 않으면 스냅이 segment.js 의 제약을 깨뜨린다.
    const snapped = snapToCues(seg, cues, config.subtitle.snapToleranceSec, {
      minSec: config.segment.minSec,
      maxSec: config.segment.maxSec,
    });
    const 구간자막 = sliceCues(cues, snapped.startSec, snapped.endSec);

    let srtPath = null;
    if (구간자막.length > 0) {
      srtPath = path.join(dir, `seg${seg.rank}.srt`);
      fs.writeFileSync(srtPath, toSrt(구간자막), "utf-8");
    }

    return {
      ...snapped,
      subtitleLineCount: 구간자막.length,
      subtitlePath: srtPath,
      subtitleText: 구간자막.map((c) => c.text).join(" "),
    };
  });

  const 후보 = 메타데이터(videoId);
  return {
    videoId,
    title: 후보.title,
    channelTitle: 후보.channelTitle,
    viewCount: 후보.viewCount,
    heatmapAvailable: true,
    bucketCount: heatmap.bucketCount,
    cueCount: cues.length,
    reason: null,
    segments: 다듬은구간,
  };
}

function main() {
  const args = parseArgs();
  const config = loadConfig("pipeline");

  let 대상 = [];
  if (args.video) {
    대상 = [args.video];
  } else {
    const 오늘 = new Date().toISOString().slice(0, 10);
    const 목록 = readJson(path.join(__dirname, "..", "runs", 오늘, "_collect", "candidates.json"));
    대상 = 목록 && 목록.candidates ? 목록.candidates.slice(0, config.output.dailyTarget).map((c) => c.videoId) : [];
  }

  step(2, `분석 — 대상 ${대상.length}편`);

  if (대상.length === 0) {
    log("  분석할 영상이 없다. 먼저 collect.js 를 돌리거나 --video 로 지정한다");
    return;
  }
  if (args.dryRun) {
    log("  (dry-run) 실제로 분석하려면 --go 를 붙인다");
    for (const v of 대상) log(`  · ${v}`);
    return;
  }

  for (const videoId of 대상) {
    const 결과 = analyzeOne(videoId, config, args);
    const p = path.join(runDir(videoId), "plan.json");
    writeJson(p, 결과);

    if (!결과.heatmapAvailable || 결과.segments.length === 0) {
      log(`  ✗ ${videoId} 건너뜀 — ${결과.reason}`);
      continue;
    }
    log(`  ✓ ${videoId} — 버킷 ${결과.bucketCount}, 자막 ${결과.cueCount}줄, 구간 ${결과.segments.length}개`);
    for (const s of 결과.segments) {
      log(`      ${s.rank}위 ${String(s.startSec).padStart(7)}s~${String(s.endSec).padStart(7)}s (${String(s.durationSec).padStart(5)}초) 최고 ${s.peakValue.toFixed(2)} 자막 ${s.subtitleLineCount}줄`);
    }
  }
}

if (require.main === module) main();
module.exports = { main, analyzeOne };
