#!/usr/bin/env node
/**
 * Stop 훅: 한 턴이 끝날 때마다 이 세션의 보드 항목을 갱신한다.
 *
 * 핵심은 last_assistant_message다. Claude Code가 이 턴의 마지막 응답 텍스트를
 * stdin으로 넘겨주므로, "이 세션이 무엇을 하다 멈췄는가"를 AI를 한 번도 더 호출하지
 * 않고 기록할 수 있다. 사람이 세션 끝에 인계문을 쓰는 규율에 의존하지 않아도 된다.
 *
 * 이 훅은 stdout에 아무것도 쓰지 않는다 — 같은 Stop 그룹의 os-retro-check.js와
 * big-change-commit-check.js가 내는 decision에 끼어들지 않기 위함이다.
 * stop_hook_active도 보지 않는다: 이 훅은 block을 내지 않으므로 무한 루프의
 * 당사자가 아니고, 이어붙은 턴의 마지막 메시지도 인계 정보로는 유효하다.
 *
 * 입력: { session_id, last_assistant_message, transcript_path, hook_event_name, ... }
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

    // 자기 파일이 없으면 만들지 않는다.
    // SessionStart를 못 받은 세션 = 이 훅을 등록하기 전부터 열려 있던 세션이다.
    // 시작 시각도 source도 모르는 반쪽짜리 항목을 만드느니 없는 편이 정직하다.
    const existing = board.readSessionFile(selfPath);
    if (!existing) process.exit(0);

    const nowIso = new Date().toISOString();
    const next = board.mergeSessionPatch(existing, {
      lastHeartbeatAt: nowIso,
      turns: (existing.turns || 0) + 1,
      // merge 안에서 개행 접기·시크릿 마스킹·240자 컷이 이뤄진다
      lastMessage: payload.last_assistant_message,
      updatedAt: nowIso,
    });

    fs.writeFileSync(selfPath, `${JSON.stringify(next, null, 2)}\n`);
  } catch (_) {
    // 기록 실패가 실제 작업을 막아서는 안 된다.
  }
  process.exit(0); // stdout 없음 — 다른 Stop 훅의 결정에 영향을 주지 않는다
});
