/**
 * 세션 컨텍스트 지도 집계 로직.
 *
 * `context-map` 스킬이 이 함수들을 불러 "세션 시작 시 실제로 무엇이 얼마나
 * 컨텍스트에 로드되는가"를 보여준다. 마크다운 지시문은 자동 테스트가 불가능하므로
 * (OS.md 2026-08-27 항목) 파싱·순회 로직을 전부 여기로 뺐다 — .claude/tests/context-map.test.js가
 * 이 파일의 인수기준을 검증한다.
 *
 * 이 파일은 순수 함수만 담는다. 모든 함수는 fs 호출을 옵션으로 주입받을 수 있어
 * 실제 파일시스템 없이도 테스트할 수 있다(stats.js와 동일한 습관).
 */
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

/**
 * 텍스트에서 `@경로` 형태의 import 줄만 추출한다.
 * 정규식 기반이라 완전한 파서가 아니다 — 줄 전체가 공백을 뺀 뒤 `@경로`인
 * 경우만 인식한다. 문장 중간에 낀 `@`나 이메일 주소 속 `@`는 오탐을 피하기 위해
 * 일부러 인식하지 않는다.
 * @returns {string[]}
 */
function parseImportLines(text) {
  if (typeof text !== "string") return [];
  const importPattern = /^@(\S+)$/;
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => importPattern.test(line))
    .map((line) => line.match(importPattern)[1]);
}

/**
 * 텍스트의 줄 수·글자 수를 센다. 줄 수는 `wc -l`과 같은 관례를 따른다 —
 * 마지막 줄바꿈 하나는 "다음 줄의 시작"이 아니라 "이전 줄의 끝"으로 보고 세지 않는다.
 */
function countSize(text) {
  if (typeof text !== "string" || text.length === 0) return { lines: 0, chars: 0 };
  const body = text.replace(/\r?\n$/, "");
  return { lines: body === "" ? 0 : body.split(/\r?\n/).length, chars: text.length };
}

/**
 * `@import` 줄 하나를 절대 경로로 해석한다. `~/`는 홈 디렉터리, `/`로 시작하면
 * 절대 경로, 그 외에는 import한 파일 기준 상대 경로로 취급한다.
 */
function resolveImportPath(importPath, fromDir) {
  if (importPath.startsWith("~")) return path.join(os.homedir(), importPath.slice(1));
  if (path.isAbsolute(importPath)) return importPath;
  return path.resolve(fromDir, importPath);
}

/**
 * `rootPath`(보통 CLAUDE.md)부터 `@import`를 재귀적으로 따라가며 트리를 만든다.
 * Claude Code의 5단계 재귀 제한을 그대로 흉내낸다 — root가 depth 1이다.
 *
 * 누락된 대상(`missing`)과 순환(`cycle`)은 예외를 던지지 않고 노드에 표시만 한다 —
 * 둘 다 실제로 있을 수 있는 상태이지 프로그램 오류가 아니기 때문이다(stats.js의
 * "파일 없음 → null" 방어적 파싱과 같은 원칙).
 *
 * @returns {{ nodes: Array<object>, totalLines: number, totalChars: number }}
 */
function resolveImportTree(rootPath, options = {}) {
  const { maxDepth = 5, readFileSync = fs.readFileSync, existsSync = fs.existsSync } = options;

  const nodes = [];
  const visited = new Set();

  function walk(filePath, depth) {
    const normalized = path.resolve(filePath);

    if (depth > maxDepth) {
      nodes.push({ path: normalized, depth, truncated: true });
      return;
    }
    if (visited.has(normalized)) {
      nodes.push({ path: normalized, depth, cycle: true });
      return;
    }
    visited.add(normalized);

    if (!existsSync(normalized)) {
      nodes.push({ path: normalized, depth, missing: true });
      return;
    }

    const text = readFileSync(normalized, "utf-8");
    const { lines, chars } = countSize(text);
    nodes.push({ path: normalized, depth, lines, chars });

    const fromDir = path.dirname(normalized);
    for (const importPath of parseImportLines(text)) {
      walk(resolveImportPath(importPath, fromDir), depth + 1);
    }
  }

  walk(path.resolve(rootPath), 1);

  const totals = nodes.reduce(
    (acc, node) => {
      if (!node.missing && !node.cycle && !node.truncated) {
        acc.totalLines += node.lines;
        acc.totalChars += node.chars;
      }
      return acc;
    },
    { totalLines: 0, totalChars: 0 }
  );

  return { nodes, ...totals };
}

/**
 * `---` frontmatter 블록에서 `키: 값` 쌍을 뽑는다. 값이 여러 줄로 이어지면
 * (이 저장소의 description처럼 한 줄로 긴 문장이 대부분이지만, 혹시 줄바꿈이 있어도)
 * 다음 키가 나오기 전까지 이어붙인다. 완전한 YAML 파서가 아니라 이 저장소의
 * 실제 frontmatter 형태(name/description/tools)만 다루는 최소 구현이다.
 */
function parseFrontmatter(text) {
  const match = typeof text === "string" ? text.match(/^---\r?\n([\s\S]*?)\r?\n---/) : null;
  if (!match) return {};

  const result = {};
  let currentKey = null;
  for (const line of match[1].split(/\r?\n/)) {
    const kv = line.match(/^([a-zA-Z_-]+):\s?(.*)$/);
    if (kv) {
      currentKey = kv[1];
      result[currentKey] = kv[2];
    } else if (currentKey) {
      result[currentKey] = `${result[currentKey]} ${line.trim()}`.trim();
    }
  }
  return result;
}

/**
 * `.claude/skills/<이름>/SKILL.md`의 매니페스트(name/description)와 전체 본문 크기를 모은다.
 * description은 "항상 로드"되는 요약, 전체 본문은 스킬이 호출될 때만 로드되는 온디맨드분이다.
 */
function listSkillManifests(skillsDir, options = {}) {
  const { readFileSync = fs.readFileSync, existsSync = fs.existsSync, readdirSync = fs.readdirSync } = options;
  if (!existsSync(skillsDir)) return [];

  return readdirSync(skillsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(skillsDir, entry.name, "SKILL.md"))
    .filter((skillFile) => existsSync(skillFile))
    .map((skillFile) => {
      const text = readFileSync(skillFile, "utf-8");
      const fm = parseFrontmatter(text);
      const { lines, chars } = countSize(text);
      return {
        name: fm.name || path.basename(path.dirname(skillFile)),
        description: fm.description || "",
        descriptionChars: (fm.description || "").length,
        fullLines: lines,
        fullChars: chars,
      };
    });
}

/**
 * `.claude/agents/*.md`의 매니페스트(name/description/tools)와 전체 본문 크기를 모은다.
 * 서브에이전트는 호출돼도 본문이 메인 대화가 아니라 격리된 컨텍스트에서만 로드된다.
 */
function listAgentManifests(agentsDir, options = {}) {
  const { readFileSync = fs.readFileSync, existsSync = fs.existsSync, readdirSync = fs.readdirSync } = options;
  if (!existsSync(agentsDir)) return [];

  return readdirSync(agentsDir)
    .filter((file) => file.endsWith(".md"))
    .map((file) => {
      const fullPath = path.join(agentsDir, file);
      const text = readFileSync(fullPath, "utf-8");
      const fm = parseFrontmatter(text);
      const { lines, chars } = countSize(text);
      return {
        name: fm.name || path.basename(file, ".md"),
        description: fm.description || "",
        descriptionChars: (fm.description || "").length,
        tools: fm.tools || null,
        fullLines: lines,
        fullChars: chars,
      };
    });
}

/**
 * `settings.json`(과 있다면 `settings.local.json`)의 `hooks` 트리를 평탄화한다.
 * 훅은 이벤트에 반응해 스크립트로 실행될 뿐 컨텍스트 토큰을 전혀 차지하지 않는다.
 */
function listRegisteredHooks(settingsPaths, options = {}) {
  const { readFileSync = fs.readFileSync, existsSync = fs.existsSync } = options;
  const paths = Array.isArray(settingsPaths) ? settingsPaths : [settingsPaths];
  const hooks = [];

  for (const settingsPath of paths) {
    if (!existsSync(settingsPath)) continue;

    let parsed;
    try {
      parsed = JSON.parse(readFileSync(settingsPath, "utf-8"));
    } catch (_) {
      continue;
    }

    const hookTree = parsed && typeof parsed.hooks === "object" ? parsed.hooks : null;
    if (!hookTree) continue;

    for (const [event, matcherGroups] of Object.entries(hookTree)) {
      if (!Array.isArray(matcherGroups)) continue;
      for (const group of matcherGroups) {
        const matcher = typeof group.matcher === "string" ? group.matcher : null;
        const groupHooks = Array.isArray(group.hooks) ? group.hooks : [];
        for (const hook of groupHooks) {
          hooks.push({ event, matcher, command: hook.command || null, source: settingsPath });
        }
      }
    }
  }

  return hooks;
}

/**
 * 설정 파일들에서 등록된 MCP 서버를 목록화한다.
 *
 * ## 왜 크기를 세지 않고 개수만 세는가 (이 함수 설계의 전부다)
 *
 * MCP 서버는 세션마다 **툴 이름 목록과 server instructions**를 컨텍스트에 싣는다.
 * 그런데 그 크기는 **디스크에서 알 수 없다** — 서버에 실제로 붙어 `tools/list`를 해야
 * 알 수 있고, HTTP 서버는 OAuth까지 필요하다.
 *
 * 그래서 추정치를 만들어 `alwaysLoaded` 합계에 섞지 않는다. 섞으면
 * `docs/context-budget.md`에 쌓인 기존 수치와 비교가 깨지고, 무엇보다
 * 잰 값과 어림잡은 값이 한 숫자에 뭉개진다.
 * `.claude/context/explanation-style.md`("확인하지 못했으면 확인하지 못했다고 적는다").
 *
 * 참고로 2026-09-07 이 저장소에서 잰 값: notion MCP는 툴 42개, 이름만 1,521자.
 * 스키마 2개 표본이 약 13,000자였으므로 전부 실렸다면 약 27만 자였을 것으로 **추정**된다
 * (상시 로드 총량 13,940자의 약 20배). Claude Code 2.1.263은 이름만 싣고
 * 스키마는 지연 로딩해 이 비용의 대부분을 이미 막고 있다.
 *
 * @returns {{name: string, transport: string, source: string, scope: string}[]}
 */
function listMcpServers(configPaths, options = {}) {
  const { readFileSync = fs.readFileSync, existsSync = fs.existsSync } = options;
  const entries = Array.isArray(configPaths) ? configPaths : [configPaths];
  const servers = [];

  for (const entry of entries) {
    const filePath = typeof entry === "string" ? entry : entry?.path;
    const scope = (typeof entry === "object" && entry?.scope) || "project";
    // `~/.claude.json`은 서버 목록이 projects[<프로젝트 경로>].mcpServers 아래에 있다.
    const projectKey = typeof entry === "object" ? entry?.projectKey : null;

    if (!filePath || !existsSync(filePath)) continue;

    let parsed;
    try {
      parsed = JSON.parse(readFileSync(filePath, "utf-8"));
    } catch (_) {
      continue; // 깨진 JSON 때문에 지도 전체가 죽지 않는다
    }

    const container = projectKey ? parsed?.projects?.[projectKey] : parsed;
    const tree = container && typeof container.mcpServers === "object" ? container.mcpServers : null;
    if (!tree) continue;

    for (const [name, config] of Object.entries(tree)) {
      servers.push({
        name,
        transport: config?.type || (config?.command ? "stdio" : "unknown"),
        source: filePath,
        scope,
      });
    }
  }

  return servers;
}

/**
 * 위 함수들을 묶어 `context-map` 스킬이 그대로 보고할 수 있는 형태로 반환한다.
 * `.claude/context/`에 아직 실제 지침 파일이 없을 때는(오늘 시점 정상 상태) 에러 대신
 * `note`에 빈 상태를 명시한다 — stats.js의 `isEmpty` 처리와 같은 정직함이다.
 *
 * @returns {{
 *   importTree: {nodes: object[], totalLines: number, totalChars: number},
 *   skills: object[],
 *   agents: object[],
 *   hooks: object[],
 *   mcpServers: object[],
 *   onDemandTotals: {skillsFullChars: number, agentsFullChars: number},
 *   note: string|null,
 * }}
 */
function buildContextMap({ projectDir, fsOverrides = {} }) {
  const claudeMdPath = path.join(projectDir, "CLAUDE.md");
  const skillsDir = path.join(projectDir, ".claude", "skills");
  const agentsDir = path.join(projectDir, ".claude", "agents");
  const settingsPath = path.join(projectDir, ".claude", "settings.json");
  const settingsLocalPath = path.join(projectDir, ".claude", "settings.local.json");
  // MCP 서버는 세 군데에 흩어져 있다: 프로젝트 `.mcp.json`(커밋됨),
  // `~/.claude.json`의 projects[프로젝트경로](local 스코프), 같은 파일의 최상위(user 스코프).
  const homeDir = fsOverrides.homeDir || os.homedir();
  const userConfigPath = path.join(homeDir, ".claude.json");
  const mcpConfigPaths = [
    { path: path.join(projectDir, ".mcp.json"), scope: "project" },
    { path: userConfigPath, scope: "local", projectKey: projectDir },
    { path: userConfigPath, scope: "user" },
  ];

  const importTree = resolveImportTree(claudeMdPath, fsOverrides);
  const skills = listSkillManifests(skillsDir, fsOverrides);
  const agents = listAgentManifests(agentsDir, fsOverrides);
  const hooks = listRegisteredHooks([settingsPath, settingsLocalPath], fsOverrides);
  const mcpServers = listMcpServers(mcpConfigPaths, fsOverrides);

  // depth 1은 CLAUDE.md, depth 2는 .claude/context/index.md(레지스트리) 자신이다.
  // 실제 개인 지침 파일은 index.md가 가리키는 depth 3부터다.
  const hasRealGuidelines = importTree.nodes.some(
    (node) => node.depth > 2 && !node.missing && !node.cycle && !node.truncated
  );

  return {
    importTree,
    skills,
    agents,
    hooks,
    mcpServers,
    onDemandTotals: {
      skillsFullChars: skills.reduce((sum, s) => sum + s.fullChars, 0),
      agentsFullChars: agents.reduce((sum, a) => sum + a.fullChars, 0),
    },
    note: hasRealGuidelines ? null : ".claude/context/ 에 아직 실제 개인 지침 파일이 없습니다 (index.md만 존재).",
  };
}

/**
 * `buildContextMap`의 결과를 "세션 시작 시 항상 내는 비용" 기준으로 요약한다.
 *
 * 왜 따로 두는가: 컨텍스트 예산을 이야기할 때마다 호출부가 같은 덧셈을 다시 하면
 * 사람마다 다른 수치가 나온다. 무엇을 상시 비용으로 셀지(= import 체인 전문 +
 * 스킬·에이전트의 description, 본문은 제외)를 여기 한 곳에 고정한다.
 *
 * 훅은 이벤트에 반응해 스크립트로 실행될 뿐 컨텍스트를 차지하지 않으므로 개수만 센다.
 */
function summarizeBudget(map) {
  const importChars = map.importTree.totalChars;
  const skillDescChars = map.skills.reduce((sum, s) => sum + s.descriptionChars, 0);
  const agentDescChars = map.agents.reduce((sum, a) => sum + a.descriptionChars, 0);
  const onDemandTotal = map.onDemandTotals.skillsFullChars + map.onDemandTotals.agentsFullChars;

  return {
    alwaysLoaded: {
      importChars,
      skillDescChars,
      agentDescChars,
      total: importChars + skillDescChars + agentDescChars,
    },
    onDemand: {
      skillsFullChars: map.onDemandTotals.skillsFullChars,
      agentsFullChars: map.onDemandTotals.agentsFullChars,
      total: onDemandTotal,
    },
    zeroCost: { hooks: map.hooks.length },
    // 세션마다 로드되지만 **디스크에서는 크기를 알 수 없는** 항목.
    // 일부러 alwaysLoaded.total 에 섞지 않는다 — 잰 값과 어림값을 한 숫자로 뭉개면
    // docs/context-budget.md 에 쌓인 이력과 비교가 깨진다. listMcpServers 주석 참고.
    unmeasured: {
      mcpServers: (map.mcpServers || []).map((s) => ({ name: s.name, transport: s.transport, scope: s.scope })),
      mcpServerCount: (map.mcpServers || []).length,
      note:
        "MCP 서버의 툴 이름 목록과 server instructions는 세션마다 로드되지만 " +
        "크기를 알려면 서버에 붙어 tools/list를 해야 한다. `claude mcp list`·`/mcp`로 확인한다.",
    },
  };
}

module.exports = {
  parseImportLines,
  countSize,
  resolveImportPath,
  resolveImportTree,
  parseFrontmatter,
  listSkillManifests,
  listAgentManifests,
  listRegisteredHooks,
  listMcpServers,
  buildContextMap,
  summarizeBudget,
};
