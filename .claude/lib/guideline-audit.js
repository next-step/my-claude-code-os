/**
 * 개인 지침(.claude/context/*.md)끼리 어긋났는지 검사한다.
 *
 * ## 무엇이 "모순"인가 — 실측이 예상을 뒤집었다
 *
 * 처음에는 "지침 A와 지침 B가 의미상 반대말을 한다"를 찾으려 했다. 2026-09-08에
 * 지침 9개를 전수로 읽어 보니 **그런 쌍은 사실상 없었다.** 겹치는 8쌍 중 3쌍은
 * 이미 우선순위 선언으로 해소돼 있었고(`explanation-style.md`와
 * `response-brevity.md`의 양방향 선언), 2쌍은 축이 달라 무해했다.
 *
 * 대신 진짜 위험은 다른 데 있었다 — **같은 규칙이 여러 파일에 값으로 중복 선언돼
 * 있고, 하나만 바꾸면 조용히 어긋난다.** 실측 8종이 평균 3곳씩 흩어져 있었다
 * (슬롯 6개/3개 이상, 한 라운드 3문항, 재시도 3회 …). 지금은 전부 일치하지만
 * 어긋나도 아무 테스트가 잡지 않았다.
 *
 * 그래서 이 파일이 보는 것은 셋이다.
 *
 *   ① 상수 불일치  — 등록된 규칙 값이 선언된 모든 자리에서 같은가   (violation)
 *   ② 참조 무결성  — 지침이 인용한 파일이 실재하는가              (violation)
 *   ③ 겹침·우선순위 — 주제가 겹치는 쌍에 상호 선언이 있는가        (note)
 *
 * ## 이 파일이 판정하지 **못하는** 것
 *
 * **겹침이 충돌인지 역할 분담인지 기계는 못 가른다.** `hook-discipline`과
 * `code-vs-instruction`은 키워드가 겹치지만 실제로는 상보적이다 — 전자는 훅/스킬 축,
 * 후자는 로직/지시문 축으로 서로 다른 것을 자른다. 그래서 ③은 위반이 아니라 note다.
 * 실제 판정은 `guideline-reviewer` 서브에이전트에게 넘긴다.
 *
 * 자유 텍스트에서 의미를 읽는 일이 정규식으로 안 된다는 것은 이 저장소가 네 번
 * 실측했다(`freshness.js` 머리말, `docs/context-ab-test.md` 실험 1~4).
 * 기계는 후보를 좁히는 데까지만 한다.
 */
const fs = require("node:fs");
const path = require("node:path");

const { listGuidelineFiles } = require("./context-inject.js");
const { textClaimsValue } = require("./freshness.js");

/** 인용으로 해석하지 않는 토큰. 전부 실제 오탐 자리에서 나왔다. */
const NOT_A_REFERENCE = [
  /[*<>]/, // 글로브(.claude/lib/*.js), 플레이스홀더(<이름>.test.js)
  /YYYY|MM|DD/, // 날짜 템플릿(docs/interview/YYYY-MM-DD-<slug>.md)
];
/** 이 확장자로 끝나는 토큰만 파일 인용으로 본다. 확장자 없는 것은 산문일 수 있다. */
const REFERENCE_EXT = /\.(md|js|json|mmd|svg)$/;
/** 바로 붙은 줄번호 꼬리(`SKILL.md:31,37-38`)를 떼어 낸다. */
const LINE_SUFFIX = /:[\d,\-\s]+$/;
/** 확장자 없는 파일명은 여기서 찾는다. */
const SEARCH_DIRS = [
  ".claude/context",
  ".claude/lib",
  ".claude/hooks",
  ".claude/tests",
  ".claude/agents",
  "docs",
  "docs/diagrams",
  "",
];

/** 지침 본문에서 백틱 스팬을 뽑는다. 이 저장소의 인용은 전부 백틱 안에 있다. */
function extractCitations(text) {
  return [...text.matchAll(/`([^`\n]+)`/g)].map((m) => m[1].trim());
}

/**
 * 인용 토큰 하나를 실제 경로로 풀어 본다.
 *
 * **해석 가능한 형식만 검사한다.** 이 저장소의 인용 형식은 10종이고 그중 6종은
 * 애초에 실재 파일이 아니다(예시·반례·글로브·플레이스홀더·외부 프로젝트·스킬 이름).
 * 그걸 다 풀려다 오탐을 내면 검사는 반드시 무시당하고, 무시당하는 검사는 없는 것만
 * 못하다. 그래서 못 푸는 것은 위반이 아니라 `skipped`로 보고한다.
 */
function resolveCitation(token, { projectDir, existsSync = fs.existsSync }) {
  if (NOT_A_REFERENCE.some((re) => re.test(token))) return { skipped: "글로브·플레이스홀더" };

  const bare = token.replace(LINE_SUFFIX, "");
  if (!REFERENCE_EXT.test(bare)) return { skipped: "확장자 없음 — 스킬 이름이나 산문일 수 있다" };

  // 아래 두 규칙은 실제 오탐에서 나왔다. 첫 구현이 5건을 잘못 잡았고, 오탐을 내는
  // 검사는 반드시 무시당하므로 규칙을 좁혔다.
  //   `.mmd`, `.svg` — "`.mmd`가 원본, `.svg`는 생성물" 처럼 확장자 자체를 가리키는 표기
  //   `SKILL.md`     — 어느 스킬인지 지목되지 않은 총칭. 스킬마다 하나씩 있어 해석 불가
  if (!bare.includes("/") && bare.startsWith(".")) return { skipped: "확장자 표기 — 파일 인용이 아니다" };
  if (bare === "SKILL.md") return { skipped: "총칭 SKILL.md — 어느 스킬인지 지목되지 않았다" };

  const candidates = bare.includes("/")
    ? [bare, path.posix.join(".claude/skills", bare)] // `atdd-status/SKILL.md`처럼 접두사가 빠진 형태
    : SEARCH_DIRS.map((d) => (d ? path.posix.join(d, bare) : bare));

  for (const rel of candidates) {
    if (existsSync(path.join(projectDir, rel))) return { resolved: rel };
  }
  return { missing: bare };
}

/** ② 참조 무결성 — 지침이 인용한 파일이 실재하는가. */
function checkReferences({ projectDir, fsOverrides = {} }) {
  const { existsSync = fs.existsSync, readFileSync = fs.readFileSync } = fsOverrides;
  const contextDir = path.join(projectDir, ".claude", "context");
  const broken = [];
  const skipped = [];

  for (const name of listGuidelineFiles(contextDir, fsOverrides)) {
    const text = readFileSync(path.join(contextDir, name), "utf-8");
    for (const token of extractCitations(text)) {
      const r = resolveCitation(token, { projectDir, existsSync });
      if (r.missing) broken.push(`${name}: \`${token}\` 이(가) 실재하지 않습니다`);
      else if (r.skipped) skipped.push(`${name}: \`${token}\` (${r.skipped})`);
    }
  }
  return { broken, skipped };
}

/**
 * ① 상수 불일치 — 등록된 규칙 값이 선언된 모든 자리에서 같은가.
 *
 * `freshness.js`의 `textClaimsValue`를 그대로 재사용한다. 값이 아니라 **문맥**으로
 * 대조해야 하는 이유는 이미 실측으로 겪었다 — 값만 찾으면 같은 파일 다른 줄의
 * 무관한 숫자에 걸려 통과해 버린다.
 */
function checkConstants({ projectDir, constants, fsOverrides = {} }) {
  const { existsSync = fs.existsSync, readFileSync = fs.readFileSync } = fsOverrides;
  const mismatched = [];
  const missingFile = [];
  const cache = new Map();

  for (const c of constants) {
    for (const site of c.sites) {
      const abs = path.join(projectDir, site.file);
      if (!cache.has(abs)) cache.set(abs, existsSync(abs) ? readFileSync(abs, "utf-8") : null);
      const text = cache.get(abs);
      if (text === null) {
        missingFile.push(`${c.name}: 선언 자리 ${site.file} 이(가) 없습니다`);
        continue;
      }
      const expected = String(c.value);
      if (!textClaimsValue(text, expected, site.pattern)) {
        mismatched.push(
          `${c.name}: ${site.file} 이(가) "${site.pattern.replace("{v}", expected)}"를 더 이상 말하지 않습니다`
        );
      }
    }
  }
  return { mismatched, missingFile };
}

/**
 * ③ 겹침·우선순위 — 주제가 겹치는 지침 쌍에 상호 참조가 있는가.
 *
 * 상호 참조가 곧 우선순위 선언은 아니다. 하지만 **서로를 언급조차 하지 않는 겹침**은
 * 확실히 미해소다. 그 정도만 기계가 좁히고, 실제 판정은 리뷰어에게 넘긴다.
 * 위반이 아니라 note인 이유는 겹침이 충돌이 아니라 역할 분담일 수 있어서다.
 */
function checkOverlaps({ projectDir, topics, resolvedElsewhere = [], fsOverrides = {} }) {
  const { readFileSync = fs.readFileSync } = fsOverrides;
  const contextDir = path.join(projectDir, ".claude", "context");
  const names = Object.keys(topics);
  const texts = {};
  for (const n of names) {
    try {
      texts[n] = readFileSync(path.join(contextDir, `${n}.md`), "utf-8");
    } catch {
      texts[n] = "";
    }
  }

  const notes = [];
  for (let i = 0; i < names.length; i++) {
    for (let j = i + 1; j < names.length; j++) {
      const [a, b] = [names[i], names[j]];
      const shared = topics[a].filter((k) => topics[b].includes(k));
      if (shared.length === 0) continue;
      if (resolvedElsewhere.some((r) => r.pair.includes(a) && r.pair.includes(b))) continue;

      const aCitesB = texts[a].includes(`${b}.md`);
      const bCitesA = texts[b].includes(`${a}.md`);
      if (aCitesB && bCitesA) continue; // 양방향 선언 — 해소된 것으로 본다
      notes.push(
        `${a} ↔ ${b}: 주제가 겹치는데(${shared.join(", ")}) 상호 참조가 없습니다` +
          ` — ${aCitesB ? "" : `${a}→${b} 없음 `}${bCitesA ? "" : `${b}→${a} 없음`}`
      );
    }
  }
  return notes;
}

/** 등록부를 읽는다. 없으면 빈 구조 — 등록부 없는 저장소에서도 돌아야 한다. */
function loadGuidelineRegistry({ projectDir, fsOverrides = {} }) {
  const { existsSync = fs.existsSync, readFileSync = fs.readFileSync } = fsOverrides;
  const p = path.join(projectDir, "docs", "guideline-constants.json");
  if (!existsSync(p)) return { constants: [], topics: {}, resolvedElsewhere: [] };
  const parsed = JSON.parse(readFileSync(p, "utf-8"));
  return {
    constants: parsed.constants || [],
    topics: parsed.topics || {},
    resolvedElsewhere: parsed.resolvedElsewhere || [],
  };
}

/** 스킬·테스트가 함께 쓰는 한 줄 진입점. */
function auditGuidelines({ projectDir, fsOverrides = {} }) {
  const reg = loadGuidelineRegistry({ projectDir, fsOverrides });
  const refs = checkReferences({ projectDir, fsOverrides });
  const consts = checkConstants({ projectDir, constants: reg.constants, fsOverrides });
  const overlapNotes = checkOverlaps({ ...reg, projectDir, fsOverrides });

  return {
    violations: [...consts.mismatched, ...consts.missingFile, ...refs.broken],
    notes: overlapNotes,
    skipped: refs.skipped,
    counts: { constants: reg.constants.length, topics: Object.keys(reg.topics).length },
    // 결과에 한계를 함께 싣는다. context-inject.js·freshness.js가 같은 이유로 그렇게 한다 —
    // 초록불을 품질 보증으로 읽는 것이 이 저장소가 반복해 겪은 실패다.
    caveat:
      "위반 0개는 '지침이 서로 모순되지 않는다'는 뜻이 아닙니다. " +
      "등록된 상수와 해석 가능한 인용만 봅니다. 의미가 서로 반대인지는 기계가 판정하지 못하며, " +
      "notes에 오른 쌍은 guideline-reviewer 서브에이전트가 판정해야 합니다.",
  };
}

module.exports = {
  extractCitations,
  resolveCitation,
  checkReferences,
  checkConstants,
  checkOverlaps,
  loadGuidelineRegistry,
  auditGuidelines,
};
