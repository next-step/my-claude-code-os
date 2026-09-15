/**
 * 업로드용 제목·설명·해시태그를 만드는 순수 함수.
 *
 * 이 모듈에는 **빠지면 안 되는 문구가 두 개** 있다.
 *
 *  1. 제휴 고지 문구. 공정거래위원회 「추천·보증 등에 관한 표시·광고 심사지침」에 따라
 *     대가를 받은 추천에는 경제적 이해관계를 표시해야 한다. 빠뜨리면 법 위반이고,
 *     쿠팡 파트너스 최종 승인 심사에서도 이 문구가 보이는 화면을 요구한다.
 *  2. 원본 출처 표기. 저작권 문제를 없애 주지는 못하지만, 원저작자를 밝히지 않는 것보다
 *     밝히는 편이 분쟁에서 불리함을 덜고 재사용 정책 심사에서도 낫다.
 *
 * 그래서 설명이 길이 상한에 걸리면 **다른 것을 먼저 줄이고 이 둘은 마지막까지 남긴다.**
 * 간결하게 만들려다 고지를 떨어뜨리는 것이 이 모듈이 망가지는 방식이다.
 */
"use strict";

const { buildShortsTitle } = require("./shorts-title.js");

/** 공정위 심사지침이 요구하는 경제적 이해관계 표시. 문구를 임의로 줄이지 않는다. */
const DISCLOSURE =
  "이 게시물은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.";

const LIMITS = Object.freeze({
  /** 유튜브 제목 상한 */
  titleChars: 100,
  /** 유튜브 설명 상한 */
  descriptionChars: 5000,
  /** 해시태그는 3개를 넘기면 유튜브가 전부 무시한다 */
  maxHashtags: 3,
});

/**
 * @param {object} p
 * @param {string} p.videoTitle 원본 영상 제목
 * @param {string} p.channelTitle 원본 채널명
 * @param {string} p.videoId 원본 영상 ID
 * @param {string[]} [p.keywords] 상품 검색어
 * @param {Array<{productName: string, deeplink: string}>} [p.products] 쿠팡 상품. 비면 자리만 비워 둔다
 * @returns {{title: string, description: string, hashtags: string[], attribution: string, disclosure: string, truncated: boolean}}
 */
function buildPublishMeta(p = {}) {
  const videoTitle = String(p.videoTitle || "").trim();
  const channelTitle = String(p.channelTitle || "").trim();
  const videoId = String(p.videoId || "").trim();

  if (!videoId) throw new Error("videoId 가 필요하다");
  if (!channelTitle) throw new Error("channelTitle 이 필요하다 — 출처 표기에 쓰인다");

  const keywords = Array.isArray(p.keywords) ? p.keywords.filter(Boolean) : [];
  const products = Array.isArray(p.products) ? p.products.filter((x) => x && x.deeplink) : [];

  const attribution = `원본 영상: ${channelTitle}\nhttps://youtu.be/${videoId}`;
  const hashtags = 해시태그(keywords);

  // 원본 제목을 그대로 자르지 않는다. 유튜브 긴 영상용 제목은 검색 노출을 노린 키워드
  // 나열이라 쇼츠에서는 잘리고 훅도 죽는다. shorts-title.js 가 훅만 뽑아 낸다.
  const { title, hook, source: titleSource } = buildShortsTitle(
    { videoTitle, keywords },
    { maxChars: LIMITS.titleChars }
  );

  // 설명은 우선순위가 낮은 것부터 버릴 수 있도록 블록으로 나눠 조립한다.
  const 상품블록 = products.length
    ? ["🛒 영상 속 상품", ...products.map((x) => `· ${x.productName}\n  ${x.deeplink}`)].join("\n")
    : "🛒 영상 속 상품\n· (링크를 여기에 넣어 주세요)";

  // **고지가 맨 앞이다.** 유튜브는 설명 첫 몇 줄만 보여 주고 나머지를 "더보기" 뒤로
  // 숨긴다. 쿠팡 가이드는 "'자세히 보기' 와 같이 추가적으로 클릭이 필요한 경우는
  // 적절한 표기 방식이 아닙니다" 라고 못박는다. 상품 링크를 먼저 두면 고지가 가려진다.
  const 필수 = [DISCLOSURE, 상품블록, attribution];
  const 선택 = [hashtags.join(" ")].filter((s) => s.length > 0);

  let description = [...필수, ...선택].join("\n\n");
  let truncated = false;

  if (description.length > LIMITS.descriptionChars) {
    // 선택 블록부터 버린다. 그래도 넘치면 상품 목록을 줄인다. 고지와 출처는 건드리지 않는다.
    description = 필수.join("\n\n");
    truncated = true;

    if (description.length > LIMITS.descriptionChars) {
      const 남는길이 =
        LIMITS.descriptionChars - (DISCLOSURE.length + attribution.length + "\n\n\n\n".length);
      description = [DISCLOSURE, 상품블록.slice(0, Math.max(0, 남는길이)), attribution].join("\n\n");
    }
  }

  return { title, titleHook: hook, titleSource, description, hashtags, attribution, disclosure: DISCLOSURE, truncated };
}

/** 검색어를 해시태그로 바꾼다. 공백과 특수문자를 빼야 유튜브가 태그로 인식한다. */
function 해시태그(keywords) {
  const seen = new Set();
  const out = [];
  for (const k of keywords) {
    const cleaned = String(k).replace(/[^0-9A-Za-z가-힣]/g, "");
    if (!cleaned || seen.has(cleaned)) continue;
    seen.add(cleaned);
    out.push(`#${cleaned}`);
    if (out.length >= LIMITS.maxHashtags) break;
  }
  return out;
}

module.exports = { buildPublishMeta, DISCLOSURE, LIMITS };
