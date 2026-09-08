/**
 * 독립 리뷰 결과를 04단계 승인 화면으로 넘길 때, 호출자가 지적을 **축소하지 않았는지** 검사한다.
 *
 * ## 왜 필요한가 (2026-09-07 실측)
 * gitStatus(브랜치·최근 커밋 5개·변경 파일)는 세션 시작 시 환경이 주입하며 서브에이전트에도
 * 그대로 간다. 저장소 안에서 끌 수단이 없다. 실측에서 `policy-reviewer` 자신은 커밋 로그가
 * 답을 알려줘도 판정이 무뎌지지 않았다(4회 모두 같은 FAIL). 그런데 **리뷰 결과를 받아 정리하는
 * 호출자**가 커밋 SHA를 인용하며 리뷰어의 지적 5~6개를 "진짜 미커버는 2개"로 깎았다
 * (누수 팔 2/2, 무누수 팔 0/2 — `docs/context-ab-test.md` 실험 3).
 *
 * 04단계 승인 화면에 올라가는 것은 호출자가 정리한 목록이므로 **사람은 깎인 목록을 본다.**
 * 누수 자체는 못 막으니 **쓰이는 지점**을 막는다.
 *
 * ## 이 검사가 잡지 못하는 것 (반드시 알고 쓸 것)
 * - 불릿 개수 비교는 **조악하다.** 항목을 병합하지 않고 문장만 무력화하면(“…이지만 문제 없다”)
 *   개수는 그대로라 통과한다.
 * - 호출자가 지적을 그대로 옮기면서 **순서를 바꾸거나 강조를 죽이는 것**도 못 잡는다.
 * - 커밋 SHA 없이 자연어로만 구현 지식을 흘리면("이미 반영된 것으로 보인다") 못 잡는다.
 *
 * 즉 이것은 **게이트가 아니라 경보**다. 통과했다고 인계가 정직했다는 뜻이 아니다.
 * 최종 판단은 04단계의 사람이 한다 — `hook-discipline.md`의 "규율은 기계, 판단은 AI, 결정은 사람".
 *
 * 순수 함수만 담는다(fs 접근 없음). `.claude/tests/review-handoff.test.js` 가 검증한다.
 */

/** 내용이 있는 불릿·번호 항목만 지적 항목으로 센다. 너무 짧은 줄은 제목·구분자로 보고 뺀다. */
const MIN_ITEM_CHARS = 10;

/** 커밋 해시로 볼 최소 길이. git의 기본 축약이 7자다. */
const SHA_PATTERN = /\b[0-9a-f]{7,40}\b/g;

/**
 * 텍스트에서 지적 항목(불릿·번호 목록)의 개수를 센다.
 * 중첩 여부는 구분하지 않는다 — 들여쓴 항목도 리뷰어가 낸 지적일 수 있기 때문이다.
 * @returns {number}
 */
function countFindings(text) {
  if (typeof text !== "string") return 0;
  return text
    .split(/\r?\n/)
    .map((line) => line.match(/^\s*(?:[-*+]|\d+\.)\s+(.*\S)\s*$/))
    .filter((match) => match !== null && match[1].length >= MIN_ITEM_CHARS).length;
}

/**
 * 텍스트에 커밋 해시로 보이는 토큰이 있는지 찾는다.
 * 16진수 7자 이상이면 해시로 본다. 오탐(예: 색상 코드)을 줄이려고 숫자만으로 된 토큰은 뺀다.
 * @returns {string[]}
 */
function citedCommits(text) {
  if (typeof text !== "string") return [];
  const found = text.match(SHA_PATTERN) || [];
  const unique = [];
  for (const token of found) {
    if (/^\d+$/.test(token)) continue; // 순수 숫자는 해시가 아니라 수치일 가능성이 높다
    if (!/[a-f]/.test(token)) continue; // 알파벳이 하나도 없으면 해시로 보지 않는다
    if (!unique.includes(token)) unique.push(token);
  }
  return unique;
}

/**
 * 리뷰어 원문과 호출자가 정리한 인계문을 비교한다.
 *
 * @param {{reviewerText: string, handoffText: string}} input
 * @returns {{
 *   reviewerItems: number, handoffItems: number, shrunk: boolean,
 *   citedCommits: string[], ok: boolean, warnings: string[],
 * }}
 */
function checkHandoff({ reviewerText, handoffText } = {}) {
  const reviewerItems = countFindings(reviewerText);
  const handoffItems = countFindings(handoffText);
  const commits = citedCommits(handoffText);
  const warnings = [];

  const shrunk = handoffItems < reviewerItems;
  if (shrunk) {
    warnings.push(
      `지적 축소: 리뷰어는 ${reviewerItems}개를 냈는데 인계문에는 ${handoffItems}개만 있습니다. 항목을 지우거나 합치지 말고 그대로 올리세요 — 무엇을 반영할지는 04단계에서 사람이 정합니다`
    );
  }
  if (commits.length > 0) {
    warnings.push(
      `구현 지식 유입: 인계문이 커밋 해시(${commits.join(", ")})를 인용합니다. 리뷰어는 구현을 못 보게 되어 있습니다 — 커밋 지식은 지적을 지우는 근거가 아니라 항목에 덧붙이는 주석으로만 쓰세요`
    );
  }

  return {
    reviewerItems,
    handoffItems,
    shrunk,
    citedCommits: commits,
    ok: warnings.length === 0,
    warnings,
  };
}

module.exports = { countFindings, citedCommits, checkHandoff, MIN_ITEM_CHARS };
