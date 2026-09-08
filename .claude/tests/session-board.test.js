/**
 * 세션 인계·협업 계층이 쓰는 집계 로직(.claude/lib/session-board.js)의 인수 테스트.
 *
 * "AC-<번호>" 접두사는 이 저장소의 다른 테스트(stats.test.js, context-map.test.js)와
 * 같은 이유로 유지한다 — 실패 원장에서 어떤 인수기준이 깨졌는지 바로 추적하기 위함이다.
 *
 * 실제 `.claude/sessions/`는 세션이 열릴 때마다 바뀌므로, 고정 픽스처
 * (.claude/tests/fixtures/session-board/)를 대상으로 검증한다. 시간에 의존하는 로직이
 * 많아 픽스처 시각을 FIXED_NOW 기준으로 고정하고 `now`를 주입한다 — 실제 시계를 쓰면
 * 오늘은 통과하고 내일은 깨지는 테스트가 된다.
 *
 * 실행: node --test .claude/tests/session-board.test.js
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  MESSAGE_MAX_CHARS,
  sanitizeSessionId,
  readSessionFile,
  listSessions,
  classifyLiveness,
  buildBoard,
  buildHandoffBrief,
  mergeSessionPatch,
  selectPrunable,
} = require("../lib/session-board.js");

const FIXTURES = path.join(__dirname, "fixtures", "session-board");
const SESSIONS = path.join(FIXTURES, "sessions");

/** 픽스처의 모든 시각은 이 기준시각에 맞춰 작성돼 있다. */
const FIXED_NOW = Date.parse("2026-09-06T03:00:00.000Z");

const LIVE_1 = "a1111111-1111-4111-8111-111111111111";
const LIVE_2 = "b2222222-2222-4222-8222-222222222222";
const STALE = "c3333333-3333-4333-8333-333333333333";
const ENDED = "d4444444-4444-4444-8444-444444444444";
const OLD_ENDED = "e5555555-5555-4555-8555-555555555555";
const MINIMAL = "f6666666-6666-4666-8666-666666666666";

const byId = (entries, id) => entries.find((e) => e.sessionId === id);

test("AC-1: sanitizeSessionId는 정상 id만 통과시키고 경로 조작 문자열은 null을 낸다", () => {
  assert.equal(sanitizeSessionId(LIVE_1), LIVE_1);

  // 훅 payload는 신뢰 경계 밖이다. 아래 값들이 그대로 파일명이 되면 저장소 밖에 쓰게 된다.
  for (const bad of ["../../etc/passwd", "..", "a/b", "a\\b", "a.b", "", "  ", null, undefined, 42, {}]) {
    assert.equal(sanitizeSessionId(bad), null, `${JSON.stringify(bad)}는 거부돼야 한다`);
  }
  // 예외를 던지지 않는다 — 훅에서 호출되므로 실패해도 작업을 막으면 안 된다.
  assert.doesNotThrow(() => sanitizeSessionId(undefined));
});

test("AC-2: readSessionFile은 없는 파일과 깨진 JSON을 예외 없이 null로 처리한다", () => {
  assert.equal(readSessionFile(path.join(SESSIONS, "없는파일.json")), null);
  assert.equal(readSessionFile(path.join(SESSIONS, "broken.json")), null);

  const ok = readSessionFile(path.join(SESSIONS, `${LIVE_1}.json`));
  assert.equal(ok.sessionId, LIVE_1);
});

test("AC-3: listSessions는 깨진 파일 하나 때문에 나머지를 잃지 않고, .json이 아닌 파일은 무시한다", () => {
  const entries = listSessions(SESSIONS);

  assert.equal(entries.length, 6, "정상 세션 파일 6개가 모두 읽혀야 한다");
  for (const id of [LIVE_1, LIVE_2, STALE, ENDED, OLD_ENDED, MINIMAL]) {
    assert.ok(byId(entries, id), `${id}가 있어야 한다`);
  }
  assert.ok(!entries.some((e) => e.sessionId === "broken"), "깨진 파일은 건너뛴다");
  assert.ok(!entries.some((e) => String(e.sessionId).includes("not-a-session")), ".txt는 무시한다");
});

test("AC-4: listSessions는 누락 필드를 기본값으로 정규화한다", () => {
  const minimal = byId(listSessions(SESSIONS), MINIMAL);

  // 호출자가 매번 방어하지 않도록 undefined가 아닌 명시적 기본값으로 채운다.
  assert.equal(minimal.turns, 0);
  assert.deepEqual(minimal.recentFiles, []);
  assert.equal(minimal.endedAt, null);
  assert.equal(minimal.endReason, null);
  assert.equal(minimal.lastMessage, null);
  assert.equal(minimal.displayName, null);
  assert.equal(minimal.gitBranch, null);
  assert.equal(minimal.lastHeartbeatAt, null);
});

test("AC-5: listSessions는 디렉터리가 없거나 비어 있어도 예외 대신 빈 배열을 낸다", () => {
  assert.deepEqual(listSessions(path.join(FIXTURES, "존재하지-않는-디렉터리")), []);
  assert.deepEqual(listSessions(path.join(FIXTURES, "sessions-empty")), []);
});

test("AC-6: classifyLiveness는 endedAt을 하트비트 신선도보다 우선한다", () => {
  const entries = listSessions(SESSIONS);
  const at = (id) => classifyLiveness(byId(entries, id), { now: FIXED_NOW });

  assert.equal(at(LIVE_1), "live", "5분 전 하트비트는 살아있다");
  assert.equal(at(STALE), "stale", "6시간 전 하트비트 + 종료표시 없음 = 강제 종료 추정");
  assert.equal(at(ENDED), "ended", "하트비트가 2분 전이어도 endedAt이 있으면 종료다");
  assert.equal(at(MINIMAL), "live", "하트비트가 아직 없으면 startedAt으로 판정한다");
});

test("AC-7: buildBoard는 자기 세션을 self로 분리하고 live 목록에서 제외한다", () => {
  const board = buildBoard({
    projectDir: path.join(FIXTURES, "project"),
    currentSessionId: LIVE_1,
    now: FIXED_NOW,
  });

  assert.equal(board.self.sessionId, LIVE_1);
  assert.ok(!byId(board.live, LIVE_1), "자기 자신은 live 목록에 없어야 한다");
  assert.ok(byId(board.stale, STALE), "다른 stale 세션은 stale에 있어야 한다");
  assert.ok(byId(board.ended, ENDED), "다른 종료 세션은 ended에 있어야 한다");
  assert.equal(board.lastEnded.sessionId, ENDED, "직전에 끝난 세션이 인계 브리핑의 주재료다");
  assert.equal(board.counts.total, 2, "counts는 자기 자신을 뺀 다른 세션 기준이다");
});

test("AC-8: buildBoard는 세션 기록이 없을 때 오류 대신 note를 낸다", () => {
  const board = buildBoard({
    projectDir: path.join(FIXTURES, "sessions-empty"),
    currentSessionId: LIVE_1,
    now: FIXED_NOW,
  });

  assert.equal(board.counts.total, 0);
  assert.deepEqual(board.live, []);
  assert.deepEqual(board.stale, []);
  assert.deepEqual(board.ended, []);
  assert.equal(board.self, null);
  assert.equal(board.lastEnded, null);
  assert.ok(board.note && board.note.includes("아직"), "빈 상태는 오류가 아니라 안내다");
});

test("AC-9: buildHandoffBrief는 maxChars 예산을 절대 넘지 않는다", () => {
  const board = buildBoard({ projectDir: FIXTURES, currentSessionId: LIVE_1, now: FIXED_NOW });
  // 픽스처 루트에는 sessions/가 있으므로 projectDir 대신 디렉터리를 직접 넘긴 보드를 쓴다.
  const full = buildBoard({
    projectDir: path.join(FIXTURES, "project"),
    currentSessionId: LIVE_1,
    now: FIXED_NOW,
  });

  for (const maxChars of [800, 300, 120, 60]) {
    const brief = buildHandoffBrief(full, { maxChars, now: FIXED_NOW });
    assert.ok(
      brief.length <= maxChars,
      `maxChars=${maxChars}인데 ${brief.length}자가 나왔다 (매 턴 상주하는 비용이므로 예산은 강제여야 한다)`
    );
  }

  const brief = buildHandoffBrief(full, { maxChars: 800, now: FIXED_NOW });
  assert.ok(brief.includes(LIVE_1.slice(0, 6)), "접히더라도 자기 세션 id는 살아남아야 한다");
  assert.ok(brief.includes("requirement-interview"), "직전 종료 세션이 뭘 하다 멈췄는지가 들어가야 한다");
  assert.ok(board.counts.total >= 0);
});

test("AC-10: buildHandoffBrief는 기록이 전혀 없어도 빈 문자열이 아니라 한 줄 안내를 낸다", () => {
  const board = buildBoard({
    projectDir: path.join(FIXTURES, "sessions-empty"),
    currentSessionId: LIVE_1,
    now: FIXED_NOW,
  });
  const brief = buildHandoffBrief(board, { now: FIXED_NOW, selfSessionId: LIVE_1 });

  // 빈 문자열을 주입하면 "왜 아무것도 안 나오지"를 사용자가 궁금해하게 된다.
  assert.ok(brief.length > 0);
  assert.ok(brief.includes(LIVE_1.slice(0, 6)));
});

test("AC-11: mergeSessionPatch는 startedAt을 보존하고 recentFiles를 중복 없이 상한까지만 쌓는다", () => {
  const existing = {
    sessionId: LIVE_1,
    startedAt: "2026-09-06T01:10:00.000Z",
    source: "startup",
    turns: 3,
    recentFiles: [{ path: "OS.md", at: "2026-09-06T02:00:00.000Z" }],
  };

  // startedAt·source는 resume/compact로 SessionStart가 재발동해도 밀리지 않아야 한다.
  const merged = mergeSessionPatch(existing, {
    startedAt: "2026-09-06T02:59:00.000Z",
    source: "resume",
    turns: 4,
  });
  assert.equal(merged.startedAt, "2026-09-06T01:10:00.000Z");
  assert.equal(merged.source, "startup");
  assert.equal(merged.turns, 4);

  // 같은 경로를 다시 만지면 새로 쌓지 않고 시각만 갱신한다.
  const again = mergeSessionPatch(existing, {
    recentFiles: [{ path: "OS.md", at: "2026-09-06T02:50:00.000Z" }],
  });
  assert.equal(again.recentFiles.length, 1);
  assert.equal(again.recentFiles[0].at, "2026-09-06T02:50:00.000Z");

  // 상한을 넘으면 최신순으로 자른다.
  let piled = { sessionId: LIVE_1, recentFiles: [] };
  for (let i = 0; i < 25; i += 1) {
    piled = mergeSessionPatch(piled, {
      recentFiles: [{ path: `file-${i}.js`, at: `2026-09-06T02:${String(i).padStart(2, "0")}:00.000Z` }],
    });
  }
  assert.equal(piled.recentFiles.length, 20);
  assert.equal(piled.recentFiles[0].path, "file-24.js", "최신 편집이 앞에 온다");

  // lastMessage는 상한까지 자르고 개행을 접는다 — 코드블록이 통째로 들어가는 걸 막는다.
  const long = mergeSessionPatch(existing, { lastMessage: `줄1\n줄2\n${"가".repeat(500)}` });
  assert.ok(long.lastMessage.length <= MESSAGE_MAX_CHARS);
  assert.ok(!long.lastMessage.includes("\n"));

  // 명백한 시크릿 접두사는 마스킹한다(로컬 파일이라도 평문으로 남기지 않는다).
  const secret = mergeSessionPatch(existing, { lastMessage: "토큰은 sk-abcdef1234567890abcdef 입니다" });
  assert.ok(!secret.lastMessage.includes("sk-abcdef1234567890abcdef"));

  // endedAt은 명시적 null로 되살릴 수 있어야 한다(clear/resume 직후 SessionStart).
  const revived = mergeSessionPatch({ ...existing, endedAt: "2026-09-06T02:00:00.000Z" }, { endedAt: null });
  assert.equal(revived.endedAt, null);
});

test("AC-12: selectPrunable은 살아있는 세션과 자기 자신을 절대 고르지 않는다", () => {
  const entries = listSessions(SESSIONS);
  const picked = selectPrunable(entries, { now: FIXED_NOW, keepDays: 30, maxFiles: 50, currentSessionId: LIVE_1 });

  assert.deepEqual(picked, [OLD_ENDED], "40일 전 종료된 세션만 정리 대상이다");
  for (const id of [LIVE_1, LIVE_2, STALE, ENDED, MINIMAL]) {
    assert.ok(!picked.includes(id), `${id}는 지우면 안 된다`);
  }

  // 살아있는 세션의 파일을 지우면 그 세션은 다음 Stop에서 조용히 다시 만들지만 이력이 날아간다.
  const aggressive = selectPrunable(entries, { now: FIXED_NOW, keepDays: 0, maxFiles: 1, currentSessionId: LIVE_1 });
  assert.ok(!aggressive.includes(LIVE_1));
  assert.ok(!aggressive.includes(LIVE_2));
  assert.ok(!aggressive.includes(STALE));

  // 정리할 게 없으면 빈 배열.
  assert.deepEqual(
    selectPrunable([], { now: FIXED_NOW, currentSessionId: LIVE_1 }),
    []
  );
});

// ── Layer 2: 세션 간 실시간 협업 ────────────────────────────────────────────

test("AC-13: findConflicts는 살아있는 다른 세션의 최근 편집만 잡는다", () => {
  const { findConflicts } = require("../lib/session-board.js");
  const projectDir = path.join(FIXTURES, "project-conflict");
  const target = ".claude/lib/session-board.js";

  const hit = findConflicts({ projectDir, currentSessionId: LIVE_1, filePath: target, now: FIXED_NOW });

  assert.equal(hit.conflicts.length, 1, "살아있는 다른 세션 하나만 잡혀야 한다");
  assert.equal(hit.conflicts[0].sessionId, LIVE_2);
  assert.ok(hit.message && hit.message.includes(target), "경고 문구에 파일 경로가 들어가야 한다");

  // 자기 자신은 충돌 상대가 아니다. stale·ended 세션도 마찬가지다 —
  // 이미 끝난 세션이 과거에 만졌다는 이유로 경고하면 경고가 소음이 된다.
  const ids = hit.conflicts.map((c) => c.sessionId);
  assert.ok(!ids.includes(LIVE_1));
  assert.ok(!ids.includes(STALE), "stale 세션이 같은 파일을 만졌어도 제외한다");
  assert.ok(!ids.includes(ENDED));

  // 아무도 안 만진 파일이면 조용하다. message가 null이면 훅은 아무것도 출력하지 않는다.
  const quiet = findConflicts({ projectDir, currentSessionId: LIVE_1, filePath: "README.md", now: FIXED_NOW });
  assert.deepEqual(quiet.conflicts, []);
  assert.equal(quiet.message, null);

  // 시간창 밖의 편집은 "지금 작업 중"이 아니다.
  const stale = findConflicts({ projectDir, currentSessionId: LIVE_1, filePath: target, now: FIXED_NOW, windowMs: 60 * 1000 });
  assert.deepEqual(stale.conflicts, []);
  assert.equal(stale.message, null);
});

test("AC-14: recordDisplayName은 자기 파일의 그 필드만 고치고 다른 필드를 지우지 않는다", () => {
  const { recordDisplayName } = require("../lib/session-board.js");
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "session-board-"));
  const sessionsDir = path.join(tmp, ".claude", "sessions");
  fs.mkdirSync(sessionsDir, { recursive: true });

  const filePath = path.join(sessionsDir, `${LIVE_1}.json`);
  fs.writeFileSync(
    filePath,
    JSON.stringify({ sessionId: LIVE_1, turns: 7, lastMessage: "건드리면 안 되는 값", displayName: null }, null, 2)
  );

  assert.equal(recordDisplayName({ projectDir: tmp, sessionId: LIVE_1, displayName: "my-claude-code-os-25" }), true);

  const after = JSON.parse(fs.readFileSync(filePath, "utf-8"));
  assert.equal(after.displayName, "my-claude-code-os-25");
  assert.equal(after.turns, 7, "훅이 쓰는 필드를 스킬이 덮어쓰면 안 된다");
  assert.equal(after.lastMessage, "건드리면 안 되는 값");

  // 훅이 먼저 등록한 세션만 대상이다. 파일이 없으면 만들지 않는다.
  const missing = `f0000000-0000-4000-8000-000000000000`;
  assert.equal(recordDisplayName({ projectDir: tmp, sessionId: missing, displayName: "없는세션" }), false);
  assert.equal(fs.existsSync(path.join(sessionsDir, `${missing}.json`)), false);

  fs.rmSync(tmp, { recursive: true, force: true });
});
