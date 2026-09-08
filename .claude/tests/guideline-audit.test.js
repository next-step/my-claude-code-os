/**
 * 지침 모순 검사(.claude/lib/guideline-audit.js)의 인수 테스트.
 *
 * AC-1~9는 가짜 fs로 순수 로직만 본다. AC-10~12는 **실제 저장소**를 대상으로 도는
 * 회귀 테스트다(context-inject.test.js AC-16·17, freshness.test.js AC-7과 같은 성격).
 *
 * 실행: node --test .claude/tests/guideline-audit.test.js
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const {
  extractCitations,
  resolveCitation,
  checkConstants,
  checkOverlaps,
  auditGuidelines,
} = require("../lib/guideline-audit.js");

const PROJECT_DIR = path.resolve(__dirname, "..", "..");

function fakeFs(files) {
  return {
    existsSync: (p) => Object.prototype.hasOwnProperty.call(files, p),
    readFileSync: (p) => {
      if (!Object.prototype.hasOwnProperty.call(files, p)) throw new Error(`ENOENT: ${p}`);
      return files[p];
    },
    readdirSync: () => [],
  };
}

test("AC-1: extractCitations는 백틱 스팬만 뽑고 줄바꿈을 넘지 않는다", () => {
  const text = "본문 `a.md` 와 `b/c.js` 를 본다.\n`d.md`\n백틱 없는 e.md 는 무시";
  assert.deepEqual(extractCitations(text), ["a.md", "b/c.js", "d.md"]);
});

test("AC-2: 글로브·플레이스홀더·날짜템플릿은 인용으로 해석하지 않는다", () => {
  const opts = { projectDir: "/repo", existsSync: () => false };
  for (const token of [".claude/lib/*.js", ".claude/tests/<이름>.test.js", "docs/interview/YYYY-MM-DD-<slug>.md"]) {
    assert.ok(resolveCitation(token, opts).skipped, `${token} 은 건너뛰어야 한다`);
  }
});

test("AC-3: 확장자 없는 토큰은 산문일 수 있으므로 건너뛴다", () => {
  const opts = { projectDir: "/repo", existsSync: () => false };
  for (const token of ["spec-decompose", "git status", "AskUserQuestion", "파일:줄", "brainstorming"]) {
    assert.ok(resolveCitation(token, opts).skipped, `${token} 은 건너뛰어야 한다`);
  }
});

test("AC-3b: 확장자 표기와 총칭 SKILL.md는 인용이 아니다 (실제 오탐 5건에서 나온 규칙)", () => {
  // 첫 구현이 "`.mmd`가 원본, `.svg`는 생성물"의 `.mmd`·`.svg`와 총칭 `SKILL.md`를
  // 끊어진 참조로 잘못 잡았다. 오탐을 내는 검사는 반드시 무시당한다.
  const opts = { projectDir: "/repo", existsSync: () => false };
  assert.ok(resolveCitation(".mmd", opts).skipped);
  assert.ok(resolveCitation(".svg", opts).skipped);
  assert.ok(resolveCitation("SKILL.md", opts).skipped);
});

test("AC-4: 줄번호 꼬리를 떼고, 스킬 접두사가 빠진 경로도 풀어 준다", () => {
  const existing = new Set(["/repo/.claude/skills/atdd-status/SKILL.md"]);
  const r = resolveCitation("atdd-status/SKILL.md:31,37-38", {
    projectDir: "/repo",
    existsSync: (p) => existing.has(p),
  });
  assert.equal(r.resolved, ".claude/skills/atdd-status/SKILL.md");
});

test("AC-5: 실재하지 않는 파일 인용은 missing으로 잡는다", () => {
  const r = resolveCitation("없는지침.md", { projectDir: "/repo", existsSync: () => false });
  assert.equal(r.missing, "없는지침.md");
});

test("AC-6: 상수가 모든 선언 자리에서 같으면 위반이 없다", () => {
  const fsOverrides = fakeFs({
    "/repo/a.md": "한 라운드 최대 3문항.",
    "/repo/b.md": "한 라운드에 최대 3개.",
  });
  const constants = [
    {
      name: "질문 상한",
      value: 3,
      sites: [
        { file: "a.md", pattern: "한 라운드 최대 {v}문항" },
        { file: "b.md", pattern: "한 라운드에 최대 {v}개" },
      ],
    },
  ];
  const r = checkConstants({ projectDir: "/repo", constants, fsOverrides });
  assert.deepEqual(r.mismatched, []);
});

test("AC-7: 한 자리만 값이 바뀌면 상수 불일치로 잡는다", () => {
  // 이것이 이 검사의 존재 이유다 — 같은 규칙이 평균 3곳에 흩어져 있고,
  // 하나만 고치면 지금까지는 아무 테스트도 잡지 않았다.
  const fsOverrides = fakeFs({
    "/repo/a.md": "한 라운드 최대 4문항.",
    "/repo/b.md": "한 라운드에 최대 3개.",
  });
  const constants = [
    {
      name: "질문 상한",
      value: 3,
      sites: [
        { file: "a.md", pattern: "한 라운드 최대 {v}문항" },
        { file: "b.md", pattern: "한 라운드에 최대 {v}개" },
      ],
    },
  ];
  const r = checkConstants({ projectDir: "/repo", constants, fsOverrides });
  assert.equal(r.mismatched.length, 1);
  assert.match(r.mismatched[0], /a\.md/);
});

test("AC-8: 선언 자리 파일이 없으면 조용히 통과시키지 않는다", () => {
  const r = checkConstants({
    projectDir: "/repo",
    constants: [{ name: "x", value: 1, sites: [{ file: "gone.md", pattern: "{v}회" }] }],
    fsOverrides: fakeFs({}),
  });
  assert.equal(r.missingFile.length, 1);
});

test("AC-9: 주제가 겹치는데 상호 참조가 없으면 note로 남긴다 (위반이 아니다)", () => {
  const dir = "/repo/.claude/context";
  const fsOverrides = fakeFs({
    [path.join(dir, "a.md")]: "짧게 쓴다. 길이는 b.md가 정한다.",
    [path.join(dir, "b.md")]: "근거를 남긴다.", // a.md를 인용하지 않는다
    [path.join(dir, "c.md")]: "무관한 주제.",
  });
  const topics = { a: ["분량"], b: ["분량"], c: ["훅"] };

  const notes = checkOverlaps({ projectDir: "/repo", topics, fsOverrides });
  assert.equal(notes.length, 1, "a↔b만 후보여야 한다 (c는 겹치지 않는다)");
  assert.match(notes[0], /b→a 없음/);

  // 양방향 선언이 있으면 해소된 것으로 본다
  const bothWays = fakeFs({
    [path.join(dir, "a.md")]: "길이는 b.md가 정한다.",
    [path.join(dir, "b.md")]: "무엇을 쓸지는 a.md가 정한다.",
  });
  assert.deepEqual(checkOverlaps({ projectDir: "/repo", topics: { a: ["분량"], b: ["분량"] }, fsOverrides: bothWays }), []);
});

test("AC-9b: resolvedElsewhere에 등록된 쌍은 후보에서 뺀다", () => {
  const dir = "/repo/.claude/context";
  const fsOverrides = fakeFs({
    [path.join(dir, "a.md")]: "수치를 박지 않는다.",
    [path.join(dir, "b.md")]: "잰 값은 로그에 남긴다.",
  });
  const args = { projectDir: "/repo", topics: { a: ["수치"], b: ["수치"] }, fsOverrides };
  assert.equal(checkOverlaps(args).length, 1);
  assert.deepEqual(
    checkOverlaps({ ...args, resolvedElsewhere: [{ pair: ["a", "b"], why: "해소 문구가 대상 문서 안에 있다" }] }),
    []
  );
});

// --- 여기부터 실제 저장소 회귀 ---

test("AC-10: 이 저장소의 지침에 상수 불일치와 끊어진 참조가 없다", () => {
  const r = auditGuidelines({ projectDir: PROJECT_DIR });
  assert.deepStrictEqual(
    r.violations,
    [],
    "지침·스킬에 중복 선언된 값이 어긋났거나, 인용한 파일이 사라졌습니다. docs/guideline-constants.json 참고"
  );
});

test("AC-11: 등록부가 비어 있지 않다", () => {
  const r = auditGuidelines({ projectDir: PROJECT_DIR });
  assert.ok(r.counts.constants >= 5, `등록된 상수가 ${r.counts.constants}개뿐입니다`);
  assert.ok(r.counts.topics >= 5, `주제가 등록된 지침이 ${r.counts.topics}개뿐입니다`);
});

test("AC-12: 결과에 '의미 모순은 판정하지 못한다'는 한계가 함께 실린다", () => {
  // 초록불을 품질 보증으로 읽는 것이 이 저장소가 반복해 겪은 실패다.
  // context-inject.js·freshness.js가 같은 이유로 결과에 한계를 싣는다.
  const r = auditGuidelines({ projectDir: PROJECT_DIR });
  assert.match(r.caveat, /모순/);
  assert.match(r.caveat, /guideline-reviewer/);
});
