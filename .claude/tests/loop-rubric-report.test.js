/**
 * 지침 구조 수치 CLI(.claude/lib/loop-rubric-report.js)의 인수 테스트.
 *
 * 이 파일이 존재하는 이유는 실주행에서 드러난 결함 하나다 — 가드가 응답만 보는 탓에
 * 지침이 조항 0개로 붕괴했는데도 셋 다 통과했다. 그래서 출력 형식이 랄프 루프의
 * 파서에 실제로 걸리는지를 문자열로 다시 적지 않고 통과시켜 확인한다.
 *
 * 실행: node --test .claude/tests/loop-rubric-report.test.js
 */
const test = require("node:test");
const assert = require("node:assert/strict");

const { formatRubricReport, readDocs } = require("../lib/loop-rubric-report.js");
const { extractFromCommand } = require("../lib/ralph-loop.js");

const DOCS = {
  "a.md": "# 가\n- 근거를 `stats.js:46`으로 인용한다.\n- 한계를 먼저 말한다.\n\n근거: `OS.md`.\n",
  "b.md": "# 나\n- 훅은 막지 않는다.\n",
};

test("AC-1 여섯 수치를 `# 이름 값` 형식으로 찍는다", () => {
  const lines = formatRubricReport(DOCS).split("\n");
  assert.equal(lines.length, 6);
  assert.ok(lines.every((l) => /^# [a-z_]+ \d+$/.test(l)), `형식이 어긋났습니다: ${lines.join(" | ")}`);
});

test("AC-2 랄프 루프의 파서가 여섯 수치를 전부 읽어 낸다", () => {
  const out = formatRubricReport(DOCS);
  for (const name of ["guideline_files", "guideline_chars", "clause_count", "citation_count", "caveat_lines", "evidence_lines"]) {
    assert.equal(typeof extractFromCommand(out, { extract: name }), "number", `${name}을 못 읽었습니다`);
  }
});

test("AC-3 조항이 0이 되면 clause_count가 0으로 드러난다", () => {
  // 실주행에서 지침이 불릿 없는 한 문장으로 붕괴했는데 응답 기반 가드는 전부 통과했다.
  const collapsed = { "a.md": "근거를 인용한다. 한계를 말한다.\n" };
  const out = formatRubricReport(collapsed);
  assert.equal(extractFromCommand(out, { extract: "clause_count" }), 0);
});

test("AC-4 파일을 지워 수치를 0으로 만드는 우회는 guideline_files로 드러난다", () => {
  const out = formatRubricReport({ "a.md": DOCS["a.md"] });
  assert.equal(extractFromCommand(out, { extract: "guideline_files" }), 1);
});

test("AC-5 디렉터리가 없으면 빈 결과를 내고 터지지 않는다", () => {
  const docs = readDocs("/없는/경로", { existsSync: () => false, readdirSync: () => [], readFileSync: () => "" });
  assert.deepEqual(docs, {});
  assert.equal(extractFromCommand(formatRubricReport(docs), { extract: "clause_count" }), 0);
});

test("AC-6 .md가 아닌 파일은 세지 않는다", () => {
  const docs = readDocs("/d", {
    existsSync: () => true,
    readdirSync: () => ["a.md", "README.txt", "b.json"],
    readFileSync: () => "- 가\n",
  });
  assert.deepEqual(Object.keys(docs), ["a.md"]);
});
