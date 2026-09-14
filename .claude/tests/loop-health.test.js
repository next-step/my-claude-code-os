/**
 * 시스템 루프 건강도(.claude/lib/loop-health.js)의 인수 테스트.
 *
 * 이 파일이 가장 신경 쓰는 것은 **점수가 좋아 보이게 만드는 실수**다. 분모를 지어내거나,
 * 없는 축을 0으로 채우거나, 사각지대를 빠뜨리면 초록불이 품질 보증으로 읽힌다.
 *
 * 실행: node --test .claude/tests/loop-health.test.js
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const { auditLoopHealth, readLedger, readRalphRuns, readDelegation, BLIND_SPOTS } = require("../lib/loop-health.js");

const ROOT = path.resolve(__dirname, "..", "..");

/** 가짜 파일시스템. 실제 저장소를 읽지 않고 읽기 함수만 본다. */
function fakeFs(files) {
  return {
    existsSync: (p) => Object.keys(files).some((k) => k === p || p.endsWith(k)),
    readFileSync: (p) => {
      const key = Object.keys(files).find((k) => k === p || p.endsWith(k));
      if (key === undefined) throw new Error(`없는 파일: ${p}`);
      return files[key];
    },
    readdirSync: (p) => {
      const prefix = Object.keys(files).find((k) => p.endsWith(k));
      return prefix ? files[prefix] : [];
    },
  };
}

test("AC-1 실패 원장에서 두 번 이상 깨진 AC를 재발로 센다", () => {
  const fs = fakeFs({
    ".claude/atdd-failure-ledger.json": JSON.stringify({
      entries: [
        { status: "FAIL", failedTests: ["AC-7: 가", "AC-9: 나"] },
        { status: "RESOLVED", failedTests: [] },
        { status: "FAIL", failedTests: ["AC-7: 가"] },
        { status: "RESOLVED", failedTests: [] },
      ],
    }),
  });
  const r = readLedger("/repo", fs);
  assert.equal(r.entries, 4);
  assert.deepEqual(r.recurring, [{ id: "AC-7", count: 2 }], "한 번 깨진 AC-9는 재발이 아니다");
});

test("AC-2 마지막 기록이 FAIL이면 지금 빨간불로 본다", () => {
  const fail = fakeFs({ ".claude/atdd-failure-ledger.json": JSON.stringify({ entries: [{ status: "RESOLVED", failedTests: [] }, { status: "FAIL", failedTests: ["AC-1: 가"] }] }) });
  const ok = fakeFs({ ".claude/atdd-failure-ledger.json": JSON.stringify({ entries: [{ status: "FAIL", failedTests: ["AC-1: 가"] }, { status: "RESOLVED", failedTests: [] }] }) });
  assert.equal(readLedger("/repo", fail).unresolved, true);
  assert.equal(readLedger("/repo", ok).unresolved, false);
});

test("AC-3 원장이 없으면 0으로 내고 터지지 않는다", () => {
  const r = readLedger("/repo", fakeFs({}));
  assert.equal(r.entries, 0);
  assert.equal(r.unresolved, false);
  assert.deepEqual(r.recurring, []);
});

test("AC-4 위임 폭 루브릭이 없으면 축을 null로 낸다 — 0으로 채우지 않는다", () => {
  // 0으로 채우면 "사람이 하는 단계가 하나도 없다"로 읽혀 점수가 실제보다 좋아 보인다.
  assert.equal(readDelegation("/repo", fakeFs({})), null);
});

test("AC-5 위임 폭은 사람이 적은 owner를 그대로 세고, human 단계를 이름으로 남긴다", () => {
  const fs = fakeFs({
    "docs/loop-delegation.json": JSON.stringify({
      stages: [
        { id: "a", name: "가", owner: "ai" },
        { id: "b", name: "나", owner: "human" },
        { id: "c", name: "다", owner: "system" },
        { id: "d", name: "라", owner: "mixed" },
      ],
    }),
  });
  const r = readDelegation("/repo", fs);
  assert.equal(r.stages, 4);
  assert.deepEqual(r.byOwner, { ai: 1, human: 1, system: 1, mixed: 1 });
  assert.deepEqual(r.humanOnly, [{ id: "b", name: "나" }]);
  assert.equal(r.delegatedRatio, 0.75);
});

test("AC-6 랄프 실행 결과가 없으면 표본 0으로 내고 터지지 않는다", () => {
  // runs/ 는 .gitignore에 있어 새 클론에는 아예 없다.
  const r = readRalphRuns("/repo", fakeFs({}));
  assert.deepEqual(r, { runs: 0, done: 0, outcomes: [] });
});

test("AC-7 점수의 분모는 검사기가 실제로 본 항목 수이며 정의가 함께 나간다", () => {
  const r = auditLoopHealth({ projectDir: ROOT });
  assert.equal(typeof r.score.denominator, "number");
  assert.ok(r.score.denominator > 0, "실제 저장소라면 본 항목이 있어야 한다");
  assert.equal(r.score.numerator + r.axes.hygiene.violations, r.score.denominator, "분자 + 위반 = 분모여야 한다");
  assert.ok(r.score.definition.includes("검사기가 실제로 본"), "정의 문구가 점수와 함께 나가야 한다");
});

test("AC-8 훑은 개수를 모르는 검사는 위반이 있을 때만 분모에 들어간다", () => {
  // 모르는 수를 지어내 분모를 부풀리면 점수가 실제보다 좋아 보인다.
  const r = auditLoopHealth({ projectDir: ROOT });
  const unreg = r.axes.hygiene.checks.find((c) => c.id === "freshness.unregistered");
  assert.equal(unreg.checked, 0, "훑은 개수를 모르므로 0이어야 한다");
});

test("AC-9 사각지대 목록과 한계 문구를 항상 함께 낸다", () => {
  const r = auditLoopHealth({ projectDir: ROOT });
  assert.ok(Array.isArray(r.blindSpots) && r.blindSpots.length >= 3);
  assert.deepEqual(r.blindSpots, BLIND_SPOTS);
  assert.ok(r.caveat.includes("검사기가 초록불이다"), "점수를 품질 보증으로 읽지 말라는 문구가 있어야 한다");
});

test("AC-10 실제 저장소에서 네 축이 모두 채워진다 (회귀)", () => {
  // context-ab.test.js AC-11·ralph-loop.test.js AC-12와 같은 성격의 실물 회귀.
  const r = auditLoopHealth({ projectDir: ROOT });
  assert.ok(r.axes.hygiene.checks.length >= 5);
  assert.equal(typeof r.axes.reliability.entries, "number");
  assert.equal(typeof r.axes.autonomy.runs, "number");
  assert.ok(r.axes.tax.alwaysLoadedChars > 0);
  assert.ok(r.axes.coverage && r.axes.coverage.stages > 0, "docs/loop-delegation.json이 커밋돼 있어야 한다");
});
