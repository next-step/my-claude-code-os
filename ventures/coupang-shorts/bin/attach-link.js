#!/usr/bin/env node
/**
 * 사람이 만들어 온 쿠팡 링크를 영상의 설명란에 넣는다.
 *
 * 사용법:
 *   node ventures/coupang-shorts/bin/attach-link.js --video <ID> --link "https://link.coupang.com/a/XXXX" --name "필립스 에어프라이어"
 *   node ventures/coupang-shorts/bin/attach-link.js --from runs/links.tsv
 *
 * 왜 이 경로가 있는가: 쿠팡 파트너스 API 키는 누적 판매 15만 원을 넘겨야 나온다.
 * 그전까지는 사람이 파트너스에서 링크를 만들어 온다. 링크만 받으면 나머지(설명란
 * 조립, 고지 문구 위치, 출처 표기, 해시태그)는 전부 자동으로 맞춰 준다.
 *
 * 브라우저로 파트너스 화면을 자동 조작하는 경로는 막혔다. 쿠팡이 로그인 관문을
 * Akamai 로 차단해, 화면 있는 브라우저로도 로그인 페이지에서 403 이 난다.
 */
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { runDir, readJson, writeJson, parseArgs, log, step } = require("./_shared.js");
const { toProduct, parseLinkFile } = require("../lib/link-input.js");
const { pickProducts } = require("../lib/product-pick.js");
const { buildPublishMeta } = require("../lib/publish-meta.js");
const { loadConfig } = require("./_shared.js");

/** 영상 하나에 상품 목록을 붙이고 설명란을 다시 만든다. */
function attachToVideo(videoId, 새상품들, config) {
  const dir = runDir(videoId);
  const metaPath = path.join(dir, "meta.json");
  const meta = readJson(metaPath);
  const plan = readJson(path.join(dir, "plan.json"));

  if (!meta || !plan) {
    return { ok: false, reason: "meta.json 또는 plan.json 이 없다. 먼저 run.js 를 돌린다" };
  }

  // 이미 붙어 있던 상품과 합친다. 같은 링크는 한 번만 남긴다.
  const 기존 = Array.isArray(meta.products) ? meta.products : [];
  const 합친것 = [...기존, ...새상품들];

  // 후보가 여럿이면 product-pick 이 고른다. 하나뿐이어도 점수와 이유는 남긴다.
  const 자막글 = (plan.segments || []).map((s) => s.subtitleText || "").join(" ");
  const { picked, ranked } = pickProducts(
    {
      candidates: 합친것,
      videoTitle: plan.title,
      subtitleText: 자막글,
      keywords: (meta.keywords || []).map((w) => ({ word: w, score: 2 })),
    },
    { max: config.coupang.maxProductsInDescription }
  );

  const 새메타 = buildPublishMeta({
    videoTitle: plan.title,
    channelTitle: plan.channelTitle,
    videoId: plan.videoId,
    keywords: meta.keywords || [],
    products: picked,
  });

  writeJson(metaPath, {
    ...meta,
    ...새메타,
    productCount: picked.length,
    products: picked,
    productRanking: ranked.map((r) => ({
      productName: r.productName,
      matchScore: r.matchScore,
      matchReasons: r.matchReasons,
      source: r.source || "api",
    })),
    linkedAt: new Date().toISOString(),
  });

  return { ok: true, picked, ranked, metaPath };
}

function main() {
  const args = parseArgs();
  const config = loadConfig("pipeline");

  // 붙일 것을 모은다. 파일이 먼저이고, 없으면 명령줄 인자를 본다.
  const 묶음 = new Map();
  const 거부 = [];

  if (args.from) {
    const p = path.isAbsolute(args.from) ? args.from : path.join(process.cwd(), args.from);
    if (!fs.existsSync(p)) {
      log(`  파일이 없다: ${p}`);
      return;
    }
    const 결과 = parseLinkFile(fs.readFileSync(p, "utf-8"));
    for (const [v, list] of 결과.byVideo) 묶음.set(v, list);
    거부.push(...결과.rejected);
  } else if (args.video && args.link) {
    try {
      묶음.set(args.video, [toProduct({ url: args.link, productName: args.name })]);
    } catch (e) {
      거부.push({ line: args.link, reason: e.message });
    }
  } else {
    log("  --video 와 --link 를 함께 주거나, --from <파일> 로 여러 건을 준다");
    log("");
    log("  파일 형식 (탭으로 나눈다, 상품명은 생략 가능):");
    log("    영상ID<탭>링크<탭>상품명");
    return;
  }

  step(4.5, `링크 붙이기 — 영상 ${묶음.size}건`);

  for (const x of 거부) log(`  ✗ ${x.line.slice(0, 50)} — ${x.reason}`);
  if (묶음.size === 0) return;

  if (args.dryRun) {
    log("  (dry-run) 실제로 붙이려면 --go 를 붙인다");
    for (const [v, list] of 묶음) log(`  · ${v} ← ${list.length}건`);
    return;
  }

  for (const [videoId, 상품들] of 묶음) {
    const r = attachToVideo(videoId, 상품들, config);
    if (!r.ok) {
      log(`  ✗ ${videoId} — ${r.reason}`);
      continue;
    }
    log(`  ✓ ${videoId} — 상품 ${r.picked.length}건 (후보 ${r.ranked.length})`);
    for (const pr of r.picked) {
      log(`      ${pr.productName}`);
      log(`      ${pr.deeplink}`);
    }
    if (r.ranked.length > r.picked.length) {
      log(`      (밀린 후보: ${r.ranked.slice(r.picked.length).map((x) => x.productName).join(", ")})`);
    }
  }

  log("\n  설명란을 다시 만들었다. 업로드 문구를 새로 뽑으려면:");
  log("    node ventures/coupang-shorts/bin/export-descriptions.js");
}

if (require.main === module) main();
module.exports = { main, attachToVideo };
