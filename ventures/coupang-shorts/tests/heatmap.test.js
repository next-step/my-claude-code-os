/** 실행: node --test ventures/coupang-shorts/tests/heatmap.test.js */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { parseHeatmapOutput, normalizeHeatmap } = require("../lib/heatmap.js");

test("AC-4: yt-dlp 가 NA 를 뱉으면 결측으로 판정하고 예외를 던지지 않는다", () => {
  for (const 출력 of ["NA", "N/A", "  NA  ", "", "null", "[]"]) {
    const 결과 = parseHeatmapOutput(출력);
    assert.equal(결과.available, false, `"${출력}" 을 결측으로 봐야 한다`);
    assert.deepEqual(결과.buckets, []);
    assert.equal(typeof 결과.reason, "string", "이유가 문자열로 담겨야 한다");
  }
});

test("AC-4b: JSON 이 아니거나 형태가 망가져도 예외를 던지지 않는다", () => {
  for (const 출력 of ["{깨진 json", "12345", undefined, null, '[{"foo":1}]', '[{"start_time":10,"end_time":5,"value":1}]']) {
    const 결과 = parseHeatmapOutput(출력);
    assert.equal(결과.available, false);
    assert.equal(typeof 결과.reason, "string");
  }
});

test("AC-5: snake_case 를 바꾸고 값을 0~1 로 정규화한다", () => {
  const 출력 = JSON.stringify([
    { start_time: 0, end_time: 6, value: 0.5 },
    { start_time: 6, end_time: 12, value: 2.0 },
    { start_time: 12, end_time: 18, value: 1.0 },
  ]);
  const 결과 = parseHeatmapOutput(출력);

  assert.equal(결과.available, true);
  assert.equal(결과.bucketCount, 3);
  assert.deepEqual(결과.buckets, [
    { startSec: 0, endSec: 6, value: 0.25 },
    { startSec: 6, endSec: 12, value: 1 },
    { startSec: 12, endSec: 18, value: 0.5 },
  ]);
});

test("AC-5b: 최댓값이 1.0 이 되도록 맞춘다 — segment.js 의 decayRatio 가 영상마다 같은 기준이 되게 하기 위해서다", () => {
  const 작은값 = normalizeHeatmap([
    { start_time: 0, end_time: 6, value: 0.01 },
    { start_time: 6, end_time: 12, value: 0.04 },
  ]);
  assert.equal(작은값.buckets[1].value, 1);
  assert.equal(작은값.buckets[0].value, 0.25);
});

test("AC-5c: 순서가 뒤섞여 들어와도 시작 시각 오름차순으로 정렬한다", () => {
  const 결과 = normalizeHeatmap([
    { start_time: 12, end_time: 18, value: 1 },
    { start_time: 0, end_time: 6, value: 1 },
    { start_time: 6, end_time: 12, value: 1 },
  ]);
  assert.deepEqual(결과.buckets.map((b) => b.startSec), [0, 6, 12]);
});

test("AC-5d: 값이 전부 0이면 정보가 없는 것으로 보고 결측 처리한다", () => {
  const 결과 = normalizeHeatmap([
    { start_time: 0, end_time: 6, value: 0 },
    { start_time: 6, end_time: 12, value: 0 },
  ]);
  assert.equal(결과.available, false);
  assert.match(결과.reason, /0/);
});
