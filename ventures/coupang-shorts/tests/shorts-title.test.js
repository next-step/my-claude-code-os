/** 실행: node --test ventures/coupang-shorts/tests/shorts-title.test.js */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { buildShortsTitle } = require("../lib/shorts-title.js");

/**
 * 실제로 처리한 영상 6편의 원본 제목이다. 규칙을 고치면 이 6개가 어떻게 변하는지
 * 여기서 바로 드러난다. 형태소 분석기 없이 어림법으로 푸는 문제라, 합성 예제보다
 * 실제 표본을 고정해 두는 편이 훨씬 잘 잡아 준다.
 */
const 실제제목 = [
  {
    원본: "에어프라이어 유료 광고에 지친 당신을 위해 직접 사서 비교했습니다",
    키워드: ["에어프라이어"],
    기대: "에어프라이어 유료 광고에 지친 당신을 위해 #shorts",
  },
  {
    원본: "25년 최고의 가습기는 이것! 돈 아껴드리는 가열식 가습기 끝장비교ㅣ내돈내산",
    키워드: ["가습기"],
    기대: "25년 최고의 가습기는 이것! #shorts",
  },
  {
    원본: '"아무거나 사면 후회합니다" 2025 가습기 추천 구매가이드🔥 가열식가습기, 초음파, 기화식 완벽 비교 추천｜신생아가습기｜디디오랩',
    키워드: ["가습기"],
    기대: "아무거나 사면 후회합니다 | 가습기 #shorts",
  },
  {
    원본: "작년보다 더 싸짐 ㄷㄷ 10~20만원대 초가성비 스테이션 무선청소기 끝장비교(26년ver.)ㅣ내돈내산",
    키워드: ["무선청소기"],
    기대: "작년보다 더 싸짐 ㄷㄷ | 무선청소기 #shorts",
  },
  {
    원본: "캡슐은 비싸요, 커피 값 아끼려면 당장 사야 하는 커피 머신 추천 | 필립스 1200 전자동 내돈내산 리뷰",
    키워드: ["커피머신"],
    기대: "캡슐은 비싸요 | 커피머신 #shorts",
  },
];

test("AC-34: 실제 영상 제목에서 훅을 뽑아 쇼츠용 제목을 만든다", () => {
  for (const { 원본, 키워드, 기대 } of 실제제목) {
    const { title } = buildShortsTitle({ videoTitle: 원본, keywords: 키워드 });
    assert.equal(title, 기대, `원본: ${원본}`);
  }
});

test("AC-34b: 따옴표 안 구절을 가장 강한 훅으로 본다", () => {
  const { title, source } = 결과("'이건 사지 마세요' 2026 가전 추천 총정리", ["가전"]);
  assert.equal(source, "따옴표");
  assert.match(title, /^이건 사지 마세요/);
});

test("AC-34c: 강조 표지는 훅에 남긴다 — 떼면 맥이 빠진다", () => {
  assert.match(결과("가격 실화냐 ㄷㄷ 무선청소기 비교", ["무선청소기"]).title, /ㄷㄷ/);
  assert.match(결과("이게 최선입니다! 커피머신 총정리", ["커피머신"]).title, /!/);
  // 물음표와 이모지는 표지로만 쓰고 제목에 넣지 않는다.
  assert.doesNotMatch(결과("진짜 살 만한가? 가습기 추천 정리", ["가습기"]).title, /\?/);
  assert.doesNotMatch(결과("꼭 보세요🔥 가습기 추천 정리", ["가습기"]).title, /🔥/);
});

test("AC-35: 검색 노출용 관용구를 훅으로 고르지 않는다", () => {
  const 관용구들 = ["구매가이드", "내돈내산", "끝장비교", "총정리", "완벽 비교"];
  for (const { 원본, 키워드 } of 실제제목) {
    const { title } = buildShortsTitle({ videoTitle: 원본, keywords: 키워드 });
    for (const w of 관용구들) {
      assert.ok(!title.includes(w), `"${w}" 가 제목에 남았다: ${title}`);
    }
  }
});

test("AC-35b: 버전 꼬리표와 이모지를 걷어 낸다", () => {
  const { title } = 결과("올해 최고 ㄷㄷ 무선청소기 비교(26년ver.)🔥", ["무선청소기"]);
  assert.doesNotMatch(title, /ver/i);
  assert.doesNotMatch(title, /26년ver/);
});

test("AC-36: 훅에 이미 상품 키워드가 있으면 또 붙이지 않는다", () => {
  const 포함 = 결과("25년 최고의 가습기는 이것! 돈 아껴드리는 가열식 가습기 끝장비교", ["가습기"]);
  assert.equal(포함.keywordAppended, false);
  assert.equal((포함.title.match(/가습기/g) || []).length, 1, "키워드가 두 번 나오면 안 된다");

  const 미포함 = 결과("아무거나 사면 후회합니다", ["가습기"]);
  assert.equal(미포함.keywordAppended, true);
  assert.match(미포함.title, /\| 가습기/);
});

test("AC-36b: 상품 키워드만으로 이뤄진 절은 훅으로 고르지 않는다", () => {
  const { title } = 결과("가습기 | 겨울에 이거 없으면 고생합니다 | 가습기 추천", ["가습기"]);
  assert.match(title, /겨울에 이거 없으면 고생합니다/);
});

test("AC-37: 제목이 유튜브 상한을 넘지 않는다", () => {
  const 긴제목 = `${"가".repeat(300)} 비교`;
  const { title } = 결과(긴제목, ["가전"]);
  assert.ok(title.length <= 100, `상한을 넘었다: ${title.length}자`);
  assert.ok(title.endsWith(" #shorts"));
});

test("AC-37b: 실제 표본의 제목이 모바일에서 잘리지 않을 길이다", () => {
  for (const { 원본, 키워드 } of 실제제목) {
    const { title } = buildShortsTitle({ videoTitle: 원본, keywords: 키워드 });
    assert.ok(title.length <= 45, `${title.length}자로 너무 길다: ${title}`);
  }
});

test("AC-37c: 원본 제목이 비어도 예외를 던지지 않는다", () => {
  assert.equal(결과("", ["가습기"]).title, "가습기 #shorts");
  assert.equal(buildShortsTitle({}).title, "#shorts");
  // 기호뿐인 제목은 다듬고 나면 아무것도 안 남는다. 억지로 쓰지 않는다.
  assert.equal(결과("!!! ???", []).title.trim(), "#shorts");
  assert.equal(결과("!!! ???", ["가습기"]).title, "가습기 #shorts");
});

test("AC-37d: 같은 입력에 항상 같은 제목을 낸다", () => {
  const 입력 = { videoTitle: 실제제목[0].원본, keywords: 실제제목[0].키워드 };
  assert.deepEqual(buildShortsTitle(입력), buildShortsTitle(입력));
});

function 결과(videoTitle, keywords) {
  return buildShortsTitle({ videoTitle, keywords });
}

test("AC-36c: 1순위 검색어만 붙인다 — 2순위까지 덧붙이면 제목이 산만해진다", () => {
  // 한때 "훅에 없는 첫 번째 검색어"를 찾게 했더니, 훅이 주제를 이미 담고 있는데도
  // 2순위 브랜드명이 덧붙어 "25년 최고의 가습기는 이것! | 가열식" 같은 제목이 나왔다.
  const 훅에있음 = 결과("25년 최고의 가습기는 이것!", ["가습기", "가열식"]);
  assert.equal(훅에있음.keywordAppended, false);
  assert.equal(훅에있음.title, "25년 최고의 가습기는 이것! #shorts");

  const 훅에없음 = 결과("아무거나 사면 후회합니다", ["가습기", "가열식"]);
  assert.equal(훅에없음.title, "아무거나 사면 후회합니다 | 가습기 #shorts");
});

test("AC-39: 관용구를 빼면 남는 것이 없는 절은 탈락시킨다 — 감점만으로는 부족하다", () => {
  // "내돈내산!" 이 1순위로 뽑혔다. 관용구라 감점했지만 강조 표지 점수가 그 감점을 덮었다.
  const { title } = 결과("내돈내산! 문의 많았던 밀폐용기 찐후기 | 다이소·이케아·락앤락 꿀템 10가지", ["밀폐용기"]);
  assert.ok(!title.startsWith("내돈내산"), `관용구뿐인 절이 뽑혔다: ${title}`);
  assert.ok(title.length > 12, `알맹이 있는 절을 골라야 한다: ${title}`);
});

test("AC-39b: 한글이 없는 짧은 절은 제품 모델명으로 보고 훅에서 뺀다", () => {
  // "R1 SE+" 가 제목으로 뽑혔다.
  const { title } = 결과("입문용 가성비 사무용까지 R1 SE+ 마우스 추천", ["마우스"]);
  assert.ok(!title.startsWith("R1 SE+"), `모델명이 훅이 되면 안 된다: ${title}`);

  // 한글이 섞인 절은 짧아도 남는다.
  assert.match(결과("오븐형 vs 바스켓형 비교", ["에어프라이어"]).title, /오븐형 vs 바스켓형/);
});

test("AC-39c: 훅 끝에 붙은 관용구와 매달린 수식어를 떼어 낸다", () => {
  assert.equal(결과("캡슐 커피머신 첫인상 리뷰 | 네스프레소", ["커피머신"]).hook, "캡슐 커피머신 첫인상");
  assert.equal(결과("겨울 이불 고르는 법 총정리", ["이불"]).hook, "겨울 이불 고르는 법");
  // 절 전체가 관용구면 떼지 않고 통째로 탈락한다 (AC-39).
  assert.ok(!결과("리뷰 | 겨울에 이거 없으면 고생합니다", ["이불"]).title.startsWith("리뷰"));

  // 관용구를 떼고 나면 꾸밈 받을 말이 사라진 수식어가 남는다. 그것도 떼어 낸다.
  assert.equal(
    결과("에어프라이어 추천, 직접 다 써본 25년차 주부의 최종 비교 후기", ["에어프라이어"]).hook,
    "직접 다 써본 25년차 주부"
  );
});

test("AC-39d: 세 규칙을 넣어도 기존 표본의 제목이 바뀌지 않는다", () => {
  // AC-34 와 같은 표본이지만, 규칙을 더할 때 옛 결과가 깨지지 않는지를 따로 확인한다.
  for (const { 원본, 키워드, 기대 } of 실제제목) {
    assert.equal(buildShortsTitle({ videoTitle: 원본, keywords: 키워드 }).title, 기대);
  }
});
