/**
 * 쿠팡이 돌려준 상품 후보 중 영상에 가장 맞는 것을 고르는 순수 함수.
 *
 * 왜 필요한가: 쿠팡 검색 API 는 **정렬도 가격 필터도 지원하지 않는다.** 최대 10개를
 * 순서 없이 던져 줄 뿐이라, 무엇이 이 영상과 맞는지는 전부 이쪽에서 판단해야 한다.
 * 지금까지는 판단 없이 앞에서부터 잘랐다.
 *
 * 가장 강한 신호는 **자막에 실제로 나온 제품명**이다. 영상이 "필립스 NA230" 을
 * 소개했다면 그 상품을 골라야 한다. 검색어만 보면 "에어프라이어" 로 아무거나 걸린다.
 * 우리는 이미 자막을 가지고 있으므로 이 신호를 공짜로 쓸 수 있다.
 *
 * 이 모듈은 API 경로와 사람이 링크를 붙여넣는 경로 양쪽에서 쓰인다. 후보가 하나뿐이면
 * 그대로 통과시키되 점수와 이유는 똑같이 남긴다 — 나중에 기준을 다듬을 근거가 된다.
 */
"use strict";

const DEFAULTS = Object.freeze({
  /** 설명란에 넣을 최대 개수 */
  max: 2,
  /** 자막·제목에 나온 말이 상품명에도 있을 때의 가중치. 가장 강한 신호다. */
  mentionWeight: 3,
  /** 검색어가 상품명에 온전히 들어있을 때 */
  keywordWeight: 2,
  /** 로켓배송 */
  rocketWeight: 1,
  /** 가격이 후보 중앙값에서 크게 벗어날 때의 감점 */
  priceOutlierPenalty: 2,
  /** 중앙값의 몇 배 밖을 벗어난 것으로 볼지 */
  priceLowRatio: 0.25,
  priceHighRatio: 4,
  /** 이 길이 미만의 말은 우연히 겹치므로 언급 신호로 세지 않는다. */
  minMentionLength: 2,
});

/**
 * @param {object} p
 * @param {Array} p.candidates 쿠팡 상품 후보. `lib/coupang.js` 의 parseSearchResponse 형태
 * @param {string} [p.videoTitle] 원본 영상 제목
 * @param {string} [p.subtitleText] 구간 자막을 이어 붙인 글
 * @param {Array<{word: string, score: number}>} [p.keywords] `lib/keyword.js` 의 scored
 * @param {object} [options]
 * @returns {{picked: Array, ranked: Array, skipped: string|null}}
 */
function pickProducts(p = {}, options = {}) {
  const o = { ...DEFAULTS, ...options };

  const candidates = (Array.isArray(p.candidates) ? p.candidates : []).filter(
    (c) => c && c.deeplink && String(c.productName || "").trim()
  );

  if (candidates.length === 0) {
    return { picked: [], ranked: [], skipped: "고를 상품 후보가 없다" };
  }

  // 영상이 실제로 말한 낱말들. 제목과 자막을 합쳐 본다.
  const 영상말 = 토큰집합(`${p.videoTitle || ""} ${p.subtitleText || ""}`, o.minMentionLength);

  // 검색어별 점수. 어떤 검색어로 찾아낸 상품인지에 따라 신뢰도가 다르다.
  const 검색어점수 = new Map();
  for (const k of Array.isArray(p.keywords) ? p.keywords : []) {
    if (k && k.word) 검색어점수.set(String(k.word), Number(k.score) || 1);
  }

  const 중앙값 = 가격중앙값(candidates);

  const ranked = candidates
    .map((c) => {
      const { score, reasons } = 점수(c, { 영상말, 검색어점수, 중앙값, o });
      return { ...c, matchScore: Math.round(score * 100) / 100, matchReasons: reasons };
    })
    // 점수 내림차순. 동점이면 로켓배송, 그다음 상품명 순으로 고정한다 — 결정론 유지.
    .sort(
      (a, b) =>
        b.matchScore - a.matchScore ||
        Number(b.isRocket) - Number(a.isRocket) ||
        String(a.productName).localeCompare(String(b.productName))
    );

  // 같은 상품이 여러 검색어에서 중복으로 들어올 수 있다.
  const 본것 = new Set();
  const picked = [];
  for (const c of ranked) {
    const 키 = c.productId != null ? `id:${c.productId}` : `url:${c.productUrl}`;
    if (본것.has(키)) continue;
    본것.add(키);
    picked.push(c);
    if (picked.length >= o.max) break;
  }

  return { picked, ranked, skipped: null };
}

function 점수(c, { 영상말, 검색어점수, 중앙값, o }) {
  const 상품명 = String(c.productName || "");
  const 상품말 = 토큰집합(상품명, o.minMentionLength);
  let score = 0;
  const reasons = [];

  // 1. 영상이 실제로 말한 낱말이 상품명에도 있는가. 가장 강한 신호다.
  const 겹친말 = [...상품말].filter((w) => 영상말.has(w));
  if (겹친말.length > 0) {
    score += o.mentionWeight * Math.min(3, 겹친말.length);
    reasons.push(`영상에 나온 말 ${겹친말.slice(0, 3).join("·")}`);
  }

  // 2. 이 상품을 찾아낸 검색어가 상품명에 온전히 들어있는가.
  const 출처 = c.sourceKeyword ? String(c.sourceKeyword) : "";
  if (출처 && 상품명.replace(/\s/g, "").includes(출처.replace(/\s/g, ""))) {
    score += o.keywordWeight;
    reasons.push(`검색어 "${출처}" 가 상품명에 있음`);
  }

  // 3. 로켓배송.
  if (c.isRocket) {
    score += o.rocketWeight;
    reasons.push("로켓배송");
  }

  // 4. 가격이 후보들에서 크게 벗어나면 깎는다. 부속품이나 묶음 상품을 거르기 위해서다.
  if (중앙값 !== null && Number.isFinite(c.productPrice) && c.productPrice > 0) {
    const 비율 = c.productPrice / 중앙값;
    if (비율 < o.priceLowRatio) {
      score -= o.priceOutlierPenalty;
      reasons.push(`다른 후보보다 지나치게 쌈 (${Math.round(비율 * 100)}%)`);
    } else if (비율 > o.priceHighRatio) {
      score -= o.priceOutlierPenalty;
      reasons.push(`다른 후보보다 지나치게 비쌈 (${Math.round(비율 * 100)}%)`);
    }
  }

  // 5. 검색어 자체의 신뢰도를 곱한다. 근거가 약한 검색어로 찾은 상품은 덜 믿는다.
  const 배수 = 출처 && 검색어점수.has(출처) ? Math.min(2, Math.max(0.5, 검색어점수.get(출처) / 2)) : 1;
  if (배수 !== 1) {
    score *= 배수;
    reasons.push(`검색어 신뢰도 ×${Math.round(배수 * 100) / 100}`);
  }

  return { score, reasons };
}

/** 후보 가격의 중앙값. 값이 없으면 null. */
function 가격중앙값(candidates) {
  const 값들 = candidates
    .map((c) => c.productPrice)
    .filter((v) => Number.isFinite(v) && v > 0)
    .sort((a, b) => a - b);
  if (값들.length === 0) return null;
  const 가운데 = Math.floor(값들.length / 2);
  return 값들.length % 2 === 1 ? 값들[가운데] : (값들[가운데 - 1] + 값들[가운데]) / 2;
}

/**
 * 글에서 낱말 집합을 만든다.
 *
 * 형태소 분석기가 없으므로 공백과 기호로만 끊는다. 그래서 "필립스" 처럼 독립된 낱말은
 * 잘 잡지만 "에어프라이어용" 같은 붙은 말은 놓친다. `keyword.js` 와 같은 한계다.
 */
function 토큰집합(text, minLength) {
  const out = new Set();
  for (const 말 of String(text).replace(/[^0-9A-Za-z가-힣]/g, " ").split(/\s+/)) {
    if (말.length >= minLength) out.add(말.toLowerCase());
  }
  return out;
}

module.exports = { pickProducts, DEFAULTS };
