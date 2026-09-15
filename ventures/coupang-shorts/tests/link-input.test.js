/** 실행: node --test ventures/coupang-shorts/tests/link-input.test.js */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { validateLink, toProduct, parseLinkFile } = require("../lib/link-input.js");

test("AC-48: 쿠팡 공식 주소만 받는다", () => {
  for (const 주소 of [
    "https://link.coupang.com/a/XXXX",
    "https://www.coupang.com/vp/products/123456",
    "https://coupang.com/vp/products/1",
  ]) {
    assert.equal(validateLink(주소).ok, true, `받아야 한다: ${주소}`);
  }

  for (const 주소 of ["https://example.com/x", "https://coupang.evil.com/a", "https://notcoupang.com/a"]) {
    const r = validateLink(주소);
    assert.equal(r.ok, false, `막아야 한다: ${주소}`);
    assert.match(r.reason, /쿠팡 주소가 아니다/);
  }
});

test("AC-48b: 단축 URL 은 이유를 밝히고 거부한다 — 쿠팡이 공개한 계정 정지 사유다", () => {
  for (const 주소 of ["https://bit.ly/abc", "https://vo.la/xyz", "https://han.gl/q", "https://me2.do/x"]) {
    const r = validateLink(주소);
    assert.equal(r.ok, false, `막아야 한다: ${주소}`);
    assert.match(r.reason, /단축 URL/);
    assert.match(r.reason, /계정 정지/, "왜 막는지 알려 줘야 한다");
  }
});

test("AC-48c: 주소 형식이 아니거나 비면 막는다", () => {
  for (const 주소 of ["", "   ", "그냥 글자", "ftp://coupang.com/a", null, undefined]) {
    assert.equal(validateLink(주소).ok, false, `막아야 한다: ${주소}`);
  }
});

test("AC-49: 검사를 통과한 링크를 API 경로와 같은 상품 형태로 바꾼다", () => {
  const p = toProduct({ url: "https://link.coupang.com/a/AAAA", productName: "필립스 에어프라이어" });

  // lib/coupang.js 의 parseSearchResponse 가 만드는 것과 같은 열쇠를 가져야 한다.
  for (const 열쇠 of ["productId", "productName", "productPrice", "productUrl", "deeplink", "isRocket", "categoryName"]) {
    assert.ok(열쇠 in p, `${열쇠} 가 없다`);
  }
  assert.equal(p.deeplink, "https://link.coupang.com/a/AAAA");
  assert.equal(p.productName, "필립스 에어프라이어");
  assert.equal(p.source, "manual", "어디서 온 링크인지 구분할 수 있어야 한다");
});

test("AC-49b: 상품명을 안 적으면 기본 이름을 넣는다", () => {
  assert.equal(toProduct({ url: "https://link.coupang.com/a/A" }).productName, "영상 속 상품");
});

test("AC-49c: 잘못된 링크로는 상품을 만들지 않는다", () => {
  assert.throws(() => toProduct({ url: "https://bit.ly/x" }), /단축 URL/);
  assert.throws(() => toProduct({ url: "" }), /비어 있다/);
});

test("AC-50: 링크 파일을 영상별로 묶는다", () => {
  const 파일 = [
    "# 주석은 건너뛴다",
    "",
    "5GTAp_RMEHc\thttps://link.coupang.com/a/AAAA\t필립스 에어프라이어",
    "5GTAp_RMEHc\thttps://link.coupang.com/a/BBBB\t쿠쿠 에어프라이어",
    "l16jYQukE80\thttps://link.coupang.com/a/CCCC",
  ].join("\n");

  const { byVideo, rejected } = parseLinkFile(파일);
  assert.equal(byVideo.size, 2);
  assert.equal(byVideo.get("5GTAp_RMEHc").length, 2);
  assert.equal(byVideo.get("l16jYQukE80")[0].productName, "영상 속 상품");
  assert.equal(rejected.length, 0);
});

test("AC-50b: 탭 대신 공백으로 적어도 받는다 — 사람이 손으로 채우는 파일이다", () => {
  const { byVideo } = parseLinkFile("5GTAp_RMEHc https://link.coupang.com/a/AAAA 필립스 에어프라이어");
  assert.equal(byVideo.get("5GTAp_RMEHc")[0].productName, "필립스 에어프라이어");
});

test("AC-50c: 잘못된 줄은 이유와 함께 버리고 나머지를 처리한다", () => {
  const 파일 = [
    "badid\thttps://link.coupang.com/a/AAAA",
    "l16jYQukE80\thttps://bit.ly/zzz",
    "링크만있음",
    "5GTAp_RMEHc\thttps://link.coupang.com/a/GOOD",
  ].join("\n");

  const { byVideo, rejected } = parseLinkFile(파일);
  assert.equal(byVideo.size, 1, "정상인 한 건은 살아야 한다");
  assert.equal(rejected.length, 3);
  assert.ok(rejected.some((r) => /영상 ID/.test(r.reason)));
  assert.ok(rejected.some((r) => /단축 URL/.test(r.reason)));
});

test("AC-50d: 빈 파일이어도 예외를 던지지 않는다", () => {
  for (const 입력 of ["", null, undefined, "\n\n\n", "# 주석만"]) {
    const r = parseLinkFile(입력);
    assert.equal(r.byVideo.size, 0);
    assert.deepEqual(r.rejected, []);
  }
});
