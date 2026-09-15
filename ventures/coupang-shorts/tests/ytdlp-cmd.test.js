/** 실행: node --test ventures/coupang-shorts/tests/ytdlp-cmd.test.js */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  buildSearchArgs, buildHeatmapArgs, buildSubtitleArgs, buildSectionDownloadArgs, FIELDS, FIELD_SEP,
} = require("../lib/ytdlp-cmd.js");

test("AC-29: 검색 인자를 배열로 돌려주어 검색어가 셸에 해석되지 않는다", () => {
  const args = buildSearchArgs("에어프라이어 $(rm -rf ~) '추천'", 5);
  assert.ok(Array.isArray(args));
  assert.equal(args[args.length - 1], "ytsearch5:에어프라이어 $(rm -rf ~) '추천'");
  assert.equal(args.filter((a) => a.includes("rm -rf")).length, 1, "검색어가 쪼개지지 않아야 한다");
});

test("AC-29b: 가져올 개수를 1~50 안으로 제한한다", () => {
  assert.match(buildSearchArgs("가전", 0).at(-1), /^ytsearch1:/);
  assert.match(buildSearchArgs("가전", 999).at(-1), /^ytsearch50:/);
  assert.match(buildSearchArgs("가전", 7.9).at(-1), /^ytsearch7:/);
  assert.throws(() => buildSearchArgs("  "), /검색어/);
});

test("AC-30: 출력 템플릿의 필드 순서가 discover.js 의 파싱 순서와 같다", () => {
  // 이 둘이 어긋나면 조회수 자리에 채널명이 들어가는 식으로 조용히 망가진다.
  const args = buildSearchArgs("가전", 3);
  const template = args[args.indexOf("--print") + 1];
  assert.deepEqual(template.split(FIELD_SEP), FIELDS.map((f) => `%(${f})s`));
  assert.deepEqual(FIELDS, ["id", "duration", "view_count", "channel", "upload_date", "title"]);
});

test("AC-31: 영상 ID 형식을 검사해 URL 조작을 막는다", () => {
  const 나쁜입력 = ["", "짧음", "../../etc/passwd", "abc def ghij", "5GTAp_RMEHc&x=1", null, 12345];
  for (const v of 나쁜입력) {
    assert.throws(() => buildHeatmapArgs(v), /영상 ID/, `막아야 한다: ${v}`);
  }
  assert.doesNotThrow(() => buildHeatmapArgs("5GTAp_RMEHc"));
});

test("AC-32: 구간 다운로드는 앞뒤로 여유를 두고 키프레임을 맞춘다", () => {
  const args = buildSectionDownloadArgs({
    videoId: "5GTAp_RMEHc", startSec: 777, endSec: 803.2, outputPath: "/tmp/x.%(ext)s", padSec: 1,
  });
  assert.equal(args[args.indexOf("--download-sections") + 1], "*776-804.2");
  assert.ok(args.includes("--force-keyframes-at-cuts"), "없으면 잘린 앞부분이 깨진 화면으로 시작한다");
  assert.equal(args[args.indexOf("--merge-output-format") + 1], "mp4");
});

test("AC-32b: 구간 시작이 0보다 작아지지 않는다", () => {
  const args = buildSectionDownloadArgs({
    videoId: "5GTAp_RMEHc", startSec: 0.5, endSec: 20, outputPath: "/tmp/x.%(ext)s", padSec: 3,
  });
  assert.equal(args[args.indexOf("--download-sections") + 1], "*0-23");
});

test("AC-32c: 구간이 뒤집혔거나 숫자가 아니면 인자를 만들지 않는다", () => {
  const 기본 = { videoId: "5GTAp_RMEHc", outputPath: "/tmp/x.%(ext)s" };
  assert.throws(() => buildSectionDownloadArgs({ ...기본, startSec: 100, endSec: 50 }), /endSec/);
  assert.throws(() => buildSectionDownloadArgs({ ...기본, startSec: "많이", endSec: 50 }), /숫자/);
  assert.throws(() => buildSectionDownloadArgs({ ...기본, startSec: 0, endSec: 10, outputPath: "" }), /outputPath/);
});

test("AC-33: 자막은 자동 생성 자막까지 받고 vtt 로 저장한다", () => {
  const args = buildSubtitleArgs("5GTAp_RMEHc", "/tmp/sub.%(ext)s", "ko");
  assert.ok(args.includes("--write-auto-subs"), "사람이 단 자막이 없는 영상이 훨씬 많다");
  assert.equal(args[args.indexOf("--sub-langs") + 1], "ko");
  assert.equal(args[args.indexOf("--sub-format") + 1], "vtt");
});
