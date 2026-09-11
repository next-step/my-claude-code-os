/** 실행: node --test ventures/coupang-shorts/tests/keyword.test.js */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { extractKeywords } = require("../lib/keyword.js");

const 실제영상 = {
  title: "에어프라이어 유료 광고에 지친 당신을 위해 직접 사서 비교했습니다",
  channelTitle: "노써치",
  subtitleText: "먼저 필립스 NA230입니다 넉넉한 용량과 성능 마감 소음 에어프라이어 바스켓형 에어프라이어 필립스",
};

test("AC-14: 제목과 자막에서 상품명 후보를 뽑는다", () => {
  const { keywords } = extractKeywords(실제영상, { boostWords: ["에어프라이어", "필립스"], limit: 3 });
  assert.ok(keywords.includes("에어프라이어"), "핵심 상품군이 빠지면 안 된다");
  assert.ok(keywords.includes("필립스"), "자막에만 나온 브랜드도 잡아야 한다");
});

test("AC-15: 불용어와 채널명을 검색어에서 뺀다", () => {
  const { scored } = extractKeywords(
    { title: "노써치 리뷰 추천 비교 에어프라이어 내돈내산", channelTitle: "노써치" },
    { requireEvidence: false }
  );
  const 나온말 = scored.map((x) => x.word);

  for (const 빼야할말 of ["노써치", "리뷰", "추천", "비교", "내돈내산"]) {
    assert.ok(!나온말.includes(빼야할말), `"${빼야할말}" 이 남아 있다`);
  }
  assert.ok(나온말.includes("에어프라이어"));
});

test("AC-15b: 서술어로 끝나는 말은 상품명으로 보지 않는다", () => {
  // 실제로 "비교했습니다" 가 2순위 검색어로 뽑히는 것을 보고 넣은 규칙이다.
  const { scored } = extractKeywords(
    { title: "에어프라이어 비교했습니다 좋습니다 사용하는 써봤는데" },
    { requireEvidence: false }
  );
  const 나온말 = scored.map((x) => x.word);

  for (const 서술어 of ["비교했습니다", "좋습니다", "사용하는", "써봤는데"]) {
    assert.ok(!나온말.includes(서술어), `서술어 "${서술어}" 가 남아 있다`);
  }
});

test("AC-15c: 숫자만 있는 말과 한 글자는 뺀다", () => {
  const { scored } = extractKeywords({ title: "2026 에어프라이어 5 대 비교" }, { requireEvidence: false });
  const 나온말 = scored.map((x) => x.word);
  assert.ok(!나온말.includes("2026"));
  assert.ok(!나온말.includes("5"));
  assert.ok(!나온말.includes("대"));
});

test("AC-15d: 조사를 떼어 같은 말로 모은다", () => {
  const { scored } = extractKeywords(
    { title: "에어프라이어를 샀다", subtitleText: "에어프라이어가 좋다 에어프라이어는 편하다 에어프라이어에서" },
    { requireEvidence: false }
  );
  const 에프 = scored.find((x) => x.word === "에어프라이어");
  assert.ok(에프, "조사가 붙은 형태들이 하나로 모여야 한다");
  assert.ok(에프.reasons.some((r) => /자막에 3번/.test(r)), `자막 빈도가 합산돼야 한다: ${에프.reasons}`);
});

test("AC-15e: 근거가 하나뿐인 말은 버리되, 전부 버려지면 근거 요구를 푼다", () => {
  // 자막이 없고 우대 목록도 없으면 제목에만 기댈 수밖에 없다. 빈손으로 돌아가면 안 된다.
  const 빈손위험 = extractKeywords({ title: "가전 구매" }, { limit: 3 });
  assert.ok(빈손위험.keywords.length >= 1, "검색어가 하나도 없으면 상품을 못 찾는다");
  assert.equal(빈손위험.evidenceRelaxed, true, "근거 요구를 풀었음을 알려야 한다");

  const 근거충분 = extractKeywords(실제영상, { boostWords: ["에어프라이어"], limit: 3 });
  assert.equal(근거충분.evidenceRelaxed, false);
});

test("AC-15f: 같은 입력에 항상 같은 검색어를 낸다", () => {
  const a = extractKeywords(실제영상, { boostWords: ["에어프라이어"], limit: 3 });
  const b = extractKeywords(실제영상, { boostWords: ["에어프라이어"], limit: 3 });
  assert.deepEqual(a, b);
});

test("AC-15g: 제목이 비어도 예외를 던지지 않는다", () => {
  for (const 입력 of [{}, { title: "" }, { title: null }, { title: "!!! ??? ..." }]) {
    const r = extractKeywords(입력);
    assert.ok(Array.isArray(r.keywords));
  }
});

test("AC-15h: 수량·차수 표현은 상품명으로 보지 않는다", () => {
  // "25년차 주부" 의 "25년차" 가 검색어로 뽑혀 쇼츠 제목에 들어가는 것을 보고 넣은 규칙이다.
  const { scored } = extractKeywords(
    { title: "25년차 주부가 고른 에어프라이어 3위 12만원 5L" },
    { requireEvidence: false }
  );
  const 나온말 = scored.map((x) => x.word);
  for (const 수량 of ["25년차", "3위", "12만원", "5L"]) {
    assert.ok(!나온말.includes(수량), `수량 표현 "${수량}" 이 남아 있다`);
  }
  assert.ok(나온말.includes("에어프라이어"));
});

test("AC-15i: 나란히 붙은 두 말을 이어 붙여 우대 목록과 맞춰 본다", () => {
  // "커피 머신" 이 두 토큰으로 쪼개져 "커피머신" 을 놓치고 브랜드명에 밀렸다.
  const { keywords } = extractKeywords(
    { title: "캡슐은 비싸요, 커피 머신 추천 | 필립스 1200 전자동 리뷰", subtitleText: "커피 머신 원두" },
    { boostWords: ["커피머신", "필립스"], limit: 3 }
  );
  assert.equal(keywords[0], "커피머신", "복합명사가 브랜드명보다 앞에 와야 한다");
});

test("AC-15j: 버전 꼬리표와 검색 노출용 관용구를 검색어로 쓰지 않는다", () => {
  // 이 값들은 해시태그로도 나가기 때문에 남으면 눈에 띈다.
  const { scored } = extractKeywords(
    { title: "무선청소기 끝장비교(26년ver.) 완벽비교 구매가이드" },
    { requireEvidence: false }
  );
  const 나온말 = scored.map((x) => x.word);
  for (const 잡음 of ["끝장비교", "26년ver", "완벽비교", "구매가이드"]) {
    assert.ok(!나온말.includes(잡음), `잡음 "${잡음}" 이 남아 있다`);
  }
  assert.ok(나온말.includes("무선청소기"));
});
