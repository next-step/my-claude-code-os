/**
 * 영상 제목과 자막에서 쿠팡에 검색할 말을 뽑는 순수 함수.
 *
 * **한계를 먼저 밝힌다.** 이 저장소는 외부 의존성을 두지 않으므로 한국어 형태소
 * 분석기를 쓸 수 없다. 그래서 여기 있는 것은 조사·접미사를 잘라 내고 빈도를 세는
 * 어림법이지 형태소 분석이 아니다. 고유명사와 복합명사를 정확히 끊지 못한다.
 *
 * 그래도 쓸 만한 이유는 두 가지다. 첫째, 쿠팡 검색이 어차피 느슨해서 "에어프라이어"
 * 정도만 맞아도 관련 상품이 나온다. 둘째, 뽑은 말을 사람이 보고 고치는 것을 전제로
 * 한다 — 이 모듈은 최종 판단이 아니라 후보 제시다.
 *
 * 정확도가 부족하다고 판단되면 이 모듈만 언어 모델 호출로 바꾸면 된다. 입력과 출력
 * 형태를 단순하게 잡아 둔 것은 그 교체를 쉽게 하기 위해서다.
 */
"use strict";

/** 상품명이 될 수 없는 말들. 제목에 흔히 붙지만 검색어로는 방해가 된다. */
const 불용어 = new Set([
  "리뷰", "후기", "추천", "비교", "테스트", "언박싱", "개봉", "순위", "베스트",
  "내돈내산", "가성비", "실사용", "직접", "구매", "구입", "쇼핑", "득템", "정리",
  "영상", "채널", "구독", "좋아요", "댓글", "광고", "협찬", "무료", "할인", "특가",
  "최고", "최악", "진짜", "완전", "정말", "너무", "그냥", "이번", "오늘", "지금",
  "여러분", "우리", "저는", "제가", "이거", "그거", "저거", "이것", "그것",
  "가이드", "총정리", "모음", "편집", "브이로그", "일상",
  "끝장비교", "완벽비교", "최종비교", "구매가이드", "솔직후기", "찐후기", "리얼후기",
  "vs", "top", "best", "review", "unboxing", "shorts",
]);

/**
 * 서술어로 끝나는 말은 상품명이 아니다. 형태소 분석기가 없으니 어미로 걸러 낸다.
 * "비교했습니다"가 검색어로 뽑히는 것을 실제로 보고 추가했다.
 */
const 서술어어미 = [
  "습니다", "ㅂ니다", "합니다", "입니다", "됩니다", "봅니다", "냅니다",
  "했다", "한다", "이다", "하다", "된다", "있다", "없다",
  "하는", "했던", "하고", "해서", "지만", "는데", "세요", "네요", "어요", "아요",
  "겠죠", "나요", "까요", "려고", "면서", "라면", "거든", "잖아",
];

/**
 * 수량·차수 표현. 상품명이 아니다.
 * "25년차 주부" 의 "25년차" 가 검색어로 뽑히는 것을 실제로 보고 넣었다.
 */
const 수량표현 =
  /^\d+(년차|개월|주년|년|번째|인용|인분|만원|원|리터|세트|셋트|년ver|ver|위|등|배|개|명|권|층|칸|L|kg|g|ml)(대|짜리|권|개|명|층|칸|세트|셋트)?$/i;

/** 잘라 낼 조사와 어미. 긴 것부터 확인해야 "으로"가 "로"보다 먼저 걸린다. */
const 조사 = [
  "으로는", "에서는", "에게는", "으로", "에서", "에게", "까지", "부터", "보다", "처럼",
  "이라는", "라는", "이랑", "하고", "이고", "만큼", "조차", "마저", "이나", "거나",
  "은", "는", "이", "가", "을", "를", "의", "에", "와", "과", "도", "만", "로", "랑",
];

const DEFAULTS = Object.freeze({
  /** 돌려줄 검색어 개수 */
  limit: 3,
  /** 이보다 짧은 말은 버린다. 한 글자는 거의 쓸모가 없다. */
  minLength: 2,
  /** 자막에서 이 횟수 이상 나오면 주제어로 본다. */
  minSubtitleHits: 2,
  /** 우대할 말 목록. config/keywords.json 에서 주입한다. */
  boostWords: [],
  /**
   * 근거를 요구할지 여부. 켜면 제목에만 한 번 나온 말은 버리고, 자막에서도 나오거나
   * 우대 목록에 있는 말만 남긴다. 형태소 분석 없이 서술어와 부사를 걸러 내는 가장
   * 효과적인 수단이라 기본값으로 켜 둔다. 남는 말이 하나도 없으면 자동으로 끈다.
   */
  requireEvidence: true,
});

/**
 * @param {object} p
 * @param {string} p.title 영상 제목
 * @param {string} [p.channelTitle] 채널명. 검색어에서 뺀다
 * @param {string} [p.subtitleText] 구간 자막을 이어 붙인 글
 * @param {object} [options]
 * @returns {{keywords: string[], scored: Array<{word: string, score: number, reasons: string[]}>}}
 */
function extractKeywords(p = {}, options = {}) {
  const o = { ...DEFAULTS, ...options };

  const title = String(p.title || "");
  const channelTitle = String(p.channelTitle || "");
  const subtitleText = String(p.subtitleText || "");

  // 채널명에 들어간 말은 상품이 아니라 채널 정체성이다. 미리 빼 둔다.
  const 채널말 = new Set(토큰화(channelTitle).map(조사떼기));

  const 제목말 = 토큰화(title).map(조사떼기);
  const 자막말 = 토큰화(subtitleText).map(조사떼기);

  const 자막빈도 = new Map();
  for (const w of 자막말) 자막빈도.set(w, (자막빈도.get(w) || 0) + 1);

  const boost = new Set(o.boostWords.map((w) => String(w).toLowerCase()));

  const 후보 = new Map();
  for (const word of 제목말) {
    if (!쓸만한가(word, o, 채널말, boost)) continue;

    const 기존 = 후보.get(word);
    if (기존) {
      기존.score += 0.1;
      continue;
    }

    const reasons = ["제목에 나옴"];
    let score = 1;
    let 길이보너스 = false;

    const hits = 자막빈도.get(word) || 0;
    if (hits >= o.minSubtitleHits) {
      score += 0.5 + Math.min(1, hits / 10);
      reasons.push(`자막에 ${hits}번`);
    }
    if (boost.has(word.toLowerCase())) {
      score += 1;
      reasons.push("우대 목록에 있음");
    }
    // 긴 말일수록 구체적이다. "에어프라이어"가 "가전"보다 낫다.
    // 다만 이것은 **근거로 세지 않는다.** 길이만 보고 통과시키면 "아껴드리" 처럼
    // 조사를 떼다 만 서술어 조각이 검색어로 올라온다 — 실제로 그렇게 나왔다.
    if (word.length >= 4) {
      score += 0.3;
      길이보너스 = true;
    }

    후보.set(word, { word, score, reasons, 길이보너스 });
  }

  // 나란히 붙은 두 말을 이어 붙여 우대 목록과 맞춰 본다.
  // "커피 머신" 이 두 토큰으로 쪼개져 "커피머신" 을 놓치고 브랜드명에 밀리는 것을
  // 실제로 보고 넣었다. 형태소 분석기가 없어 복합명사를 못 끊는 한계를 좁히는 방편이다.
  for (const 말들 of [제목말, 자막말]) {
    for (let i = 0; i + 1 < 말들.length; i += 1) {
      const 붙인말 = 말들[i] + 말들[i + 1];
      if (!boost.has(붙인말.toLowerCase())) continue;
      if (후보.has(붙인말)) continue;
      if (!쓸만한가(붙인말, o, 채널말, boost)) continue;
      const 자막에 = 자막빈도.get(말들[i]) || 0;
      후보.set(붙인말, {
        word: 붙인말,
        score: 2.5 + Math.min(1, 자막에 / 10),
        reasons: ["붙여 보니 우대 목록에 있음", "제목·자막에 나옴"],
      });
    }
  }

  // 제목에 없더라도 자막에서 아주 자주 나오고 우대 목록에 있으면 넣는다.
  for (const [word, hits] of 자막빈도) {
    if (후보.has(word)) continue;
    if (!boost.has(word.toLowerCase())) continue;
    if (!쓸만한가(word, o, 채널말, boost)) continue;
    후보.set(word, { word, score: 0.8 + Math.min(1, hits / 10), reasons: [`자막에 ${hits}번`, "우대 목록에 있음"] });
  }

  const 정렬 = (arr) =>
    [...arr].sort((a, b) => b.score - a.score || b.word.length - a.word.length || a.word.localeCompare(b.word));

  const 전체 = 정렬([...후보.values()]);

  // 근거가 있는 말만 남긴다. 전부 걸러지면 근거 요구를 포기하고 전체를 쓴다
  // — 자막이 없는 영상에서 빈손으로 돌아가지 않기 위해서다.
  //
  // 근거는 "제목에 나옴" 말고 하나 더 있어야 한다. 자막에 여러 번 나오거나 우대 목록에
  // 있어야 하고, 길이가 길다는 것만으로는 통과시키지 않는다. 길이만으로 통과시켰더니
  // "아껴드리" 처럼 조사를 떼다 만 서술어 조각이 검색어로 올라왔다.
  //
  // **거르기를 먼저 하고 표시를 나중에 한다.** 처음에는 "구체적인 말(근거 아님)" 이라는
  // 꼬리표를 reasons 에 먼저 붙였는데, 그 바람에 근거 개수가 다시 2가 되어 거르기가
  // 통째로 무력해졌다. 설명하려고 붙인 꼬리표가 판정을 바꿔 버린 것이다.
  const 근거있음 = 전체.filter((x) => x.reasons.length >= 2);
  const 최종 = o.requireEvidence && 근거있음.length > 0 ? 근거있음 : 전체;

  /** 점수에만 반영된 길이 보너스를 사람이 읽을 수 있게 표시한다. 반드시 판정 뒤에 부른다. */
  const 표시 = (arr) =>
    arr.map(({ 길이보너스, ...나머지 }) =>
      길이보너스 ? { ...나머지, reasons: [...나머지.reasons, "구체적인 말(근거 아님)"] } : 나머지
    );

  return {
    keywords: 최종.slice(0, o.limit).map((x) => x.word),
    scored: 표시(최종),
    evidenceRelaxed: o.requireEvidence && 근거있음.length === 0,
  };
}

function 쓸만한가(word, o, 채널말, boost) {
  if (word.length < o.minLength) return false;
  if (불용어.has(word.toLowerCase())) return false;
  // 채널명에 든 말은 상품이 아니라 채널 정체성이라 뺀다. **단 우대 목록에 있으면 남긴다.**
  // "앳키친 | 에어프라이어 요리" 채널에서 "에어프라이어" 가 통째로 지워지는 것을
  // 실제로 보고 넣은 예외다. 채널이 상품군 이름을 달고 있는 경우가 드물지 않다.
  if (채널말.has(word) && !(boost && boost.has(word.toLowerCase()))) return false;
  // 숫자만 있는 말(연도, 개수)은 상품명이 아니다.
  if (/^[0-9]+$/.test(word)) return false;
  // 수량·차수 표현도 마찬가지다.
  if (수량표현.test(word)) return false;
  // 서술어로 끝나면 상품명이 아니다.
  if (서술어어미.some((e) => word.length > e.length && word.endsWith(e))) return false;
  // 제품 모델명 조각은 상품군이 아니다. "A9", "X1", "T50air" 같은 것들이다.
  // 쿠팡에 그대로 검색하면 엉뚱한 결과가 나온다. 다만 "USB", "SSD" 처럼 한글이 없어도
  // 그 자체로 상품군인 말이 있어서, 우대 목록에 있거나 숫자 없는 세 글자 이상이면 남긴다.
  if (모델명조각(word) && !(boost && boost.has(word.toLowerCase()))) return false;
  return true;
}

/**
 * 한글이 하나도 없는 짧은 말이나 숫자가 섞인 말은 제품 모델명 조각으로 본다.
 * "USB"·"SSD" 처럼 숫자 없는 세 글자 이상은 그 자체로 상품군일 수 있어 남긴다.
 */
function 모델명조각(word) {
  if (/[가-힣]/.test(word)) return false;
  return word.length < 3 || /\d/.test(word);
}

/** 한글·영숫자 덩어리만 남기고 쪼갠다. */
function 토큰화(text) {
  return String(text)
    .replace(/[^0-9A-Za-z가-힣\s]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
}

/** 끝에 붙은 조사를 뗀다. 떼고 나서 너무 짧아지면 원래 말을 쓴다. */
function 조사떼기(word) {
  for (const j of 조사) {
    if (word.length > j.length + 1 && word.endsWith(j)) {
      return word.slice(0, -j.length);
    }
  }
  return word;
}

module.exports = { extractKeywords, DEFAULTS, 불용어 };
