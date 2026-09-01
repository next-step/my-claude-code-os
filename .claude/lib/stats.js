/**
 * 스킬 사용 통계 집계 로직.
 *
 * ATDD 06단계 산출물 — .claude/tests/stats.test.js 의 AC-1~8을 통과시키기 위한 구현이다.
 * `skill-stat` 스킬이 이 함수들을 불러 결과를 표로 보여준다.
 *
 * 로직을 마크다운 지시문에서 떼어내 여기에 둔 이유: 마크다운은 자동 테스트가 불가능하기 때문이다.
 * 검증할 것은 코드로, 보여줄 것은 지시문으로 나눈다.
 */
const fs = require("node:fs");

/** lastUsedAt이 실제 시각으로 해석되는 값인지 판정한다. 빈 문자열·누락·"어제쯤" 같은 값은 무효다. */
function toTimestamp(value) {
  if (typeof value !== "string" || value.trim() === "") return null;
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? null : ms;
}

/**
 * 통계 파일을 읽어서 파싱한 객체를 돌려준다. 읽기 전용이며 절대 쓰지 않는다(AC-6).
 * 파일이 없거나 내용이 깨졌으면 null을 돌려준다 — 호출자가 "기록 없음"으로 다루게 하기 위함이다.
 */
function readStats(filePath) {
  try {
    if (!fs.existsSync(filePath)) return null;
    const parsed = JSON.parse(fs.readFileSync(filePath, "utf-8"));
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch (_) {
    return null;
  }
}

/**
 * 통계 객체를 사람이 보기 좋은 형태로 집계한다.
 *
 * @returns {{
 *   isEmpty: boolean,
 *   message: string|null,
 *   totalCalls: number,
 *   rows: Array<{rank:number, name:string, count:number, lastUsedAt:string|null}>,
 *   mostUsed: {name:string, count:number}|null,
 *   recent: {names:string[], at:string}|null,
 *   recentMessage: string|null,
 * }}
 */
function summarize(stats) {
  const skills = stats && typeof stats.skills === "object" && stats.skills !== null ? stats.skills : {};
  const names = Object.keys(skills);

  // AC-3: 기록 자체가 없는 상태. 오류를 던지지 않고 안내 문구만 담아 돌려준다.
  if (names.length === 0) {
    return {
      isEmpty: true,
      message: "아직 기록된 스킬 호출이 없습니다",
      totalCalls: 0,
      rows: [],
      mostUsed: null,
      recent: null,
      recentMessage: null,
    };
  }

  const entries = names.map((name) => {
    const raw = skills[name] || {};
    return {
      name,
      count: typeof raw.count === "number" ? raw.count : 0,
      lastUsedAt: typeof raw.lastUsedAt === "string" ? raw.lastUsedAt : null,
    };
  });

  // AC-5: 기존 출력 — count 내림차순 순위 표, 최다 사용 스킬, 전체 호출 수.
  const rows = entries
    .slice()
    .sort((a, b) => b.count - a.count)
    .map((entry, index) => ({ rank: index + 1, name: entry.name, count: entry.count, lastUsedAt: entry.lastUsedAt }));

  const mostUsed = { name: rows[0].name, count: rows[0].count };
  const totalCalls =
    typeof stats.totalCalls === "number"
      ? stats.totalCalls
      : entries.reduce((sum, entry) => sum + entry.count, 0);

  // AC-7: lastUsedAt이 없거나 무효한 항목은 최근 사용 계산에서만 빠진다(순위 표에는 남는다).
  const dated = entries
    .map((entry) => ({ name: entry.name, at: entry.lastUsedAt, ms: toTimestamp(entry.lastUsedAt) }))
    .filter((entry) => entry.ms !== null);

  // AC-8: 유효한 시각이 하나도 없으면 최근 사용 자리에 안내만 두고 나머지는 정상 출력한다.
  if (dated.length === 0) {
    return { isEmpty: false, message: null, totalCalls, rows, mostUsed, recent: null, recentMessage: "최근 사용 정보 없음" };
  }

  const latestMs = Math.max(...dated.map((entry) => entry.ms));
  // AC-2: 동률이면 한 개만 고르지 않고 모두 나열하되 이름 오름차순으로 정렬한다.
  const tied = dated.filter((entry) => entry.ms === latestMs).sort((a, b) => a.name.localeCompare(b.name));

  return {
    isEmpty: false,
    message: null,
    totalCalls,
    rows,
    mostUsed,
    // AC-1: 가장 최근 사용 스킬 이름과 그 시각.
    recent: { names: tied.map((entry) => entry.name), at: tied[0].at },
    recentMessage: null,
  };
}

module.exports = { readStats, summarize };
