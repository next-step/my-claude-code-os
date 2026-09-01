/**
 * skill-stat "가장 최근에 사용한 스킬" 기능의 인수 테스트.
 *
 * ATDD 05단계 산출물 — 04단계에서 사람이 승인한 AC-1~8에 1:1로 대응한다.
 * 테스트 이름의 `AC-<번호>` 접두사는 실패 원장에서 어떤 인수기준이 깨졌는지
 * 바로 추적하기 위한 것이므로 임의로 바꾸지 않는다.
 *
 * 실행: node --test .claude/tests/
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const { readStats, summarize } = require("../lib/stats.js");

/** 테스트용 통계 데이터를 임시 파일로 떨어뜨리고 경로를 돌려준다. */
function writeTempStats(data) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "atdd-stats-"));
  const file = path.join(dir, "skill-usage-stats.json");
  fs.writeFileSync(file, JSON.stringify(data, null, 2) + "\n");
  return file;
}

test("AC-1: 유효한 lastUsedAt이 있으면 가장 최근 사용 스킬 이름과 시각을 함께 보여준다", () => {
  const result = summarize({
    totalCalls: 6,
    skills: {
      "git-commit-message": { count: 4, lastUsedAt: "2026-08-26T09:00:00.000Z" },
      "skill-stat": { count: 2, lastUsedAt: "2026-08-27T10:30:00.000Z" },
    },
  });

  assert.ok(result.recent, "recent 정보가 있어야 한다");
  assert.deepEqual(result.recent.names, ["skill-stat"]);
  assert.equal(result.recent.at, "2026-08-27T10:30:00.000Z");
});

test("AC-2: 최근 사용 시각이 동률이면 모두 나열하되 이름 오름차순으로 정렬한다", () => {
  const sameMoment = "2026-08-27T10:30:00.000Z";
  const result = summarize({
    totalCalls: 5,
    skills: {
      zeta: { count: 1, lastUsedAt: sameMoment },
      alpha: { count: 3, lastUsedAt: sameMoment },
      older: { count: 1, lastUsedAt: "2026-08-01T00:00:00.000Z" },
    },
  });

  assert.deepEqual(result.recent.names, ["alpha", "zeta"], "동률 항목을 모두, 이름 오름차순으로");
  assert.equal(result.recent.at, sameMoment);
});

test("AC-3: 기록이 없으면 안내 문구만 내고 오류나 빈 값이 나오지 않는다", () => {
  const missingFile = summarize(readStats(path.join(os.tmpdir(), "atdd-없는파일.json")));
  assert.equal(missingFile.isEmpty, true);
  assert.equal(missingFile.message, "아직 기록된 스킬 호출이 없습니다");

  const emptySkills = summarize({ totalCalls: 0, skills: {} });
  assert.equal(emptySkills.isEmpty, true);
  assert.equal(emptySkills.message, "아직 기록된 스킬 호출이 없습니다");
  assert.deepEqual(emptySkills.rows, [], "빈 값 대신 빈 배열이어야 한다");
  assert.equal(emptySkills.recent, null);
});

test("AC-4: 최다 사용 스킬과 최근 사용 스킬이 같아도 두 정보 모두 표시된다", () => {
  const result = summarize({
    totalCalls: 5,
    skills: {
      "skill-stat": { count: 4, lastUsedAt: "2026-08-27T10:30:00.000Z" },
      "git-commit-message": { count: 1, lastUsedAt: "2026-08-20T09:00:00.000Z" },
    },
  });

  assert.equal(result.mostUsed.name, "skill-stat");
  assert.deepEqual(result.recent.names, ["skill-stat"]);
  assert.ok(result.mostUsed, "최다 사용 정보가 생략되면 안 된다");
  assert.ok(result.recent, "최근 사용 정보가 생략되면 안 된다");
});

test("AC-5: 기존 출력(순위 표·최다 사용·전체 호출 수)이 그대로 유지된다", () => {
  const result = summarize({
    totalCalls: 9,
    skills: {
      b: { count: 2, lastUsedAt: "2026-08-27T10:00:00.000Z" },
      a: { count: 5, lastUsedAt: "2026-08-25T10:00:00.000Z" },
      c: { count: 2, lastUsedAt: "2026-08-26T10:00:00.000Z" },
    },
  });

  assert.equal(result.totalCalls, 9);
  assert.equal(result.mostUsed.name, "a");
  assert.equal(result.mostUsed.count, 5);
  assert.equal(result.rows.length, 3);
  assert.equal(result.rows[0].rank, 1);
  assert.equal(result.rows[0].name, "a");
  assert.ok(
    result.rows[0].count >= result.rows[1].count && result.rows[1].count >= result.rows[2].count,
    "count 내림차순으로 정렬되어야 한다"
  );
});

test("AC-6: 통계 파일은 어떤 경우에도 수정되지 않는다", () => {
  const file = writeTempStats({
    totalCalls: 3,
    skills: { "skill-stat": { count: 3, lastUsedAt: "2026-08-27T10:00:00.000Z" } },
  });
  const before = fs.readFileSync(file, "utf-8");

  summarize(readStats(file));

  assert.equal(fs.readFileSync(file, "utf-8"), before, "읽기만 해야 하며 내용이 바뀌면 안 된다");
});

test("AC-7: lastUsedAt이 없거나 무효한 항목만 제외하고 나머지로 정상 판정한다", () => {
  const result = summarize({
    totalCalls: 7,
    skills: {
      "no-timestamp": { count: 3 },
      "bad-timestamp": { count: 2, lastUsedAt: "어제쯤" },
      "good-one": { count: 2, lastUsedAt: "2026-08-27T10:00:00.000Z" },
    },
  });

  assert.deepEqual(result.recent.names, ["good-one"], "무효 항목만 빠지고 유효 항목으로 판정");
  assert.equal(result.rows.length, 3, "순위 표에서는 제외하지 않는다");
  assert.equal(result.mostUsed.name, "no-timestamp", "최다 사용 판정은 영향받지 않는다");
});

test("AC-8: 유효한 lastUsedAt이 하나도 없으면 안내만 하고 나머지는 정상 출력한다", () => {
  const result = summarize({
    totalCalls: 4,
    skills: {
      one: { count: 3 },
      two: { count: 1, lastUsedAt: "" },
    },
  });

  assert.equal(result.isEmpty, false, "기록 자체는 있으므로 빈 상태가 아니다");
  assert.equal(result.recent, null);
  assert.equal(result.recentMessage, "최근 사용 정보 없음");
  assert.equal(result.rows.length, 2);
  assert.equal(result.mostUsed.name, "one");
  assert.equal(result.totalCalls, 4);
});
