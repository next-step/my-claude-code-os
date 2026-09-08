#!/usr/bin/env node
/**
 * SessionEnd 훅: 세션이 정상적으로 끝났다는 표시를 남긴다.
 *
 * 이 표시가 왜 필요한가:
 *   하트비트만 보면 "30분째 조용한 세션"과 "닫힌 세션"을 구분할 수 없다. endedAt이
 *   있으면 정상 종료, 없는데 하트비트가 낡았으면 터미널 강제 종료로 갈린다. 후자를
 *   stale로 표시하는 건 오류 보고가 아니라 사실 보고다 — SessionEnd는 창을 강제로
 *   닫으면 오지 않기 때문이다.
 *
 * SessionEnd는 컨텍스트를 주입할 수 없고 stdout은 디버그 로그로만 가므로
 * 아무것도 출력하지 않는다.
 *
 * 입력: { session_id, reason, transcript_path, cwd, hook_event_name }
 *   reason: clear | resume | logout | prompt_input_exit | other
 */
const fs = require("node:fs");
const path = require("node:path");

const board = require("../lib/session-board.js");

let input = "";
process.stdin.on("data", (chunk) => {
  input += chunk;
});

process.stdin.on("end", () => {
  try {
    const payload = input ? JSON.parse(input) : {};

    const sessionId = board.sanitizeSessionId(payload.session_id);
    if (!sessionId) process.exit(0);

    const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
    const selfPath = path.join(projectDir, ".claude", "sessions", `${sessionId}.json`);

    const existing = board.readSessionFile(selfPath);
    if (!existing) process.exit(0);

    const nowIso = new Date().toISOString();
    const next = board.mergeSessionPatch(existing, {
      endedAt: nowIso,
      endReason: typeof payload.reason === "string" && payload.reason !== "" ? payload.reason : "other",
      updatedAt: nowIso,
    });

    fs.writeFileSync(selfPath, `${JSON.stringify(next, null, 2)}\n`);
  } catch (_) {
    // 종료 기록 실패가 세션 종료를 막아서는 안 된다.
  }
  process.exit(0);
});
