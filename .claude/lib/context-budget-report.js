#!/usr/bin/env node
/**
 * 컨텍스트 예산을 랄프 루프가 읽을 수 있는 한 줄짜리 지표로 찍는 얇은 CLI.
 *
 * 왜 별도 파일인가: `context-map.js`에는 CLI 진입점이 없고, 스킬 세 곳이 그 모듈을
 * 라이브러리로만 쓴다. 랄프 루프의 `kind: "command"` 지표를 위해 그쪽에 `process.argv`를
 * 들이면 읽는 쪽만 있던 모듈에 실행 책임이 섞인다. 그래서 계산은 전부
 * `summarizeBudget`에 두고 여기서는 출력 형식만 맡는다.
 *
 * 출력 형식은 취향이 아니라 계약이다. `ralph-loop.js`의 `extractFromCommand`가
 * `^\s*(?:#|ℹ)\s*<이름>\s+(\d+)` 로 파싱하므로(`ralph-loop.js:264`), 이름과 숫자 사이에
 * 다른 문자가 끼면 지표를 못 읽고 그 회차가 통째로 `null`이 된다. `null`은 통과로 치지
 * 않으므로(`ralph-loop.js:297`) 형식이 깨지면 루프가 영원히 성공하지 못한다.
 * `node --test`의 TAP 요약(`# pass 240`)과 같은 형식을 일부러 따랐다.
 *
 * 이 파일은 어떤 랄프 목표의 `editable`에도 들어가면 안 된다. 점수를 내는 코드를 루프가
 * 고칠 수 있으면, 목표를 달성하는 가장 짧은 경로가 "지표를 조작하는 것"이 된다.
 */
const path = require("node:path");
const { buildContextMap, summarizeBudget } = require("./context-map.js");

/**
 * 지표 이름과 값을 고정한다. 이름을 바꾸면 커밋된 목표 정의(`experiments/ralph/goals/*.json`)가
 * 조용히 깨지므로, 바꿀 때는 목표 정의도 같이 고친다.
 */
function collectBudgetMetrics(budget) {
  return [
    ["always_loaded_chars", budget.alwaysLoaded.total],
    ["import_chars", budget.alwaysLoaded.importChars],
    ["skill_desc_chars", budget.alwaysLoaded.skillDescChars],
    ["agent_desc_chars", budget.alwaysLoaded.agentDescChars],
    ["on_demand_chars", budget.onDemand.total],
  ];
}

function formatBudgetReport(budget) {
  return collectBudgetMetrics(budget)
    .map(([name, value]) => `# ${name} ${value}`)
    .join("\n");
}

function main(argv = []) {
  const rootFlag = argv.indexOf("--root");
  const projectDir = rootFlag !== -1 && argv[rootFlag + 1]
    ? path.resolve(argv[rootFlag + 1])
    : process.cwd();
  const budget = summarizeBudget(buildContextMap({ projectDir }));
  return formatBudgetReport(budget);
}

module.exports = { collectBudgetMetrics, formatBudgetReport, main };

if (require.main === module) {
  try {
    console.log(main(process.argv.slice(2)));
  } catch (err) {
    console.error(`오류: ${err.message}`);
    process.exit(1);
  }
}
