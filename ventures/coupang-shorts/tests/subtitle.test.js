/** 실행: node --test ventures/coupang-shorts/tests/subtitle.test.js */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { parseVtt, sliceCues, snapToCues, toSrt } = require("../lib/subtitle.js");

/** 유튜브 자동 생성 자막의 굴러가는 캡션 구조를 그대로 흉내 낸 것이다. */
const 굴러가는자막 = `WEBVTT
Kind: captions
Language: ko

00:00:00.080 --> 00:00:02.110 align:start position:0%
 
요즘<00:00:00.399><c> 유튜브에서</c><00:00:01.199><c> 에어프라이어</c>

00:00:02.110 --> 00:00:02.120 align:start position:0%
요즘 유튜브에서 에어프라이어
 

00:00:02.120 --> 00:00:04.390 align:start position:0%
요즘 유튜브에서 에어프라이어
리뷰를<00:00:02.600><c> 많이</c><00:00:03.100><c> 보셨을</c><00:00:03.800><c> 겁니다</c>

00:00:04.390 --> 00:00:04.400 align:start position:0%
리뷰를 많이 보셨을 겁니다
 

00:00:04.400 --> 00:00:07.000 align:start position:0%
리뷰를 많이 보셨을 겁니다
그런데<00:00:04.900><c> 대부분</c><00:00:05.500><c> 광고입니다</c>
`;

test("AC-11: 굴러가는 캡션에서 새 내용만 남기고 중복을 걷어 낸다", () => {
  const cues = parseVtt(굴러가는자막);

  assert.deepEqual(cues.map((c) => c.text), [
    "요즘 유튜브에서 에어프라이어",
    "리뷰를 많이 보셨을 겁니다",
    "그런데 대부분 광고입니다",
  ]);
  // 10밀리초짜리 화면 지우기 큐는 버려야 한다.
  assert.equal(cues.length, 3, "빈 큐까지 세면 5개가 된다");
});

test("AC-11b: 낱말 단위 시각 표시와 HTML 기호를 걷어 낸다", () => {
  const cues = parseVtt(굴러가는자막);
  for (const c of cues) {
    assert.doesNotMatch(c.text, /[<>]/, `태그가 남았다: ${c.text}`);
  }
});

test("AC-11c: 실제 자막 파일에서도 같은 수로 정리된다", () => {
  // 실제로 받아 본 파일을 그대로 고정해 둔 것이다. 형식이 바뀌면 여기서 먼저 드러난다.
  const 경로 = path.join(__dirname, "..", "fixtures", "subtitle-rolling-sample.vtt");
  const cues = parseVtt(fs.readFileSync(경로, "utf-8"));

  assert.ok(cues.length > 0, "실제 파일에서 큐가 하나도 안 나오면 파서가 형식을 못 읽는 것이다");
  // 같은 문장이 연달아 두 번 나오면 안 된다.
  for (let i = 1; i < cues.length; i += 1) {
    assert.notEqual(cues[i].text, cues[i - 1].text, `${i}번째에서 같은 문장이 반복된다`);
  }
});

test("AC-12: 구간에 걸치는 자막만 남기고 시작 시각을 0부터 다시 매긴다", () => {
  const cues = parseVtt(굴러가는자막);
  const sliced = sliceCues(cues, 2.12, 7.0);

  assert.deepEqual(sliced.map((c) => c.text), ["리뷰를 많이 보셨을 겁니다", "그런데 대부분 광고입니다"]);
  assert.equal(sliced[0].startSec, 0, "첫 자막이 0초에서 시작해야 한다");
  assert.ok(sliced[sliced.length - 1].endSec <= 7.0 - 2.12 + 0.001, "구간 밖으로 넘치면 안 된다");
});

test("AC-13: 경계를 허용 범위 안의 자막 경계로 옮긴다", () => {
  const cues = parseVtt(굴러가는자막);
  // 4.4초 큐 시작에서 0.3초 벗어난 곳을 시작점으로 준다.
  const snapped = snapToCues({ startSec: 4.7, endSec: 6.5 }, cues, 3);

  assert.equal(snapped.startSec, 4.4, "가장 가까운 자막 시작으로 옮겨야 한다");
  assert.equal(snapped.endSec, 7.0, "가장 가까운 자막 끝으로 옮겨야 한다");
  assert.equal(snapped.snappedStart, true);
  assert.equal(snapped.snappedEnd, true);
});

test("AC-13b: 허용 범위 밖이면 옮기지 않는다 — 억지로 맞추면 구간이 끌려간다", () => {
  const cues = parseVtt(굴러가는자막);
  const snapped = snapToCues({ startSec: 100, endSec: 130 }, cues, 3);

  assert.equal(snapped.startSec, 100);
  assert.equal(snapped.endSec, 130);
  assert.equal(snapped.snappedStart, false);
  assert.equal(snapped.snappedEnd, false);
});

test("AC-13c: 자막이 아예 없어도 예외를 던지지 않고 구간을 그대로 돌려준다", () => {
  for (const 자막 of [[], null, undefined]) {
    const snapped = snapToCues({ startSec: 10, endSec: 40 }, 자막, 3);
    assert.equal(snapped.startSec, 10);
    assert.equal(snapped.snappedStart, false);
  }
  assert.deepEqual(parseVtt(""), []);
  assert.deepEqual(parseVtt(null), []);
});

test("AC-13d: 옮기다가 구간이 뒤집히면 옮기지 않은 것으로 되돌린다", () => {
  const cues = [
    { startSec: 10, endSec: 12, text: "가" },
    { startSec: 12, endSec: 14, text: "나" },
  ];
  // 시작을 12로 당기고 끝을 12로 미루면 길이가 0이 된다.
  const snapped = snapToCues({ startSec: 11.5, endSec: 12.5 }, cues, 3);
  assert.ok(snapped.endSec > snapped.startSec, "길이가 0 이하인 구간을 내놓으면 안 된다");
});

test("AC-13e: SRT 시각 형식은 쉼표를 쓰고 세 자리 밀리초를 채운다", () => {
  const srt = toSrt([
    { startSec: 0, endSec: 2.269, text: "첫 줄" },
    { startSec: 2.279, endSec: 63.05, text: "둘째 줄" },
  ]);

  assert.match(srt, /^1\n00:00:00,000 --> 00:00:02,269\n첫 줄\n/);
  assert.match(srt, /2\n00:00:02,279 --> 00:01:03,050\n둘째 줄\n/);
  assert.doesNotMatch(srt, /\d\.\d{3} -->/, "SRT 는 마침표가 아니라 쉼표를 쓴다");
});

test("AC-13f: 경계를 옮긴 결과가 길이 제약을 깨면 되돌린다", () => {
  // 회귀 테스트. 실제로 돌려 보니 2위 구간이 스냅 때문에 14.95초가 되어
  // segment.js 가 지킨 최소 길이 15초를 밑돌았다.
  const cues = [
    { startSec: 140.16, endSec: 143, text: "가" },
    { startSec: 143, endSec: 155.11, text: "나" },
  ];
  const 원본 = { startSec: 140, endSec: 155.5, durationSec: 15.5 };

  const 제약없음 = snapToCues(원본, cues, 3);
  assert.ok(제약없음.endSec - 제약없음.startSec < 15, "제약을 주지 않으면 15초를 밑돈다");

  const 제약있음 = snapToCues(원본, cues, 3, { minSec: 15, maxSec: 60 });
  assert.equal(제약있음.startSec, 140, "되돌려야 한다");
  assert.equal(제약있음.endSec, 155.5);
  assert.equal(제약있음.snappedStart, false);
});
