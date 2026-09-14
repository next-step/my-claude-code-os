/**
 * 회차별 관측 루브릭(.claude/lib/loop-rubric.js)의 인수 테스트.
 *
 * 이 루브릭은 **판정이 아니라 기록**이다. 그래서 테스트가 가장 신경 쓰는 것은
 * 점수가 좋아 보이게 만드는 실수다 — 0으로 나누기, null을 0으로 읽기,
 * 대리 지표를 본체로 말하기.
 *
 * 실행: node --test .claude/tests/loop-rubric.test.js
 */
const test = require("node:test");
const assert = require("node:assert/strict");

const { scoreRubric, measureDoc, countClauses } = require("../lib/loop-rubric.js");

const BEFORE = {
  "a.md": [
    "# 제목",
    "",
    "- **결론만 주지 않는다.** 근거를 `stats.js:46`으로 인용한다.",
    "- 한계와 실패를 먼저 말한다. 초록불을 품질 보증으로 포장하지 않는다.",
    "",
    "근거: `OS.md` 2026-08-27.",
  ].join("\n"),
};

test("AC-1 여섯 차원을 내고 그중 하나는 사람 몫으로 비워 둔다", () => {
  const r = scoreRubric({ before: BEFORE, after: BEFORE });
  assert.equal(r.dimensions.length, 6);
  const human = r.dimensions.find((d) => d.direction === "human");
  assert.equal(human.id, "readability");
  assert.equal(human.value, null);
  assert.ok(human.note.includes("null을 점수 0으로 읽지 않는다"));
});

test("AC-2 바뀐 것이 없으면 기계 차원이 전부 1이다", () => {
  const r = scoreRubric({ before: BEFORE, after: BEFORE });
  for (const d of r.dimensions.filter((x) => x.direction !== "human")) {
    assert.equal(d.value, 1, `${d.id}가 1이어야 합니다: ${d.value}`);
  }
});

test("AC-3 근거와 한계를 지우면 해당 차원만 떨어진다", () => {
  const after = { "a.md": "# 제목\n\n- 결론만 준다.\n" };
  const r = scoreRubric({ before: BEFORE, after });
  const by = Object.fromEntries(r.dimensions.map((d) => [d.id, d.value]));
  assert.ok(by.reduction < 1, "자수는 줄어야 합니다");
  assert.equal(by.evidence, 0, "인용과 근거 줄이 사라졌습니다");
  assert.equal(by.caveat, 0, "한계 표지가 사라졌습니다");
});

test("AC-4 기준이 0이면 비율을 만들지 않고 null로 낸다", () => {
  // 0을 1.0으로 채우면 "완벽히 보존했다"로 읽혀 점수가 실제보다 좋아 보인다.
  const before = { "a.md": "그냥 문장.\n" };
  const after = { "a.md": "그냥 문장.\n" };
  const r = scoreRubric({ before, after });
  const evidence = r.dimensions.find((d) => d.id === "evidence");
  assert.equal(evidence.value, null, "인용이 애초에 0개면 보존율을 만들 수 없습니다");
  assert.deepEqual(evidence.raw, { before: 0, after: 0 });
});

test("AC-5 차원마다 무엇의 대리물인지 밝힌다", () => {
  const r = scoreRubric({ before: BEFORE, after: BEFORE });
  for (const d of r.dimensions.filter((x) => x.direction !== "human")) {
    assert.equal(typeof d.proxyFor, "string");
    assert.ok(d.proxyFor.length > 0, `${d.id}에 proxyFor가 있어야 합니다`);
  }
});

test("AC-6 판정이 아니라 기록이라는 사실을 caveat에 싣는다", () => {
  const r = scoreRubric({ before: BEFORE, after: BEFORE });
  assert.ok(r.caveat.includes("판정이 아니다"));
  assert.ok(r.caveat.includes("종료 판정에 쓰이지 않는다"));
});

test("AC-7 조항 수는 불릿과 헤딩을 센다", () => {
  assert.equal(countClauses("# 가\n- 나\n- 다\n평범한 줄\n"), 3);
});

test("AC-8 밀도는 자수당 근거로 재므로 균일하게 깎으면 1 근처가 된다", () => {
  // 감축과 보존을 한 축에서 본다. 절반으로 줄이면서 근거도 절반이면 밀도는 유지된다.
  const before = { "a.md": "근거: `a.js:1`\n".repeat(10) };
  const after = { "a.md": "근거: `a.js:1`\n".repeat(5) };
  const density = scoreRubric({ before, after }).dimensions.find((d) => d.id === "density");
  assert.ok(Math.abs(density.value - 1) < 0.05, `밀도가 1 근처여야 합니다: ${density.value}`);
});

test("AC-9 파일 하나의 원시 수치를 따로 낼 수 있다", () => {
  const m = measureDoc(BEFORE["a.md"]);
  assert.ok(m.chars > 0);
  assert.equal(m.evidenceLines, 1, "`근거:`로 시작하는 줄 하나");
  assert.ok(m.citations >= 1, "`stats.js:46` 인용을 잡아야 합니다");
});
