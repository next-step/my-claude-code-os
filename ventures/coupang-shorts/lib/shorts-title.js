/**
 * 원본 영상 제목에서 훅을 뽑아 쇼츠용 제목을 만드는 순수 함수.
 *
 * 왜 원본 제목을 재료로 쓰는가: 사람이 쓴 글이라 오타가 없고, 이미 클릭을 받아 본
 * 문구다. 구간 자막이 더 구체적이긴 하지만 자동 생성이라 오타가 섞인다 — 실제로
 * "조지루시"가 "조직"으로 적혀 있었다.
 *
 * 원본 제목은 유튜브 긴 영상용이라 그대로 쓸 수 없다. 검색 노출을 노린 키워드 나열과
 * "구매가이드", "내돈내산", "끝장비교" 같은 관용구가 붙어 있고, 쇼츠에서는 길어서
 * 잘린다. 그래서 절로 쪼갠 뒤 점수를 매겨 가장 훅에 가까운 절 하나를 고른다.
 *
 * 형태소 분석기가 없으므로 여기 있는 것은 어림법이다. 실제 영상 6편의 제목을 기준
 * 표본으로 삼아 테스트에 박아 두었으니, 규칙을 고치면 그 6개가 어떻게 변하는지 바로
 * 드러난다.
 */
"use strict";

/** 쇼츠 제목의 목표 길이. 모바일에서 이보다 길면 뒤가 잘린다. */
const TARGET_CHARS = 38;

/** 유튜브 제목 상한. */
const MAX_CHARS = 100;

const 꼬리표 = " #shorts";

/** 절을 가르는 기호. 유튜브 제목에서 실제로 쓰이는 것들이다. */
const 구분기호 = /[|｜ㅣ/·•\-—–,，、(){}\[\]]+/;

/**
 * 절을 가르는 연결어미. 이 말로 끝나는 지점에서도 한 번 더 자른다.
 * "유료 광고에 지친 당신을 위해 직접 사서 비교했습니다" 처럼 기호가 하나도 없는
 * 긴 제목을 다루기 위해 필요하다.
 */
const 연결어미 = ["위해", "위하여", "려면", "하려면", "때문에", "덕분에"];

/** 검색 노출용으로 붙는 관용구. 훅이 아니라 잡음이다. */
const 관용구 = [
  "구매가이드", "구매 가이드", "내돈내산", "끝장비교", "끝장 비교", "완벽비교", "완벽 비교",
  "총정리", "최종정리", "솔직후기", "찐후기", "리얼후기", "협찬아님", "광고아님",
  "추천", "비교", "리뷰", "후기", "가이드", "정리", "모음", "순위", "베스트",
];

/**
 * 절이 훅으로 쓸 만한 알맹이를 가졌는지 본다.
 *
 * 관용구에 감점만 주면 강조 표지 점수가 그 감점을 덮는다. 실제로 "내돈내산!" 이
 * 1순위로 뽑혔는데, 관용구를 빼고 나면 남는 것이 느낌표뿐인 절이었다.
 * 감점이 아니라 탈락으로 다뤄야 하는 경우다.
 */
function 알맹이있는가(text) {
  let 남은것 = String(text);
  for (const w of 관용구) 남은것 = 남은것.split(w).join("");
  남은것 = 남은것.replace(/[^0-9A-Za-z가-힣]/g, "");
  return 남은것.length >= 3;
}

/**
 * 제품 모델명처럼 한글이 하나도 없는 짧은 절은 훅이 아니다.
 * "R1 SE+" 가 제목으로 뽑히는 것을 실제로 보고 넣었다.
 */
function 모델명인가(text) {
  const 한글수 = (String(text).match(/[가-힣]/g) || []).length;
  return 한글수 === 0 && String(text).length < 15;
}

/**
 * 뒤에 매달린 말을 떼어 낸다. 두 가지를 본다.
 *
 *  1. 관용구. "캡슐 커피머신 첫인상 리뷰" 의 "리뷰" 같은 것.
 *  2. 뒤에 올 말이 사라져 붕 뜬 수식어. 관용구를 떼고 나면 흔히 생긴다.
 *     "직접 다 써본 25년차 주부의 최종 비교 후기" 에서 "비교 후기" 를 떼면
 *     "…주부의 최종" 이 남는데, 꾸밈을 받을 말이 없어 읽히지 않는다.
 */
const 매달린수식어 = ["최종", "최고", "최신", "최강", "역대", "진짜", "완전", "강력", "본격", "완벽"];

function 꼬리다듬기(text) {
  let 말들 = String(text).split(/\s+/).filter(Boolean);
  while (말들.length > 1) {
    const 끝말 = 말들[말들.length - 1].replace(/[!?~.]+$/, "");
    if (!관용구.includes(끝말) && !매달린수식어.includes(끝말)) break;
    말들 = 말들.slice(0, -1);
  }

  // 관형격 조사만 떼고 말 자체는 남긴다. "주부의" 를 통째로 지우면 "직접 다 써본
  // 25년차" 가 되어 오히려 더 허전해진다 — 조사만 떼면 "…25년차 주부" 로 끝난다.
  const 끝 = 말들[말들.length - 1];
  if (말들.length > 1 && /^.{2,}의$/.test(끝)) {
    말들[말들.length - 1] = 끝.slice(0, -1);
  }

  return 말들.join(" ");
}

/** 버전 꼬리표. `(26년ver.)` 같은 것. */
const 버전꼬리 = /\(?\s*\d{2,4}\s*년?\s*ver\.?\s*\)?/gi;

/**
 * @param {object} p
 * @param {string} p.videoTitle 원본 제목
 * @param {string[]} [p.keywords] 상품 검색어. 첫 번째를 제목에 붙인다
 * @param {object} [options] `{ targetChars, maxChars, suffix }`
 * @returns {{title: string, hook: string, source: string, keywordAppended: boolean}}
 */
function buildShortsTitle(p = {}, options = {}) {
  const targetChars = options.targetChars || TARGET_CHARS;
  const maxChars = options.maxChars || MAX_CHARS;
  const suffix = options.suffix === undefined ? 꼬리표 : options.suffix;

  const 원본 = 정리(String(p.videoTitle || ""));
  const keywords = Array.isArray(p.keywords) ? p.keywords.filter(Boolean) : [];
  // 훅에 이미 들어 있지 않은 첫 번째 검색어를 고른다. 1순위만 보면, 훅이 그 말을
  // 품고 있을 때 키워드를 통째로 못 붙인다 — "오븐형 vs 바스켓형" 이 그런 경우였다.
  const 대표키워드 = keywords[0] || "";

  if (!원본) {
    const 제목 = 대표키워드 ? `${대표키워드}${suffix}` : suffix.trim();
    return { title: 제목, hook: "", source: "제목 없음", keywordAppended: Boolean(대표키워드) };
  }

  const 후보들 = 절뽑기(원본);
  const 점수표 = 후보들
    .map((절) => ({ text: 절.text, ...점수매기기(절, 대표키워드, targetChars) }))
    .sort((a, b) => b.score - a.score || a.text.length - b.text.length);

  const 최고 = 점수표[0];
  // 다듬고 나서 아무것도 안 남는 제목이 있다. 기호뿐인 제목이 그렇다.
  // 그때는 원본을 억지로 쓰지 않고 키워드만으로 제목을 만든다.
  let hook = 다듬기(최고 ? 최고.text : 원본);
  if (!hook) {
    const 제목 = 대표키워드 ? `${대표키워드}${suffix}` : suffix.trim();
    return { title: 제목, hook: "", source: "훅 없음", keywordAppended: Boolean(대표키워드) };
  }

  // 1순위 검색어만 본다. 훅에 이미 들어 있으면 붙이지 않는다.
  // 한때 "훅에 없는 첫 번째 검색어"를 찾게 했더니, 훅이 주제를 이미 담고 있는데도
  // 2순위 브랜드명을 덧붙여 제목이 길고 산만해졌다. 되돌렸다.
  const 붙인공백없는훅 = hook.replace(/\s/g, "");
  const 첫검색어 = keywords[0] || "";
  const 붙일키워드 = 첫검색어 && !붙인공백없는훅.includes(String(첫검색어).replace(/\s/g, "")) ? 첫검색어 : "";
  const keywordAppended = Boolean(붙일키워드);

  let title = keywordAppended ? `${hook} | ${붙일키워드}${suffix}` : `${hook}${suffix}`;

  // 상한을 넘기면 훅부터 줄인다. 키워드와 꼬리표는 남긴다.
  if (title.length > maxChars) {
    const 여유 = maxChars - (title.length - hook.length) - 1;
    hook = `${hook.slice(0, Math.max(1, 여유))}…`;
    title = keywordAppended ? `${hook} | ${붙일키워드}${suffix}` : `${hook}${suffix}`;
  }

  return { title, hook, source: 최고 ? 최고.source : "원본 전체", keywordAppended };
}

/** 제목을 절 후보로 쪼갠다. 따옴표 안과 강조 표지로 끝나는 구간을 먼저 챙긴다. */
function 절뽑기(원본) {
  const 후보 = [];

  // 1. 따옴표 안. 가장 강한 훅이다.
  for (const m of 원본.matchAll(/["“”'']([^"“”'']{4,40})["“”'']/g)) {
    후보.push({ text: m[1], kind: "따옴표" });
  }

  // 2. 강조 표지로 끝나는 구간. **표지를 훅에 포함시킨다** — "작년보다 더 싸짐 ㄷㄷ"
  //    에서 ㄷㄷ 를 떼면 맥없어진다. 표지 자체가 훅의 일부다.
  for (const m of 원본.matchAll(/([^!?|｜ㅣ/,，、()\[\]]{4,40}?\s*(?:ㄷㄷ+|ㅋㅋ+|[!]+))/gu)) {
    후보.push({ text: m[1], kind: "강조" });
  }
  // 이모지와 물음표는 표지로만 쓰고 훅에 넣지 않는다.
  for (const m of 원본.matchAll(/([^!?|｜ㅣ/,，、()\[\]]{4,40}?)\s*(?:[?]+|[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}])/gu)) {
    후보.push({ text: m[1], kind: "강조" });
  }

  // 3. 기호로 쪼갠 절.
  for (const 조각 of 원본.split(구분기호)) {
    const t = 조각.trim();
    if (t.length >= 4) 후보.push({ text: t, kind: "절" });
  }

  // 4. 연결어미에서 한 번 더 자른다. 기호가 없는 긴 제목을 위해서다.
  for (const 조각 of [...후보]) {
    for (const 어미 of 연결어미) {
      const i = 조각.text.indexOf(어미);
      if (i > 3 && i + 어미.length < 조각.text.length) {
        후보.push({ text: 조각.text.slice(0, i + 어미.length), kind: "연결어미" });
      }
    }
  }

  // 5. 아무것도 못 뽑았으면 원본 전체를 후보로 둔다.
  if (후보.length === 0) 후보.push({ text: 원본, kind: "전체" });

  const 본것 = new Set();
  return 후보
    .map((x) => ({ ...x, text: 꼬리다듬기(다듬기(x.text)) }))
    .filter((x) => {
      if (!x.text || x.text.length < 4 || 본것.has(x.text)) return false;
      // 관용구를 빼면 남는 것이 없는 절과 제품 모델명은 훅이 아니다. 감점이 아니라 탈락이다.
      if (!알맹이있는가(x.text)) return false;
      if (모델명인가(x.text)) return false;
      본것.add(x.text);
      return true;
    });
}

function 점수매기기(절, 대표키워드, targetChars) {
  const t = 절.text;
  let score = 0;
  const 이유 = [];

  if (절.kind === "따옴표") { score += 6; 이유.push("따옴표 안"); }
  else if (절.kind === "강조") { score += 4; 이유.push("강조 표지"); }
  else if (절.kind === "연결어미") { score += 0.5; 이유.push("연결어미에서 끊음"); }

  // 문장처럼 끝나면 훅으로 읽힌다.
  // 종결 형태를 넓게 본다. "비싸요" 처럼 어간이 붙은 말을 놓치면 가장 좋은 훅을 놓친다.
  if (/(요|다|까|죠|네|음|함|짐|것|이것|세요|니다)[!.?]?$/.test(t)) {
    score += 2;
    이유.push("문장처럼 끝남");
  }

  // 길이. 쇼츠 훅은 짧을수록 읽힌다. 12자 안팎을 이상으로 보고 완만하게 깎는다.
  const 이상길이 = 12;
  score += Math.max(0, 3 - Math.abs(t.length - 이상길이) / 8);

  // 관용구가 들어 있으면 깎는다.
  const 걸린관용구 = 관용구.filter((w) => t.includes(w));
  if (걸린관용구.length > 0) {
    score -= 1.5 * 걸린관용구.length;
    이유.push(`관용구 ${걸린관용구.join("·")}`);
  }

  // 상품 키워드만으로 이뤄진 절은 훅이 아니다.
  const 키워드뺀나머지 = 대표키워드 ? t.split(대표키워드).join("").replace(/[\s]/g, "") : t;
  if (대표키워드 && 키워드뺀나머지.length <= 3) {
    score -= 4;
    이유.push("키워드뿐");
  }

  // 화자가 드러나면 사람 이야기로 읽힌다.
  if (/(내가|제가|직접|년차|주부|아빠|엄마|써본|사서|당신)/.test(t)) {
    score += 1.5;
    이유.push("화자가 드러남");
  }

  // 숫자가 있으면 구체적이다. 다만 연도만 있는 것은 뺀다.
  if (/\d/.test(t) && !/^\s*(20)?\d{2}\s*년?\s*$/.test(t)) {
    score += 1;
    이유.push("숫자 포함");
  }

  if (t.length > targetChars) { score -= 2; 이유.push("너무 김"); }

  return { score: Math.round(score * 100) / 100, reasons: 이유, source: 절.kind };
}

/** 절 하나를 다듬는다. 버전 꼬리표와 앞뒤 잡기호를 걷어 낸다. */
function 다듬기(text) {
  return String(text)
    .replace(버전꼬리, " ")
    .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, " ")
    .replace(/^[\s"“”''·,，、!?~\-—–]+/, "")
    // 끝의 ! 와 ㄷㄷ 는 남긴다. 훅의 일부다.
    .replace(/[\s"“”''·,，、~\-—–]+$/, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** 원본 제목 전체를 한 번 정리한다. */
function 정리(text) {
  return text.replace(/\s+/g, " ").trim();
}

module.exports = { buildShortsTitle, TARGET_CHARS, MAX_CHARS };
