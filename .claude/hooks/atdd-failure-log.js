#!/usr/bin/env node
/**
 * PostToolUse 훅: Bash 도구로 `node --test` 가 실행된 직후 그 출력을 파싱해
 * .claude/atdd-failure-ledger.json 에 인수 테스트 실패를 자동 기록한다.
 *
 * 왜 훅으로 만드는가:
 *   ATDD 07단계("실패 원장에 기록")를 AI가 기억해서 수행하면 바쁠 때 빼먹는다.
 *   훅으로 만들면 AI가 깜빡해도 기록은 남는다 — 규율을 성실성이 아니라 시스템에 맡기는 설계다.
 *
 * 입력: Claude Code가 stdin으로 넘겨주는 훅 payload(JSON)
 *   { tool_name: "Bash", tool_input: { command: "..." }, tool_response: { stdout, stderr } | "..." }
 *
 * 기록 규칙:
 *   - 실패가 1건 이상  → status "FAIL" 항목을 추가한다.
 *   - 실패가 0건인데 직전 항목이 FAIL → status "RESOLVED" 항목을 추가한다(빨간불이 풀린 시점).
 *   - 실패가 0건이고 직전도 초록불 → 아무것도 기록하지 않는다(원장이 통과 로그로 뒤덮이지 않게).
 *
 * 어떤 경우에도 예외를 밖으로 던지지 않는다. 기록 실패가 실제 작업을 막아서는 안 되기 때문이다.
 */
const fs = require("fs");
const path = require("path");

/** node:test 출력에서 요약 수치를 뽑는다. TAP 리포터(`# fail 3`)와 spec 리포터(`ℹ fail 3`) 양쪽을 지원한다. */
function readCount(output, key) {
  const m = output.match(new RegExp("^[^\\S\\n]*(?:#|ℹ)[^\\S\\n]*" + key + "[^\\S\\n]+(\\d+)", "m"));
  return m ? Number(m[1]) : null;
}

/** 깨진 테스트 이름 목록을 뽑는다. TAP은 `not ok 1 - 이름`, spec은 `✖ 이름 (1.2ms)` 형태다. */
function readFailedTests(output) {
  const names = [];
  const tap = /^not ok \d+ - (.+)$/gm;
  const spec = /^[^\S\n]*✖[^\S\n]+(.+)$/gm;
  let m;
  while ((m = tap.exec(output)) !== null) names.push(m[1]);
  while ((m = spec.exec(output)) !== null) names.push(m[1]);
  return names
    // 리포터가 덧붙이는 실행 시간 꼬리표를 떼어낸다.
    .map((n) => n.replace(/\s*\(\d+(?:\.\d+)?ms\)\s*$/, "").trim())
    // spec 리포터가 찍는 머리글·요약 줄은 테스트 이름이 아니므로 걸러낸다.
    .filter((n) => n && !/^(failing tests:|tests|suites|pass|fail|cancelled|skipped|todo)\b/.test(n))
    // 같은 이름이 두 리포터 형식으로 중복 수집되는 경우를 정리한다.
    .filter((n, i, arr) => arr.indexOf(n) === i);
}

let input = "";
process.stdin.on("data", (chunk) => {
  input += chunk;
});

process.stdin.on("end", () => {
  try {
    const payload = JSON.parse(input);
    const command = (payload && payload.tool_input && payload.tool_input.command) || "";

    // 인수 테스트 실행이 아니면 관심 대상이 아니다.
    if (!/node\s+(?:--experimental-test-runner\s+)?--test\b/.test(command)) {
      process.exit(0);
    }

    const res = payload.tool_response;
    const output =
      typeof res === "string"
        ? res
        : [res && res.stdout, res && res.stderr].filter(Boolean).join("\n");
    if (!output) {
      process.exit(0);
    }

    const fail = readCount(output, "fail");
    const pass = readCount(output, "pass");
    const total = readCount(output, "tests");
    // 요약 줄을 못 찾았다면 테스트가 실행되지 않은 것이므로 기록하지 않는다.
    if (fail === null) {
      process.exit(0);
    }

    const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
    const ledgerPath = path.join(projectDir, ".claude", "atdd-failure-ledger.json");

    let ledger = { entries: [] };
    if (fs.existsSync(ledgerPath)) {
      try {
        const parsed = JSON.parse(fs.readFileSync(ledgerPath, "utf-8"));
        if (parsed && Array.isArray(parsed.entries)) {
          ledger = parsed;
        }
      } catch (_) {
        // 파일이 손상된 경우 새로 시작한다.
      }
    }

    const last = ledger.entries[ledger.entries.length - 1];
    let status;
    if (fail > 0) {
      status = "FAIL";
    } else if (last && last.status === "FAIL") {
      status = "RESOLVED"; // 빨간불이 풀린 시점만 남긴다.
    } else {
      process.exit(0); // 계속 초록불이면 기록하지 않는다.
    }

    ledger.entries.push({
      recordedAt: new Date().toISOString(),
      status,
      total,
      pass,
      fail,
      failedTests: status === "FAIL" ? readFailedTests(output) : [],
      command,
    });
    ledger.updatedAt = new Date().toISOString();

    fs.mkdirSync(path.dirname(ledgerPath), { recursive: true });
    fs.writeFileSync(ledgerPath, JSON.stringify(ledger, null, 2) + "\n");
  } catch (_) {
    // 기록은 best-effort. 실패해도 조용히 종료한다.
  }
  process.exit(0);
});
