/** 실행: node --test ventures/coupang-shorts/tests/budget.test.js */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { emptyState, checkBudget, recordCall, cacheLookup, cacheStore } = require("../lib/budget.js");

const 기준 = Date.parse("2026-09-11T10:00:00Z");
const 한시간 = 3600 * 1000;

/** n회 호출한 상태를 만든다. */
function 호출상태(n, 시작 = 기준) {
  let s = emptyState();
  for (let i = 0; i < n; i += 1) s = recordCall(s, { now: 시작 + i * 1000 });
  return s;
}

test("AC-19: 한 시간에 10회를 넘으면 거부한다", () => {
  const 아홉번 = checkBudget(호출상태(9), { now: 기준 + 10000 });
  assert.equal(아홉번.allowed, true);
  assert.equal(아홉번.remaining, 1);

  const 열번 = checkBudget(호출상태(10), { now: 기준 + 11000 });
  assert.equal(열번.allowed, false);
  assert.equal(열번.used, 10);
  assert.equal(열번.remaining, 0);
  assert.ok(열번.retryAfterMs > 0, "언제 다시 되는지 알려 줘야 한다");
  assert.match(열번.warning, /한도/);
});

test("AC-20: 한 시간이 지난 기록은 집계에서 뺀다", () => {
  const s = 호출상태(10);

  assert.equal(checkBudget(s, { now: 기준 + 11000 }).allowed, false);
  // 첫 호출이 창 밖으로 나가면 한 칸이 빈다.
  assert.equal(checkBudget(s, { now: 기준 + 한시간 + 1 }).allowed, true);
  assert.equal(checkBudget(s, { now: 기준 + 한시간 + 1 }).used, 9);
  // 전부 지나면 처음으로 돌아간다.
  assert.equal(checkBudget(s, { now: 기준 + 2 * 한시간 }).used, 0);
});

test("AC-20b: 기록할 때 창 밖으로 나간 것을 함께 버려 상태가 무한히 커지지 않는다", () => {
  let s = 호출상태(10);
  s = recordCall(s, { now: 기준 + 2 * 한시간 });
  assert.equal(s.calls.length, 1, "오래된 기록 10개가 남아 있으면 안 된다");
});

test("AC-21: 캐시가 살아 있으면 호출을 세지 않는다", () => {
  let s = emptyState();
  s = cacheStore(s, "에어프라이어", [{ productName: "쿠쿠 에어프라이어" }], { now: 기준 });

  const 적중 = cacheLookup(s, "에어프라이어", { now: 기준 + 60000 });
  assert.equal(적중.hit, true);
  assert.equal(적중.value[0].productName, "쿠쿠 에어프라이어");

  // 캐시를 넣고 빼는 동안 호출 기록은 늘지 않아야 한다.
  assert.equal(checkBudget(s, { now: 기준 }).used, 0);
});

test("AC-21b: 캐시는 유효기간이 지나면 비적중으로 판정한다", () => {
  let s = cacheStore(emptyState(), "에어프라이어", ["값"], { now: 기준 });

  assert.equal(cacheLookup(s, "에어프라이어", { now: 기준 + 23 * 한시간 }).hit, true);
  assert.equal(cacheLookup(s, "에어프라이어", { now: 기준 + 25 * 한시간 }).hit, false);
});

test("AC-21c: 검색어의 앞뒤 공백과 대소문자로 캐시가 갈리지 않는다", () => {
  const s = cacheStore(emptyState(), "AirFryer", ["값"], { now: 기준 });
  assert.equal(cacheLookup(s, "  airfryer  ", { now: 기준 }).hit, true);
});

test("AC-21d: 캐시에 넣을 때 만료된 항목을 함께 치운다", () => {
  let s = cacheStore(emptyState(), "오래된말", ["값"], { now: 기준 });
  s = cacheStore(s, "새로운말", ["값"], { now: 기준 + 25 * 한시간 });

  assert.deepEqual(Object.keys(s.cache), ["새로운말"], "만료된 항목이 남아 있으면 파일이 계속 커진다");
});

test("AC-21e: 상태 파일이 망가졌거나 비어도 예외를 던지지 않는다", () => {
  for (const 망가진상태 of [null, undefined, {}, "문자열", { calls: "배열 아님" }, { cache: 42 }]) {
    const r = checkBudget(망가진상태, { now: 기준 });
    assert.equal(r.allowed, true);
    assert.equal(r.used, 0);
    assert.equal(cacheLookup(망가진상태, "가전", { now: 기준 }).hit, false);
  }
});

test("AC-21f: 한도에 가까워지면 경고를 남긴다", () => {
  assert.equal(checkBudget(호출상태(5), { now: 기준 + 6000 }).warning, null);
  assert.match(checkBudget(호출상태(8), { now: 기준 + 9000 }).warning, /2회 남았다/);
});
