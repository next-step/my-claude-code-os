#!/usr/bin/env node
/**
 * 만들어 둔 쇼츠의 업로드용 문구를 한 파일로 모은다.
 *
 * 사용법:
 *   node ventures/coupang-shorts/bin/export-descriptions.js
 *   node ventures/coupang-shorts/bin/export-descriptions.js --channel https://youtube.com/@...
 *
 * 산출물은 `runs/upload-guide.md` 다. **커밋되지 않는다** — 채널 주소가 들어가고,
 * 이 저장소는 공개 커밋되기 때문이다(.claude/context/sensitive-info.md).
 *
 * 1순위 구간의 평균값 순으로 줄 세운다. 시청자가 많이 되돌려 본 구간일수록 앞에 온다.
 */
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { ROOT, readJson, parseArgs, log } = require("./_shared.js");

/** 쿠팡 검색 결과로 바로 가는 주소. 클릭 한 번을 줄이려고 미리 만들어 둔다. */
const COUPANG_SEARCH = "https://www.coupang.com/np/search?q=";

/** 파트너스 링크 생성 화면. 상품 주소를 여기에 붙여 넣으면 제휴 링크가 나온다. */
const PARTNERS_LINK_TOOL = "https://partners.coupang.com/#affiliate/ws/link";

/** 검색어를 쿠팡 검색 링크로 바꾼다. */
function 검색링크(keyword) {
  return `${COUPANG_SEARCH}${encodeURIComponent(String(keyword).trim())}`;
}

/** runs/ 아래의 모든 영상을 모은다. 같은 영상이 여러 날에 있으면 최근 것을 쓴다. */
function 영상모으기() {
  const 뿌리 = path.join(ROOT, "runs");
  if (!fs.existsSync(뿌리)) return [];

  const 모음 = new Map();
  const 날짜들 = fs.readdirSync(뿌리).filter((n) => /^\d{4}-\d{2}-\d{2}$/.test(n)).sort();

  for (const 날짜 of 날짜들) {
    for (const 이름 of fs.readdirSync(path.join(뿌리, 날짜))) {
      if (이름.startsWith("_")) continue;
      const dir = path.join(뿌리, 날짜, 이름);
      const meta = readJson(path.join(dir, "meta.json"));
      const plan = readJson(path.join(dir, "plan.json"));
      if (!meta || !plan || !Array.isArray(plan.segments) || plan.segments.length === 0) continue;

      const 영상들 = plan.segments
        .map((s) => ({ ...s, file: `short${s.rank}.mp4` }))
        .filter((s) => fs.existsSync(path.join(dir, s.file)));
      if (영상들.length === 0) continue;

      // 날짜 오름차순으로 돌므로 나중 것이 앞의 것을 덮는다.
      모음.set(이름, { dir, 날짜, meta, plan, 영상들, top: plan.segments[0] });
    }
  }

  return [...모음.values()].sort((a, b) => (b.top.meanValue || 0) - (a.top.meanValue || 0));
}

function 문서만들기(영상들, channel) {
  const 줄 = [];
  줄.push("# 업로드 문구 모음");
  줄.push("");
  줄.push(`생성 시각: ${new Date().toISOString().replace("T", " ").slice(0, 16)}`);
  if (channel) 줄.push(`채널: ${channel}`);
  줄.push(`영상: ${영상들.length}건, 쇼츠 ${영상들.reduce((n, v) => n + v.영상들.length, 0)}편`);
  줄.push("");
  줄.push("1순위 구간을 시청자가 얼마나 되돌려 봤는지(평균값) 순으로 줄 세웠다. 위에서부터 올리면 된다.");
  줄.push("");
  const 링크없음 = 영상들.filter((v) => !(v.meta.products || []).length);
  줄.push(`상품 링크가 붙은 영상 ${영상들.length - 링크없음.length}건, 아직 빈 영상 ${링크없음.length}건.`);
  줄.push("");
  줄.push("## 링크 붙이는 법");
  줄.push("");
  줄.push("각 영상의 검색어를 누르면 쿠팡 검색 결과로 바로 간다. 상품을 고른 뒤 그 주소를");
  줄.push(`[파트너스 링크 생성기](${PARTNERS_LINK_TOOL})에 붙여 넣으면 제휴 링크가 나온다.`);
  줄.push("");
  줄.push("**설명란을 손으로 고치지 않는다.** 아래처럼 넘기면 고지 문구 위치와 출처 표기를 맞춰서 다시 만들어 준다.");
  줄.push("");
  줄.push("```bash");
  줄.push('node ventures/coupang-shorts/bin/attach-link.js --go \\');
  줄.push('  --video <영상ID> --link "https://link.coupang.com/a/XXXX" --name "상품명"');
  줄.push("```");
  줄.push("");
  줄.push("여러 건을 한 번에 넣으려면 `runs/links.tsv` 를 채우고 아래를 돌린다. 영상 ID 는 미리 적어 두었다.");
  줄.push("");
  줄.push("```bash");
  줄.push("node ventures/coupang-shorts/bin/attach-link.js --go --from ventures/coupang-shorts/runs/links.tsv");
  줄.push("```");
  줄.push("");
  줄.push("> 단축 URL 은 넣지 않는다. 쿠팡이 공개한 계정 정지 사유 중 하나다. 파트너스가 준 주소를 그대로 쓴다.");
  줄.push("> API 키가 생기면 이 과정 전체가 자동화된다. 키는 누적 판매 15만 원을 넘겨야 발급된다(SETUP.md).");
  줄.push("");
  줄.push("## 올릴 때마다 확인할 것");
  줄.push("");
  줄.push("- [ ] 유튜브 업로드 화면의 **'유료 프로모션 포함' 체크박스**를 켰는가");
  줄.push("- [ ] 설명 **맨 첫 줄**이 대가성 문구인가 (아래 문구를 그대로 붙여 넣으면 맞다)");
  줄.push("- [ ] 상품 링크 자리를 실제 쿠팡 파트너스 링크로 바꿨는가");
  줄.push("- [ ] 영상 좌측 상단에 '유료광고 포함' 배지가 보이는가 (파이프라인이 넣지만 눈으로 확인한다)");
  줄.push("");
  줄.push("맨 아래 두 항목은 쿠팡 최종 승인 심사에서 직접 본다. 설명란이 펼쳐진 화면을 캡처해 두면");
  줄.push("나중에 활동 스크린샷으로 쓸 수 있다.");
  줄.push("");

  const 자막없음 = 영상들.filter((v) => (v.plan.cueCount || 0) === 0);
  if (자막없음.length > 0) {
    줄.push("> **주의**: 아래 영상은 원본에 한국어 자막이 없어 우리 자막도 넣지 못했다.");
    줄.push("> 화면에 들어간 변형이 타이틀과 출처 표기뿐이라 재사용 콘텐츠 판정에서 가장 불리하다.");
    줄.push(`> 첫 업로드로는 피하는 편이 낫다 — ${자막없음.map((v) => v.meta.title.replace(" #shorts", "")).join(", ")}`);
    줄.push("");
  }

  줄.push("---");
  줄.push("");

  영상들.forEach((v, i) => {
    const { meta, plan, top } = v;
    줄.push(`## ${i + 1}. ${meta.title}`);
    줄.push("");
    줄.push(`- 원본: ${plan.channelTitle} — https://youtu.be/${plan.videoId}`);
    줄.push(`- 구간 품질: 평균 ${(top.meanValue || 0).toFixed(2)} / 최고 ${(top.peakValue || 0).toFixed(2)}`);
    줄.push(`- 자막: ${plan.cueCount || 0}줄${(plan.cueCount || 0) === 0 ? "  ⚠️ 없음" : ""}`);
    const 검색어들 = (meta.keywords || []).filter(Boolean);
    줄.push(
      검색어들.length > 0
        ? `- 쿠팡 검색: ${검색어들.map((k) => `[${k}](${검색링크(k)})`).join(" · ")}`
        : "- 쿠팡 검색: (검색어 없음)"
    );
    const 상품들 = meta.products || [];
    if (상품들.length > 0) {
      줄.push(`- 상품: ${상품들.map((x) => x.productName).join(", ")}${meta.needsReview ? "  ⚠️ 확인 필요" : ""}`);
      const 순위 = (meta.productRanking || []).slice(0, 3);
      if (순위.length > 1) {
        줄.push(`- 고른 근거: ${순위.map((r) => `${r.productName.slice(0, 18)}(${r.matchScore})`).join(" > ")}`);
      }
    } else {
      줄.push("- 상품: **아직 없음.** 위의 검색어를 눌러 링크를 만들고 attach-link.js 로 넣는다");
    }
    줄.push("");
    줄.push("올릴 파일:");
    for (const s of v.영상들) {
      줄.push(`- \`${path.relative(process.cwd(), path.join(v.dir, s.file))}\` — ${s.durationSec}초, 자막 ${s.subtitleLineCount}줄`);
    }
    줄.push("");
    줄.push("제목 (복사해서 붙여 넣기):");
    줄.push("");
    줄.push("```");
    줄.push(meta.title);
    줄.push("```");
    줄.push("");
    줄.push("설명 (복사해서 붙여 넣기):");
    줄.push("");
    줄.push("```");
    줄.push(meta.description);
    줄.push("```");
    줄.push("");
    줄.push("---");
    줄.push("");
  });

  return 줄.join("\n");
}

function main() {
  const args = parseArgs();
  const channel = args._.find((a) => a.startsWith("http")) || 채널인자(process.argv);

  const 영상들 = 영상모으기();
  if (영상들.length === 0) {
    log("올릴 영상이 없다. 먼저 run.js 를 돌린다");
    return;
  }

  const 문서 = 문서만들기(영상들, channel);
  const 경로 = path.join(ROOT, "runs", "upload-guide.md");
  fs.writeFileSync(경로, `${문서}\n`, "utf-8");

  // 링크를 채워 넣을 틀을 만든다. **이미 있으면 덮지 않는다** — 사람이 적어 둔 것을 지우면 안 된다.
  const 틀경로 = path.join(ROOT, "runs", "links.tsv");
  if (!fs.existsSync(틀경로)) {
    const 틀 = [
      "# 쿠팡 링크를 채우고 아래를 돌린다:",
      "#   node ventures/coupang-shorts/bin/attach-link.js --go --from ventures/coupang-shorts/runs/links.tsv",
      "#",
      "# 형식: 영상ID <탭> 링크 <탭> 상품명(생략 가능)",
      "# 단축 URL 은 넣지 않는다 — 쿠팡 계정 정지 사유다.",
      "",
      ...영상들
        .filter((v) => !(v.meta.products || []).length)
        .map((v) => `${v.plan.videoId}\t\t# ${v.meta.title.replace(" #shorts", "")}`),
      "",
    ].join("\n");
    fs.writeFileSync(틀경로, 틀, "utf-8");
    log(`→ ${path.relative(process.cwd(), 틀경로)} (링크를 채워 넣을 틀)`);
  }

  log(`영상 ${영상들.length}건, 쇼츠 ${영상들.reduce((n, v) => n + v.영상들.length, 0)}편`);
  log(`→ ${path.relative(process.cwd(), 경로)}`);
}

/** `--channel <주소>` 를 읽는다. parseArgs 가 모르는 인자라 여기서 따로 본다. */
function 채널인자(argv) {
  const i = argv.indexOf("--channel");
  return i !== -1 ? argv[i + 1] : "";
}

if (require.main === module) main();
module.exports = { main, 문서만들기, 검색링크, COUPANG_SEARCH, PARTNERS_LINK_TOOL };
