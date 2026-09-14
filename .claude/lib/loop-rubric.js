/**
 * 랄프 루프 회차마다 산출물이 어떻게 변해가는지 여러 관점으로 기록한다.
 *
 * ## 왜 종료 판정에 물리지 않는가
 *
 * 이 저장소는 `.claude/context/context-experiment.md`에 "자동 채점 결과를 믿지 않는다 —
 * 세 실험 연속으로 채점 기준이 대상보다 부정확했다"를 적어 뒀고, `ralph-loop/SKILL.md`가
 * 그 이유로 품질 채점을 종료 판정에서 뺐다. 여기 있는 점수는 **관측 기록이지 판정이 아니다.**
 * 루프를 멈추고 이어가는 결정은 지금처럼 기계가 다툼 없이 세는 지표가 한다.
 *
 * 점수를 판정에 물리면 루프가 점수를 최적화한다. 예를 들어 `evidence` 차원은 백틱과 숫자로
 * 된 인용 패턴을 세는데, 이걸 목표로 걸면 아무 데나 `a.md:1`을 뿌리는 것이 최단 경로가 된다.
 *
 * ## 각 차원이 무엇의 대리물인지 밝힌다
 *
 * 기계가 세는 다섯 차원은 전부 **대리 지표**다. `caveat`은 "한계를 말했는가"를 재는 것이
 * 아니라 그런 낱말이 든 줄의 수를 센다. 그 차이를 `proxyFor`에 적어 두는 이유는, 나중에
 * 이 숫자를 읽는 사람이 대리물을 본체로 착각하지 않게 하기 위해서다.
 * 여섯째 `readability`는 대리물조차 없어서 사람이 채운다 — `null`로 낸다.
 */

/** 한계·실패를 말하는 줄의 대리 표지. 목록을 늘리면 과거 기록과 비교가 깨지므로 신중히 고친다. */
const CAVEAT_MARKERS = ["한계", "실패", "착각", "함정", "위험", "못 ", "않는다", "주의"];

/** `파일.확장자:숫자` 또는 백틱 안의 경로 인용. */
const CITATION_RE = /`[^`\n]*\.[A-Za-z]{2,5}:\d+[^`\n]*`|`[^`\n]*\.(?:md|js|json|mmd)`/g;

function countMatches(text, re) {
  const m = String(text || "").match(re);
  return m ? m.length : 0;
}

function countLinesWith(text, markers) {
  return String(text || "")
    .split("\n")
    .filter((line) => markers.some((k) => line.includes(k)))
    .length;
}

/** 불릿과 헤딩의 수. "조항이 몇 개 남았는가"의 대리물이다. */
function countClauses(text) {
  return String(text || "")
    .split("\n")
    .filter((line) => /^\s*[-*|] |^#{1,6} /.test(line))
    .length;
}

/** 파일 하나의 원시 수치. 비교는 여기서 하지 않는다. */
function measureDoc(text) {
  const s = String(text || "");
  return {
    chars: s.length,
    clauses: countClauses(s),
    citations: countMatches(s, CITATION_RE),
    caveatLines: countLinesWith(s, CAVEAT_MARKERS),
    evidenceLines: countLinesWith(s, ["근거:"]),
  };
}

function sumMeasures(docs) {
  const total = { chars: 0, clauses: 0, citations: 0, caveatLines: 0, evidenceLines: 0 };
  for (const text of Object.values(docs || {})) {
    const m = measureDoc(text);
    for (const k of Object.keys(total)) total[k] += m[k];
  }
  return total;
}

/** 0으로 나누지 않는다. 기준이 0이면 비율을 만들지 않고 null로 낸다 — 1.0으로 채우면 완벽해 보인다. */
function ratio(after, before) {
  if (!before) return null;
  return Number((after / before).toFixed(4));
}

/**
 * 기준 상태와 회차 상태를 받아 여섯 차원을 낸다.
 * `before`/`after`는 `{ 경로: 내용 }` 형태다.
 */
function scoreRubric({ before, after }) {
  const b = sumMeasures(before);
  const a = sumMeasures(after);
  const files = Object.keys(after || {});

  const dimensions = [
    {
      id: "reduction",
      label: "감축량",
      proxyFor: "지침이 실제로 줄었는가",
      value: ratio(a.chars, b.chars),
      raw: { before: b.chars, after: a.chars },
      direction: "lower-is-better",
    },
    {
      id: "evidence",
      label: "근거 보존",
      proxyFor: "`파일:줄` 인용과 `근거:` 줄이 남았는가. 인용의 내용이 맞는지는 보지 않는다",
      value: ratio(a.citations + a.evidenceLines, b.citations + b.evidenceLines),
      raw: { before: b.citations + b.evidenceLines, after: a.citations + a.evidenceLines },
      direction: "higher-is-better",
    },
    {
      id: "caveat",
      label: "한계 표지 보존",
      proxyFor: "한계·실패를 말하는 줄이 남았는가. 그런 낱말이 든 줄을 셀 뿐 뜻을 보지는 않는다",
      value: ratio(a.caveatLines, b.caveatLines),
      raw: { before: b.caveatLines, after: a.caveatLines },
      direction: "higher-is-better",
    },
    {
      id: "clause",
      label: "조항 보존",
      proxyFor: "규칙 항목이 몇 개 남았는가. 불릿과 헤딩의 수를 센다",
      value: ratio(a.clauses, b.clauses),
      raw: { before: b.clauses, after: a.clauses },
      direction: "higher-is-better",
    },
    {
      id: "density",
      label: "근거 밀도",
      proxyFor: "줄인 뒤에도 자수당 근거가 유지되는가. 감축과 보존을 한 축에서 본다",
      value: b.chars && a.chars
        ? Number((((a.citations + a.evidenceLines) / a.chars) / ((b.citations + b.evidenceLines) / b.chars || 1)).toFixed(4))
        : null,
      raw: { beforePerKChar: b.chars ? Number((((b.citations + b.evidenceLines) / b.chars) * 1000).toFixed(2)) : null, afterPerKChar: a.chars ? Number((((a.citations + a.evidenceLines) / a.chars) * 1000).toFixed(2)) : null },
      direction: "higher-is-better",
    },
    {
      id: "readability",
      label: "가독성",
      proxyFor: null,
      value: null,
      raw: null,
      direction: "human",
      note: "대리 지표가 없다. 사람이 스냅샷을 읽고 판단한다. null을 점수 0으로 읽지 않는다.",
    },
  ];

  return {
    files: files.length,
    dimensions,
    caveat:
      "이 점수는 관측 기록이지 판정이 아니다. 종료 판정에 쓰이지 않는다. "
      + "다섯 차원 전부 대리 지표이며 proxyFor에 무엇의 대리물인지 적혀 있다. "
      + "readability는 사람이 채운다 — null은 0이 아니라 '아직 안 봤다'는 뜻이다.",
  };
}

module.exports = { scoreRubric, measureDoc, sumMeasures, countClauses, CAVEAT_MARKERS };
