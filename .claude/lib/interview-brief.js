/**
 * 인터뷰 브리프(requirement-interview 01.5단계 산출물)의 형식·완결성 검증 로직.
 *
 * ATDD 06단계 산출물 — .claude/tests/interview-brief.test.js 의 AC-1~11을 통과시키기 위한 구현이다.
 *
 * **이 파일이 검증하는 것과 하지 않는 것을 명확히 한다.**
 * - 검증한다: 슬롯이 다 채워졌는가, 플레이스홀더가 남았는가, 목표가 한 문장인가,
 *   범위 밖이 실제로 잠겼는가, 분류가 유효한가. 전부 형식으로 판정 가능한 것들이다.
 * - 검증하지 않는다: 질문이 좋았는가, 답이 사실인가, 인터뷰가 충분했는가.
 *   슬롯에 그럴듯한 아무 문장이나 넣으면 이 검사는 통과한다. 그 구멍은 메우지 않고
 *   사람 승인(04단계)에 남긴다 — 형식 검사를 품질 보증으로 착각하는 것이 더 위험하기 때문이다.
 *
 * 로직을 마크다운 지시문에서 떼어내 여기에 둔 이유는 `stats.js`와 같다: 마크다운은 자동 테스트가 불가능하다.
 */
const fs = require("node:fs");

/** 브리프가 반드시 담아야 하는 슬롯. 순서는 문서에 나타나는 순서이며 이 순서 자체가 인터뷰 진행 순서다. */
const REQUIRED_SLOTS = ["목표", "현재 상태", "기대 동작", "완료 조건", "범위 밖", "미해결 가정"];

/** 요청 분류 — 질문 예산이 여기서 나오므로 유효값이 아니면 브리프를 통과시키지 않는다. */
const ALLOWED_KINDS = ["spike", "bounded", "architectural"];

/** 인터뷰가 끝나지 않았다는 신호. 남아 있으면 사람에게 되돌려야 한다. */
const PLACEHOLDER_TOKENS = ["TBD", "TODO", "FIXME", "XXX", "???", "미정", "추후 결정", "정하지 않음"];

/**
 * 플레이스홀더 검사에서 제외되는 슬롯.
 * '미해결 가정'은 애초에 아직 정하지 않은 것을 적는 자리라, 같은 어휘라도 결손이 아니라 산출물이다.
 */
const PLACEHOLDER_EXEMPT_SLOTS = ["미해결 가정"];

/** '없음'만 적어 두고 넘어가는 것을 잠금으로 인정하지 않기 위한 목록(범위 밖 전용). */
const EMPTY_ANSWERS = ["없음", "없다", "해당 없음", "n/a", "na", "none"];

/** 완료 조건이 관측 가능해 보이는지 판단하는 약한 휴리스틱. 확신할 수 없으므로 경고로만 쓴다. */
const OBSERVABLE_HINTS = [
  "표시", "노출", "보인다", "반환", "돌려", "저장", "응답", "전송", "기록",
  "실패", "통과", "포함", "이하", "이상", "미만", "초과", "정렬",
];

/** `## 슬롯명` 단위로 본문을 잘라 { 슬롯명: 본문 } 으로 돌려준다. */
function parseSlots(markdown) {
  const slots = {};
  const lines = String(markdown).split(/\r?\n/);
  let current = null;
  let buffer = [];

  const flush = () => {
    if (current !== null) slots[current] = buffer.join("\n").trim();
  };

  for (const line of lines) {
    const heading = line.match(/^##\s+(.+?)\s*$/);
    if (heading) {
      flush();
      current = heading[1];
      buffer = [];
      continue;
    }
    if (current !== null) buffer.push(line);
  }
  flush();

  return slots;
}

/** 머리말의 `- 분류: <값>` 을 뽑는다. 없으면 null. */
function parseKind(markdown) {
  const match = String(markdown).match(/^\s*[-*]\s*분류\s*:\s*(.+?)\s*$/m);
  return match ? match[1] : null;
}

/** 본문에서 불릿 항목만 뽑는다. 불릿이 하나도 없으면 빈 배열. */
function bulletItems(body) {
  return String(body)
    .split(/\r?\n/)
    .map((line) => line.match(/^\s*(?:[-*]|\d+\.)\s+(.*\S)\s*$/))
    .filter(Boolean)
    .map((match) => match[1].trim());
}

/** 문장 수를 센다. 한국어/영어 종결부호 기준이며, 목표가 한 문장인지 판정하는 데만 쓴다. */
function countSentences(text) {
  return String(text)
    .split(/[.!?。]+(?=\s|$)/)
    .map((part) => part.trim())
    .filter((part) => part.length > 0).length;
}

/**
 * 인터뷰 브리프 마크다운을 검증한다.
 *
 * @param {string} markdown 브리프 본문
 * @returns {{
 *   ok: boolean,
 *   missingSlots: string[],
 *   placeholders: Array<{slot: string, token: string}>,
 *   violations: string[],
 *   warnings: string[],
 * }}
 */
function validateBrief(markdown) {
  const source = typeof markdown === "string" ? markdown : "";
  const slots = parseSlots(source);

  const missingSlots = [];
  const placeholders = [];
  const violations = [];
  const warnings = [];

  // AC-3/AC-4: 슬롯이 없거나, 제목만 있고 본문이 비어 있으면 둘 다 '결손'으로 본다.
  for (const slot of REQUIRED_SLOTS) {
    const body = slots[slot];
    if (typeof body !== "string" || body === "") missingSlots.push(slot);
  }

  // AC-5/AC-6: 남아 있는 플레이스홀더를 슬롯 이름과 함께 보고한다(미해결 가정 슬롯은 제외).
  for (const slot of REQUIRED_SLOTS) {
    if (PLACEHOLDER_EXEMPT_SLOTS.includes(slot)) continue;
    const body = slots[slot];
    if (!body) continue;
    for (const token of PLACEHOLDER_TOKENS) {
      const pattern = new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i");
      if (pattern.test(body)) placeholders.push({ slot, token });
    }
  }

  // AC-9: 분류가 곧 질문 예산이므로, 값이 없거나 목록에 없으면 통과시키지 않는다.
  const kind = parseKind(source);
  if (kind === null) {
    violations.push("분류(spike/bounded/architectural)가 머리말에 없습니다");
  } else if (!ALLOWED_KINDS.includes(kind)) {
    violations.push(`분류 값이 올바르지 않습니다: "${kind}" (허용: ${ALLOWED_KINDS.join(", ")})`);
  }

  // AC-7: 목표는 한 문장. 두 문장이 되는 순간 요구사항이 둘로 쪼개져 있다는 신호다.
  const goal = slots["목표"];
  if (goal) {
    const goalLines = goal.split(/\r?\n/).filter((line) => line.trim() !== "");
    if (goalLines.length > 1 || countSentences(goal) > 1) {
      violations.push("목표는 한 문장이어야 합니다 (두 개 이상이면 요구사항을 나눠서 인터뷰하세요)");
    }
  }

  // AC-8: 범위 밖은 '없음'으로 넘어갈 수 없다. 여기서 잠그지 않으면 나중에 반드시 새어 나온다.
  const outOfScope = slots["범위 밖"];
  if (outOfScope) {
    const items = bulletItems(outOfScope);
    const meaningful = items.filter((item) => !EMPTY_ANSWERS.includes(item.toLowerCase()));
    if (meaningful.length === 0) {
      violations.push("범위 밖에 실제 항목이 최소 1개는 있어야 합니다 ('없음'은 잠금으로 인정하지 않습니다)");
    }
  }

  // AC-10: 관측 가능성은 형식으로 확신할 수 없다. 실패시키지 않고 경고로만 남겨 사람에게 넘긴다.
  const doneWhen = slots["완료 조건"];
  if (doneWhen) {
    const items = bulletItems(doneWhen);
    const observable = items.some(
      (item) => /\d/.test(item) || OBSERVABLE_HINTS.some((hint) => item.includes(hint))
    );
    if (items.length === 0) {
      violations.push("완료 조건은 항목(불릿)으로 최소 1개 적어야 합니다");
    } else if (!observable) {
      warnings.push("완료 조건에서 관측 가능한 표현(수치·상태 변화)을 찾지 못했습니다 — 사람이 직접 확인하세요");
    }
  }

  return {
    ok: missingSlots.length === 0 && placeholders.length === 0 && violations.length === 0,
    missingSlots,
    placeholders,
    violations,
    warnings,
  };
}

/**
 * 브리프 파일을 읽어 문자열로 돌려준다. 읽기 전용이며 절대 쓰지 않는다(AC-11).
 * 파일이 없거나 읽을 수 없으면 null — 호출자가 "브리프 없음"으로 다루게 하기 위함이다.
 */
function readBrief(filePath) {
  try {
    if (!fs.existsSync(filePath)) return null;
    return fs.readFileSync(filePath, "utf-8");
  } catch (_) {
    return null;
  }
}

module.exports = { REQUIRED_SLOTS, ALLOWED_KINDS, parseSlots, validateBrief, readBrief };
