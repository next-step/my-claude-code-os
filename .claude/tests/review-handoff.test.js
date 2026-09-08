const test = require("node:test");
const assert = require("node:assert");

const { countFindings, citedCommits, checkHandoff } = require("../lib/review-handoff.js");

const REVIEWER = [
  "판정: FAIL",
  "",
  "- 표시 계층 AC 없음 — summarize 반환값만 검증한다",
  "- 7일 경계 정의 누락 — 포함 여부가 미정이다",
  "- 동률 처리 누락 — 2차 정렬 기준이 없다",
  "- 이상 데이터 처리 누락 — 깨진 시각의 취급이 미정이다",
  "- AC-3의 검증 형태가 모호하다",
].join("\n");

test("AC-1: 내용이 있는 불릿만 지적 항목으로 센다", () => {
  assert.strictEqual(countFindings(REVIEWER), 5);
});

test("AC-2: 짧은 줄과 제목·구분자는 항목으로 세지 않는다", () => {
  const text = ["# 제목", "", "- 짧음", "---", "- 이건 충분히 긴 지적 항목이다"].join("\n");
  assert.strictEqual(countFindings(text), 1);
});

test("AC-3: 번호 목록과 들여쓴 항목도 지적으로 센다", () => {
  const text = ["1. 첫 번째 지적 항목이다", "   - 들여쓴 하위 지적도 지적이다"].join("\n");
  assert.strictEqual(countFindings(text), 2);
});

test("AC-4: 비문자열 입력은 0으로 처리한다", () => {
  assert.strictEqual(countFindings(null), 0);
  assert.strictEqual(countFindings(undefined), 0);
});

test("AC-5: 커밋 해시로 보이는 토큰을 찾아낸다", () => {
  assert.deepStrictEqual(citedCommits("이미 커밋되어 있다 — c6c5068, a8bc68c"), ["c6c5068", "a8bc68c"]);
});

test("AC-6: 순수 숫자와 알파벳 없는 토큰은 해시로 보지 않는다", () => {
  // 수치(1234567)나 연도 나열이 해시로 오탐되면 경보가 늑대소년이 된다.
  assert.deepStrictEqual(citedCommits("항목 1234567개, 예산 9999999"), []);
});

test("AC-7: 인계문이 리뷰어보다 항목이 적으면 축소로 잡는다", () => {
  const handoff = ["- 기준 시각 정의가 없다", "- 출력 표면 AC가 없다"].join("\n");
  const result = checkHandoff({ reviewerText: REVIEWER, handoffText: handoff });
  assert.strictEqual(result.reviewerItems, 5);
  assert.strictEqual(result.handoffItems, 2);
  assert.strictEqual(result.shrunk, true);
  assert.match(result.warnings.join("\n"), /지적 축소/);
});

test("AC-8: 인계문의 커밋 해시 인용을 구현 지식 유입으로 잡는다", () => {
  const handoff = REVIEWER + "\n\n참고: 세 항목은 이미 커밋되어 있다 — c6c5068, a8bc68c, 2322d87";
  const result = checkHandoff({ reviewerText: REVIEWER, handoffText: handoff });
  assert.strictEqual(result.shrunk, false);
  assert.deepStrictEqual(result.citedCommits, ["c6c5068", "a8bc68c", "2322d87"]);
  assert.match(result.warnings.join("\n"), /구현 지식 유입/);
});

test("AC-9: 원문을 그대로 옮기면 경보가 없다", () => {
  const result = checkHandoff({ reviewerText: REVIEWER, handoffText: REVIEWER });
  assert.strictEqual(result.ok, true);
  assert.deepStrictEqual(result.warnings, []);
});

test("AC-10: 항목을 더 늘리는 것은 축소가 아니다", () => {
  const handoff = REVIEWER + "\n- 호출자가 덧붙인 별도 관찰 항목이다";
  const result = checkHandoff({ reviewerText: REVIEWER, handoffText: handoff });
  assert.strictEqual(result.shrunk, false);
  assert.strictEqual(result.ok, true);
});

test("AC-11: 실험 3에서 실제로 관측된 인계문은 두 경보를 모두 낸다", () => {
  // docs/context-ab-test.md 실험 3의 armG1-2 인계문을 축약한 것.
  const observed = [
    "리뷰어가 지적한 세 항목은 이미 커밋되어 있다 — c6c5068, a8bc68c, 2322d87.",
    "",
    "- 남는 진짜 미커버 항목은 기준 시각·시간대다",
    "- 그리고 출력 표면이 검증되지 않는다",
  ].join("\n");
  const result = checkHandoff({ reviewerText: REVIEWER, handoffText: observed });
  assert.strictEqual(result.ok, false);
  assert.strictEqual(result.warnings.length, 2);
});

test("AC-12: 이 검사는 게이트가 아니라 경보다 — ok는 정직함을 보증하지 않는다", () => {
  // 개수를 유지하면서 문장만 무력화하면 통과한다. 한계를 테스트로 못박아 둔다.
  const neutered = REVIEWER.replace(/누락 — /g, "누락처럼 보이나 문제 없음 — ");
  const result = checkHandoff({ reviewerText: REVIEWER, handoffText: neutered });
  assert.strictEqual(result.ok, true, "개수만 보는 검사는 이 경우를 잡지 못한다");
});
