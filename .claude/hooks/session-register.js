#!/usr/bin/env node
/**
 * SessionStart 훅: 세션이 열리거나 이어질 때, 이 세션을 보드에 등록하고
 * "직전 세션이 무엇을 하다 멈췄는지 / 지금 누가 살아서 뭘 하고 있는지"를
 * additionalContext로 주입한다.
 *
 * 왜 훅으로 만드는가:
 *   사람이 매번 /session-board를 쳐야 한다면 그건 결국 안 치게 된다. 세션이 열리는
 *   순간은 사람이 개입할 수 없는 시점이고, 바로 그때 맥락이 필요하다. 훅만이 그 자리에
 *   설 수 있다 — "빼먹지 않는 규율"은 훅의 몫이고 "무엇을 할지"는 AI의 몫이라는
 *   이 저장소의 분업 그대로다.
 *
 * 입력: Claude Code가 stdin으로 넘겨주는 SessionStart 훅 payload(JSON)
 *   { session_id, source, cwd, transcript_path, hook_event_name }
 * 출력: { hookSpecificOutput: { hookEventName, additionalContext } }
 *
 * 어떤 경우에도 예외를 밖으로 던지지 않는다. 인계 정보가 없다고 세션 시작을
 * 막아서는 안 되기 때문이다.
 */
const fs = require("node:fs");
const path = require("node:path");
const { execSync } = require("node:child_process");

const board = require("../lib/session-board.js");

/** 정리 기준: 종료된 지 이만큼 지났거나, 파일이 이 개수를 넘으면 오래된 것부터 지운다. */
const KEEP_DAYS = 30;
const MAX_FILES = 50;

let input = "";
process.stdin.on("data", (chunk) => {
  input += chunk;
});

process.stdin.on("end", () => {
  try {
    const payload = input ? JSON.parse(input) : {};

    // 훅 payload는 신뢰 경계 밖이다. 파일명이 될 값이므로 먼저 검사한다.
    const sessionId = board.sanitizeSessionId(payload.session_id);
    if (!sessionId) process.exit(0);

    const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
    const sessionsDir = path.join(projectDir, ".claude", "sessions");
    const selfPath = path.join(sessionsDir, `${sessionId}.json`);
    const now = Date.now();
    const nowIso = new Date(now).toISOString();

    // [1] 브리핑을 자기 파일을 쓰기 *전에* 만든다.
    //     순서를 뒤집으면 방금 등록한 자기 자신이 "지금 살아있는 다른 세션"에 섞인다.
    const snapshot = board.buildBoard({ projectDir, currentSessionId: sessionId, now });
    const brief = board.buildHandoffBrief(snapshot, { now, selfSessionId: sessionId });

    // [2] 자기 세션 등록
    let gitBranch = null;
    try {
      gitBranch = execSync("git rev-parse --abbrev-ref HEAD", {
        cwd: projectDir,
        encoding: "utf-8",
        stdio: ["ignore", "pipe", "ignore"],
      }).trim() || null;
    } catch (_) {
      // git 저장소가 아니거나 git이 없으면 브랜치 없이 진행한다
    }

    const existing = board.readSessionFile(selfPath);
    const next = board.mergeSessionPatch(existing, {
      sessionId,
      source: typeof payload.source === "string" ? payload.source : null,
      cwd: typeof payload.cwd === "string" ? payload.cwd : projectDir,
      gitBranch,
      startedAt: nowIso,
      lastHeartbeatAt: nowIso,
      updatedAt: nowIso,
      // clear/resume로 끝났다가 같은 터미널에서 곧바로 다시 열린 경우 되살린다.
      // (merge는 undefined만 무시하고 null은 반영한다)
      endedAt: null,
      endReason: null,
    });

    fs.mkdirSync(sessionsDir, { recursive: true });
    fs.writeFileSync(selfPath, `${JSON.stringify(next, null, 2)}\n`);

    // [3] 오래된 세션 파일 정리. 살아있는 세션과 자기 자신은 selectPrunable이 걸러낸다.
    const all = board.listSessions(sessionsDir);
    for (const id of board.selectPrunable(all, { now, keepDays: KEEP_DAYS, maxFiles: MAX_FILES, currentSessionId: sessionId })) {
      try {
        fs.unlinkSync(path.join(sessionsDir, `${id}.json`));
      } catch (_) {
        // 이미 지워졌거나 권한이 없으면 그냥 둔다
      }
    }

    // [4] 인계 브리핑 주입
    process.stdout.write(
      JSON.stringify({
        hookSpecificOutput: { hookEventName: "SessionStart", additionalContext: brief },
      })
    );
  } catch (_) {
    // 인계는 best-effort. 실패해도 조용히 종료한다.
  }
  process.exit(0);
});
