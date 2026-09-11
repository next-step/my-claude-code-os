#!/usr/bin/env node
/**
 * 4단계: 수익화. 검색어를 뽑아 쿠팡 상품을 찾고 업로드용 문구를 만든다.
 *
 * 사용법:
 *   node ventures/coupang-shorts/bin/monetize.js --video 5GTAp_RMEHc --go
 *   node ventures/coupang-shorts/bin/monetize.js --video 5GTAp_RMEHc --go --fake
 *
 * **쿠팡 API 키가 없으면 자동으로 가짜 모드로 돈다.** 키는 누적 판매 15만 원을 넘겨
 * 최종 승인을 받아야 발급되므로(SETUP.md), 그전까지는 검색어와 문구만 만들어 주고
 * 상품 링크는 사람이 쿠팡 파트너스 사이트에서 손으로 만들어 넣는다.
 */
"use strict";

const path = require("node:path");
const {
  loadConfig, loadCredentials, hasCoupangCredentials, runDir, readJson, writeJson,
  budgetStatePath, parseArgs, log, step,
} = require("./_shared.js");
const { extractKeywords } = require("../lib/keyword.js");
const { searchProducts } = require("../lib/coupang.js");
const { emptyState, checkBudget, recordCall, cacheLookup, cacheStore } = require("../lib/budget.js");
const { buildPublishMeta } = require("../lib/publish-meta.js");

/** 키가 없을 때 쓰는 가짜 응답. 상품 자리를 비워 두어 사람이 채우게 한다. */
function 가짜검색(keyword) {
  return { ok: true, products: [], error: null, fake: true, keyword };
}

/**
 * 검색어 하나로 상품을 찾는다. 캐시를 먼저 보고, 한도를 확인한 뒤에 부른다.
 * @returns {{products: Array, source: string, state: object}}
 */
async function 상품찾기({ keyword, state, creds, config, 가짜인가 }) {
  const now = Date.now();

  const 캐시 = cacheLookup(state, keyword, { now, cacheTtlMs: config.coupang.cacheTtlHours * 3600000 });
  if (캐시.hit) {
    return { products: 캐시.value, source: `캐시 (${Math.round(캐시.ageMs / 60000)}분 전)`, state };
  }

  if (가짜인가) {
    return { products: 가짜검색(keyword).products, source: "가짜 모드 (쿠팡 키 없음)", state };
  }

  const 예산 = checkBudget(state, { now, limitPerHour: config.coupang.limitPerHour });
  if (!예산.allowed) {
    return { products: [], source: `한도 초과 — ${예산.warning}`, state };
  }
  if (예산.warning) log(`    경고: ${예산.warning}`);

  const r = await searchProducts({
    keyword,
    limit: config.coupang.searchLimit,
    accessKey: creds.coupangAccessKey,
    secretKey: creds.coupangSecretKey,
  });

  let 새상태 = recordCall(state, { now, limitPerHour: config.coupang.limitPerHour });
  if (!r.ok) return { products: [], source: `실패 — ${r.error}`, state: 새상태 };

  새상태 = cacheStore(새상태, keyword, r.products, { now, cacheTtlMs: config.coupang.cacheTtlHours * 3600000 });
  return { products: r.products, source: `쿠팡 API (${r.products.length}건)`, state: 새상태 };
}

async function main() {
  const args = parseArgs();
  const config = loadConfig("pipeline");
  const keywordConfig = loadConfig("keywords");
  const creds = loadCredentials();

  if (!args.video) {
    log("  --video <영상ID> 가 필요하다");
    return;
  }

  const dir = runDir(args.video);
  const plan = readJson(path.join(dir, "plan.json"));

  step(4, `수익화 — ${args.video}`);

  if (!plan || !plan.segments || plan.segments.length === 0) {
    log("  분석 결과가 없다. 먼저 analyze.js 를 돌린다");
    return;
  }

  const 가짜인가 = args.fake || !hasCoupangCredentials(creds);
  if (가짜인가) {
    log("  쿠팡 키가 없어 가짜 모드로 돈다 — 검색어와 문구만 만들고 링크 자리는 비워 둔다");
  }

  // 1위 구간의 자막까지 합쳐 검색어를 뽑는다. 자막이 주제를 가장 잘 담고 있다.
  const 자막글 = plan.segments.map((s) => s.subtitleText || "").join(" ");
  const { keywords, scored, evidenceRelaxed } = extractKeywords(
    { title: plan.title, channelTitle: plan.channelTitle, subtitleText: 자막글 },
    { boostWords: keywordConfig.boostWords, limit: 3 }
  );

  log(`  검색어: ${keywords.join(", ") || "(없음)"}${evidenceRelaxed ? "  (근거 요구를 풀었다)" : ""}`);
  for (const s of scored.slice(0, 5)) log(`    · ${s.word} (${s.reasons.join(", ")})`);

  if (args.dryRun) {
    log("  (dry-run) 실제로 상품을 찾으려면 --go 를 붙인다");
    return;
  }

  // 쿠팡 호출 예산은 저장소 전체에서 하나다.
  let state = readJson(budgetStatePath(), emptyState());
  const products = [];

  for (const keyword of keywords) {
    const r = await 상품찾기({ keyword, state, creds, config, 가짜인가 });
    state = r.state;
    log(`  "${keyword}" → ${r.source}`);
    products.push(...r.products);
    if (products.length >= config.coupang.maxProductsInDescription) break;
  }

  if (!가짜인가) writeJson(budgetStatePath(), state);

  const meta = buildPublishMeta({
    videoTitle: plan.title,
    channelTitle: plan.channelTitle,
    videoId: plan.videoId,
    keywords,
    products: products.slice(0, config.coupang.maxProductsInDescription),
  });

  const 결과 = {
    videoId: plan.videoId,
    generatedAt: new Date().toISOString(),
    fakeMode: 가짜인가,
    keywords,
    productCount: products.length,
    ...meta,
    segments: plan.segments.map((s) => ({
      rank: s.rank, startSec: s.startSec, endSec: s.endSec, durationSec: s.durationSec,
      file: `short${s.rank}.mp4`,
    })),
  };

  const p = writeJson(path.join(dir, "meta.json"), 결과);

  log(`\n  제목: ${meta.title}`);
  log("  ─ 설명 ─");
  for (const line of meta.description.split("\n")) log(`  ${line}`);
  log(`\n  → ${path.relative(process.cwd(), p)}`);
}

if (require.main === module) main();
module.exports = { main };
