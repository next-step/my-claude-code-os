/** 실행: node --test ventures/coupang-shorts/tests/coupang.test.js */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  signedDate, buildAuthorization, buildSearchRequest, buildDeeplinkRequest,
  searchProducts, parseSearchResponse, SEARCH_PATH,
} = require("../lib/coupang.js");

/** 새어 나가면 안 되는 값. 테스트가 이 문자열을 어디서든 찾으면 실패한다. */
const SECRET = "coupang_secret_should_never_leak_1234567890";
const ACCESS = "AKIA_TEST_ACCESS";
const 고정시각 = new Date("2026-09-11T04:05:06Z");

test("AC-16: 같은 입력에 항상 같은 서명을 만든다", () => {
  const 인자 = { method: "GET", path: SEARCH_PATH, query: "keyword=a&limit=5", accessKey: ACCESS, secretKey: SECRET, now: 고정시각 };
  const a = buildAuthorization(인자);
  const b = buildAuthorization(인자);

  assert.equal(a.signature, b.signature);
  assert.equal(a.signedDate, "260911T040506Z", "쿠팡은 yyMMddTHHmmssZ 형식의 GMT 시각을 쓴다");
  assert.match(a.authorization, /^CEA algorithm=HmacSHA256, access-key=AKIA_TEST_ACCESS, signed-date=260911T040506Z, signature=[0-9a-f]{64}$/);
});

test("AC-16b: 시각·메서드·경로·쿼리 중 하나만 달라도 서명이 달라진다", () => {
  const 기본 = { method: "GET", path: SEARCH_PATH, query: "keyword=a", accessKey: ACCESS, secretKey: SECRET, now: 고정시각 };
  const 원본 = buildAuthorization(기본).signature;

  const 변형들 = [
    { ...기본, method: "POST" },
    { ...기본, path: "/다른/경로" },
    { ...기본, query: "keyword=b" },
    { ...기본, now: new Date("2026-09-11T04:05:07Z") },
    { ...기본, secretKey: "다른시크릿" },
  ];
  for (const v of 변형들) {
    assert.notEqual(buildAuthorization(v).signature, 원본);
  }
});

test("AC-17: 에러 메시지에 시크릿 키가 새지 않는다", async () => {
  // 네트워크가 예외를 던지고, 그 예외 메시지에 시크릿이 섞여 있는 최악의 경우.
  const 새는fetch = async () => {
    throw new Error(`connect ECONNREFUSED. Authorization: CEA ... secret=${SECRET}`);
  };

  const r = await searchProducts({
    keyword: "에어프라이어", accessKey: ACCESS, secretKey: SECRET, now: 고정시각, fetchImpl: 새는fetch,
  });

  assert.equal(r.ok, false);
  assert.equal(typeof r.error, "string");
  assert.ok(!r.error.includes(SECRET), `시크릿이 에러 메시지에 들어갔다: ${r.error}`);
});

test("AC-17b: 만들어진 요청의 어디에도 시크릿 키가 평문으로 들어가지 않는다", () => {
  const req = buildSearchRequest({ keyword: "에어프라이어", accessKey: ACCESS, secretKey: SECRET, now: 고정시각 });
  const 전부 = JSON.stringify(req);

  assert.ok(!전부.includes(SECRET), "요청 어디에도 시크릿이 있으면 안 된다");
  assert.ok(전부.includes(ACCESS), "액세스 키는 헤더에 들어가는 것이 맞다");

  const dl = buildDeeplinkRequest({ urls: ["https://www.coupang.com/vp/products/1"], accessKey: ACCESS, secretKey: SECRET, now: 고정시각 });
  assert.ok(!JSON.stringify(dl).includes(SECRET));
});

test("AC-18: 검색 응답을 상품 후보 목록으로 파싱한다", () => {
  const 응답 = {
    rCode: "0", rMessage: "",
    data: {
      landingUrl: "https://link.coupang.com/a/ZZZZ",
      productData: [
        { productId: 1, productName: "쿠쿠 에어프라이어 5L", productPrice: 89000, productImage: "https://img/1.jpg", productUrl: "https://link.coupang.com/a/AAAA", isRocket: true, categoryName: "주방가전" },
        { productId: 2, productName: "필립스 에어프라이어", productPrice: 159000, productUrl: "https://link.coupang.com/a/BBBB", isRocket: false },
        { productId: 3, productName: "주소 없는 상품" },
      ],
    },
  };

  const products = parseSearchResponse(응답);
  assert.equal(products.length, 2, "주소가 없는 항목은 링크를 걸 수 없으니 버려야 한다");
  assert.equal(products[0].productName, "쿠쿠 에어프라이어 5L");
  assert.equal(products[0].deeplink, "https://link.coupang.com/a/AAAA", "검색 응답의 productUrl 이 이미 제휴 링크다");
  assert.equal(products[0].isRocket, true);
  assert.equal(products[1].productPrice, 159000);
});

test("AC-18b: 응답이 비었거나 형태가 달라도 예외를 던지지 않는다", () => {
  for (const 응답 of [null, undefined, {}, { data: {} }, { data: { productData: "배열 아님" } }, { data: { productData: [] } }]) {
    assert.deepEqual(parseSearchResponse(응답), []);
  }
});

test("AC-18c: 상태 코드가 실패면 이유를 담아 돌려주고 예외를 던지지 않는다", async () => {
  const 거부하는fetch = async () => ({ ok: false, status: 429, json: async () => ({}) });
  const r = await searchProducts({ keyword: "가전", accessKey: ACCESS, secretKey: SECRET, fetchImpl: 거부하는fetch });

  assert.equal(r.ok, false);
  assert.deepEqual(r.products, []);
  assert.match(r.error, /429/);
});

test("AC-18d: 가짜 응답을 주입하면 네트워크 없이 끝까지 돈다 — API 키를 받기 전의 경로다", async () => {
  const 가짜fetch = async (url, init) => {
    assert.match(url, /products\/search\?keyword=/, "검색 URL 이 만들어져야 한다");
    assert.match(init.headers.Authorization, /^CEA algorithm=HmacSHA256/);
    return { ok: true, status: 200, json: async () => ({ data: { productData: [{ productId: 9, productName: "가짜 상품", productPrice: 1000, productUrl: "https://link.coupang.com/a/FAKE" }] } }) };
  };

  const r = await searchProducts({ keyword: "에어프라이어", accessKey: ACCESS, secretKey: SECRET, now: 고정시각, fetchImpl: 가짜fetch });
  assert.equal(r.ok, true);
  assert.equal(r.products[0].deeplink, "https://link.coupang.com/a/FAKE");
});

test("AC-18e: 자격이 없거나 검색어가 비면 요청을 만들지 않는다", () => {
  assert.throws(() => buildSearchRequest({ keyword: "", accessKey: ACCESS, secretKey: SECRET }), /검색어/);
  assert.throws(() => buildSearchRequest({ keyword: "가전", secretKey: SECRET }), /액세스 키/);
  assert.throws(() => buildSearchRequest({ keyword: "가전", accessKey: ACCESS }), /시크릿 키/);
  assert.throws(() => buildDeeplinkRequest({ urls: [], accessKey: ACCESS, secretKey: SECRET }), /주소/);
});

test("AC-18f: 검색 개수를 1~10 안으로 제한한다 — 쿠팡이 회당 10개까지만 돌려준다", () => {
  assert.match(buildSearchRequest({ keyword: "가전", limit: 999, accessKey: ACCESS, secretKey: SECRET }).url, /limit=10$/);
  assert.match(buildSearchRequest({ keyword: "가전", limit: 0, accessKey: ACCESS, secretKey: SECRET }).url, /limit=1$/);
});

test("AC-18g: signedDate 는 주입받은 시각을 쓴다 — 실제 시계를 쓰면 서명 테스트가 매번 달라진다", () => {
  assert.equal(signedDate(new Date("2026-01-02T03:04:05Z")), "260102T030405Z");
  assert.equal(signedDate(Date.parse("2099-12-31T23:59:59Z")), "991231T235959Z");
});
