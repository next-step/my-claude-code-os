/**
 * 문서 낡음 감지(.claude/lib/freshness.js)의 인수 테스트.
 *
 * "AC-<번호>" 접두사는 이 저장소의 다른 테스트와 같은 이유로 유지한다 —
 * 실패 원장에서 어떤 인수기준이 깨졌는지 바로 추적하기 위함이다.
 *
 * AC-1~6은 가짜 fs로 순수 로직만 본다. AC-7~9는 **실제 저장소**를 대상으로 도는
 * 회귀 테스트다(context-inject.test.js의 AC-16·17과 같은 성격) — 문서가 낡는 순간
 * 여기서 빨간불이 뜨는 것이 이 파일의 존재 이유다.
 *
 * 실행: node --test .claude/tests/freshness.test.js
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const {
  countTests,
  countDiagrams,
  formatFact,
  textClaimsValue,
  normalizeForMatch,
  checkRegistry,
  findUnregisteredNumbers,
  resolveFact,
  loadRegistry,
  auditFreshness,
} = require("../lib/freshness.js");

const PROJECT_DIR = path.resolve(__dirname, "..", "..");

/** 경로 → 내용 맵으로 가짜 fs를 만든다. context-map.test.js와 같은 방식이다. */
function fakeFs(files, dirs = {}) {
  return {
    existsSync: (p) => Object.prototype.hasOwnProperty.call(files, p) || Object.prototype.hasOwnProperty.call(dirs, p),
    readFileSync: (p) => {
      if (!Object.prototype.hasOwnProperty.call(files, p)) throw new Error(`ENOENT: ${p}`);
      return files[p];
    },
    readdirSync: (p) => (dirs[p] || []).map((name) => ({ name, isFile: () => true, isDirectory: () => false })),
  };
}

test("AC-1: countTests는 .test.js 파일 수와 최상위 test( 선언 수를 센다", () => {
  const dir = "/repo/.claude/tests";
  const files = {
    [path.join(dir, "a.test.js")]: 'test("AC-1: 하나", () => {});\ntest("AC-2: 둘", () => {});\n',
    // 들여쓰기된 test( 와 주석 속 test( 는 세지 않는다 — 최상위 선언만 본다
    [path.join(dir, "b.test.js")]: 'test("셋", () => {\n  test("중첩은 안 셈", () => {});\n});\n// test("주석", ...)\n',
    [path.join(dir, "helper.js")]: "module.exports = {};",
  };
  const fs = fakeFs(files, { [dir]: ["a.test.js", "b.test.js", "helper.js"] });
  assert.deepEqual(countTests(dir, fs), { testFileCount: 2, testCount: 3 });
});

test("AC-1b: 테스트 디렉터리가 없으면 예외 없이 0을 돌려준다", () => {
  assert.deepEqual(countTests("/nope", fakeFs({})), { testFileCount: 0, testCount: 0 });
});

test("AC-2: countDiagrams는 .mmd만 세고 생성물 .svg는 세지 않는다", () => {
  const dir = "/repo/docs/diagrams";
  const fs = fakeFs({}, { [dir]: ["01.mmd", "01.svg", "02.mmd", "README.md", "mermaid-config.json"] });
  assert.equal(countDiagrams(dir, fs), 2);
});

test("AC-3: textClaimsValue는 숫자 경계를 보고, 더 긴 숫자의 일부에 걸리지 않는다", () => {
  assert.equal(textClaimsValue("스킬 14개", "14"), true);
  assert.equal(textClaimsValue("항목 144개", "14"), false);
  assert.equal(textClaimsValue("자수 1,145", "14"), false);
  assert.equal(textClaimsValue("합계 15,259자", "15,259"), true);
  assert.equal(textClaimsValue("합계 115,259자", "15,259"), false);
});

test("AC-3b: 소수점 앞자리에 걸려 낡음을 놓치지 않는다 (08의 '4.3배' 함정)", () => {
  // 08 개요에는 "상시의 4.3배"가 있다. 경계만 보면 agentCount=4가 여기 걸려
  // 에이전트 수가 실제로 낡아도 통과해 버린다. 느슨한 일치는 검사를 통과시키는
  // 방향으로 틀리기 때문에 더 위험하다.
  assert.equal(textClaimsValue("온디맨드는 상시의 4.3배", "4"), false);
  assert.equal(textClaimsValue("상시의 4.3배 · 에이전트 4개", "4"), true);
});

test("AC-3c: pattern을 주면 그 문맥에서만 값을 인정한다 (파일 단위 검사의 실패를 막는다)", () => {
  // 실제로 겪은 실패다. 08 다이어그램의 "스킬 14개"를 "스킬 99개"로 바꿔도, 같은 파일
  // 다른 줄의 "14개 · 스킬 선택의 유일한 근거" 때문에 검사가 통과해 버렸다.
  // 값만 찾으면 주장이 여러 개인 문서에서 원리적으로 무력하다.
  const doc = "스킬 99개<br/>같은 대화\n14개 · 스킬 선택의 유일한 근거";
  assert.equal(textClaimsValue(doc, "14"), true, "값만 보면 통과해 버린다 (이것이 문제였다)");
  assert.equal(textClaimsValue(doc, "14", "스킬 {v}개"), false, "문맥을 보면 낡음이 드러나야 한다");
  assert.equal(textClaimsValue("스킬 14개<br/>같은 대화", "14", "스킬 {v}개"), true);
});

test("AC-3d: normalizeForMatch는 .svg의 태그·공백만 걷어내고 다른 확장자는 건드리지 않는다", () => {
  // mermaid가 단어마다 tspan으로 쪼개 놓아서, 정규화 없이는 "스킬 14개"가 통째로 없다.
  const svg = '<text><tspan>스킬</tspan><tspan> 14개</tspan></text>';
  assert.equal(normalizeForMatch(svg, "a.svg"), "스킬14개");
  assert.equal(normalizeForMatch("스킬 14개", "a.mmd"), "스킬 14개");
  // 정규화한 본문과 정규화한 패턴이 짝을 이뤄야 한다
  assert.equal(
    textClaimsValue(normalizeForMatch(svg, "a.svg"), "14", normalizeForMatch("스킬 {v}개", "a.svg")),
    true
  );
});

test("AC-4: formatFact는 plain과 comma 표기를 구분한다", () => {
  assert.equal(formatFact(15259, "comma"), "15,259");
  assert.equal(formatFact(15259, "plain"), "15259");
  assert.equal(formatFact(14, "plain"), "14");
});

test("AC-5: checkRegistry는 일치·불일치·파일없음·알 수 없는 사실을 갈라서 보고한다", () => {
  const facts = { skillCount: 14, hookCount: 8 };
  const fs = fakeFs({
    "/repo/docs/good.mmd": "스킬 14개",
    "/repo/docs/stale.mmd": "훅 4개",
  });
  const registry = [
    { file: "docs/good.mmd", fact: "skillCount", format: "plain", label: "맞는 것" },
    { file: "docs/stale.mmd", fact: "hookCount", format: "plain", label: "낡은 것" },
    { file: "docs/gone.mmd", fact: "skillCount", format: "plain", label: "없는 파일" },
    { file: "docs/good.mmd", fact: "오타난이름", format: "plain", label: "오타" },
  ];
  const r = checkRegistry({ facts, registry, projectDir: "/repo", fsOverrides: fs });

  assert.deepEqual(r.ok, ["맞는 것"]);
  assert.equal(r.stale.length, 1);
  assert.match(r.stale[0], /낡은 것/);
  assert.equal(r.missingFile.length, 1);
  assert.match(r.missingFile[0], /없는 파일/);
  assert.equal(r.unknownFact.length, 1);
  assert.match(r.unknownFact[0], /오타난이름/);
});

test("AC-5b: 등록된 파일이 없으면 조용히 통과시키지 않는다", () => {
  // AC-B5(context-map.test.js:185)는 다이어그램이 없으면 return 해버려서,
  // 파일을 지우면 검사 자체가 사라지는 사각지대가 있었다. 그 실수를 반복하지 않는다.
  const r = checkRegistry({
    facts: { skillCount: 14 },
    registry: [{ file: "docs/gone.mmd", fact: "skillCount", format: "plain" }],
    projectDir: "/repo",
    fsOverrides: fakeFs({}),
  });
  assert.equal(r.ok.length, 0);
  assert.equal(r.missingFile.length, 1);
});

test("AC-6: loadRegistry는 배열과 {claims} 형식을 모두 받고, 파일이 없으면 빈 배열이다", () => {
  const p = "/repo/docs/facts-registry.json";
  const asArray = loadRegistry({
    projectDir: "/repo",
    fsOverrides: fakeFs({ [p]: '[{"file":"a","fact":"skillCount"}]' }),
  });
  assert.equal(asArray.length, 1);

  const asObject = loadRegistry({
    projectDir: "/repo",
    fsOverrides: fakeFs({ [p]: '{"_why":["설명"],"claims":[{"file":"a","fact":"skillCount"}]}' }),
  });
  assert.equal(asObject.length, 1);

  assert.deepEqual(loadRegistry({ projectDir: "/repo", fsOverrides: fakeFs({}) }), []);
});

// --- 여기부터 실제 저장소 회귀 (context-inject.test.js AC-16·17과 같은 성격) ---

test("AC-7: 이 저장소의 등록된 주장이 전부 실측과 일치한다", () => {
  const r = auditFreshness({ projectDir: PROJECT_DIR });
  assert.deepStrictEqual(
    [...r.stale, ...r.missingFile, ...r.unknownFact],
    [],
    "문서에 박힌 수치가 낡았습니다. .mmd 를 고친 뒤 docs/diagrams/README.md 의 명령으로 .svg 를 다시 생성하세요"
  );
});

test("AC-8: 등록부가 비어 있지 않고, 개요 다이어그램과 그 생성물이 등록돼 있다", () => {
  const registry = loadRegistry({ projectDir: PROJECT_DIR });
  assert.ok(registry.length >= 10, `등록된 주장이 ${registry.length}개뿐입니다`);

  // .mmd만 등록하면 "소스는 고쳤는데 .svg 재생성을 잊는" 실수를 못 잡는다.
  // docs-diagrams.md가 경고하는 실패라 생성물도 함께 등록한다.
  for (const needle of ["08-context-overview.mmd", "08-context-overview.svg", "07-context-system.mmd"]) {
    assert.ok(
      registry.some((c) => c.file.includes(needle)),
      `${needle} 가 등록부에 없습니다`
    );
  }
});

test("AC-9: 결과에 '등록된 것만 본다'는 한계가 함께 실린다", () => {
  // context-inject.js가 "위반 0개가 도달을 뜻하지 않는다"를 결과에 싣는 것과 같은 이유다.
  // 초록불을 품질 보증으로 읽는 것이 이 저장소가 반복해 겪은 실패다.
  const r = auditFreshness({ projectDir: PROJECT_DIR });
  assert.match(r.caveat, /등록/);
  assert.equal(typeof r.registered, "number");
});

// --- 미등록 수치 탐지 (2026-09-08 추가) ---
// 등록부만 보는 검사에는 "새 수치를 적고 등록을 잊으면 조용히 낡는다"는 구멍이 있었다.
// 범위를 다이어그램으로 좁히면 성립한다는 것을 실측으로 확인하고 추가했다.

/** 다이어그램 하나짜리 가짜 저장소. */
function diagramRepo(content, name = "x.mmd") {
  const dir = "/repo/docs/diagrams";
  return {
    existsSync: (p) => p === dir,
    readdirSync: () => [{ name, isFile: () => true, isDirectory: () => false }],
    readFileSync: () => content,
  };
}

test("AC-10: classDef·linkStyle 줄의 색상 hex를 수치로 세지 않는다", () => {
  const mmd = [
    'flowchart LR',
    '    A["아무 숫자 없음"]',
    '    classDef human fill:#fde68a,stroke:#b45309,color:#111827;',
    '    linkStyle 7 stroke:#b91c1c,stroke-width:2px;',
  ].join("\n");
  const r = findUnregisteredNumbers({ projectDir: "/repo", registry: [], fsOverrides: diagramRepo(mmd) });
  assert.deepEqual(r.unregistered, []);
});

test("AC-11: 라벨(큰따옴표) 밖의 숫자는 보지 않는다", () => {
  // mermaid 문법(노드 id, linkStyle 인덱스)은 사실 주장이 아니다.
  const r = findUnregisteredNumbers({
    projectDir: "/repo",
    registry: [],
    fsOverrides: diagramRepo('flowchart LR\n    N12 --> N34\n    A["글자만"]'),
  });
  assert.deepEqual(r.unregistered, []);
});

test("AC-12: 단계번호·절참조·연도·날짜·AC범위는 내장 면제된다", () => {
  const mmd = 'flowchart LR\n    A["05 구현 · 10.3절 · 2026-09-08 · AC-1~17 · 2026"]';
  const r = findUnregisteredNumbers({ projectDir: "/repo", registry: [], fsOverrides: diagramRepo(mmd) });
  assert.deepEqual(r.unregistered, []);
});

test("AC-13: 등록된 패턴이 덮는 숫자는 미등록으로 세지 않는다", () => {
  const mmd = 'flowchart LR\n    A["스킬 14개"]';
  const registry = [{ file: "docs/diagrams/x.mmd", fact: "skillCount", format: "plain", pattern: "스킬 {v}개" }];
  assert.deepEqual(
    findUnregisteredNumbers({ projectDir: "/repo", registry, fsOverrides: diagramRepo(mmd) }).unregistered,
    []
  );
  // 등록이 없으면 잡혀야 한다 — 이게 이 검사의 존재 이유다
  assert.equal(
    findUnregisteredNumbers({ projectDir: "/repo", registry: [], fsOverrides: diagramRepo(mmd) }).unregistered.length,
    1
  );
});

test("AC-14: 면제는 값으로 통과시키되, why가 없으면 거부한다", () => {
  const mmd = 'flowchart LR\n    A["툴 42개"]';
  const good = findUnregisteredNumbers({
    projectDir: "/repo",
    registry: [],
    exemptions: [{ file: "docs/diagrams/x.mmd", value: "42", why: "외부 서버 값이라 잴 수 없다" }],
    fsOverrides: diagramRepo(mmd),
  });
  assert.deepEqual(good.unregistered, []);
  assert.deepEqual(good.badExemptions, []);

  // 이유 없는 면제는 검사를 조용히 무력화하는 가장 쉬운 길이라 거부한다.
  const bad = findUnregisteredNumbers({
    projectDir: "/repo",
    registry: [],
    exemptions: [{ file: "docs/diagrams/x.mmd", value: "42", why: "  " }],
    fsOverrides: diagramRepo(mmd),
  });
  assert.equal(bad.badExemptions.length, 1);
  assert.equal(bad.unregistered.length, 1, "why 없는 면제는 면제로 쳐 주지 않는다");
});

test("AC-15: guidelineChars처럼 여러 개짜리 사실은 key로 지목해야 한다", () => {
  const facts = { guidelineChars: { "requirement-gate": 1821 } };
  assert.equal(resolveFact(facts, { fact: "guidelineChars", key: "requirement-gate" }).value, 1821);
  assert.match(resolveFact(facts, { fact: "guidelineChars" }).error, /key가 필요/);
  assert.match(resolveFact(facts, { fact: "guidelineChars", key: "없는지침" }).error, /없습니다/);
});

test("AC-16: 이 저장소의 다이어그램에 미등록·불량면제 수치가 없다", () => {
  const r = auditFreshness({ projectDir: PROJECT_DIR });
  assert.deepStrictEqual(
    [...r.unregistered, ...r.badExemptions],
    [],
    "다이어그램에 등록도 면제도 되지 않은 숫자가 있습니다. docs/facts-registry.json 의 claims 또는 exemptions에 넣으세요"
  );
});
