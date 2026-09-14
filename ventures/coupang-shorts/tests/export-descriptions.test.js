/**
 * 실행: node --test ventures/coupang-shorts/tests/export-descriptions.test.js
 *
 * 관례에서 조금 벗어난 파일이다. 이 저장소는 `lib/` 의 순수 함수에만 테스트를 짝짓는데,
 * 여기서는 `bin/` 스크립트가 내보낸 순수 함수를 검사한다. 검색어를 URL 로 인코딩하는
 * 부분은 한글이 섞여 틀리기 쉽고, 틀리면 링크가 조용히 엉뚱한 데로 간다 — 눈으로는
 * 알 수 없는 종류의 결함이라 코드로 잠가 둔다.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { 검색링크, 문서만들기, COUPANG_SEARCH } = require("../bin/export-descriptions.js");

test("AC-42: 한글 검색어를 URL 로 올바르게 인코딩한다", () => {
  assert.equal(검색링크("에어프라이어"), `${COUPANG_SEARCH}%EC%97%90%EC%96%B4%ED%94%84%EB%9D%BC%EC%9D%B4%EC%96%B4`);
  assert.equal(검색링크("커피머신"), `${COUPANG_SEARCH}%EC%BB%A4%ED%94%BC%EB%A8%B8%EC%8B%A0`);

  // 디코딩하면 원래 말이 그대로 나와야 한다.
  for (const 말 of ["에어프라이어", "게이밍 의자", "USB 허브", "락앤락"]) {
    const 뒷부분 = 검색링크(말).slice(COUPANG_SEARCH.length);
    assert.equal(decodeURIComponent(뒷부분), 말.trim());
  }
});

test("AC-42b: 공백과 특수문자가 주소를 깨뜨리지 않는다", () => {
  const 링크 = 검색링크("  게이밍 의자 & 책상  ");
  assert.doesNotMatch(링크, /\s/, "주소에 공백이 남으면 안 된다");
  assert.ok(링크.startsWith(COUPANG_SEARCH));
  assert.equal(decodeURIComponent(링크.slice(COUPANG_SEARCH.length)), "게이밍 의자 & 책상");
});

test("AC-43: 영상마다 검색어를 누를 수 있는 링크로 적는다", () => {
  const 문서 = 문서만들기([{
    dir: "/tmp/runs/2026-09-14/abc",
    날짜: "2026-09-14",
    meta: {
      title: "제목 #shorts",
      description: "설명",
      keywords: ["에어프라이어", "필립스"],
    },
    plan: { videoId: "abcdefghijk", channelTitle: "어떤채널", cueCount: 100, segments: [] },
    영상들: [{ rank: 1, durationSec: 30, subtitleLineCount: 5, file: "short1.mp4" }],
    top: { meanValue: 0.9, peakValue: 1.0 },
  }], "https://youtube.com/@test");

  assert.match(문서, /\[에어프라이어\]\(https:\/\/www\.coupang\.com\/np\/search\?q=%/);
  assert.match(문서, /\[필립스\]\(https:\/\/www\.coupang\.com\/np\/search\?q=%/);
  assert.match(문서, /파트너스 링크 생성기/, "링크를 만들 곳도 알려 줘야 한다");
});

test("AC-43b: 검색어가 없는 영상도 문서를 깨뜨리지 않는다", () => {
  const 문서 = 문서만들기([{
    dir: "/tmp/runs/2026-09-14/abc",
    날짜: "2026-09-14",
    meta: { title: "제목 #shorts", description: "설명", keywords: [] },
    plan: { videoId: "abcdefghijk", channelTitle: "어떤채널", cueCount: 0, segments: [] },
    영상들: [{ rank: 1, durationSec: 30, subtitleLineCount: 0, file: "short1.mp4" }],
    top: { meanValue: 0.5, peakValue: 0.6 },
  }], "");

  assert.match(문서, /검색어 없음/);
  // 자막이 0줄이면 경고가 붙어야 한다.
  assert.match(문서, /자막이 없어/);
});
