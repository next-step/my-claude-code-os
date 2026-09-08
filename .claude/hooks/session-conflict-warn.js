#!/usr/bin/env node
/**
 * PreToolUse(Edit|Write|Bash) 훅: 파일을 고치기 직전에, 살아있는 다른 세션이 방금 그 파일을
 * 만졌는지 확인해 경고를 얹는다. 동시에 이 세션의 편집 이력도 보드에 남긴다.
 *
 * 왜 Bash까지 보는가:
 *   파일을 만드는 문은 둘이다 — 전용 도구(`Edit`/`Write`의 file_path)와 Bash(리다이렉션·
 *   히어독·`cp`/`mv`/`sed -i`). 2026-09-07에 이 훅이 `Edit|Write`에만 걸려 있는 동안
 *   Bash 히어독으로 다른 세션의 지침 파일을 덮어썼고, 훅은 발동조차 하지 않았다.
 *   **훅이 지키는 문이 하나뿐이면 다른 문으로 들어온 변경은 그냥 통과한다.**
 *   Bash 명령에서 대상 경로를 뽑는 일은 `.claude/lib/write-targets.js`가 맡는다.
 *
 * 왜 막지 않고 경고만 하는가:
 *   permissionDecision:"deny" 로 편집을 막을 수도 있지만 그러지 않는다. 훅은 "다른
 *   세션이 4분 전에 만졌다"는 사실만 알 뿐, 그게 진짜 충돌인지(같은 함수를 고치는 중인지,
 *   그냥 읽고 지나간 건지)는 모른다. 이 저장소의 일관된 분업 그대로다 —
 *   **규율은 훅, 판단은 AI, 결정은 사람.** os-retro-check.js가 커밋을 막지 않고
 *   물어보게만 시키는 것과 같다.
 *
 * 비용에 민감한 훅이다. 모든 Edit/Write/Bash마다 실행되므로 git 호출도, 트랜스크립트 읽기도
 * 하지 않는다. 세션이 자기 하나뿐이면 즉시 종료한다 — 혼자 작업할 땐 사실상 no-op이다.
 *
 * 입력: { session_id, tool_name, tool_input: { file_path } | { command }, ... }
 */
const fs = require("node:fs");
const path = require("node:path");

const board = require("../lib/session-board.js");
const { extractWriteTargets } = require("../lib/write-targets.js");

/** 한 명령이 건드리는 경로가 많아도 앞에서 자른다 — 훅은 빨라야 한다. */
const MAX_TARGETS = 10;

let input = "";
process.stdin.on("data", (chunk) => {
  input += chunk;
});

process.stdin.on("end", () => {
  try {
    const payload = input ? JSON.parse(input) : {};

    const sessionId = board.sanitizeSessionId(payload.session_id);
    if (!sessionId) process.exit(0);

    const toolInput = payload.tool_input || {};
    const rawPaths =
      typeof toolInput.file_path === "string" && toolInput.file_path !== ""
        ? [toolInput.file_path]
        : extractWriteTargets(toolInput.command).slice(0, MAX_TARGETS);
    if (rawPaths.length === 0) process.exit(0);

    const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
    const sessionsDir = path.join(projectDir, ".claude", "sessions");

    // 빠른 종료: 보드에 자기 자신뿐이면 비교할 상대가 없다.
    let fileCount = 0;
    try {
      fileCount = fs.readdirSync(sessionsDir).filter((n) => n.endsWith(".json")).length;
    } catch (_) {
      process.exit(0); // 보드 자체가 없으면 할 일이 없다
    }
    if (fileCount <= 1) process.exit(0);

    // 저장소 안쪽 파일은 상대 경로로 맞춘다 — 세션마다 절대 경로가 다를 수 있기 때문이다.
    const filePaths = rawPaths.map((rawPath) => {
      const absolute = path.isAbsolute(rawPath) ? rawPath : path.resolve(projectDir, rawPath);
      const relative = path.relative(projectDir, absolute);
      return relative && !relative.startsWith("..") ? relative : rawPath;
    });

    const now = Date.now();
    const messages = [];
    for (const filePath of filePaths) {
      const { message } = board.findConflicts({ projectDir, currentSessionId: sessionId, filePath, now });
      if (message) messages.push(message);
    }

    // 자기 편집 이력 기록. dedupe와 20개 상한은 mergeSessionPatch가 처리한다.
    const selfPath = path.join(sessionsDir, `${sessionId}.json`);
    const existing = board.readSessionFile(selfPath);
    if (existing) {
      const nowIso = new Date(now).toISOString();
      const next = board.mergeSessionPatch(existing, {
        recentFiles: filePaths.map((filePath) => ({ path: filePath, at: nowIso })),
        updatedAt: nowIso,
      });
      fs.writeFileSync(selfPath, `${JSON.stringify(next, null, 2)}\n`);
    }

    if (messages.length === 0) process.exit(0); // 충돌이 없으면 조용하다

    process.stdout.write(
      JSON.stringify({
        hookSpecificOutput: { hookEventName: "PreToolUse", additionalContext: messages.join("\n") },
      })
    );
  } catch (_) {
    // 경고는 best-effort. 실패해도 편집을 막아서는 안 된다.
  }
  process.exit(0);
});
