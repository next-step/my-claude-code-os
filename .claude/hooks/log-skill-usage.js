#!/usr/bin/env node
/**
 * PostToolUse 훅: Skill 도구 호출 직후 실행되어
 * .claude/skill-usage-stats.json 에 스킬별 호출 횟수를 누적 기록한다.
 *
 * 입력: Claude Code가 stdin으로 넘겨주는 훅 payload(JSON)
 *   { tool_name: "Skill", tool_input: { skill: "<스킬 이름>", ... }, ... }
 *
 * 어떤 경우에도(파싱 실패, 파일 손상 등) 예외를 밖으로 던지지 않는다.
 * 로깅 실패가 실제 Claude 동작(툴 호출)을 막아서는 안 되기 때문이다.
 */
const fs = require("fs");
const path = require("path");

let input = "";
process.stdin.on("data", (chunk) => {
  input += chunk;
});

process.stdin.on("end", () => {
  try {
    const payload = JSON.parse(input);
    const skillName = payload && payload.tool_input && payload.tool_input.skill;
    if (!skillName) {
      process.exit(0);
    }

    const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
    const statsPath = path.join(projectDir, ".claude", "skill-usage-stats.json");

    let stats = { totalCalls: 0, skills: {} };
    if (fs.existsSync(statsPath)) {
      try {
        const parsed = JSON.parse(fs.readFileSync(statsPath, "utf-8"));
        if (parsed && typeof parsed === "object") {
          stats = parsed;
        }
      } catch (_) {
        // 파일이 손상된 경우 새로 시작한다.
      }
    }
    if (!stats.skills || typeof stats.skills !== "object") {
      stats.skills = {};
    }

    const now = new Date().toISOString();
    const entry = stats.skills[skillName] || { count: 0, firstUsedAt: now };
    entry.count = (entry.count || 0) + 1;
    entry.lastUsedAt = now;
    stats.skills[skillName] = entry;
    stats.totalCalls = (stats.totalCalls || 0) + 1;
    stats.updatedAt = now;

    fs.mkdirSync(path.dirname(statsPath), { recursive: true });
    fs.writeFileSync(statsPath, JSON.stringify(stats, null, 2) + "\n");
  } catch (_) {
    // 로깅은 best-effort. 실패해도 조용히 종료한다.
  }
  process.exit(0);
});
