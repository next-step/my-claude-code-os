/**
 * 쿠팡 API 호출 예산과 캐시를 판정하는 순수 함수.
 *
 * 왜 필요한가: 쿠팡 파트너스 검색 API 는 **시간당 10회**로 제한된다. 이 파이프라인의
 * 처리량을 가르는 가장 좁은 길목이므로, 호출하기 전에 세어 보고 막아야 한다.
 * 한도를 넘겨 거부당하면 그 영상은 상품 없이 나가고 사람이 손으로 메워야 한다.
 *
 * 상태를 파일에 쓰고 읽는 일은 여기서 하지 않는다. 상태를 인자로 받아 새 상태를
 * 돌려주는 형태라 시계도 파일도 없이 테스트할 수 있다. 실제 저장은 `bin/` 이 한다.
 */
"use strict";

const 한시간 = 3600 * 1000;

const DEFAULTS = Object.freeze({
  /** 쿠팡 검색 API 의 시간당 호출 한도 */
  limitPerHour: 10,
  /** 한도를 세는 창의 길이 */
  windowMs: 한시간,
  /** 검색 결과를 재활용하는 기간. 상품 구성이 하루 사이에 크게 바뀌지 않는다. */
  cacheTtlMs: 24 * 한시간,
  /** 한도에 얼마나 가까워지면 경고할지 */
  warnAtRemaining: 3,
});

/** 빈 상태. 처음 돌릴 때 쓴다. */
function emptyState() {
  return { calls: [], cache: {} };
}

/**
 * 지금 호출해도 되는지 판정한다.
 *
 * @param {object} state `{ calls: number[], cache: object }`
 * @param {object} [options]
 * @returns {{allowed: boolean, used: number, remaining: number, retryAfterMs: number, warning: string|null}}
 */
function checkBudget(state, options = {}) {
  const o = { ...DEFAULTS, ...options };
  const now = Number.isFinite(o.now) ? o.now : Date.now();

  const 유효한호출 = 창안의호출(state, now, o.windowMs);
  const used = 유효한호출.length;
  const remaining = Math.max(0, o.limitPerHour - used);

  if (remaining > 0) {
    const warning =
      remaining <= o.warnAtRemaining
        ? `쿠팡 검색 호출이 ${remaining}회 남았다 (시간당 ${o.limitPerHour}회 한도)`
        : null;
    return { allowed: true, used, remaining, retryAfterMs: 0, warning };
  }

  // 가장 오래된 호출이 창 밖으로 나가야 한 칸이 빈다.
  const 가장오래된 = Math.min(...유효한호출);
  const retryAfterMs = Math.max(0, 가장오래된 + o.windowMs - now);

  return {
    allowed: false,
    used,
    remaining: 0,
    retryAfterMs,
    warning: `시간당 한도 ${o.limitPerHour}회를 다 썼다. ${Math.ceil(retryAfterMs / 60000)}분 뒤에 다시 된다`,
  };
}

/** 호출 한 건을 기록한 새 상태를 돌려준다. 창 밖으로 나간 기록은 함께 버린다. */
function recordCall(state, options = {}) {
  const o = { ...DEFAULTS, ...options };
  const now = Number.isFinite(o.now) ? o.now : Date.now();
  return {
    ...정상화(state),
    calls: [...창안의호출(state, now, o.windowMs), now],
  };
}

/**
 * 캐시를 확인한다. 살아 있으면 호출을 세지 않아도 된다.
 * @returns {{hit: boolean, value: any, ageMs: number|null}}
 */
function cacheLookup(state, key, options = {}) {
  const o = { ...DEFAULTS, ...options };
  const now = Number.isFinite(o.now) ? o.now : Date.now();

  const entry = 정상화(state).cache[캐시키(key)];
  if (!entry || !Number.isFinite(entry.at)) return { hit: false, value: null, ageMs: null };

  const ageMs = now - entry.at;
  if (ageMs < 0 || ageMs > o.cacheTtlMs) return { hit: false, value: null, ageMs };

  return { hit: true, value: entry.value, ageMs };
}

/** 캐시에 넣은 새 상태를 돌려준다. 만료된 항목은 함께 치운다. */
function cacheStore(state, key, value, options = {}) {
  const o = { ...DEFAULTS, ...options };
  const now = Number.isFinite(o.now) ? o.now : Date.now();

  const 살아있는것 = {};
  const cache = 정상화(state).cache;
  for (const [k, v] of Object.entries(cache)) {
    if (v && Number.isFinite(v.at) && now - v.at <= o.cacheTtlMs) 살아있는것[k] = v;
  }
  살아있는것[캐시키(key)] = { at: now, value };

  return { ...정상화(state), cache: 살아있는것 };
}

/** 검색어를 캐시 키로 바꾼다. 앞뒤 공백과 대소문자 차이로 캐시가 갈리지 않게 한다. */
function 캐시키(key) {
  return String(key || "").trim().toLowerCase();
}

function 창안의호출(state, now, windowMs) {
  return 정상화(state).calls.filter((t) => Number.isFinite(t) && now - t < windowMs && t <= now);
}

/** 파일이 망가졌거나 비었을 때를 대비해 형태를 맞춘다. */
function 정상화(state) {
  if (!state || typeof state !== "object") return emptyState();
  return {
    calls: Array.isArray(state.calls) ? state.calls : [],
    cache: state.cache && typeof state.cache === "object" ? state.cache : {},
  };
}

module.exports = { emptyState, checkBudget, recordCall, cacheLookup, cacheStore, DEFAULTS };
