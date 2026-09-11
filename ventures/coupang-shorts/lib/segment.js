/**
 * 히트맵에서 쇼츠로 쓸 구간을 고르는 순수 함수.
 *
 * 이 사업의 핵심 판단이 여기 한 곳에 모여 있다. 그래서 `.claude/context/code-vs-instruction.md`
 * 의 관례대로 부작용을 일절 두지 않는다 — 시간도 난수도 파일도 쓰지 않으므로
 * 같은 입력에 항상 같은 결과가 나오고, 그래서 테스트로 잠글 수 있다.
 *
 * 입력은 yt-dlp 가 주는 히트맵을 `heatmap.js` 가 정규화한 형태다:
 *   [{ startSec, endSec, value }]  (value 는 0~1, startSec 오름차순)
 *
 * 자막 경계로 구간을 다듬는 일은 여기서 하지 않는다 — `subtitle.js` 의 몫이다.
 * 이 모듈은 "시청자가 어디를 다시 봤는가"만 보고, 말이 잘리는지 여부는 보지 않는다.
 */
"use strict";

/**
 * 기본값의 근거.
 * - targetSec 45: 쇼츠는 최대 3분까지 올릴 수 있지만 실제로 끝까지 보는 길이는 1분 안쪽이다.
 * - minSec 15: 이보다 짧으면 상품을 설명할 시간이 나오지 않는다.
 * - maxSec 60: 60초를 넘기면 쇼츠 피드에서 이탈이 급격히 늘어난다고 알려져 있다.
 * - decayRatio 0.6: 최고점의 60% 아래로 떨어지면 "그 장면이 아니다"로 본다. 첫 추정치이고
 *   실제 표본을 돌려 보고 조정할 값이다.
 * - minGapSec 30: 상위 구간끼리 너무 붙으면 사실상 같은 장면을 두 번 뽑게 된다.
 */
const DEFAULTS = Object.freeze({
  targetSec: 45,
  minSec: 15,
  maxSec: 60,
  topN: 3,
  minGapSec: 30,
  decayRatio: 0.6,
  excludeHeadSec: 0,
  excludeTailSec: 0,
});

/** 소수 첫째 자리까지만 남긴다. ffmpeg 인자로 그대로 넘어가므로 자릿수를 고정한다. */
function round1(n) {
  return Math.round(n * 10) / 10;
}

/**
 * [start, end) 구간의 시간 가중 평균값.
 *
 * 버킷이 균등 분할이라고 가정하지 않고 겹치는 길이로 가중한다 — yt-dlp 가 항상
 * 100등분을 준다는 보장이 없고, 가정이 깨져도 조용히 틀린 값을 내지 않게 하기 위해서다.
 */
function meanValueOver(buckets, start, end) {
  if (!(end > start)) return 0;
  let weighted = 0;
  let covered = 0;
  for (const b of buckets) {
    const lo = Math.max(b.startSec, start);
    const hi = Math.min(b.endSec, end);
    if (hi <= lo) continue;
    weighted += b.value * (hi - lo);
    covered += hi - lo;
  }
  return covered > 0 ? weighted / covered : 0;
}

/** 주어진 구간에 걸치는 버킷 중 값이 가장 큰 것. 동점이면 앞선 것을 쓴다(결정론 유지). */
function peakBucketIn(buckets, start, end) {
  let best = null;
  for (const b of buckets) {
    if (b.endSec <= start || b.startSec >= end) continue;
    if (best === null || b.value > best.value) best = b;
  }
  return best;
}

/**
 * 히트맵에서 상위 구간을 고른다.
 *
 * 절차:
 *  1. targetSec 길이 창을 훑어 평균값이 가장 높은 위치를 찾는다.
 *  2. 그 창 안의 최고점 버킷에서 좌우로 넓히되, 값이 최고점의 decayRatio 아래로
 *     떨어지면 멈춘다. 장면의 실제 경계를 따라가기 위해서다.
 *  3. 길이를 [minSec, maxSec] 로 맞춘다.
 *  4. 고른 구간 좌우 minGapSec 을 가리고 1번으로 돌아가 topN 개를 채운다.
 *
 * @returns {{segments: Array, skipped: string|null}} 고를 수 없으면 segments 는 빈 배열이고
 *   skipped 에 이유가 담긴다. 예외를 던지지 않는다 — 한 영상이 실패해도 배치 전체가
 *   멈추면 안 되기 때문이다.
 */
function selectSegments(buckets, options = {}) {
  const opt = { ...DEFAULTS, ...options };

  if (!Array.isArray(buckets) || buckets.length === 0) {
    return { segments: [], skipped: "히트맵이 비어 있다" };
  }

  const sorted = [...buckets]
    .filter((b) => b && Number.isFinite(b.startSec) && Number.isFinite(b.endSec) && b.endSec > b.startSec)
    .sort((a, b) => a.startSec - b.startSec);

  if (sorted.length === 0) {
    return { segments: [], skipped: "유효한 버킷이 없다" };
  }

  const videoStart = sorted[0].startSec;
  const videoEnd = sorted[sorted.length - 1].endSec;

  // 도입부·말미를 제외한다. 인트로와 아웃트로가 히트맵 상위에 잡히는 왜곡이 흔하다.
  const lowerBound = videoStart + Math.max(0, opt.excludeHeadSec);
  const upperBound = videoEnd - Math.max(0, opt.excludeTailSec);

  if (upperBound - lowerBound < opt.minSec) {
    return { segments: [], skipped: "제외 구간을 빼고 나면 최소 길이를 채울 수 없다" };
  }

  /** 이미 고른 구간들. 겹침 판정에 쓴다. */
  const taken = [];
  const segments = [];

  for (let rank = 1; rank <= opt.topN; rank += 1) {
    const picked = pickOne(sorted, opt, lowerBound, upperBound, taken);
    if (!picked) break;
    taken.push(picked);
    segments.push({
      rank,
      startSec: round1(picked.startSec),
      endSec: round1(picked.endSec),
      durationSec: round1(picked.endSec - picked.startSec),
      peakValue: picked.peakValue,
      meanValue: round1(picked.meanValue * 1000) / 1000,
    });
  }

  if (segments.length === 0) {
    return { segments: [], skipped: "조건을 만족하는 구간을 찾지 못했다" };
  }
  return { segments, skipped: null };
}

/** 이미 고른 구간과 minGapSec 안으로 겹치는지. */
function blocked(start, end, taken, minGapSec) {
  return taken.some((t) => start < t.endSec + minGapSec && end > t.startSec - minGapSec);
}

/**
 * 구간 하나를 고른다. 못 고르면 null.
 *
 * 후보 창을 평균값 내림차순으로 **전부** 훑는다. 처음에는 1등 창 하나만 보고 실패하면
 * 포기했는데, 실제 히트맵을 넣어 보니 상위 구간을 3개 요청해도 1개만 나왔다.
 * 1등 창에서 넓힌 구간이 이미 고른 구간과 겹쳐 버려지면 그대로 끝나 버렸기 때문이다.
 * 2등·3등 창으로 넘어가면 대부분 살아남는다.
 */
function pickOne(buckets, opt, lowerBound, upperBound, taken) {
  // 1. targetSec 창을 훑어 후보를 모으고 평균값 순으로 줄 세운다.
  const windowLen = Math.min(opt.targetSec, upperBound - lowerBound);
  const 후보들 = [];

  for (const b of buckets) {
    const start = Math.max(b.startSec, lowerBound);
    const end = start + windowLen;
    if (end > upperBound) continue;
    if (blocked(start, end, taken, opt.minGapSec)) continue;
    후보들.push({ start, mean: meanValueOver(buckets, start, end) });
  }

  // 동점이면 앞선 시작점을 먼저 쓴다 — 결정론을 유지하기 위해서다.
  후보들.sort((a, b) => (b.mean - a.mean) || (a.start - b.start));

  for (const 후보 of 후보들) {
    const 결과 = 넓히기(buckets, opt, lowerBound, upperBound, taken, 후보.start, windowLen);
    if (결과) return 결과;
  }
  return null;
}

/** 후보 창 하나에서 실제 구간을 넓혀 본다. 조건을 못 맞추면 null. */
function 넓히기(buckets, opt, lowerBound, upperBound, taken, bestStart, windowLen) {
  // 2. 창 안의 최고점에서 좌우로 넓힌다.
  const peak = peakBucketIn(buckets, bestStart, bestStart + windowLen);
  if (!peak) return null;
  const threshold = peak.value * opt.decayRatio;

  let start = peak.startSec;
  let end = peak.endSec;

  let grew = true;
  while (grew && end - start < opt.maxSec) {
    grew = false;
    const left = buckets.filter((b) => b.endSec <= start).pop();
    const right = buckets.find((b) => b.startSec >= end);

    // 좌우 중 값이 큰 쪽을 먼저 먹는다. 경계가 한쪽으로 치우치지 않게 하기 위해서다.
    const leftOk = left && left.value >= threshold && left.startSec >= lowerBound;
    const rightOk = right && right.value >= threshold && right.endSec <= upperBound;

    if (leftOk && (!rightOk || left.value >= right.value)) {
      start = left.startSec;
      grew = true;
    } else if (rightOk) {
      end = right.endSec;
      grew = true;
    }
  }

  // 3. 길이를 [minSec, maxSec] 안으로 맞춘다.
  if (end - start > opt.maxSec) {
    // 최고점을 가운데 두고 자른다.
    const center = (peak.startSec + peak.endSec) / 2;
    start = center - opt.maxSec / 2;
    end = center + opt.maxSec / 2;
  }
  while (end - start < opt.minSec) {
    const need = opt.minSec - (end - start);
    const canLeft = start - lowerBound;
    const canRight = upperBound - end;
    if (canLeft <= 0 && canRight <= 0) break;
    const takeLeft = Math.min(canLeft, need / 2);
    const takeRight = Math.min(canRight, need - takeLeft);
    start -= takeLeft;
    end += takeRight;
    if (takeLeft <= 0 && takeRight <= 0) break;
  }

  start = Math.max(start, lowerBound);
  end = Math.min(end, upperBound);

  if (end - start < opt.minSec) return null;
  if (blocked(start, end, taken, opt.minGapSec)) return null;

  return { startSec: start, endSec: end, peakValue: peak.value, meanValue: meanValueOver(buckets, start, end) };
}

module.exports = { selectSegments, meanValueOver, DEFAULTS };
