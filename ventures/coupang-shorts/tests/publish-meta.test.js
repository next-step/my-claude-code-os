/** 실행: node --test ventures/coupang-shorts/tests/publish-meta.test.js */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { buildPublishMeta, DISCLOSURE, LIMITS } = require("../lib/publish-meta.js");

const 기본 = {
  videoTitle: "에어프라이어로 만드는 초간단 간식",
  channelTitle: "어떤요리채널",
  videoId: "dQw4w9WgXcQ",
  keywords: ["에어프라이어", "간식"],
  products: [{ productName: "쿠쿠 에어프라이어 5L", deeplink: "https://link.coupang.com/a/XXXX" }],
};

test("AC-26: 제휴 고지 문구가 항상 설명에 들어간다", () => {
  const 경우들 = [
    기본,
    { ...기본, products: [] },
    { ...기본, keywords: [] },
    { ...기본, products: [], keywords: [], videoTitle: "" },
  ];
  for (const 입력 of 경우들) {
    const meta = buildPublishMeta(입력);
    assert.ok(meta.description.includes(DISCLOSURE), "고지 문구가 설명에 있어야 한다");
    assert.equal(meta.disclosure, DISCLOSURE);
  }
});

test("AC-26b: 설명이 상한을 넘겨 잘려도 고지 문구와 출처는 남는다", () => {
  // 상품을 아주 많이 넣어 상한을 넘긴다.
  const 상품많음 = Array.from({ length: 400 }, (_, i) => ({
    productName: `상품${i} `.repeat(10),
    deeplink: `https://link.coupang.com/a/${i}`,
  }));
  const meta = buildPublishMeta({ ...기본, products: 상품많음 });

  assert.equal(meta.truncated, true, "잘렸음을 표시해야 한다");
  assert.ok(meta.description.length <= LIMITS.descriptionChars, `설명이 상한을 넘었다: ${meta.description.length}자`);
  assert.ok(meta.description.includes(DISCLOSURE), "잘려도 고지 문구는 남아야 한다");
  assert.ok(meta.description.includes("어떤요리채널"), "잘려도 출처는 남아야 한다");
});

test("AC-27: 원본 채널명과 주소가 설명에 들어간다", () => {
  const meta = buildPublishMeta(기본);
  assert.ok(meta.description.includes("어떤요리채널"));
  assert.ok(meta.description.includes("https://youtu.be/dQw4w9WgXcQ"));
  assert.ok(meta.attribution.includes("어떤요리채널"));
});

test("AC-27b: 출처에 쓸 채널명이 없으면 만들지 않고 막는다", () => {
  assert.throws(() => buildPublishMeta({ ...기본, channelTitle: "" }), /channelTitle/);
  assert.throws(() => buildPublishMeta({ ...기본, videoId: "" }), /videoId/);
});

test("AC-28: 제목과 설명이 유튜브 상한을 넘지 않는다", () => {
  const 긴제목 = "가".repeat(300);
  const meta = buildPublishMeta({ ...기본, videoTitle: 긴제목 });

  assert.ok(meta.title.length <= LIMITS.titleChars, `제목이 상한을 넘었다: ${meta.title.length}자`);
  assert.ok(meta.title.endsWith(" #shorts"), "쇼츠 표시가 붙어야 한다");
  assert.ok(meta.description.length <= LIMITS.descriptionChars);
});

test("AC-28b: 해시태그는 3개까지만 만들고 특수문자를 뺀다", () => {
  const meta = buildPublishMeta({
    ...기본,
    keywords: ["에어 프라이어", "간식!", "에어 프라이어", "요리", "주방", "가전"],
  });
  assert.deepEqual(meta.hashtags, ["#에어프라이어", "#간식", "#요리"]);
});

test("AC-28c: 상품이 없으면 사람이 손으로 링크를 넣을 자리를 남긴다", () => {
  // 쿠팡 API 키를 받기 전(누적 판매 15만 원 이전)에 쓰는 경로다.
  const meta = buildPublishMeta({ ...기본, products: [] });
  assert.match(meta.description, /링크를 여기에 넣어 주세요/);
  assert.ok(meta.description.includes(DISCLOSURE));
});
