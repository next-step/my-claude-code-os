/**
 * 검색 결과를 쇼츠 소재 후보 목록으로 거르고 점수를 매기는 순수 함수.
 *
 * 계획에는 `trending.js` 로 적혀 있었으나 이름과 역할을 바꿨다. 유튜브가 2025-07-21 에
 * 인기 급상승 페이지를 폐지했고 공식 API 의 `chart=mostPopular` 가 음악·영화·게임
 * 차트만 돌려주게 되어, 상품이 등장하는 영상을 거기서 찾을 수 없기 때문이다.
 * 대신 상품군 키워드로 검색해 조회수와 업로드 시점으로 거른다.
 *
 * 이 모듈은 **무엇을 자를지 정하지 않는다.** 어떤 영상을 들여다볼 가치가 있는지만
 * 판정하고, 실제 구간 선택은 `segment.js` 의 몫이다.
 */
"use strict";

const { FIELD_SEP } = require("./ytdlp-cmd.js");

const DEFAULTS = Object.freeze({
  /** 히트맵이 의미를 가지려면 어느 정도 길어야 한다. 3분 미만은 잘라 낼 여지가 없다. */
  minDurationSec: 180,
  /** 너무 길면 내려받기와 분석이 비싸지고, 구간 하나가 전체를 대표하지 못한다. */
  maxDurationSec: 3600,
  /** 조회수가 적으면 유튜브가 히트맵 자체를 만들어 주지 않는다. */
  minViewCount: 50000,
  /** 너무 오래된 영상은 이미 쇼츠로 잘려 돌아다닌다. */
  maxAgeDays: 365,
  /** 오늘 날짜. 주입받아야 내일 깨지는 테스트가 되지 않는다. */
  today: null,
});

/**
 * 제목에 들어가면 상품이 등장할 가능성이 높은 말들. 가중치를 함께 둔다.
 * 완벽한 분류기가 아니라 정렬을 위한 어림값이다 — 최종 판단은 사람이 한다.
 */
const 신호어 = Object.freeze([
  { 말: ["리뷰", "후기", "review"], 점수: 0.3 },
  { 말: ["추천", "베스트", "top", "순위"], 점수: 0.25 },
  { 말: ["비교", "vs", "대결", "테스트"], 점수: 0.25 },
  { 말: ["언박싱", "개봉", "unboxing"], 점수: 0.3 },
  { 말: ["가성비", "실사용", "직접 써", "내돈내산"], 점수: 0.3 },
  { 말: ["구매", "구입", "쇼핑", "득템"], 점수: 0.15 },
]);

/** 상품과 연결하기 어려워 거르는 말들. */
const 제외어 = Object.freeze(["브이로그", "vlog", "먹방 실시간", "라이브", "live", "쇼츠", "shorts", "노래", "커버"]);

/**
 * yt-dlp `--print` 출력을 후보 목록으로 바꾼다.
 *
 * @param {string} stdout 탭으로 구분된 줄들
 * @param {object} [options]
 * @returns {{candidates: Array, rejected: Array}}
 */
function parseSearchOutput(stdout, options = {}) {
  const o = { ...DEFAULTS, ...options };
  const today = o.today ? new Date(o.today) : new Date();

  const candidates = [];
  const rejected = [];

  const lines = String(stdout || "").split("\n");
  for (const line of lines) {
    if (!line.trim()) continue;
    const row = 줄파싱(line);
    if (!row) {
      rejected.push({ line: line.slice(0, 80), reason: "형식이 맞지 않는다" });
      continue;
    }

    const 판정 = 거르기(row, o, today);
    if (판정) {
      rejected.push({ videoId: row.videoId, title: row.title, reason: 판정 });
      continue;
    }

    const { productScore, reasons } = 점수매기기(row);
    candidates.push({ ...row, productScore, reasons });
  }

  // 상품 가능성이 높은 순, 같으면 조회수가 많은 순. 동점이면 ID 순으로 고정한다.
  candidates.sort(
    (a, b) =>
      b.productScore - a.productScore ||
      b.viewCount - a.viewCount ||
      a.videoId.localeCompare(b.videoId)
  );

  return { candidates, rejected };
}

function 줄파싱(line) {
  const parts = line.split(FIELD_SEP);
  if (parts.length < 6) return null;

  const [id, duration, viewCount, channel, uploadDate, ...rest] = parts;
  if (!/^[A-Za-z0-9_-]{11}$/.test(id)) return null;

  const durationSec = 숫자(duration);
  if (durationSec === null) return null;

  return {
    videoId: id,
    durationSec,
    // 조회수가 비공개면 yt-dlp 가 "NA" 를 준다. 0 으로 두고 하한에서 걸리게 한다.
    viewCount: 숫자(viewCount) ?? 0,
    channelTitle: channel === "NA" ? "" : channel,
    uploadDate: /^\d{8}$/.test(uploadDate) ? uploadDate : null,
    // 제목에 탭이 들어간 희귀한 경우를 대비해 나머지를 다시 붙인다.
    title: rest.join(FIELD_SEP).trim(),
  };
}

/** 거를 이유를 돌려준다. 없으면 null. */
function 거르기(row, o, today) {
  if (row.durationSec < o.minDurationSec) return `너무 짧다 (${row.durationSec}초)`;
  if (row.durationSec > o.maxDurationSec) return `너무 길다 (${row.durationSec}초)`;
  if (row.viewCount < o.minViewCount) return `조회수가 적어 히트맵이 없을 가능성이 높다 (${row.viewCount})`;
  if (!row.channelTitle) return "채널명을 알 수 없어 출처를 표기할 수 없다";

  const 나이 = 지난날수(row.uploadDate, today);
  if (나이 !== null && 나이 > o.maxAgeDays) return `너무 오래됐다 (${나이}일)`;

  const 소문자 = row.title.toLowerCase();
  const 걸린제외어 = 제외어.find((w) => 소문자.includes(w.toLowerCase()));
  if (걸린제외어) return `상품과 연결하기 어려운 유형이다 ("${걸린제외어}")`;

  return null;
}

function 점수매기기(row) {
  const 소문자 = row.title.toLowerCase();
  let score = 0;
  const reasons = [];

  for (const { 말, 점수 } of 신호어) {
    const 걸린말 = 말.find((w) => 소문자.includes(w.toLowerCase()));
    if (걸린말) {
      score += 점수;
      reasons.push(`제목에 "${걸린말}"`);
    }
  }

  // 조회수가 아주 많으면 히트맵이 촘촘하고 구간도 뚜렷하다.
  if (row.viewCount >= 1000000) {
    score += 0.2;
    reasons.push("조회수 100만 이상");
  } else if (row.viewCount >= 300000) {
    score += 0.1;
    reasons.push("조회수 30만 이상");
  }

  return { productScore: Math.round(Math.min(1, score) * 100) / 100, reasons };
}

function 지난날수(uploadDate, today) {
  if (!uploadDate) return null;
  const y = Number(uploadDate.slice(0, 4));
  const m = Number(uploadDate.slice(4, 6));
  const d = Number(uploadDate.slice(6, 8));
  const then = Date.UTC(y, m - 1, d);
  const now = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  return Math.floor((now - then) / 86400000);
}

function 숫자(v) {
  if (v === "NA" || v === "" || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

module.exports = { parseSearchOutput, DEFAULTS };
