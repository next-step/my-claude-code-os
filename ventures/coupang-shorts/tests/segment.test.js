/**
 * segment.js 인수 테스트.
 *
 * 실행: node --test ventures/coupang-shorts/tests/segment.test.js
 * (디렉터리를 지정하면 Node 가 `.` 으로 시작하는 경로를 건너뛰는 문제와 별개로,
 *  이 저장소는 파일을 직접 지정하는 것을 관례로 삼는다 — code-vs-instruction.md)
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { selectSegments, meanValueOver } = require("../lib/segment.js");

/** 값 배열을 균등 버킷으로 만든다. yt-dlp 가 주는 형태를 흉내 낸 것이다. */
function buckets(values, bucketSec = 6) {
  return values.map((value, i) => ({
    startSec: i * bucketSec,
    endSec: (i + 1) * bucketSec,
    value,
  }));
}

/** 지정한 위치에 봉우리가 하나 있는 프로필. 나머지는 낮은 평지다. */
function peakAt(length, peakIndex, width = 8, base = 0.2, top = 1.0) {
  return Array.from({ length }, (_, i) => {
    const d = Math.abs(i - peakIndex);
    if (d > width) return base;
    return base + (top - base) * (1 - d / (width + 1));
  });
}

test("AC-6: 평균값이 가장 높은 구간을 1순위로 고른다", () => {
  // 100버킷 × 6초 = 600초 영상. 50번 버킷(300초 부근)에 봉우리를 둔다.
  const { segments, skipped } = selectSegments(buckets(peakAt(100, 50)));

  assert.equal(skipped, null);
  assert.ok(segments.length >= 1, "구간이 하나 이상 나와야 한다");

  const first = segments[0];
  assert.equal(first.rank, 1);
  // 봉우리 중심(300초)이 1순위 구간 안에 들어와야 한다.
  assert.ok(first.startSec <= 300 && first.endSec >= 306, `1순위가 봉우리를 품어야 하는데 ${first.startSec}~${first.endSec} 이다`);
});

test("AC-7: 고른 구간의 길이가 항상 최소·최대 범위 안에 있다", () => {
  const 프로필들 = [
    peakAt(100, 50),              // 가운데 봉우리 하나
    peakAt(100, 3, 2),            // 맨 앞의 아주 좁은 봉우리
    peakAt(100, 96, 2),           // 맨 뒤의 아주 좁은 봉우리
    Array.from({ length: 100 }, () => 0.5),        // 완전히 평평함
    Array.from({ length: 100 }, (_, i) => i / 100), // 단조 증가
  ];

  for (const values of 프로필들) {
    const { segments } = selectSegments(buckets(values), { minSec: 15, maxSec: 60 });
    for (const s of segments) {
      assert.ok(s.durationSec >= 15, `최소 길이 미달: ${s.durationSec}초`);
      assert.ok(s.durationSec <= 60, `최대 길이 초과: ${s.durationSec}초`);
    }
  }
});

test("AC-8: 상위 구간끼리 지정한 간격 이상 떨어져 있다", () => {
  // 봉우리 세 개를 멀찍이 떨어뜨려 둔다.
  const values = Array.from({ length: 200 }, () => 0.1);
  for (const center of [30, 100, 170]) {
    for (let i = center - 5; i <= center + 5; i += 1) values[i] = 0.9;
  }

  const minGapSec = 30;
  const { segments } = selectSegments(buckets(values), { topN: 3, minGapSec });
  assert.equal(segments.length, 3, "봉우리가 셋이면 셋을 다 골라야 한다");

  const 정렬 = [...segments].sort((a, b) => a.startSec - b.startSec);
  for (let i = 1; i < 정렬.length; i += 1) {
    const 간격 = 정렬[i].startSec - 정렬[i - 1].endSec;
    assert.ok(간격 >= minGapSec, `${i}번과 ${i + 1}번 사이가 ${간격}초로 너무 붙어 있다`);
  }
});

test("AC-9: 도입부와 말미를 제외하는 옵션이 적용된다", () => {
  // 인트로(맨 앞)에 가장 큰 봉우리를 두어, 제외하지 않으면 그것이 뽑히게 만든다.
  const values = Array.from({ length: 100 }, () => 0.2);
  for (let i = 0; i < 6; i += 1) values[i] = 1.0;      // 0~36초 인트로
  for (let i = 48; i < 56; i += 1) values[i] = 0.7;    // 288~336초 본문

  const 제외없음 = selectSegments(buckets(values), { topN: 1 });
  assert.ok(제외없음.segments[0].startSec < 60, "제외하지 않으면 인트로가 뽑혀야 한다");

  const 제외함 = selectSegments(buckets(values), { topN: 1, excludeHeadSec: 60, excludeTailSec: 30 });
  assert.ok(제외함.segments[0].startSec >= 60, `도입부 제외가 적용되지 않았다: ${제외함.segments[0].startSec}초`);
  assert.ok(제외함.segments[0].endSec <= 600 - 30, `말미 제외가 적용되지 않았다: ${제외함.segments[0].endSec}초`);
});

test("AC-10: 같은 입력에 항상 같은 결과를 낸다", () => {
  const input = buckets(peakAt(100, 42));
  const 첫번째 = selectSegments(input);
  const 두번째 = selectSegments(input);
  const 세번째 = selectSegments(buckets(peakAt(100, 42)));

  assert.deepEqual(첫번째, 두번째);
  assert.deepEqual(첫번째, 세번째);
});

test("AC-10b: 히트맵이 비었거나 망가져도 예외를 던지지 않고 이유를 돌려준다", () => {
  for (const 입력 of [[], null, undefined, [{ startSec: 10, endSec: 5, value: 1 }]]) {
    const 결과 = selectSegments(입력);
    assert.deepEqual(결과.segments, []);
    assert.equal(typeof 결과.skipped, "string", "건너뛴 이유가 문자열로 담겨야 한다");
  }
});

test("AC-10c: 구간 평균값은 겹치는 길이로 가중한다", () => {
  // 0~10초 값 1.0, 10~20초 값 0.0 인 버킷 두 개.
  const b = [
    { startSec: 0, endSec: 10, value: 1.0 },
    { startSec: 10, endSec: 20, value: 0.0 },
  ];
  assert.equal(meanValueOver(b, 0, 10), 1.0);
  assert.equal(meanValueOver(b, 0, 20), 0.5);
  assert.equal(meanValueOver(b, 5, 15), 0.5);
  assert.equal(meanValueOver(b, 5, 5), 0, "길이가 0이면 0을 돌려준다");
});

test("AC-8b: 1등 후보 창이 버려져도 다음 후보로 넘어가 구간을 채운다", () => {
  // 회귀 테스트. 실제 히트맵(214초 영상)을 넣었을 때 topN=3 인데 1개만 나왔다.
  // 1등 창에서 넓힌 구간이 이미 고른 구간과 겹쳐 버려지자 그대로 포기했기 때문이다.
  // 값이 단조 감소하는 프로필이 그 상황을 그대로 재현한다.
  const 단조감소 = Array.from({ length: 100 }, (_, i) => 1 - i / 120);
  const { segments } = selectSegments(buckets(단조감소), { topN: 3, minGapSec: 30 });

  assert.ok(segments.length >= 2, `후보를 이어서 훑지 않으면 1개만 나온다 (나온 개수: ${segments.length})`);
  assert.deepEqual(segments.map((s) => s.rank), segments.map((_, i) => i + 1), "순위가 1부터 연속이어야 한다");
});

test("AC-8c: 영상이 짧아 topN 을 채울 수 없으면 채운 만큼만 돌려준다", () => {
  // 60초짜리 영상에는 15초 구간 세 개가 30초 간격으로 들어갈 수 없다.
  const { segments, skipped } = selectSegments(buckets(peakAt(10, 5), 6), { topN: 3, minGapSec: 30 });
  assert.ok(segments.length < 3, "억지로 세 개를 만들어 내면 안 된다");
  assert.ok(segments.length >= 1);
  assert.equal(skipped, null);
});
