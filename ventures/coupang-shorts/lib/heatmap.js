/**
 * yt-dlp 가 뱉은 히트맵 출력을 `segment.js` 가 먹을 수 있는 형태로 정규화한다.
 *
 * 이 모듈이 짊어진 위험: 히트맵은 유튜브 공식 API에 없는 값이다. yt-dlp 가 플레이어
 * 내부 응답에서 긁어 오는 것이라 유튜브가 구조를 바꾸면 언제든 사라진다. 실제로
 * 값이 나오지 않는 결함 보고(yt-dlp #8189)가 있었다. 그래서 이 모듈의 가장 중요한
 * 책임은 "파싱"이 아니라 **없을 때 조용히 없다고 말하는 것**이다 — 예외를 던지면
 * 영상 한 편 때문에 배치 전체가 멈춘다.
 *
 * yt-dlp 원본 형태 (snake_case 이므로 여기서 한 번 바꿔 준다):
 *   [{ "start_time": 0.0, "end_time": 6.1, "value": 0.23 }, ...]
 */
"use strict";

/** yt-dlp 가 값이 없을 때 내놓는 표기들. `--print` 는 보통 "NA" 를 쓴다. */
const 결측표기 = new Set(["NA", "N/A", "null", "none", "", "[]"]);

/**
 * `yt-dlp --print "%(heatmap)j"` 의 표준출력 한 줄을 받아 정규화한다.
 *
 * @param {string} raw yt-dlp 표준출력
 * @returns {{available: boolean, buckets: Array, reason: string|null, bucketCount: number}}
 */
function parseHeatmapOutput(raw) {
  if (typeof raw !== "string") {
    return 없음("히트맵 출력이 문자열이 아니다");
  }

  const trimmed = raw.trim();
  if (결측표기.has(trimmed)) {
    return 없음("yt-dlp 가 히트맵을 내놓지 않았다 (조회수가 적거나 유튜브가 제공하지 않는 영상)");
  }

  let parsed;
  try {
    parsed = JSON.parse(trimmed);
  } catch (_) {
    return 없음("히트맵 출력이 JSON 이 아니다");
  }

  return normalizeHeatmap(parsed);
}

/**
 * 이미 파싱된 배열을 정규화한다. `--dump-json` 으로 받은 경우의 진입점이다.
 *
 * 값은 최댓값으로 나눠 0~1 로 맞춘다. yt-dlp 가 주는 값의 범위가 영상마다 다를 수
 * 있는데, `segment.js` 의 decayRatio 가 "최고점 대비 비율"로 판정하므로 최고점을
 * 1.0 에 고정해 두어야 영상끼리 같은 기준이 적용된다.
 */
function normalizeHeatmap(parsed) {
  if (!Array.isArray(parsed) || parsed.length === 0) {
    return 없음("히트맵이 빈 배열이다");
  }

  const raw = [];
  for (const item of parsed) {
    if (!item || typeof item !== "object") continue;
    const startSec = 숫자(item.start_time ?? item.startSec);
    const endSec = 숫자(item.end_time ?? item.endSec);
    const value = 숫자(item.value);
    if (startSec === null || endSec === null || value === null) continue;
    if (endSec <= startSec) continue;
    raw.push({ startSec, endSec, value });
  }

  if (raw.length === 0) {
    return 없음("히트맵 항목이 전부 형식에 맞지 않는다");
  }

  raw.sort((a, b) => a.startSec - b.startSec);

  const max = raw.reduce((m, b) => (b.value > m ? b.value : m), 0);
  // 최댓값이 0이면 나눌 수 없다. 전 구간이 0인 히트맵은 정보가 없는 것과 같다.
  if (max <= 0) {
    return 없음("히트맵 값이 전부 0이다");
  }

  const buckets = raw.map((b) => ({
    startSec: b.startSec,
    endSec: b.endSec,
    value: Math.min(1, Math.max(0, b.value / max)),
  }));

  return { available: true, buckets, reason: null, bucketCount: buckets.length };
}

function 없음(reason) {
  return { available: false, buckets: [], reason, bucketCount: 0 };
}

function 숫자(v) {
  const n = typeof v === "string" ? Number(v) : v;
  return Number.isFinite(n) ? n : null;
}

module.exports = { parseHeatmapOutput, normalizeHeatmap };
