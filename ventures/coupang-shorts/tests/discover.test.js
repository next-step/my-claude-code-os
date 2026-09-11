/** 실행: node --test ventures/coupang-shorts/tests/discover.test.js */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { parseSearchOutput } = require("../lib/discover.js");
const { FIELD_SEP } = require("../lib/ytdlp-cmd.js");

/** yt-dlp --print 출력 한 줄을 만든다. */
function 줄({ id = "5GTAp_RMEHc", duration = 873, views = 511447, channel = "노써치", date = "20260801", title = "에어프라이어 리뷰" }) {
  return [id, duration, views, channel, date, title].join(FIELD_SEP);
}

/** 오늘을 고정한다. 실제 시계를 쓰면 오늘 통과하고 내일 깨지는 테스트가 된다. */
const 오늘 = "2026-09-11T00:00:00.000Z";

test("AC-1: 조회수와 길이 하한에 미달한 영상을 후보에서 제외한다", () => {
  const stdout = [
    줄({ id: "aaaaaaaaaaa", duration: 60, title: "짧은 리뷰" }),
    줄({ id: "bbbbbbbbbbb", views: 1200, title: "조회수 적은 리뷰" }),
    줄({ id: "ccccccccccc", duration: 7200, title: "아주 긴 리뷰" }),
    줄({ id: "ddddddddddd", title: "정상 리뷰" }),
  ].join("\n");

  const { candidates, rejected } = parseSearchOutput(stdout, { today: 오늘 });

  assert.deepEqual(candidates.map((c) => c.videoId), ["ddddddddddd"]);
  assert.equal(rejected.length, 3);
  assert.match(rejected.find((r) => r.videoId === "aaaaaaaaaaa").reason, /짧다/);
  assert.match(rejected.find((r) => r.videoId === "bbbbbbbbbbb").reason, /조회수/);
  assert.match(rejected.find((r) => r.videoId === "ccccccccccc").reason, /길다/);
});

test("AC-2: 너무 오래된 영상을 제외하고, 기준 날짜를 주입받아 판정한다", () => {
  const stdout = [
    줄({ id: "aaaaaaaaaaa", date: "20240101", title: "오래된 리뷰" }),
    줄({ id: "bbbbbbbbbbb", date: "20260801", title: "최근 리뷰" }),
  ].join("\n");

  const { candidates } = parseSearchOutput(stdout, { today: 오늘 });
  assert.deepEqual(candidates.map((c) => c.videoId), ["bbbbbbbbbbb"]);

  // 기준 날짜를 옮기면 판정도 따라 바뀌어야 한다 — 실제 시계를 쓰지 않는다는 증거다.
  const 과거기준 = parseSearchOutput(stdout, { today: "2024-02-01T00:00:00.000Z", maxAgeDays: 365 });
  assert.ok(과거기준.candidates.some((c) => c.videoId === "aaaaaaaaaaa"));
});

test("AC-3: 제목에 상품 신호어가 있으면 점수를 높이고 이유를 남긴다", () => {
  const stdout = [
    줄({ id: "aaaaaaaaaaa", title: "그냥 이야기" }),
    줄({ id: "bbbbbbbbbbb", title: "에어프라이어 추천 비교 리뷰 내돈내산" }),
  ].join("\n");

  const { candidates } = parseSearchOutput(stdout, { today: 오늘 });

  const 밋밋 = candidates.find((c) => c.videoId === "aaaaaaaaaaa");
  const 신호많음 = candidates.find((c) => c.videoId === "bbbbbbbbbbb");

  assert.ok(신호많음.productScore > 밋밋.productScore, "신호어가 많은 쪽 점수가 높아야 한다");
  assert.ok(신호많음.reasons.length >= 3, "어떤 신호어가 걸렸는지 남겨야 한다");
  assert.equal(candidates[0].videoId, "bbbbbbbbbbb", "점수가 높은 쪽이 앞에 와야 한다");
});

test("AC-3b: 상품과 연결하기 어려운 유형은 제외한다", () => {
  const stdout = [
    줄({ id: "aaaaaaaaaaa", title: "일상 브이로그" }),
    줄({ id: "bbbbbbbbbbb", title: "신곡 커버" }),
    줄({ id: "ccccccccccc", title: "에어프라이어 리뷰" }),
  ].join("\n");

  const { candidates, rejected } = parseSearchOutput(stdout, { today: 오늘 });
  assert.deepEqual(candidates.map((c) => c.videoId), ["ccccccccccc"]);
  assert.equal(rejected.length, 2);
});

test("AC-3c: 출처를 표기할 채널명이 없으면 후보에서 뺀다", () => {
  // 채널명을 모르면 출처 표기를 만들 수 없고, 그러면 publish-meta 가 막는다.
  const stdout = 줄({ channel: "NA" });
  const { candidates, rejected } = parseSearchOutput(stdout, { today: 오늘 });
  assert.equal(candidates.length, 0);
  assert.match(rejected[0].reason, /채널명/);
});

test("AC-3d: 깨진 줄과 빈 줄이 섞여도 멈추지 않고 나머지를 처리한다", () => {
  const stdout = [
    "형식이 전혀 다른 줄",
    "",
    "짧은\t줄",
    줄({ id: "ddddddddddd", title: "정상 리뷰" }),
    "   ",
  ].join("\n");

  const { candidates, rejected } = parseSearchOutput(stdout, { today: 오늘 });
  assert.equal(candidates.length, 1);
  assert.ok(rejected.length >= 2);
});

test("AC-3e: 같은 입력에 항상 같은 순서를 낸다", () => {
  const stdout = [
    줄({ id: "aaaaaaaaaaa", title: "에어프라이어 리뷰", views: 100000 }),
    줄({ id: "bbbbbbbbbbb", title: "에어프라이어 리뷰", views: 100000 }),
  ].join("\n");

  const 첫번째 = parseSearchOutput(stdout, { today: 오늘 });
  const 두번째 = parseSearchOutput(stdout, { today: 오늘 });
  assert.deepEqual(첫번째, 두번째);
  assert.deepEqual(첫번째.candidates.map((c) => c.videoId), ["aaaaaaaaaaa", "bbbbbbbbbbb"]);
});
