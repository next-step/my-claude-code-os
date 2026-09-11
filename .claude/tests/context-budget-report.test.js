/**
 * context-budget-report CLI의 인수 테스트.
 *
 * 이 파일이 지키는 것은 한 가지다 — **출력 형식이 랄프 루프의 파서와 맞는가.**
 * 두 파일이 각자 맞다고 믿으면서 서로 안 맞는 상황이 이 계약이 깨지는 방식이라,
 * 형식을 문자열로 다시 적어 확인하지 않고 `extractFromCommand`에 실제로 통과시킨다.
 * 형식이 어긋나면 지표가 `null`이 되고, `null`은 통과로 치지 않으므로
 * (`ralph-loop.js:297`) 루프가 이유 없이 영원히 실패한다.
 *
 * 실행: node --test .claude/tests/context-budget-report.test.js
 */
const test = require("node:test");
const assert = require("node:assert/strict");

const { collectBudgetMetrics, formatBudgetReport } = require("../lib/context-budget-report.js");
const { extractFromCommand } = require("../lib/ralph-loop.js");

/** 실제 저장소를 읽지 않고 형식만 보기 위한 최소 예산 객체. */
function fakeBudget() {
  return {
    alwaysLoaded: { total: 19097, importChars: 10896, skillDescChars: 6536, agentDescChars: 1665 },
    onDemand: { total: 76169, skillsFullChars: 65168, agentsFullChars: 11001 },
  };
}

test("AC-1 예산 요약에서 지표 5종을 이름과 값 쌍으로 뽑는다", () => {
  const metrics = collectBudgetMetrics(fakeBudget());
  const names = metrics.map(([name]) => name);
  assert.deepEqual(names, [
    "always_loaded_chars",
    "import_chars",
    "skill_desc_chars",
    "agent_desc_chars",
    "on_demand_chars",
  ]);
  assert.equal(metrics.every(([, value]) => Number.isInteger(value)), true);
});

test("AC-2 지표마다 한 줄씩 찍고 줄 수가 지표 수와 같다", () => {
  const lines = formatBudgetReport(fakeBudget()).split("\n");
  assert.equal(lines.length, collectBudgetMetrics(fakeBudget()).length);
});

test("AC-3 랄프 루프의 extractFromCommand가 지표 5종을 전부 읽어 낸다", () => {
  const budget = fakeBudget();
  const output = formatBudgetReport(budget);
  for (const [name, value] of collectBudgetMetrics(budget)) {
    assert.equal(extractFromCommand(output, { extract: name }), value, `${name}을 못 읽었다`);
  }
});

test("AC-4 stdout/stderr로 나뉘어 온 실행 결과에서도 읽어 낸다", () => {
  const output = { stdout: formatBudgetReport(fakeBudget()), stderr: "" };
  assert.equal(extractFromCommand(output, { extract: "always_loaded_chars" }), 19097);
});

test("AC-5 짧은 이름이 긴 이름의 줄에 잘못 걸리지 않는다", () => {
  // `import_chars`는 `always_loaded_chars` 줄 안에 없지만, 파서가 `#` 직후부터 이름을
  // 찾지 않고 아무 데서나 찾으면 다른 줄을 집을 수 있다. 값으로 구분해 확인한다.
  const output = formatBudgetReport(fakeBudget());
  assert.equal(extractFromCommand(output, { extract: "import_chars" }), 10896);
});

test("AC-6 없는 지표를 물으면 null을 돌려준다 — 못 잰 것을 통과로 치지 않기 위해서다", () => {
  const output = formatBudgetReport(fakeBudget());
  assert.equal(extractFromCommand(output, { extract: "mcp_chars" }), null);
});
