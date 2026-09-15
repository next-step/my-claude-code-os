/**
 * 사람이 붙여넣은 쿠팡 링크를 검사하고 상품 형태로 바꾸는 순수 함수.
 *
 * 쿠팡 파트너스 API 키는 누적 판매 15만 원을 넘겨야 나온다(SETUP.md). 그전까지는
 * 사람이 파트너스 사이트에서 링크를 만들어 온다. 이 모듈은 그 링크를 받아
 * `lib/coupang.js` 가 API 에서 만들어 내는 것과 **같은 형태**로 바꾼다. 그래야
 * 뒤쪽 계층(product-pick, publish-meta)이 두 경로를 구분하지 않아도 된다.
 *
 * **가장 중요한 일은 검사다.** 쿠팡이 공개한 계정 정지 사유 다섯 가지 가운데 하나가
 * "비공식 단축 URL" 이다. 사람이 링크를 짧게 만들어 붙여넣으면 계정이 날아간다.
 * 그래서 쿠팡 공식 도메인이 아닌 주소는 받지 않는다.
 */
"use strict";

/** 쿠팡이 만들어 주는 링크의 도메인. 이 밖의 주소는 받지 않는다. */
const 허용도메인 = ["link.coupang.com", "coupang.com", "www.coupang.com"];

/**
 * 흔히 쓰이는 단축 서비스. 여기 걸리면 이유를 분명히 밝히고 거부한다.
 * 목록에 없는 단축 서비스도 허용 도메인 검사에서 함께 걸린다.
 */
const 단축서비스 = ["bit.ly", "tinyurl.com", "buly.kr", "vo.la", "han.gl", "abr.ge", "me2.do", "url.kr", "zrr.kr"];

/**
 * 링크 한 건을 검사한다.
 * @returns {{ok: boolean, url: string|null, reason: string|null}}
 */
function validateLink(raw) {
  const 주소 = String(raw || "").trim();
  if (!주소) return { ok: false, url: null, reason: "주소가 비어 있다" };

  let parsed;
  try {
    parsed = new URL(주소);
  } catch (_) {
    return { ok: false, url: null, reason: "주소 형식이 아니다" };
  }

  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    return { ok: false, url: null, reason: `http(s) 주소가 아니다 (${parsed.protocol})` };
  }

  const host = parsed.hostname.toLowerCase();

  if (단축서비스.some((s) => host === s || host.endsWith(`.${s}`))) {
    return {
      ok: false,
      url: null,
      reason: `단축 URL 은 쓸 수 없다 (${host}). 쿠팡이 공개한 계정 정지 사유 중 하나다 — 파트너스가 만들어 준 주소를 그대로 넣는다`,
    };
  }

  const 허용됨 = 허용도메인.some((d) => host === d || host.endsWith(`.${d}`));
  if (!허용됨) {
    return {
      ok: false,
      url: null,
      reason: `쿠팡 주소가 아니다 (${host}). link.coupang.com 또는 coupang.com 만 받는다`,
    };
  }

  return { ok: true, url: 주소, reason: null };
}

/**
 * 검사를 통과한 링크를 상품 형태로 바꾼다. API 경로가 만드는 것과 같은 모양이다.
 * 사람이 상품명을 적지 않으면 비워 두고, 설명란에는 링크만 나간다.
 */
function toProduct({ url, productName = "", productPrice = null } = {}) {
  const 검사 = validateLink(url);
  if (!검사.ok) throw new Error(검사.reason);

  return {
    productId: null,
    productName: String(productName || "").trim() || "영상 속 상품",
    productPrice: Number.isFinite(productPrice) ? productPrice : null,
    productImage: null,
    productUrl: 검사.url,
    deeplink: 검사.url,
    isRocket: false,
    categoryName: null,
    // 어디서 온 링크인지 남긴다. API 경로와 섞였을 때 구분하기 위해서다.
    source: "manual",
  };
}

/**
 * 링크 모음 파일을 읽어 영상별로 묶는다.
 *
 * 한 줄에 한 건이고 탭으로 나눈다. 사람이 손으로 채우는 파일이라 형식을 최대한 느슨하게
 * 받는다 — 빈 줄, `#` 주석, 앞뒤 공백, 상품명 생략을 모두 허용한다.
 *
 *   영상ID <탭> 링크 <탭> 상품명(생략 가능)
 *
 * @returns {{byVideo: Map<string, Array>, rejected: Array<{line: string, reason: string}>}}
 */
function parseLinkFile(text) {
  const byVideo = new Map();
  const rejected = [];

  for (const 원본줄 of String(text || "").split("\n")) {
    const 줄 = 원본줄.trim();
    if (!줄 || 줄.startsWith("#")) continue;

    // 탭이 없으면 공백으로도 나눠 본다. 사람이 탭 대신 공백을 넣는 일이 흔하다.
    const 조각 = (줄.includes("\t") ? 줄.split("\t") : 줄.split(/\s+/)).map((s) => s.trim()).filter(Boolean);
    if (조각.length < 2) {
      rejected.push({ line: 줄.slice(0, 80), reason: "영상ID 와 링크가 모두 필요하다" });
      continue;
    }

    const [videoId, url, ...나머지] = 조각;
    if (!/^[A-Za-z0-9_-]{11}$/.test(videoId)) {
      rejected.push({ line: 줄.slice(0, 80), reason: `유튜브 영상 ID 형식이 아니다 (${videoId})` });
      continue;
    }

    let product;
    try {
      product = toProduct({ url, productName: 나머지.join(" ") });
    } catch (e) {
      rejected.push({ line: 줄.slice(0, 80), reason: e.message });
      continue;
    }

    if (!byVideo.has(videoId)) byVideo.set(videoId, []);
    byVideo.get(videoId).push(product);
  }

  return { byVideo, rejected };
}

module.exports = { validateLink, toProduct, parseLinkFile, 허용도메인 };
