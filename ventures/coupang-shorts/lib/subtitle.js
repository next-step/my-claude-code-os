/**
 * 자막을 파싱해 구간에 걸치는 부분만 잘라 내고, 구간 경계를 말이 끊기지 않는 곳으로 옮긴다.
 *
 * 실제 자막을 받아 보고서야 알게 된 것: 유튜브 자동 생성 자막은 평범한 VTT 가 아니라
 * **굴러가는 캡션(rolling caption)** 이다. 세 가지 특징이 있고 전부 다뤄야 한다.
 *
 *  1. 큐마다 바로 앞 줄이 통째로 다시 들어온다. 마지막 줄만 새 내용이다.
 *  2. 큐 사이에 길이 10밀리초짜리 빈 큐가 끼어 있다. 화면을 지우는 용도다.
 *  3. 새 줄에는 `<00:00:01.199><c>단어</c>` 같은 낱말 단위 시각 표시가 박혀 있다.
 *
 * 이것을 모르고 그냥 파싱하면 같은 문장이 세 번씩 찍힌 자막이 나온다.
 * 사람이 직접 단 자막은 이런 구조가 없지만, 마지막 줄만 취하는 방식은 그쪽에서도
 * 그대로 맞으므로 두 경우를 따로 처리하지 않는다.
 */
"use strict";

/** 이보다 짧은 큐는 화면을 지우려고 끼워 넣은 것이다. */
const 최소큐길이초 = 0.05;

/**
 * WebVTT 문자열을 큐 목록으로 바꾼다.
 * @returns {Array<{startSec: number, endSec: number, text: string}>}
 */
function parseVtt(text) {
  const 원본 = String(text || "");
  if (!원본.trim()) return [];

  const cues = [];
  // 빈 줄로 블록을 나눈다. \r\n 도 함께 받는다.
  const blocks = 원본.replace(/\r\n/g, "\n").split(/\n{2,}/);

  for (const block of blocks) {
    const lines = block.split("\n");
    const 시각줄 = lines.findIndex((l) => l.includes("-->"));
    if (시각줄 === -1) continue;

    const 시각 = 시각파싱(lines[시각줄]);
    if (!시각) continue;
    if (시각.endSec - 시각.startSec < 최소큐길이초) continue;

    // 마지막 줄만 새 내용이다. 앞 줄들은 직전 큐에서 굴러 온 것이다.
    const 내용줄 = lines.slice(시각줄 + 1).map(태그제거).filter((l) => l.length > 0);
    if (내용줄.length === 0) continue;

    const text = 내용줄[내용줄.length - 1];
    if (!text) continue;

    // 바로 앞 큐와 내용이 같으면 버린다. 굴러가는 캡션에서 흔히 생긴다.
    const 직전 = cues[cues.length - 1];
    if (직전 && 직전.text === text) {
      직전.endSec = Math.max(직전.endSec, 시각.endSec);
      continue;
    }

    cues.push({ startSec: 시각.startSec, endSec: 시각.endSec, text });
  }

  return cues;
}

/** `00:00:02.110 --> 00:00:04.390 align:start position:0%` 를 초로 바꾼다. */
function 시각파싱(line) {
  const m = line.match(
    /(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})/
  );
  if (!m) return null;
  const 초 = (h, mi, s, ms) => Number(h) * 3600 + Number(mi) * 60 + Number(s) + Number(ms.padEnd(3, "0")) / 1000;
  const startSec = 초(m[1], m[2], m[3], m[4]);
  const endSec = 초(m[5], m[6], m[7], m[8]);
  if (!(endSec > startSec)) return null;
  return { startSec, endSec };
}

/** `<00:00:01.199>`, `<c>`, `</c>` 같은 표시를 걷어 낸다. */
function 태그제거(line) {
  return String(line)
    .replace(/<[^>]*>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * 구간에 걸치는 큐만 남기고 시작 시각을 0부터 다시 매긴다.
 *
 * 렌더할 때 원본에서 구간만 잘라 내므로, 잘린 영상의 시간축에 맞춰야 자막이 맞는다.
 */
function sliceCues(cues, startSec, endSec) {
  const out = [];
  for (const c of cues) {
    if (c.endSec <= startSec || c.startSec >= endSec) continue;
    const s = Math.max(c.startSec, startSec) - startSec;
    const e = Math.min(c.endSec, endSec) - startSec;
    if (e - s < 0.1) continue;
    out.push({ startSec: round3(s), endSec: round3(e), text: c.text });
  }
  return out;
}

/**
 * 구간 경계를 가장 가까운 자막 경계로 옮긴다. 말이 중간에서 잘리는 것을 막기 위해서다.
 *
 * 허용 범위 밖이면 옮기지 않는다. 억지로 맞추면 구간이 엉뚱한 곳으로 끌려간다.
 *
 * 옮긴 결과가 길이 제약을 깨면 되돌린다. 실제로 돌려 보니 2위 구간이 14.95초가 되어
 * 최소 길이 15초를 밑돌았다 — `segment.js` 가 지킨 제약을 여기서 깨뜨린 것이다.
 *
 * @param {object} [limits] `{ minSec, maxSec }`. 주지 않으면 길이를 검사하지 않는다
 * @returns {{startSec, endSec, snappedStart: boolean, snappedEnd: boolean}}
 */
function snapToCues(segment, cues, toleranceSec = 3, limits = {}) {
  if (!segment || !Number.isFinite(segment.startSec) || !Number.isFinite(segment.endSec)) {
    throw new Error("segment 에 startSec 과 endSec 이 필요하다");
  }
  if (!Array.isArray(cues) || cues.length === 0) {
    return { ...segment, snappedStart: false, snappedEnd: false };
  }

  const 시작후보 = 가장가까운값(cues.map((c) => c.startSec), segment.startSec, toleranceSec);
  const 끝후보 = 가장가까운값(cues.map((c) => c.endSec), segment.endSec, toleranceSec);

  const startSec = 시작후보 === null ? segment.startSec : 시작후보;
  const endSec = 끝후보 === null ? segment.endSec : 끝후보;

  // 옮기다가 구간이 뒤집히거나 길이 제약을 깨면 옮기지 않은 것으로 되돌린다.
  const 길이 = endSec - startSec;
  const 너무짧음 = Number.isFinite(limits.minSec) && 길이 < limits.minSec;
  const 너무김 = Number.isFinite(limits.maxSec) && 길이 > limits.maxSec;

  if (endSec <= startSec || 너무짧음 || 너무김) {
    return { ...segment, snappedStart: false, snappedEnd: false };
  }

  return {
    ...segment,
    startSec: round3(startSec),
    endSec: round3(endSec),
    durationSec: round3(endSec - startSec),
    snappedStart: 시작후보 !== null,
    snappedEnd: 끝후보 !== null,
  };
}

function 가장가까운값(values, target, tolerance) {
  let best = null;
  let bestDist = Infinity;
  for (const v of values) {
    const d = Math.abs(v - target);
    if (d <= tolerance && d < bestDist) {
      bestDist = d;
      best = v;
    }
  }
  return best;
}

/** 큐 목록을 SRT 문자열로 만든다. ffmpeg 의 subtitles 필터가 읽는 형식이다. */
function toSrt(cues) {
  return cues
    .map((c, i) => `${i + 1}\n${srt시각(c.startSec)} --> ${srt시각(c.endSec)}\n${c.text}\n`)
    .join("\n");
}

function srt시각(sec) {
  const total = Math.max(0, sec);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = Math.floor(total % 60);
  const ms = Math.round((total - Math.floor(total)) * 1000);
  const p = (n, w = 2) => String(n).padStart(w, "0");
  return `${p(h)}:${p(m)}:${p(s)},${p(ms, 3)}`;
}

function round3(n) {
  return Math.round(n * 1000) / 1000;
}

module.exports = { parseVtt, sliceCues, snapToCues, toSrt };
