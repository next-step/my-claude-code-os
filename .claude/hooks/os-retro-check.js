#!/usr/bin/env node
/**
 * Stop 훅: Claude가 한 턴을 마치고 멈추려는 시점에, 이번 세션에서 OS 구조
 * (스킬/에이전트/훅/docs) 관련 파일이 실제로 바뀌었는지 확인한다.
 *
 * 왜 훅으로 만드는가:
 *   훅(이 스크립트)은 사람에게 직접 질문을 던질 수 없다 — 명령을 실행해 결과를
 *   표준출력으로 돌려줄 뿐이다. 그래서 이 훅은 "물어보는 일"을 직접 하지 않고,
 *   decision:"block" 으로 Claude의 턴을 계속 이어가게 한 뒤, reason에 담은 지시로
 *   Claude가 회고를 정리하고 AskUserQuestion으로 사람에게 직접 물어보게 시킨다.
 *   판단과 대화는 AI(Claude)의 몫, "빼먹지 않고 매번 확인하는 규율"은 훅의 몫이다.
 *
 * 매 턴마다 울리면 소음이 되므로, git 상태를 봐서 OS 관련 파일이 실제로
 * 바뀐 경우에만 발동한다. 같은 변경 내용에 대해서는 한 번만 물어보도록
 * .claude/.os-retro-state.json 에 마지막으로 알린 서명(signature)을 남긴다.
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

// OS.md에 반영할 만한 변경으로 볼 경로. OS.md 자기 자신은 "결과물"이지 "원인"이
// 아니므로 트리거 대상에서 제외한다.
const RELEVANT_PATTERN = /^(\.claude\/(skills|agents|hooks|lib|tests)\/|docs\/)/;

let input = "";
process.stdin.on("data", (chunk) => {
  input += chunk;
});

process.stdin.on("end", () => {
  try {
    const payload = input ? JSON.parse(input) : {};

    // 이미 이 훅의 block 지시로 이어지고 있는 턴이면 다시 block하지 않는다.
    // (무한 루프 방지 — Claude Code가 넘겨주는 표준 플래그)
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

    const relevantFiles = statusOutput
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        // "R  old -> new" 형태(rename)는 새 경로만 취한다.
        const arrowIdx = line.indexOf(" -> ");
        const raw = arrowIdx !== -1 ? line.slice(arrowIdx + 4) : line.slice(3);
        return raw.trim().replace(/^"|"$/g, "");
      })
      .filter((f) => RELEVANT_PATTERN.test(f));

    if (relevantFiles.length === 0) {
      process.exit(0);
    }

    // 파일 목록뿐 아니라 mtime·size까지 서명에 포함해, 같은 파일을 다시
    // 고친 경우에도(경로 목록은 그대로라도) 새로 감지되게 한다.
    const signatureParts = relevantFiles
      .sort()
      .map((f) => {
        try {
          const st = fs.statSync(path.join(projectDir, f));
          return `${f}:${st.mtimeMs}:${st.size}`;
        } catch (_) {
          return `${f}:missing`;
        }
      });
    const signature = crypto
      .createHash("sha256")
      .update(signatureParts.join("|"))
      .digest("hex");

    const statePath = path.join(projectDir, ".claude", ".os-retro-state.json");
    let state = {};
    if (fs.existsSync(statePath)) {
      try {
        state = JSON.parse(fs.readFileSync(statePath, "utf-8"));
      } catch (_) {
        state = {};
      }
    }

    if (state.lastSurfacedSignature === signature) {
      process.exit(0); // 이미 같은 변경에 대해 한 번 물어봤다
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

    const fileList = relevantFiles.map((f) => `- ${f}`).join("\n");
    const reason = [
      "이번 세션에서 OS 구조와 관련된 파일이 바뀌었습니다 (Stop 훅 os-retro-check.js 감지):",
      fileList,
      "",
      "다음을 진행하세요:",
      "1. 이번 변경이 무엇을 위한 것이었는지, 어떤 고민·트레이드오프가 있었는지 1~3문장으로 회고를 정리하세요.",
      "2. OS.md의 관련 섹션(8. 설계 노트 / 7. 열린 질문 / 9. 기능 정리 등) 중 반영할 곳이 있는지 판단하세요.",
      "3. 반영할 내용이 있다면 정확한 문구와 위치를 먼저 제시하고, AskUserQuestion으로 'OS.md에 반영할까요?'라고 반드시 먼저 물어본 뒤, 승인한 경우에만 Edit으로 반영하세요. 반영할 내용이 없다고 판단되면 그 이유를 한 줄로 알려주고 넘어가세요.",
      "4. 이미 이번 세션에서 같은 내용을 회고·반영했다면 다시 반복하지 말고 그냥 넘어가세요.",
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
