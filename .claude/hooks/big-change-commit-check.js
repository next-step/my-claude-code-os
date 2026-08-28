#!/usr/bin/env node
/**
 * Stop 훅: Claude가 한 턴을 마치고 멈추려는 시점에, 커밋되지 않은 변경량이
 * "크다"고 볼 만한지 확인한다.
 *
 * 왜 훅으로 만드는가 (os-retro-check.js와 동일한 설계):
 *   훅(이 스크립트)은 사람에게 직접 질문을 던질 수 없다 — 명령을 실행해 결과를
 *   표준출력으로 돌려줄 뿐이다. 그래서 이 훅은 "커밋할지 물어보는 일"을 직접
 *   하지 않고, decision:"block" 으로 Claude의 턴을 계속 이어가게 한 뒤, reason에
 *   담은 지시로 Claude가 변경 내용을 요약하고 AskUserQuestion으로 사람에게 직접
 *   커밋 여부를 물어보게 시킨다. "변경이 큰가"의 판단 재료(파일 수·줄 수)는 훅이
 *   계산하지만, 실제 커밋 여부 결정과 커밋 메시지 작성은 AI와 사람의 몫이다.
 *
 * 매 턴마다 울리면 소음이 되므로, 같은 변경 상태(git status 서명)에 대해서는
 * 한 번만 물어보도록 .claude/.commit-check-state.json 에 마지막으로 알린
 * 서명을 남긴다. 커밋이 되거나 파일이 더 바뀌면 서명이 달라져 다시 물어본다.
 *
 * 입력: Claude Code가 stdin으로 넘겨주는 Stop 훅 payload(JSON)
 *   { session_id, transcript_path, hook_event_name, stop_hook_active }
 *
 * 어떤 경우에도 예외를 밖으로 던지지 않는다. 이 확인이 실패해도 실제 작업을
 * 막아서는 안 되기 때문이다.
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const crypto = require("crypto");

// "큰 변경"으로 볼 기준. 파일 수 또는 변경 줄 수 중 하나만 넘어도 발동한다.
const FILES_THRESHOLD = 5;
const LINES_THRESHOLD = 150;

// 읽어서 줄 수를 셀 파일 크기 상한. 너무 큰 파일은 읽지 않고 파일 수에만 반영한다.
const MAX_READ_BYTES = 2 * 1024 * 1024;

let input = "";
process.stdin.on("data", (chunk) => {
  input += chunk;
});

process.stdin.on("end", () => {
  try {
    const payload = input ? JSON.parse(input) : {};

    // 이미 이 훅(혹은 다른 Stop 훅)의 block 지시로 이어지고 있는 턴이면
    // 다시 block하지 않는다. (무한 루프 방지 — Claude Code 표준 플래그)
    if (payload.stop_hook_active) {
      process.exit(0);
    }

    const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();

    let statusOutput;
    try {
      statusOutput = execSync("git status --porcelain", {
        cwd: projectDir,
        encoding: "utf-8",
      });
    } catch (_) {
      process.exit(0); // git 저장소가 아니거나 git이 없으면 조용히 종료
    }

    const statusLines = statusOutput
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    if (statusLines.length === 0) {
      process.exit(0); // 커밋 안 된 변경이 없으면 볼 것도 없다
    }

    // tracked(추적 중) 변경분: staged + unstaged 합산 통계
    let filesChanged = 0;
    let linesChanged = 0;
    try {
      const shortstat = execSync("git diff --shortstat HEAD", {
        cwd: projectDir,
        encoding: "utf-8",
      }).trim();
      const filesMatch = shortstat.match(/(\d+) files? changed/);
      const insMatch = shortstat.match(/(\d+) insertions?\(\+\)/);
      const delMatch = shortstat.match(/(\d+) deletions?\(-\)/);
      if (filesMatch) filesChanged += Number(filesMatch[1]);
      if (insMatch) linesChanged += Number(insMatch[1]);
      if (delMatch) linesChanged += Number(delMatch[1]);
    } catch (_) {
      // 최초 커밋 전(HEAD 없음) 등 diff가 안 되는 경우는 무시하고 계속 진행
    }

    // untracked(새 파일) 변경분: 파일 수 + 대략의 줄 수
    const untrackedFiles = statusLines
      .filter((line) => line.startsWith("??"))
      .map((line) => line.slice(3).trim().replace(/^"|"$/g, ""));

    for (const f of untrackedFiles) {
      filesChanged += 1;
      try {
        const fullPath = path.join(projectDir, f);
        const st = fs.statSync(fullPath);
        if (st.isFile() && st.size <= MAX_READ_BYTES) {
          const content = fs.readFileSync(fullPath, "utf-8");
          linesChanged += content.split("\n").length;
        }
      } catch (_) {
        // 디렉터리이거나 읽을 수 없는(예: 바이너리) 파일은 파일 수에만 반영
      }
    }

    const isBig = filesChanged >= FILES_THRESHOLD || linesChanged >= LINES_THRESHOLD;
    if (!isBig) {
      process.exit(0);
    }

    // 같은 변경 상태에 대해 두 번 묻지 않도록 git status 내용으로 서명을 만든다.
    const signature = crypto
      .createHash("sha256")
      .update(statusLines.sort().join("|"))
      .digest("hex");

    const statePath = path.join(projectDir, ".claude", ".commit-check-state.json");
    let state = {};
    if (fs.existsSync(statePath)) {
      try {
        state = JSON.parse(fs.readFileSync(statePath, "utf-8"));
      } catch (_) {
        state = {};
      }
    }

    if (state.lastSurfacedSignature === signature) {
      process.exit(0); // 이미 같은 변경 상태에 대해 한 번 물어봤다
    }

    fs.mkdirSync(path.dirname(statePath), { recursive: true });
    fs.writeFileSync(
      statePath,
      JSON.stringify(
        { lastSurfacedSignature: signature, surfacedAt: new Date().toISOString() },
        null,
        2
      ) + "\n"
    );

    const reason = [
      `커밋되지 않은 변경이 커졌습니다 (Stop 훅 big-change-commit-check.js 감지: 약 ${filesChanged}개 파일, ${linesChanged}줄 변경).`,
      "",
      "다음을 진행하세요:",
      "1. `git status`와 `git diff`(또는 `git diff --stat`)로 지금까지 바뀐 내용을 확인하세요.",
      "2. 무엇을 위한 변경인지 1~2문장으로 요약하세요.",
      "3. AskUserQuestion으로 '지금 중간 커밋을 할까요?'라고 반드시 먼저 물어보세요. 절대 먼저 커밋하지 마세요.",
      "4. 사용자가 승인하면, 관련 파일만 골라 `git add`하고(민감한 파일은 제외), Conventional Commits 스타일 메시지로 커밋하세요. 사용자가 원치 않으면 커밋하지 말고 하던 작업을 계속하세요.",
      "5. 이미 이번 턴에서 같은 변경에 대해 이미 물어봤다면 다시 반복하지 마세요.",
    ].join("\n");

    process.stdout.write(
      JSON.stringify({
        decision: "block",
        reason,
        hookSpecificOutput: { hookEventName: "Stop" },
      })
    );
  } catch (_) {
    // 확인은 best-effort. 실패해도 조용히 종료한다.
  }
  process.exit(0);
});
