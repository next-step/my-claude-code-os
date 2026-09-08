/**
 * 개인 지침(.claude/context/)의 **등록 정합성과 선언 일관성**을 감사한다.
 *
 * `context-map.js`가 "무엇이 얼마나 로드되는가"(양)를 본다면, 이 파일은
 * "레지스트리와 실제 파일이 어긋나지 않는가"(정합성)를 본다.
 *
 * ## 이 파일이 검증하지 **못하는** 것 — 2026-09-07에 실측으로 밝혀진 사실
 *
 * 처음 이 파일을 쓸 때는 서브에이전트별로 지침을 주입하거나 차단할 수 있다고 보고,
 * 에이전트 파일의 표식(`@import` 줄 · 0단계 읽기 지시)이 그 스위치라고 가정했다.
 * **그 가정은 틀렸다.** 실측 결과:
 *
 *   - `policy-reviewer`(도구는 Read뿐, 실제 도구 호출 0회)가 지침 8개를 **전문으로** 인용했다.
 *   - 경로는 `CLAUDE.md` → `@.claude/context/index.md` → 지침 8개이며,
 *     이 체인은 **모든 서브에이전트에 그대로 상속된다.** gitStatus·userEmail도 함께 온다.
 *   - `os-builder`는 지침 8개를 Read로 읽지도 않았다 — 이미 컨텍스트에 있었기 때문이다.
 *
 * 즉 **에이전트 파일의 표식은 주입을 켜거나 끄지 않는다.** 표식은 "이 에이전트가
 * 지침을 따르기로 선언했는가"라는 *의도의 기록*일 뿐이다. 그래서 이 파일은
 * `injected`/`blocked` 같은 말을 쓰지 않고 `declared`(선언)라고 부른다.
 *
 * 다만 ATDD의 독립 리뷰가 무의미해진 것은 아니다. **차단에는 두 종류가 있다.**
 *   (a) 호출자가 자기 분해 과정·자기평가를 리뷰어에게 넘기지 않는 것 — 이건 실재하며
 *       `atdd-orchestrator`가 지킨다(`OS.md` 2026-08-27·08-28의 FAIL 사례가 그 증거).
 *   (b) 세션 컨텍스트가 서브에이전트에 닿지 않는 것 — 이건 성립하지 않는다.
 * 이 파일은 (b)를 검증한다고 주장했었다. 지금은 주장하지 않는다.
 *
 * 오염 여부도 실측했다(`docs/context-ab-test.md` 실험 2): 지침이 주입된 리뷰어와
 * 없는 리뷰어가 같은 AC 목록에 4회 모두 같은 판정을 냈다. **해로운 오염은 관측되지 않았다.**
 *
 * 순수 함수만 담고 fs는 주입받는다(stats.js·context-map.js와 같은 관례).
 * .claude/tests/context-inject.test.js 가 검증한다.
 */
const fs = require("node:fs");
const path = require("node:path");

const { parseImportLines, parseFrontmatter, resolveImportPath } = require("./context-map.js");

/** 지침이 아니라 계층 자체를 설명하는 파일. 등록 대상에서 제외한다. */
const NON_GUIDELINE_FILES = new Set(["index.md", "README.md"]);

/** description에 이 문구가 있으면 독립 판정 역할을 **선언한** 에이전트로 본다(강제가 아니라 선언이다). */
const INDEPENDENCE_MARKER = "독립적으로 판정";

/** 레지스트리를 루트 기준 경로로 잘못 적는 실전 함정. index.md 기준 상대경로여야 한다. */
const ROOT_RELATIVE_PREFIX = ".claude/";

/** `.claude/context/`에 실제로 존재하는 지침 파일 이름 목록. */
function listGuidelineFiles(contextDir, options = {}) {
  const { existsSync = fs.existsSync, readdirSync = fs.readdirSync } = options;
  if (!existsSync(contextDir)) return [];
  return readdirSync(contextDir)
    .filter((name) => name.endsWith(".md") && !NON_GUIDELINE_FILES.has(name))
    .sort();
}

/**
 * 레지스트리(index.md)와 실제 파일을 대조한다.
 * @returns {{registered: string[], files: string[], orphans: string[], missing: string[], badPaths: string[]}}
 */
function auditRegistry({ projectDir, fsOverrides = {} }) {
  const { existsSync = fs.existsSync, readFileSync = fs.readFileSync } = fsOverrides;
  const contextDir = path.join(projectDir, ".claude", "context");
  const indexPath = path.join(contextDir, "index.md");

  const files = listGuidelineFiles(contextDir, fsOverrides);
  if (!existsSync(indexPath)) {
    return { registered: [], files, orphans: files, missing: [], badPaths: [] };
  }

  const registered = parseImportLines(readFileSync(indexPath, "utf-8"));
  const badPaths = registered.filter((entry) => entry.startsWith(ROOT_RELATIVE_PREFIX));

  const resolved = registered.map((entry) => resolveImportPath(entry, contextDir));
  const missing = registered.filter((entry, i) => !existsSync(resolved[i]));
  const registeredNames = new Set(resolved.map((abs) => path.basename(abs)));
  const orphans = files.filter((name) => !registeredNames.has(name));

  return { registered, files, orphans, missing, badPaths };
}

/**
 * 서브에이전트 하나의 기대(독립 심판인가)와 실제(주입 표식이 있는가)를 읽는다.
 */
function inspectAgent(agentPath, registryPath, options = {}) {
  const { readFileSync = fs.readFileSync } = options;
  const text = readFileSync(agentPath, "utf-8");
  const frontmatter = parseFrontmatter(text);
  const agentDir = path.dirname(agentPath);

  const hasImportLine = parseImportLines(text).some(
    (entry) => path.resolve(resolveImportPath(entry, agentDir)) === path.resolve(registryPath)
  );

  // `@` 줄이 서브에이전트 파일에서도 해석되는지는 확인되지 않았다(2026-09-07 미해결 가정).
  // 그래서 본문에 "레지스트리를 읽어라"는 지시도 함께 요구한다 — 둘 중 하나만으로는
  // 주입을 보장할 수 없기 때문이다. 지시문은 `@` 줄이 아닌 곳에서 레지스트리 경로를 언급한다.
  const withoutImportLines = text
    .split(/\r?\n/)
    .filter((line) => !/^@\S+$/.test(line.trim()))
    .join("\n");
  const hasReadStep = withoutImportLines.includes(".claude/context/index.md");

  return {
    name: frontmatter.name || path.basename(agentPath, ".md"),
    independent: (frontmatter.description || "").includes(INDEPENDENCE_MARKER),
    hasImportLine,
    hasReadStep,
  };
}

/**
 * `.claude/agents/*.md` 전체의 **선언**을 읽는다.
 *
 * 반환하는 것은 "이 에이전트가 지침을 받는가"가 아니라 "이 에이전트가 무엇을 선언했는가"다.
 * 실제 주입은 `CLAUDE.md` 체인 상속으로 전원에게 일어나며 여기서 통제되지 않는다(헤더 주석 참고).
 */
function auditAgents({ projectDir, fsOverrides = {} }) {
  const { existsSync = fs.existsSync, readdirSync = fs.readdirSync } = fsOverrides;
  const agentsDir = path.join(projectDir, ".claude", "agents");
  const registryPath = path.join(projectDir, ".claude", "context", "index.md");
  if (!existsSync(agentsDir)) return [];

  return readdirSync(agentsDir)
    .filter((name) => name.endsWith(".md"))
    .sort()
    .map((name) => {
      const info = inspectAgent(path.join(agentsDir, name), registryPath, fsOverrides);
      // 표식이 하나라도 있으면 "지침을 따르겠다고 선언했다"로 본다.
      const declaresGuidelines = info.hasImportLine || info.hasReadStep;
      return {
        name: info.name,
        declaresIndependence: info.independent,
        declaresGuidelines,
        hasImportLine: info.hasImportLine,
        hasReadStep: info.hasReadStep,
        // 한 파일이 "독립 판정한다"와 "지침을 따른다"를 동시에 선언하면 그 파일이 스스로 모순이다.
        consistent: !(info.independent && declaresGuidelines),
      };
    });
}

/**
 * 레지스트리 정합성과 에이전트 선언 일관성을 합쳐 위반 목록을 만든다.
 *
 * **위반 0개가 "지침이 의도한 곳에만 도달한다"는 뜻이 아니다.** 지침은 모든
 * 서브에이전트에 도달한다. 위반 0개는 (1) 레지스트리와 파일이 어긋나지 않고
 * (2) 어떤 에이전트도 자기 선언 안에서 모순되지 않는다는 뜻일 뿐이다.
 */
function auditInjection({ projectDir, fsOverrides = {} }) {
  const registry = auditRegistry({ projectDir, fsOverrides });
  const agents = auditAgents({ projectDir, fsOverrides });
  const violations = [];
  const notes = [];

  for (const name of registry.orphans) {
    violations.push(`고아 지침: ${name} 이 .claude/context/index.md 에 등록되지 않았습니다`);
  }
  for (const entry of registry.missing) {
    violations.push(`끊어진 등록: index.md 의 @${entry} 가 가리키는 파일이 없습니다`);
  }
  for (const entry of registry.badPaths) {
    violations.push(
      `경로 오기: @${entry} 는 루트 기준입니다. index.md 기준 상대경로(파일 이름만)로 적어야 조용히 누락되지 않습니다`
    );
  }
  for (const agent of agents) {
    if (!agent.consistent) {
      violations.push(
        `선언 모순: ${agent.name} 이 description에서는 독립 판정을 선언하면서 본문에서는 지침을 따르겠다고 선언합니다 (둘 중 하나를 지우세요)`
      );
    } else if (!agent.declaresIndependence && !agent.declaresGuidelines) {
      // 위반이 아니다 — 상속으로 지침은 어차피 도달한다. 다만 의도가 파일에 안 남는다.
      notes.push(`${agent.name}: 지침을 따르겠다는 선언이 본문에 없습니다 (동작에는 영향 없음, 의도 기록만 빠짐)`);
    }
  }

  return {
    ok: violations.length === 0,
    registry,
    agents,
    notes,
    // 검증기가 통제하지 못하는 사실을 결과에 같이 실어, 호출부가 오해하지 않게 한다.
    reality:
      "모든 서브에이전트는 CLAUDE.md → index.md → 지침 체인을 상속받습니다. 아래 선언은 의도의 기록이지 주입 스위치가 아닙니다 (2026-09-07 실측).",
    counts: {
      guidelines: registry.files.length,
      agentsDeclaringGuidelines: agents.filter((a) => a.declaresGuidelines).length,
      agentsDeclaringIndependence: agents.filter((a) => a.declaresIndependence).length,
    },
    violations,
  };
}

module.exports = { listGuidelineFiles, auditRegistry, inspectAgent, auditAgents, auditInjection, INDEPENDENCE_MARKER };
