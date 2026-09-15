#!/usr/bin/env node
/**
 * 지침 파일의 구조 수치를 랄프 루프가 guard로 걸 수 있는 형태로 찍는다.
 *
 * ## 왜 필요한가
 *
 * `context-slim-30` 실주행에서 가드 세 개가 전부 통과한 채 지침이 붕괴했다. 조항이 80개에서
 * 0개가 됐고 다이어그램 필수 옵션 3종이 사라졌는데 `citation` 가드는 통과했다.
 * 이유는 구조적이다 — **가드는 응답을 보는데 무너진 것은 지침이다.** 모델은 지침에 인용
 * 예시가 없어도 저장소를 읽고 인용하므로, 응답만 보는 가드는 지침이 비어도 거의 통과한다.
 *
 * 그래서 지침 **자체**를 세는 표면을 만든다. `loop-rubric.js`가 이미 같은 수치를 내고 있으므로
 * 계산은 전부 거기 위임하고, 여기서는 출력 형식만 맡는다(`context-budget-report.js`와 같은 구조).
 *
 * 출력 형식은 계약이다. `ralph-loop.js`의 `extractFromCommand`가 `# <이름> <숫자>`로 파싱한다.
 *
 * 이 파일은 어떤 목표의 `editable`에도 들어가면 안 된다. 점수를 내는 코드를 루프가 고칠 수
 * 있으면 목표 달성의 최단 경로가 지표 조작이 된다(`ralph-loop` SKILL.md).
 */
const fs = require("node:fs");
const path = require("node:path");

const { sumMeasures } = require("./loop-rubric.js");

/** 기본 대상은 개인 지침 디렉터리다. `--dir`로 바꿀 수 있다. */
function readDocs(dir, fsImpl = fs) {
  const docs = {};
  if (!fsImpl.existsSync(dir)) return docs;
  for (const name of fsImpl.readdirSync(dir)) {
    if (!name.endsWith(".md")) continue;
    docs[name] = fsImpl.readFileSync(path.join(dir, name), "utf8");
  }
  return docs;
}

/**
 * 이름을 바꾸면 커밋된 목표 정의가 조용히 깨진다. 바꿀 때는 목표 정의도 같이 고친다.
 * `guideline_files`를 함께 내는 이유는, 파일을 통째로 지워서 다른 수치를 0으로 만드는
 * 우회를 사람이 알아볼 수 있게 하기 위해서다.
 */
function formatRubricReport(docs) {
  const m = sumMeasures(docs);
  return [
    ["guideline_files", Object.keys(docs).length],
    ["guideline_chars", m.chars],
    ["clause_count", m.clauses],
    ["citation_count", m.citations],
    ["caveat_lines", m.caveatLines],
    ["evidence_lines", m.evidenceLines],
  ].map(([k, v]) => `# ${k} ${v}`).join("\n");
}

function main(argv = []) {
  const i = argv.indexOf("--dir");
  const dir = i !== -1 && argv[i + 1] ? path.resolve(argv[i + 1]) : path.join(process.cwd(), ".claude", "context");
  return formatRubricReport(readDocs(dir));
}

module.exports = { readDocs, formatRubricReport, main };

if (require.main === module) {
  try {
    console.log(main(process.argv.slice(2)));
  } catch (err) {
    console.error(`오류: ${err.message}`);
    process.exit(1);
  }
}
