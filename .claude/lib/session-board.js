/**
 * 세션 인계·협업 계층의 집계 로직.
 *
 * 세션마다 훅이 `.claude/sessions/<session_id>.json` 파일 하나를 남긴다. 이 파일들을
 * 모아 "지금 누가 살아서 무엇을 하고 있는가 / 직전 세션은 어디까지 하다 멈췄는가"를
 * 만들어 내는 것이 이 모듈의 일이다.
 *
 * 왜 세션당 파일 1개인가:
 *   보드를 단일 JSON 하나로 두면 여러 세션이 동시에 read-modify-write 하다 갱신이
 *   유실된다. 파일을 쪼개면 각 파일의 필자가 그 세션 하나뿐이라 락이 필요 없고,
 *   파일 하나가 깨져도 나머지는 멀쩡하다.
 *
 * 이 파일은 순수 함수만 담는다(recordDisplayName만 좁은 예외). 모든 함수는 fs 호출을
 * 옵션으로 주입받을 수 있고, 시간에 의존하는 함수는 `now`를 주입받는다 — 실제 시계를
 * 쓰면 오늘 통과하고 내일 깨지는 테스트가 되기 때문이다(context-map.js와 같은 습관).
 *
 * .claude/tests/session-board.test.js 가 이 파일의 인수기준을 검증한다.
 */
const fs = require("node:fs");
const path = require("node:path");

/** 하트비트가 이 시간 넘게 안 오면 죽은 세션으로 본다. */
const STALE_AFTER_MS = 30 * 60 * 1000;
/** 이 시간 안에 만진 파일만 "지금 작업 중"으로 보고 충돌 경고를 낸다. */
const CONFLICT_WINDOW_MS = 30 * 60 * 1000;
/** 세션 하나가 기억하는 최근 편집 파일 수. */
const MAX_RECENT_FILES = 20;
/** lastMessage 저장 상한. 코드블록이 통째로 들어가는 걸 막는다. */
const MESSAGE_MAX_CHARS = 240;
/** SessionStart가 주입할 브리핑의 상한. 매 턴 상주하는 비용이라 짧아야 한다. */
const BRIEF_MAX_CHARS = 800;
/** 보드에 보여줄 종료 세션 수. */
const MAX_ENDED_SHOWN = 5;

/**
 * session_id를 파일명으로 써도 안전한지 검사한다.
 * 훅 payload는 신뢰 경계 밖이다 — `../`나 슬래시가 섞인 값이 그대로 파일명이 되면
 * 저장소 바깥에 쓰게 된다. UUID보다 살짝 넉넉하게 허용하되 경로 문자는 전부 막는다.
 * @returns {string|null} 안전하면 원본, 아니면 null (예외를 던지지 않는다)
 */
function sanitizeSessionId(id) {
  if (typeof id !== "string") return null;
  return /^[A-Za-z0-9_-]{8,64}$/.test(id) ? id : null;
}

/** 시각 문자열을 ms로. 누락·빈 문자열·"어제쯤" 같은 값은 null (stats.js와 같은 계약). */
function toTimestamp(value) {
  if (typeof value !== "string" || value.trim() === "") return null;
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? null : ms;
}

/** "14분 전"처럼 사람이 읽는 상대 시각. 값이 없으면 "시각 미상". */
function formatRelative(value, now = Date.now()) {
  const ms = toTimestamp(value);
  if (ms === null) return "시각 미상";
  const diff = Math.max(0, now - ms);
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "방금 전";
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}

/**
 * 대화 내용을 세션 파일에 남기기 전에 다듬는다.
 * 개행을 접고, 명백한 시크릿 접두사를 가리고, 상한까지 자른다.
 * 이 필드는 대화의 일부를 로컬 파일에 남긴다 — 그래서 .claude/sessions/ 는 gitignore된다.
 */
function condenseMessage(text, maxChars = MESSAGE_MAX_CHARS) {
  if (typeof text !== "string") return null;
  const folded = text.replace(/\s+/g, " ").trim();
  if (folded === "") return null;
  const masked = folded.replace(/\b(?:sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{8,}|AKIA[0-9A-Z]{8,})/g, "***");
  return masked.length > maxChars ? masked.slice(0, maxChars) : masked;
}

const asString = (value) => (typeof value === "string" && value !== "" ? value : null);

/** 세션 파일 하나를 정규화한다. 누락 필드는 undefined가 아니라 명시적 기본값으로 채운다. */
function normalizeEntry(raw) {
  if (!raw || typeof raw !== "object") return null;
  const sessionId = asString(raw.sessionId);
  if (!sessionId) return null;

  const recentFiles = Array.isArray(raw.recentFiles)
    ? raw.recentFiles
        .filter((f) => f && typeof f === "object" && asString(f.path))
        .map((f) => ({ path: f.path, at: asString(f.at) }))
    : [];

  return {
    sessionId,
    startedAt: asString(raw.startedAt),
    source: asString(raw.source),
    cwd: asString(raw.cwd),
    gitBranch: asString(raw.gitBranch),
    lastHeartbeatAt: asString(raw.lastHeartbeatAt),
    turns: typeof raw.turns === "number" && Number.isFinite(raw.turns) ? raw.turns : 0,
    lastMessage: asString(raw.lastMessage),
    recentFiles,
    endedAt: asString(raw.endedAt),
    endReason: asString(raw.endReason),
    displayName: asString(raw.displayName),
    updatedAt: asString(raw.updatedAt),
  };
}

/**
 * 세션 파일 하나를 읽어 정규화해 돌려준다. 읽기 전용이다.
 * 없거나 깨졌으면 null — 호출자가 "기록 없음"으로 다루게 하기 위함이다.
 */
function readSessionFile(filePath, options = {}) {
  const { readFileSync = fs.readFileSync, existsSync = fs.existsSync } = options;
  try {
    if (!existsSync(filePath)) return null;
    return normalizeEntry(JSON.parse(readFileSync(filePath, "utf-8")));
  } catch (_) {
    return null;
  }
}

/**
 * `.claude/sessions/` 전체를 훑어 정규화된 엔트리 배열을 만든다.
 * 디렉터리가 없으면 빈 배열이다 — 첫 세션에서는 정상 상태이지 오류가 아니다.
 * 깨진 파일 하나가 전체를 무너뜨리지 않도록 파일 단위로 건너뛴다.
 */
function listSessions(sessionsDir, options = {}) {
  const { readdirSync = fs.readdirSync } = options;
  let names;
  try {
    names = readdirSync(sessionsDir);
  } catch (_) {
    return [];
  }
  return names
    .filter((name) => typeof name === "string" && name.endsWith(".json"))
    .sort()
    .map((name) => readSessionFile(path.join(sessionsDir, name), options))
    .filter(Boolean);
}

/**
 * 세션 하나의 생존 상태를 판정한다.
 *   "ended" — SessionEnd가 정상적으로 왔다
 *   "live"  — 하트비트(없으면 시작 시각)가 staleAfterMs 이내
 *   "stale" — 하트비트가 낡았는데 종료 표시도 없다 (터미널 강제 종료 추정)
 * endedAt이 있으면 하트비트가 아무리 신선해도 "ended"가 우선한다.
 */
function classifyLiveness(entry, options = {}) {
  const { now = Date.now(), staleAfterMs = STALE_AFTER_MS } = options;
  if (!entry) return "stale";
  if (entry.endedAt) return "ended";
  // 하트비트는 첫 턴이 끝나야 찍힌다. 막 등록된 세션은 startedAt으로 판정한다.
  const ref = toTimestamp(entry.lastHeartbeatAt) ?? toTimestamp(entry.startedAt);
  if (ref === null) return "stale";
  return now - ref <= staleAfterMs ? "live" : "stale";
}

/** 표시용 파생 필드를 붙인다. 스킬과 훅이 같은 표현을 쓰도록 여기서 한 번만 만든다. */
function decorate(entry, now, staleAfterMs) {
  return {
    ...entry,
    liveness: classifyLiveness(entry, { now, staleAfterMs }),
    shortId: entry.sessionId.slice(0, 6),
    heartbeatAgo: formatRelative(entry.lastHeartbeatAt || entry.startedAt, now),
    topFiles: entry.recentFiles.slice(0, 3).map((f) => f.path),
  };
}

const byRecency = (field) => (a, b) => (toTimestamp(b[field]) ?? 0) - (toTimestamp(a[field]) ?? 0);

/**
 * 보드 전체를 만든다. session-board 스킬이 이 결과를 그대로 표로 렌더링한다.
 * live/stale/ended와 counts는 모두 "자기 자신을 뺀 다른 세션" 기준이다.
 */
function buildBoard({ projectDir, currentSessionId = null, now = Date.now(), staleAfterMs = STALE_AFTER_MS, fsOverrides = {} }) {
  const sessionsDir = path.join(projectDir, ".claude", "sessions");
  const entries = listSessions(sessionsDir, fsOverrides).map((e) => decorate(e, now, staleAfterMs));

  const self = entries.find((e) => e.sessionId === currentSessionId) || null;
  const others = entries.filter((e) => e.sessionId !== currentSessionId);

  const live = others.filter((e) => e.liveness === "live").sort(byRecency("lastHeartbeatAt"));
  const stale = others.filter((e) => e.liveness === "stale").sort(byRecency("lastHeartbeatAt"));
  const endedAll = others.filter((e) => e.liveness === "ended").sort(byRecency("endedAt"));
  const ended = endedAll.slice(0, MAX_ENDED_SHOWN);

  const total = live.length + stale.length + endedAll.length;
  return {
    self,
    live,
    stale,
    ended,
    lastEnded: endedAll[0] || null,
    counts: { live: live.length, stale: stale.length, ended: endedAll.length, total },
    // 빈 상태는 오류가 아니다. 안내 문구만 담아 돌려준다(stats.js의 isEmpty와 같은 태도).
    note: total === 0 ? "아직 다른 세션의 기록이 없습니다 — 이 저장소에서 열린 첫 세션이거나, 훅을 등록한 뒤 아직 다른 세션이 열리지 않았습니다." : null,
  };
}

/**
 * SessionStart 훅이 additionalContext로 주입할 문자열을 만든다.
 *
 * maxChars를 절대 넘지 않는다 — 매 턴 상주하는 비용이므로 예산은 강제여야 하고,
 * 자를지 말지는 훅이 판단할 일이 아니라 여기의 책임이다. 넘칠 것 같으면
 * 우선순위(자기 id > 살아있는 세션 > 직전 종료 세션 > 안내문)대로 뒤에서부터 접는다.
 *
 * 브리핑을 만드는 시점에는 아직 자기 세션 파일을 쓰기 전이라 board.self가 없다.
 * 그래서 selfSessionId를 따로 받는다.
 */
function buildHandoffBrief(board, options = {}) {
  const { maxChars = BRIEF_MAX_CHARS, now = Date.now(), selfSessionId = null } = options;
  const selfId = selfSessionId || (board && board.self ? board.self.sessionId : null);
  const live = (board && board.live) || [];
  const lastEnded = board ? board.lastEnded : null;

  const line = (e) => {
    const parts = [`${e.shortId}…`, e.heartbeatAgo, `${e.turns}턴`];
    if (e.displayName) parts.splice(1, 0, e.displayName);
    if (e.lastMessage) parts.push(`"${e.lastMessage.slice(0, 120)}"`);
    if (e.topFiles.length > 0) parts.push(e.topFiles[0]);
    return `- ${parts.join(" · ")}`;
  };

  const blocks = [];
  blocks.push(`내 세션 id: ${selfId || "(알 수 없음)"}`);

  if (live.length > 0) {
    const shown = live.slice(0, 3).map(line);
    if (live.length > 3) shown.push(`- …외 ${live.length - 3}개`);
    blocks.push([`지금 살아있는 다른 세션 ${live.length}개:`, ...shown].join("\n"));
  }

  if (lastEnded) {
    const when = formatRelative(lastEnded.endedAt, now);
    const head = `직전에 끝난 세션 (${when}, ${lastEnded.turns}턴, ${lastEnded.endReason || "종료 사유 미상"}):`;
    blocks.push(lastEnded.lastMessage ? `${head}\n"${lastEnded.lastMessage.slice(0, 200)}"` : head);
  }

  if (live.length === 0 && !lastEnded) {
    blocks.push("다른 활성 세션 없음, 직전 세션 기록 없음.");
  } else {
    blocks.push("같은 파일을 고치기 전에 위 목록을 확인할 것. 전체 보드는 /session-board.");
  }

  // 앞에서부터 담되, 넣었을 때 예산을 넘기는 블록은 건너뛴다.
  let body = "";
  for (const block of blocks) {
    const candidate = body ? `${body}\n\n${block}` : block;
    if (candidate.length <= maxChars) body = candidate;
  }

  const header = "[세션 인계 · SessionStart 훅 자동 주입]";
  const withHeader = body ? `${header}\n${body}` : header;
  // 마지막 안전망 — 어떤 경우에도 예산을 넘기지 않는다.
  return (withHeader.length <= maxChars ? withHeader : body).slice(0, maxChars);
}

/**
 * 기존 세션 파일 객체에 patch를 병합한 새 객체를 돌려준다.
 * 순수 함수라 테스트할 수 있고, 실제 파일 쓰기는 호출한 훅이 한 줄로 처리한다 —
 * 이 모듈을 읽기 전용에 가깝게 유지하기 위함이다.
 *
 * undefined인 필드는 무시하고 null은 반영한다. clear/resume 직후 SessionStart가
 * endedAt: null을 명시적으로 넘겨 세션을 되살릴 수 있어야 하기 때문이다.
 */
function mergeSessionPatch(existing, patch, options = {}) {
  const { maxRecentFiles = MAX_RECENT_FILES } = options;
  const base = existing && typeof existing === "object" ? existing : {};
  const incoming = patch && typeof patch === "object" ? patch : {};

  const next = { ...base };
  for (const [key, value] of Object.entries(incoming)) {
    if (value !== undefined) next[key] = value;
  }

  // 세션의 "처음"은 한 번 정해지면 밀리지 않는다.
  // resume/compact로 SessionStart가 재발동해도 시작 시각이 덮이면 안 되기 때문이다.
  if (base.startedAt) next.startedAt = base.startedAt;
  if (base.source) next.source = base.source;

  if (incoming.recentFiles !== undefined) {
    const merged = [];
    const seen = new Set();
    // 새로 들어온 항목이 앞선다 → 같은 경로는 최신 시각만 남는다.
    for (const f of [...(incoming.recentFiles || []), ...(base.recentFiles || [])]) {
      if (!f || typeof f !== "object" || typeof f.path !== "string" || seen.has(f.path)) continue;
      seen.add(f.path);
      merged.push({ path: f.path, at: asString(f.at) });
    }
    merged.sort(byRecency("at"));
    next.recentFiles = merged.slice(0, maxRecentFiles);
  } else {
    next.recentFiles = base.recentFiles || [];
  }

  if (incoming.lastMessage !== undefined) {
    next.lastMessage = condenseMessage(incoming.lastMessage);
  }

  return next;
}

/**
 * 지울 세션 파일의 sessionId를 고른다(실제 삭제는 SessionStart 훅이 한다).
 * live/stale 세션과 자기 자신은 절대 고르지 않는다 — 살아있는 세션의 파일을 지우면
 * 그 세션은 다음 Stop에서 조용히 다시 만들지만 그동안의 이력이 날아간다.
 */
function selectPrunable(sessions, options = {}) {
  const { now = Date.now(), keepDays = 30, maxFiles = 50, currentSessionId = null, staleAfterMs = STALE_AFTER_MS } = options;
  const all = Array.isArray(sessions) ? sessions : [];

  const endedOthers = all
    .filter((e) => e && e.sessionId !== currentSessionId)
    .filter((e) => classifyLiveness(e, { now, staleAfterMs }) === "ended")
    .sort(byRecency("endedAt"));

  const cutoff = now - keepDays * 24 * 60 * 60 * 1000;
  const picked = new Set(
    endedOthers.filter((e) => (toTimestamp(e.endedAt) ?? 0) <= cutoff).map((e) => e.sessionId)
  );

  // 개수 상한을 넘으면 오래 전에 끝난 것부터 추가로 정리한다.
  for (let i = endedOthers.length - 1; i >= 0 && all.length - picked.size > maxFiles; i -= 1) {
    picked.add(endedOthers[i].sessionId);
  }

  return [...picked];
}

/**
 * 지금 편집하려는 파일을 최근에 만진 "살아있는 다른 세션"을 찾는다.
 *
 * 자기 자신, stale/ended 세션, windowMs 밖의 기록은 제외한다 — 이미 끝난 세션이
 * 과거에 만졌다는 이유로 경고하면 경고가 소음이 되고, 소음이 된 경고는 무시된다.
 *
 * 충돌이 없으면 message가 null이다. 호출한 훅은 message가 null이면 아무것도 출력하지 않는다.
 */
function findConflicts({
  projectDir,
  currentSessionId = null,
  filePath,
  now = Date.now(),
  windowMs = CONFLICT_WINDOW_MS,
  staleAfterMs = STALE_AFTER_MS,
  fsOverrides = {},
}) {
  const empty = { conflicts: [], message: null };
  if (typeof filePath !== "string" || filePath === "") return empty;

  const sessionsDir = path.join(projectDir, ".claude", "sessions");
  const conflicts = [];

  for (const entry of listSessions(sessionsDir, fsOverrides)) {
    if (entry.sessionId === currentSessionId) continue;
    if (classifyLiveness(entry, { now, staleAfterMs }) !== "live") continue;

    const touch = entry.recentFiles.find((f) => f.path === filePath);
    if (!touch) continue;
    const at = toTimestamp(touch.at);
    if (at === null || now - at > windowMs) continue;

    conflicts.push({
      sessionId: entry.sessionId,
      displayName: entry.displayName,
      shortId: entry.sessionId.slice(0, 6),
      at: touch.at,
      ago: formatRelative(touch.at, now),
    });
  }

  if (conflicts.length === 0) return empty;
  conflicts.sort(byRecency("at"));

  const who = conflicts
    .map((c) => `${c.shortId}\u2026${c.displayName ? `(${c.displayName})` : ""}가 ${c.ago}`)
    .join(", ");
  return {
    conflicts,
    message:
      `[세션 충돌 경고] ${filePath} 는 살아있는 다른 세션 ${who}에 편집했습니다. ` +
      "덮어쓰기 전에 /session-board 로 확인하거나 /session-relay 로 그쪽 세션에 물어보세요.",
  };
}

/**
 * 이 모듈에서 파일시스템에 직접 쓰는 유일한 함수 — 의도적으로 좁게 낸 예외다.
 *
 * 왜 훅이 못 하고 스킬이 해야 하는가:
 *   ListAgents가 주는 표시 이름("my-claude-code-os-25")은 훅이 알 수 없다. 훅은 도구를
 *   호출할 수 없기 때문이다. 게다가 ListAgents의 대괄호 ref는 훅이 받는 session_id와
 *   별도 id 공간이라 사후 매칭도 불가능하다. 자기 이름을 아는 주체는 세션 자신뿐이므로,
 *   세션(=스킬)이 자기 파일의 이 한 필드만 채운다.
 *
 * 자기 파일의 displayName 외에는 아무것도 건드리지 않고, 파일이 없으면 만들지 않는다
 * (훅이 먼저 등록한 세션만 대상이다).
 * @returns {boolean} 기록했으면 true
 */
function recordDisplayName({ projectDir, sessionId, displayName, fsOverrides = {} }) {
  const {
    readFileSync = fs.readFileSync,
    existsSync = fs.existsSync,
    writeFileSync = fs.writeFileSync,
  } = fsOverrides;

  const safeId = sanitizeSessionId(sessionId);
  const name = asString(displayName);
  if (!safeId || !name) return false;

  const filePath = path.join(projectDir, ".claude", "sessions", `${safeId}.json`);
  try {
    if (!existsSync(filePath)) return false;
    const raw = JSON.parse(readFileSync(filePath, "utf-8"));
    if (!raw || typeof raw !== "object") return false;
    if (raw.displayName === name) return true;

    raw.displayName = name;
    raw.updatedAt = new Date().toISOString();
    writeFileSync(filePath, `${JSON.stringify(raw, null, 2)}\n`);
    return true;
  } catch (_) {
    return false;
  }
}

module.exports = {
  STALE_AFTER_MS,
  CONFLICT_WINDOW_MS,
  MAX_RECENT_FILES,
  MESSAGE_MAX_CHARS,
  BRIEF_MAX_CHARS,
  sanitizeSessionId,
  formatRelative,
  condenseMessage,
  readSessionFile,
  listSessions,
  classifyLiveness,
  buildBoard,
  buildHandoffBrief,
  mergeSessionPatch,
  selectPrunable,
  findConflicts,
  recordDisplayName,
};
