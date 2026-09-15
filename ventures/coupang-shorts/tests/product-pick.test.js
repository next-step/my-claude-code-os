/** 실행: node --test ventures/coupang-shorts/tests/product-pick.test.js */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { pickProducts } = require("../lib/product-pick.js");

/** 실제 쿠팡 검색 결과에서 흔히 나오는 형태를 흉내 낸 후보들이다. */
function 후보들() {
  return [
    { productId: 1, productName: "쿠쿠 에어프라이어 5L 소형", productPrice: 89000, deeplink: "a", productUrl: "a", isRocket: true, sourceKeyword: "에어프라이어" },
    { productId: 2, productName: "필립스 에어프라이어 NA230 6.2L", productPrice: 159000, deeplink: "b", productUrl: "b", isRocket: true, sourceKeyword: "에어프라이어" },
    { productId: 3, productName: "에어프라이어 전용 종이호일 100매", productPrice: 3900, deeplink: "c", productUrl: "c", isRocket: true, sourceKeyword: "에어프라이어" },
    { productId: 4, productName: "업소용 대형 에어프라이어 20L", productPrice: 890000, deeplink: "d", productUrl: "d", isRocket: false, sourceKeyword: "에어프라이어" },
  ];
}

test("AC-44: 자막에 나온 제품명이 상품명에 있으면 가장 앞에 온다", () => {
  const { picked, ranked } = pickProducts({
    candidates: 후보들(),
    videoTitle: "에어프라이어 비교",
    subtitleText: "먼저 필립스 NA230입니다 넉넉한 용량과 성능",
  });

  assert.match(picked[0].productName, /필립스/, `자막이 말한 제품이 1위여야 한다: ${picked[0].productName}`);
  assert.ok(ranked[0].matchReasons.some((r) => r.includes("필립스")), "이유에 근거가 남아야 한다");
});

test("AC-44b: 자막 신호가 없으면 다른 기준으로 고른다", () => {
  const { picked } = pickProducts({ candidates: 후보들(), videoTitle: "", subtitleText: "" });
  assert.ok(picked.length > 0, "자막이 없어도 골라야 한다");
  // 부속품과 극단적으로 비싼 것은 뒤로 밀려야 한다.
  assert.doesNotMatch(picked[0].productName, /종이호일/);
});

test("AC-45: 부속품처럼 지나치게 싼 상품을 뒤로 민다", () => {
  const { ranked } = pickProducts({ candidates: 후보들(), subtitleText: "에어프라이어" });
  const 종이호일 = ranked.find((r) => r.productName.includes("종이호일"));
  const 본품 = ranked.find((r) => r.productName.includes("쿠쿠"));

  assert.ok(종이호일.matchScore < 본품.matchScore, "부속품이 본품보다 앞서면 안 된다");
  assert.ok(종이호일.matchReasons.some((r) => r.includes("쌈")), "이유를 남겨야 한다");
});

test("AC-45b: 지나치게 비싼 묶음·업소용도 뒤로 민다", () => {
  const { ranked } = pickProducts({ candidates: 후보들(), subtitleText: "에어프라이어" });
  const 업소용 = ranked.find((r) => r.productName.includes("업소용"));
  assert.ok(업소용.matchReasons.some((r) => r.includes("비쌈")));
});

test("AC-46: 로켓배송을 우대한다", () => {
  const 같은조건 = [
    { productId: 1, productName: "가전 제품 A", productPrice: 50000, deeplink: "a", productUrl: "a", isRocket: false },
    { productId: 2, productName: "가전 제품 A", productPrice: 50000, deeplink: "b", productUrl: "b", isRocket: true },
  ];
  const { picked } = pickProducts({ candidates: 같은조건 });
  assert.equal(picked[0].productId, 2);
});

test("AC-46b: 검색어 신뢰도가 낮으면 그 검색어로 찾은 상품을 덜 믿는다", () => {
  const 후보 = [
    { productId: 1, productName: "확실한 검색어 상품", productPrice: 50000, deeplink: "a", productUrl: "a", isRocket: true, sourceKeyword: "에어프라이어" },
    { productId: 2, productName: "약한 검색어 상품", productPrice: 50000, deeplink: "b", productUrl: "b", isRocket: true, sourceKeyword: "가전" },
  ];
  const { ranked } = pickProducts({
    candidates: 후보,
    keywords: [{ word: "에어프라이어", score: 4 }, { word: "가전", score: 1 }],
  });
  const 강함 = ranked.find((r) => r.productId === 1);
  const 약함 = ranked.find((r) => r.productId === 2);
  assert.ok(강함.matchScore > 약함.matchScore, "신뢰도 높은 검색어의 상품이 앞서야 한다");
});

test("AC-47: 같은 상품이 여러 검색어에서 중복으로 들어와도 한 번만 넣는다", () => {
  const 중복 = [
    { productId: 7, productName: "같은 상품", productPrice: 50000, deeplink: "x", productUrl: "x", isRocket: true, sourceKeyword: "가", keywordScore: 2 },
    { productId: 7, productName: "같은 상품", productPrice: 50000, deeplink: "x", productUrl: "x", isRocket: true, sourceKeyword: "나", keywordScore: 2 },
    { productId: 8, productName: "다른 상품", productPrice: 50000, deeplink: "y", productUrl: "y", isRocket: true, sourceKeyword: "가", keywordScore: 2 },
  ];
  const { picked } = pickProducts({ candidates: 중복 }, { max: 2 });
  assert.deepEqual(picked.map((x) => x.productId), [7, 8]);
});

test("AC-47b: 링크가 없거나 이름이 빈 후보는 버린다", () => {
  const 망가진것 = [
    { productId: 1, productName: "정상", productPrice: 1000, deeplink: "a", productUrl: "a" },
    { productId: 2, productName: "링크 없음", productPrice: 1000 },
    { productId: 3, productName: "   ", deeplink: "c", productUrl: "c" },
  ];
  const { picked, ranked } = pickProducts({ candidates: 망가진것 });
  assert.equal(ranked.length, 1);
  assert.equal(picked[0].productName, "정상");
});

test("AC-47c: 후보가 없으면 예외를 던지지 않고 이유를 돌려준다", () => {
  for (const 입력 of [[], null, undefined]) {
    const r = pickProducts({ candidates: 입력 });
    assert.deepEqual(r.picked, []);
    assert.equal(typeof r.skipped, "string");
  }
});

test("AC-47d: 같은 입력에 항상 같은 순서를 낸다", () => {
  const 입력 = { candidates: 후보들(), subtitleText: "필립스 NA230" };
  const a = pickProducts(입력);
  const b = pickProducts(입력);
  assert.deepEqual(a.ranked.map((x) => x.productId), b.ranked.map((x) => x.productId));
});

test("AC-47e: 고른 이유를 항상 남긴다 — 나중에 기준을 다듬을 근거다", () => {
  const { ranked } = pickProducts({ candidates: 후보들(), subtitleText: "필립스" });
  for (const r of ranked) {
    assert.ok(Array.isArray(r.matchReasons), "이유가 배열이어야 한다");
    assert.ok(Number.isFinite(r.matchScore), "점수가 숫자여야 한다");
  }
});
