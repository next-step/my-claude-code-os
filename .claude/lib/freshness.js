/**
 * 문서에 박힌 "사실 주장"이 실측과 어긋났는지 검사한다.
 *
 * ## 왜 필요한가
 *
 * `.claude/context/docs-diagrams.md`가 이미 규칙을 갖고 있다 — "문서에 지금 이 순간의
 * 수치를 박아 넣지 않는다. 수치는 스킬이 실행 시점에 집계한다." 예외는 08 개요
 * 다이어그램 하나뿐이고, 그 예외에도 "낡으면 드러날 경로를 함께 둔다"는 조건이 붙었다.
 *
 * 그런데 2026-09-08 전수 조사에서 20곳 이상이 이미 틀려 있었다. `OS.md:160`은
 * "이전 판 수치가 이미 낡아 있었다 — 셀 때마다 재확인하는 습관을 들인다"고 교훈까지
 * 적어 놓고 **다시 낡았다.** `hook-discipline.md`의 "성실성에 기대면 바쁠 때 빠진다"가
 * 문서 계층에서 그대로 재현된 것이다.
 *
 * ## 설계 — 지우고, 못 지우는 것만 등록한다
 *
 * 낡음을 막는 길은 둘뿐이다: 낡을 수 있는 것을 없애거나, 남는 것을 기계가 감시하거나.
 * 그래서 실행 시점에 답할 수 있는 값은 문서에서 **지웠고**, 지우면 목적이 사라지는
 * 자리(개요 다이어그램)만 `docs/facts-registry.json`에 **등록**해 이 파일이 감시한다.
 *
 * ## 등록을 잊는 것까지 잡는다 (2026-09-08 추가)
 *
 * 처음에는 "등록되지 않은 수치는 감지하지 못한다"를 한계로 적어 두고 시도하지
 * 않았다. 다시 재 보니 **범위를 좁히면 성립했다.**
 *
 *   다이어그램 소스 8개          잔여 숫자 21개   → 성립
 *   스킬 본문 14개               잔여 숫자 214개  → 불가 (대부분 목록 번호)
 *
 * 그래서 다이어그램 안에서는 등록도 면제도 되지 않은 숫자를 찾아낸다
 * (`findUnregisteredNumbers`). 범위를 다이어그램으로 한정한 것은 타협이 아니다 —
 * `docs-diagrams.md`가 수치를 허용한 자리가 거기뿐이고, 나머지 문서는 애초에
 * 수치를 담으면 안 된다.
 *
 * ## 그래도 검증하지 **못하는** 것
 *
 * **다이어그램 밖의 수치는 보지 않는다.** `OS.md`나 새 `docs/*.md`에 숫자를 넣으면
 * 여전히 조용히 낡는다. 범위를 넓히면 오탐이 압도해(실측 214개) 검사가 무시당하고,
 * 무시당하는 검사는 없는 것만 못하다. 자유 텍스트에서 "이 숫자가 무엇을 주장하는가"를
 * 알아내는 것은 정규식으로 풀 수 없다 — 이 저장소가 네 번 확인한 사실이다
 * (`docs/context-ab-test.md:62-63, 121-125, 190-196` 및 실험 4).
 */
const fs = require("node:fs");
const path = require("node:path");

const { buildContextMap, summarizeBudget } = require("./context-map.js");

/** 등록부가 쓸 수 있는 사실 이름. 오타를 조용히 통과시키지 않으려고 명시해 둔다. */
const KNOWN_FACTS = [
  "skillCount",
  "agentCount",
  "hookCount",
  "guidelineCount",
  "mcpServerCount",
  "diagramCount",
  "testFileCount",
  "testCount",
  "alwaysLoadedTotal",
  "importChars",
  "skillDescChars",
  "agentDescChars",
  "onDemandTotal",
  "onDemandSkillsChars",
  "onDemandAgentsChars",
  // 지침 하나하나의 자수. 등록부가 `"fact": "guidelineChars", "key": "requirement-gate"`
  // 형태로 어느 지침인지 지목한다. 08 개요가 지침별 자수를 나열하는데 지금까지
  // 아무도 감시하지 않았다 — 미등록 수치 탐지가 처음 드러낸 사각지대다.
  "guidelineChars",
];

/**
 * `.claude/tests/*.test.js` 의 파일 수와 그 안에 선언된 테스트 수를 센다.
 *
 * 테스트를 **실행하지 않고** 정적으로 센다. 실행해서 세면 이 검사가 테스트 스위트에
 * 의존하게 되어, 하나가 깨지면 낡음 검사까지 같이 죽는다. 근사값이라는 대가를 치른다 —
 * 반복문으로 동적 생성하는 테스트는 빠진다(현재 저장소에는 없으나 보장은 아니다).
 */
function countTests(testsDir, options = {}) {
  const { existsSync = fs.existsSync, readdirSync = fs.readdirSync, readFileSync = fs.readFileSync } = options;
  if (!existsSync(testsDir)) return { testFileCount: 0, testCount: 0 };

  const files = readdirSync(testsDir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".test.js"))
    .map((entry) => path.join(testsDir, entry.name));

  let testCount = 0;
  for (const file of files) {
    const text = readFileSync(file, "utf-8");
    // 줄 맨 앞의 `test(` 선언만 센다. 주석이나 문자열 속 "test("에 걸리지 않게
    // 들여쓰기 0단계로 한정했다 — 이 저장소의 테스트는 전부 최상위 선언이다.
    const matches = text.match(/^test\s*\(/gm);
    testCount += matches ? matches.length : 0;
  }
  return { testFileCount: files.length, testCount };
}

/** `docs/diagrams/*.mmd` 개수. `.svg`는 생성물이므로 세지 않는다. */
function countDiagrams(diagramsDir, options = {}) {
  const { existsSync = fs.existsSync, readdirSync = fs.readdirSync } = options;
  if (!existsSync(diagramsDir)) return 0;
  return readdirSync(diagramsDir, { withFileTypes: true }).filter(
    (entry) => entry.isFile() && entry.name.endsWith(".mmd")
  ).length;
}

/**
 * 저장소의 현재 사실을 한 사전으로 모은다.
 *
 * 개수·자수는 대부분 `context-map.js`가 이미 재고 있으므로 그대로 재사용한다.
 * 여기서 새로 세는 것은 테스트 수와 다이어그램 수 둘뿐이다.
 */
function collectFacts({ projectDir, fsOverrides = {} }) {
  const map = buildContextMap({ projectDir, fsOverrides });
  const budget = summarizeBudget(map);

  // depth 1은 CLAUDE.md, depth 2는 index.md(레지스트리) 자신이다.
  // 실제 지침은 depth 3부터 — buildContextMap의 hasRealGuidelines와 같은 기준을 쓴다.
  const guidelineCount = map.importTree.nodes.filter(
    (node) => node.depth > 2 && !node.missing && !node.cycle && !node.truncated
  ).length;

  const { testFileCount, testCount } = countTests(path.join(projectDir, ".claude", "tests"), fsOverrides);

  // 지침 이름 → 자수. 파일명에서 .md를 떼어 등록부가 부르기 쉬운 키로 쓴다.
  const guidelineChars = {};
  for (const node of map.importTree.nodes) {
    if (node.depth > 2 && !node.missing && !node.cycle && !node.truncated) {
      guidelineChars[path.basename(node.path, ".md")] = node.chars;
    }
  }

  return {
    guidelineChars,
    skillCount: map.skills.length,
    agentCount: map.agents.length,
    hookCount: map.hooks.length,
    guidelineCount,
    mcpServerCount: budget.unmeasured.mcpServerCount,
    diagramCount: countDiagrams(path.join(projectDir, "docs", "diagrams"), fsOverrides),
    testFileCount,
    testCount,
    alwaysLoadedTotal: budget.alwaysLoaded.total,
    importChars: budget.alwaysLoaded.importChars,
    skillDescChars: budget.alwaysLoaded.skillDescChars,
    agentDescChars: budget.alwaysLoaded.agentDescChars,
    onDemandTotal: budget.onDemand.total,
    onDemandSkillsChars: budget.onDemand.skillsFullChars,
    onDemandAgentsChars: budget.onDemand.agentsFullChars,
  };
}

/** 숫자를 등록부가 지정한 표기로 바꾼다. `14`와 `15,259`는 다른 문자열이다. */
function formatFact(value, format) {
  return format === "comma" ? value.toLocaleString("en-US") : String(value);
}

/**
 * 등록 항목이 가리키는 실측값을 꺼낸다.
 *
 * 대부분의 사실은 숫자 하나지만 `guidelineChars`처럼 **여러 개짜리**인 것이 있다.
 * 그런 사실은 등록부가 `key`로 어느 것인지 지목한다. 지목이 없거나 없는 이름을
 * 가리키면 조용히 통과시키지 않고 이유를 돌려준다 — 오타 하나로 검사가 사라지는
 * 것이 이 저장소가 반복해 겪은 실패다.
 */
function resolveFact(facts, entry) {
  const value = facts[entry.fact];
  if (typeof value === "number") return { value };
  if (value && typeof value === "object") {
    if (!entry.key) return { error: `"${entry.fact}"는 여러 개짜리 사실이라 key가 필요합니다` };
    if (!(entry.key in value)) return { error: `"${entry.fact}"에 "${entry.key}"가 없습니다` };
    return { value: value[entry.key] };
  }
  return { error: `"${entry.fact}"의 실측값을 찾지 못했습니다` };
}

/**
 * 등록된 주장이 문서 안에 그 값으로 들어 있는지 본다.
 *
 * ## 왜 값만 찾으면 안 되는가 — 실측으로 확인한 실패
 *
 * 처음에는 "파일 어딘가에 이 숫자가 있는가"만 봤다(AC-B5, `context-map.test.js:197`과
 * 같은 방식). 그런데 08 다이어그램의 `스킬 14개`를 일부러 `스킬 99개`로 바꿔도
 * **검사가 통과했다.** 같은 파일 다른 줄에 "14개 · 스킬 선택의 유일한 근거"가 있어서
 * "파일에 14가 있다"가 여전히 참이었기 때문이다.
 *
 * 즉 파일 단위 검사는 **주장이 여러 개인 문서에서 원리적으로 무력하다.** 그래서
 * 등록부가 값이 아니라 **문맥(`pattern`)** 을 등록하게 바꿨다. `"스킬 {v}개"` 처럼
 * 주장이 실제로 쓰인 모양을 적으면, 그 자리가 바뀌어야만 통과한다.
 *
 * 숫자 경계도 함께 본다 — `14`가 `144`나 `1,145`에 걸리면 안 되고, 08의 "상시의 4.3배"
 * 때문에 `4`가 소수점 앞자리에 걸려도 안 된다. 느슨한 일치는 **검사를 통과시키는
 * 방향으로** 틀리기 때문에 더 위험하다.
 */
function textClaimsValue(text, expected, pattern) {
  const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const boundedValue = `(?<![\\d,.])${escapeRe(expected)}(?![\\d,]|\\.\\d)`;

  if (!pattern) return new RegExp(boundedValue).test(text);

  // pattern 은 `{v}` 자리에 값이 들어가는 문자열이다. 나머지는 그대로 찾는다.
  const source = pattern.split("{v}").map(escapeRe).join(boundedValue);
  return new RegExp(source).test(text);
}

/**
 * 생성된 SVG는 mermaid가 **단어마다 `<tspan>`으로 쪼개** 놓아서 `"스킬 14개"` 같은
 * 문맥 패턴이 통째로는 절대 나오지 않는다. 태그와 공백을 걷어내 한 줄로 만든 뒤 비교한다.
 *
 * 공백까지 지우는 이유: 쪼개진 tspan 사이에 공백이 있을 수도 없을 수도 있어서,
 * 남겨 두면 파일마다 결과가 달라진다. 패턴도 같은 방식으로 정규화해 짝을 맞춘다.
 *
 * 한계: 이 정규화는 **텍스트 순서만** 보존한다. 시각적 배치가 바뀌어도 잡지 못한다.
 */
function normalizeForMatch(text, filePath) {
  if (!filePath.endsWith(".svg")) return text;
  return text.replace(/<[^>]*>/g, "").replace(/\s+/g, "");
}

/**
 * 등록부의 각 주장을 실측과 대조한다.
 *
 * 파일이 없으면 **조용히 통과시키지 않는다.** AC-B5의 `if (!existsSync) return;`
 * (`context-map.test.js:185`)은 다이어그램을 지우면 검사가 사라지는 사각지대를 만들었다.
 * 같은 실수를 반복하지 않으려고 `missingFile`로 따로 보고한다.
 */
function checkRegistry({ facts, registry, projectDir, fsOverrides = {} }) {
  const { existsSync = fs.existsSync, readFileSync = fs.readFileSync } = fsOverrides;
  const result = { ok: [], stale: [], missingFile: [], unknownFact: [] };
  const cache = new Map();

  for (const entry of registry) {
    const label = entry.label || `${entry.file} → ${entry.fact}`;

    if (!KNOWN_FACTS.includes(entry.fact)) {
      result.unknownFact.push(`${label}: 알 수 없는 사실 이름 "${entry.fact}"`);
      continue;
    }

    const abs = path.join(projectDir, entry.file);
    if (!cache.has(abs)) {
      cache.set(abs, existsSync(abs) ? readFileSync(abs, "utf-8") : null);
    }
    const text = cache.get(abs);
    if (text === null) {
      result.missingFile.push(`${label}: 등록된 파일이 없습니다 (${entry.file})`);
      continue;
    }

    const resolved = resolveFact(facts, entry);
    if (resolved.error) {
      result.unknownFact.push(`${label}: ${resolved.error}`);
      continue;
    }
    const expected = formatFact(resolved.value, entry.format);
    const haystack = normalizeForMatch(text, entry.file);
    const needle = entry.pattern ? normalizeForMatch(entry.pattern, entry.file) : undefined;
    if (textClaimsValue(haystack, expected, needle)) {
      result.ok.push(label);
    } else {
      const shown = entry.pattern ? `"${entry.pattern.replace("{v}", expected)}"` : expected;
      result.stale.push(`${label}: 실측 ${shown} 이(가) ${entry.file} 안에 없습니다`);
    }
  }
  return result;
}

// --- 미등록 수치 탐지 -------------------------------------------------------
//
// 등록부만 보는 검사에는 큰 구멍이 있다: **새 수치를 적고 등록을 잊으면 조용히 낡는다.**
// 그 구멍을 메우려면 "문서에 있는데 등록되지 않은 숫자"를 찾아야 하는데, 순진하게
// 모든 숫자를 세면 오탐이 압도한다. 2026-09-08 실측:
//
//   범위                          잔여 숫자
//   docs/diagrams/*.mmd (8개)     21개   → 성립
//   .claude/skills/*/SKILL.md     214개  → 불가 (대부분 목록 번호)
//
// 그래서 **다이어그램만** 본다. 타협이 아니라 `docs-diagrams.md`가 수치를 허용한
// 자리가 거기뿐이기 때문이다. 나머지 문서는 애초에 수치를 담으면 안 된다.

/** 색상 hex(`#111827`)와 스타일 수치가 사는 줄. 여기 숫자는 사실 주장이 아니다. */
const STYLE_LINE = /^\s*(classDef|linkStyle|style |%%)/;
/** mermaid 라벨은 큰따옴표 안에 있다. 그 밖은 문법이라 보지 않는다. */
const LABEL = /"([^"]*)"/g;
const NUMBER = /\d[\d,]*(?:\.\d+)?/g;
/** 라벨 안이지만 사실 주장이 아닌 것들. 먼저 지운 뒤 숫자를 센다. */
const NON_CLAIM_SPANS = [
  /20\d\d-\d\d-\d\d/g, // 날짜
  /AC-[\dA-Za-z]+(?:~[\dA-Za-z]+)?/g, // AC 번호·범위 (AC-1~17, AC-B1~B5)
];
/** 값 자체로 판별되는 면제. 저장소마다 같은 모양이라 코드에 둔다. */
const BUILTIN_EXEMPT = [
  { re: /^0[1-9]$/, why: "파이프라인 단계 번호" },
  { re: /^\d{1,2}\.\d$/, why: "OS.md 절 참조" },
  { re: /^20\d\d$/, why: "연도" },
];

/**
 * 다이어그램에서 등록되지도 면제되지도 않은 숫자를 찾는다.
 *
 * `exemptions`는 사람이 "이 숫자는 사실 주장이 아니다"라고 선언한 목록이며
 * **`why`가 없으면 거부한다.** 이유 없는 면제는 검사를 조용히 무력화하는 가장 쉬운
 * 길이고, 그렇게 무력화된 검사는 초록불이라 아무도 의심하지 않는다.
 */
function findUnregisteredNumbers({ projectDir, registry, exemptions = [], fsOverrides = {} }) {
  const { existsSync = fs.existsSync, readdirSync = fs.readdirSync, readFileSync = fs.readFileSync } = fsOverrides;
  const unregistered = [];
  const badExemptions = [];

  for (const ex of exemptions) {
    if (!ex.why || !String(ex.why).trim()) {
      badExemptions.push(`${ex.file || "?"} 의 "${ex.value}" 면제에 why가 없습니다`);
    }
  }

  const diagramsDir = path.join(projectDir, "docs", "diagrams");
  if (!existsSync(diagramsDir)) return { unregistered, badExemptions };

  const files = readdirSync(diagramsDir, { withFileTypes: true })
    .filter((e) => e.isFile() && e.name.endsWith(".mmd"))
    .map((e) => e.name)
    .sort();

  for (const name of files) {
    const rel = path.posix.join("docs", "diagrams", name);
    const claims = registry.filter((c) => c.file === rel);
    const exempt = exemptions.filter((e) => e.file === rel && e.why && String(e.why).trim());
    const text = readFileSync(path.join(diagramsDir, name), "utf-8");

    for (const line of text.split("\n")) {
      if (STYLE_LINE.test(line)) continue;
      for (const [, label] of line.matchAll(LABEL)) {
        let scrubbed = label;
        for (const re of NON_CLAIM_SPANS) scrubbed = scrubbed.replace(re, "");

        for (const [num] of scrubbed.matchAll(NUMBER)) {
          if (BUILTIN_EXEMPT.some((b) => b.re.test(num))) continue;
          if (exempt.some((e) => String(e.value) === num)) continue;
          // 등록된 주장이 이 라벨 안에서 이 숫자를 덮고 있으면 미등록이 아니다.
          const covered = claims.some((c) => c.pattern && label.includes(c.pattern.replace("{v}", num)));
          if (covered) continue;
          unregistered.push(`${rel}: "${num}" 이(가) 등록도 면제도 되지 않았습니다 — ${label.slice(0, 40)}`);
        }
      }
    }
  }
  return { unregistered, badExemptions };
}

/**
 * 등록부 파일을 읽는다. 없으면 빈 배열 — 등록부가 없는 저장소에서도 이 lib이 돌아야 한다.
 *
 * 파일 최상위는 `claims` 배열과 `_`로 시작하는 설명 필드로 되어 있다. JSON에는 주석을
 * 달 수 없는데, 등록부는 "왜 이 값이 여기 있나"를 읽는 사람이 가장 궁금해할 파일이라
 * 설명을 파일 안에 두는 쪽을 택했다. 배열만 반환해 호출부는 그 구분을 몰라도 된다.
 */
function loadRegistry({ projectDir, fsOverrides = {} }) {
  const { existsSync = fs.existsSync, readFileSync = fs.readFileSync } = fsOverrides;
  const registryPath = path.join(projectDir, "docs", "facts-registry.json");
  if (!existsSync(registryPath)) return [];
  const parsed = JSON.parse(readFileSync(registryPath, "utf-8"));
  return Array.isArray(parsed) ? parsed : parsed.claims || [];
}

/** 면제 목록을 읽는다. 등록부와 같은 파일에 두어 "무엇을 보고 무엇을 안 보는가"가 한 화면에 있게 한다. */
function loadExemptions({ projectDir, fsOverrides = {} }) {
  const { existsSync = fs.existsSync, readFileSync = fs.readFileSync } = fsOverrides;
  const registryPath = path.join(projectDir, "docs", "facts-registry.json");
  if (!existsSync(registryPath)) return [];
  const parsed = JSON.parse(readFileSync(registryPath, "utf-8"));
  return Array.isArray(parsed) ? [] : parsed.exemptions || [];
}

/** 스킬·테스트가 함께 쓰는 한 줄 진입점. */
function auditFreshness({ projectDir, fsOverrides = {} }) {
  const facts = collectFacts({ projectDir, fsOverrides });
  const registry = loadRegistry({ projectDir, fsOverrides });
  const exemptions = loadExemptions({ projectDir, fsOverrides });
  const check = checkRegistry({ facts, registry, projectDir, fsOverrides });
  const scan = findUnregisteredNumbers({ projectDir, registry, exemptions, fsOverrides });
  return {
    facts,
    ...check,
    ...scan,
    registered: registry.length,
    exempted: exemptions.length,
    // 한계를 결과에 함께 싣는다 — context-inject.js가 같은 이유로 그렇게 한다.
    // 다만 실제 능력보다 비관적으로 적는 것도 거짓이다. 이제 다이어그램 안에서는
    // 등록을 잊은 수치까지 잡는다. 못 보는 것은 다이어그램 **밖**이다.
    caveat:
      "이 검사는 docs/diagrams/*.mmd 안에서는 등록되지 않은 수치까지 찾아냅니다. " +
      "그 밖의 문서(OS.md, docs/*.md, SKILL.md)에 박힌 수치는 보지 않습니다 — " +
      "스킬 본문은 목록 번호 때문에 오탐이 압도해(실측 214개) 검사가 성립하지 않습니다.",
  };
}

module.exports = {
  KNOWN_FACTS,
  countTests,
  countDiagrams,
  collectFacts,
  formatFact,
  textClaimsValue,
  normalizeForMatch,
  checkRegistry,
  loadRegistry,
  loadExemptions,
  resolveFact,
  findUnregisteredNumbers,
  auditFreshness,
};
