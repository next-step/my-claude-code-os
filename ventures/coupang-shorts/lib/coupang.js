/**
 * 쿠팡 파트너스 API 연동. 서명 생성과 응답 파싱만 하고, **네트워크는 주입받는다.**
 *
 * `fetchImpl` 을 주입받는 것은 `.claude/lib/notion-min.js:286` 과 같은 관례다.
 * 테스트가 네트워크를 타지 않아야 하고, 무엇보다 지금은 API 키 자체가 없다.
 * 쿠팡 파트너스 API 키는 누적 판매 15만 원을 넘겨 최종 승인을 받아야 발급되므로
 * (SETUP.md 참고) 당분간은 가짜 응답을 주입해 돌린다. 키가 생기면 주입만 바꾼다.
 *
 * 서명 방식은 쿠팡 공식 문서와 공개된 구현 예제 두 곳에서 확인했다.
 *   message   = signed-date + HTTP 메서드 + 경로 + 쿼리스트링(물음표 제외)
 *   signature = HMAC-SHA256(시크릿 키, message) 를 16진수로
 *   헤더       = CEA algorithm=HmacSHA256, access-key=..., signed-date=..., signature=...
 *   signed-date = yyMMddTHHmmssZ 형식의 GMT 시각
 *
 * **시크릿 키는 이 모듈 밖으로 절대 나가지 않는다.** 에러 메시지에 요청 정보를 담을
 * 때 키가 섞여 나가는 사고가 흔해서, 그 성질을 테스트로 고정해 두었다.
 */
"use strict";

const crypto = require("node:crypto");

const DOMAIN = "https://api-gateway.coupang.com";
const BASE_PATH = "/v2/providers/affiliate_open_api/apis/openapi";
const SEARCH_PATH = `${BASE_PATH}/products/search`;
const DEEPLINK_PATH = `${BASE_PATH}/deeplink`;

/** 쿠팡 검색 API 가 한 번에 돌려주는 최대 개수. */
const MAX_LIMIT = 10;

/**
 * `yyMMddTHHmmssZ` 형식의 GMT 시각.
 * @param {Date|number} [now] 주입받는다. 실제 시계를 쓰면 테스트가 매번 달라진다.
 */
function signedDate(now = Date.now()) {
  const d = now instanceof Date ? now : new Date(now);
  const p = (n) => String(n).padStart(2, "0");
  return (
    `${p(d.getUTCFullYear() % 100)}${p(d.getUTCMonth() + 1)}${p(d.getUTCDate())}` +
    `T${p(d.getUTCHours())}${p(d.getUTCMinutes())}${p(d.getUTCSeconds())}Z`
  );
}

/**
 * Authorization 헤더 값을 만든다.
 * @param {object} p
 * @param {string} p.method HTTP 메서드 (대문자)
 * @param {string} p.path 경로. 쿼리스트링을 포함하지 않는다
 * @param {string} [p.query] 쿼리스트링. 물음표를 포함하지 않는다
 * @param {string} p.accessKey
 * @param {string} p.secretKey
 * @param {Date|number} [p.now]
 */
function buildAuthorization({ method, path, query = "", accessKey, secretKey, now }) {
  if (!method || !path) throw new Error("method 와 path 가 필요하다");
  if (!accessKey) throw new Error("쿠팡 액세스 키가 없다");
  if (!secretKey) throw new Error("쿠팡 시크릿 키가 없다");

  const datetime = signedDate(now);
  const message = datetime + method.toUpperCase() + path + query;
  const signature = crypto.createHmac("sha256", secretKey).update(message).digest("hex");

  return {
    authorization: `CEA algorithm=HmacSHA256, access-key=${accessKey}, signed-date=${datetime}, signature=${signature}`,
    signedDate: datetime,
    signature,
  };
}

/** 검색 요청 한 건의 URL·헤더를 만든다. 실제로 보내지는 않는다. */
function buildSearchRequest({ keyword, limit = MAX_LIMIT, accessKey, secretKey, now }) {
  const 말 = String(keyword || "").trim();
  if (!말) throw new Error("검색어가 필요하다");

  const n = Math.max(1, Math.min(MAX_LIMIT, Math.floor(limit)));
  const query = `keyword=${encodeURIComponent(말)}&limit=${n}`;
  const { authorization } = buildAuthorization({
    method: "GET", path: SEARCH_PATH, query, accessKey, secretKey, now,
  });

  return {
    url: `${DOMAIN}${SEARCH_PATH}?${query}`,
    method: "GET",
    headers: { Authorization: authorization, "Content-Type": "application/json;charset=UTF-8" },
  };
}

/** 딥링크 생성 요청을 만든다. 이미 알고 있는 상품 주소를 제휴 링크로 바꾼다. */
function buildDeeplinkRequest({ urls, accessKey, secretKey, now }) {
  const 목록 = (Array.isArray(urls) ? urls : [urls]).filter(Boolean).map(String);
  if (목록.length === 0) throw new Error("변환할 주소가 필요하다");

  const { authorization } = buildAuthorization({
    method: "POST", path: DEEPLINK_PATH, accessKey, secretKey, now,
  });

  return {
    url: `${DOMAIN}${DEEPLINK_PATH}`,
    method: "POST",
    headers: { Authorization: authorization, "Content-Type": "application/json;charset=UTF-8" },
    body: JSON.stringify({ coupangUrls: 목록 }),
  };
}

/**
 * 검색을 실제로 보낸다. `fetchImpl` 을 주입받아 테스트에서는 네트워크를 타지 않는다.
 * @returns {{ok: boolean, products: Array, error: string|null}}
 */
async function searchProducts({ keyword, limit, accessKey, secretKey, now, fetchImpl }) {
  const req = buildSearchRequest({ keyword, limit, accessKey, secretKey, now });
  const doFetch = fetchImpl || globalThis.fetch;

  let res;
  try {
    res = await doFetch(req.url, { method: req.method, headers: req.headers });
  } catch (e) {
    // 예외 메시지를 그대로 흘리지 않는다. 네트워크 계층이 요청 헤더를 통째로 에러에
    // 담는 일이 있고, 거기에는 시크릿에서 파생된 서명이 들어 있다.
    return {
      ok: false,
      products: [],
      error: `쿠팡 검색 요청이 실패했다: ${안전한오류(e, [secretKey, accessKey, 서명뽑기(req)])}`,
    };
  }

  if (!res || !res.ok) {
    const status = res ? res.status : "응답 없음";
    return { ok: false, products: [], error: `쿠팡 검색이 거부됐다 (상태 ${status})` };
  }

  let json;
  try {
    json = await res.json();
  } catch (_) {
    return { ok: false, products: [], error: "쿠팡 응답이 JSON 이 아니다" };
  }

  return { ok: true, products: parseSearchResponse(json), error: null };
}

/** 쿠팡 검색 응답에서 필요한 항목만 뽑는다. */
function parseSearchResponse(json) {
  const rows = json && json.data && Array.isArray(json.data.productData) ? json.data.productData : [];
  const out = [];
  for (const r of rows) {
    if (!r || !r.productUrl) continue;
    out.push({
      productId: r.productId ?? null,
      productName: String(r.productName || "").trim(),
      productPrice: Number.isFinite(r.productPrice) ? r.productPrice : null,
      productImage: r.productImage || null,
      productUrl: r.productUrl,
      // 검색 응답의 productUrl 은 이미 제휴 추적이 붙은 주소다. 별도 딥링크 변환이 필요 없다.
      deeplink: r.productUrl,
      isRocket: Boolean(r.isRocket),
      categoryName: r.categoryName || null,
    });
  }
  return out;
}

/**
 * 예외 메시지에서 비밀값을 지운다.
 *
 * 길이를 자르는 것만으로는 부족하다. 실제로 테스트가 잡아낸 결함이다 — 200자 안에
 * 시크릿이 들어 있으면 그대로 새어 나갔다. 아는 비밀값을 하나하나 지운 뒤에 자른다.
 */
function 안전한오류(e, secrets = []) {
  let msg = e && typeof e.message === "string" ? e.message : String(e);
  for (const s of secrets) {
    if (typeof s === "string" && s.length >= 8) {
      msg = msg.split(s).join("***");
    }
  }
  return msg.slice(0, 200);
}

/** 요청 헤더에서 서명 부분만 꺼낸다. 시크릿에서 파생된 값이라 함께 지운다. */
function 서명뽑기(req) {
  const auth = req && req.headers && req.headers.Authorization;
  if (typeof auth !== "string") return "";
  const m = auth.match(/signature=([0-9a-f]+)/);
  return m ? m[1] : "";
}

module.exports = {
  signedDate,
  buildAuthorization,
  buildSearchRequest,
  buildDeeplinkRequest,
  searchProducts,
  parseSearchResponse,
  DOMAIN,
  SEARCH_PATH,
  DEEPLINK_PATH,
  MAX_LIMIT,
};
