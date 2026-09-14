#!/usr/bin/env node
/**
 * 1단계: 소재 수집. 키워드로 검색해 후보 목록을 만든다.
 *
 * 사용법:
 *   node ventures/coupang-shorts/bin/collect.js            (dry-run: 무엇을 할지만 보여준다)
 *   node ventures/coupang-shorts/bin/collect.js --go
 *   node ventures/coupang-shorts/bin/collect.js --go --keyword "무선청소기 추천"
 *
 * 검색은 yt-dlp 가 한다. 유튜브가 2025-07-21 에 인기 급상승 페이지를 폐지해
 * 공식 API 의 chart=mostPopular 로는 상품이 나오는 영상을 찾을 수 없기 때문이다.
 */
"use strict";

const path = require("node:path");
const { loadConfig, runDir, writeJson, run, parseArgs, log, step } = require("./_shared.js");
const { buildSearchArgs } = require("../lib/ytdlp-cmd.js");
const { parseSearchOutput, selectDailyQueries } = require("../lib/discover.js");

function main() {
  const args = parseArgs();
  const config = loadConfig("pipeline");
  const keywords = loadConfig("keywords");

  const perKeyword = args.limit || config.discover.perKeyword;

  // 전체를 매번 돌리지 않고 날짜 기준으로 그날 몫만 고른다.
  const 회전 = selectDailyQueries(keywords.searchQueries, {
    perDay: config.discover.queriesPerDay,
    date: new Date(),
  });
  const 검색어들 = args.keyword ? [args.keyword] : 회전.queries;

  const 회전설명 = args.keyword
    ? ""
    : ` (전체 ${keywords.searchQueries.length}개 중 오늘 몫, 한 바퀴 ${회전.cycleDays}일)`;
  step(1, `소재 수집 — 검색어 ${검색어들.length}개${회전설명}, 검색어당 ${perKeyword}편`);

  if (args.dryRun) {
    log("  (dry-run) 실제로 검색하려면 --go 를 붙인다");
    for (const k of 검색어들) log(`  · ${k}`);
    return;
  }

  const 오늘 = new Date();
  const 전체후보 = [];
  const 전체제외 = [];

  for (const 검색어 of 검색어들) {
    const r = run("yt-dlp", buildSearchArgs(검색어, perKeyword), { timeoutMs: 180000 });
    if (!r.ok) {
      log(`  ✗ "${검색어}" 검색 실패 (${r.status}) ${(r.stderr || r.error || "").slice(0, 120)}`);
      continue;
    }

    const { candidates, rejected } = parseSearchOutput(r.stdout, {
      ...config.discover,
      today: 오늘.toISOString(),
    });

    for (const c of candidates) 전체후보.push({ ...c, searchQuery: 검색어 });
    전체제외.push(...rejected);
    log(`  · "${검색어}" → 후보 ${candidates.length} / 제외 ${rejected.length}`);
  }

  // 같은 영상이 여러 검색어에서 나올 수 있다. 점수가 높은 쪽을 남긴다.
  const 중복제거 = new Map();
  for (const c of 전체후보) {
    const 기존 = 중복제거.get(c.videoId);
    if (!기존 || c.productScore > 기존.productScore) 중복제거.set(c.videoId, c);
  }

  const candidates = [...중복제거.values()].sort(
    (a, b) => b.productScore - a.productScore || b.viewCount - a.viewCount
  );

  const 결과 = {
    collectedAt: 오늘.toISOString(),
    queries: 검색어들,
    candidateCount: candidates.length,
    rejectedCount: 전체제외.length,
    candidates,
  };

  const p = path.join(runDir("_collect", 오늘), "candidates.json");
  writeJson(p, 결과);

  log(`\n  후보 ${candidates.length}편 (중복 제거 전 ${전체후보.length}편)`);
  for (const c of candidates.slice(0, 10)) {
    log(`  ${String(c.productScore).padStart(4)} | ${String(c.viewCount).padStart(9)}회 | ${c.videoId} | ${c.title.slice(0, 40)}`);
  }
  log(`\n  → ${path.relative(process.cwd(), p)}`);
}

if (require.main === module) main();
module.exports = { main };
