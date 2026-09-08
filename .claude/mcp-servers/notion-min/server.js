#!/usr/bin/env node
"use strict";
/**
 * notion-min — 툴 2개만 노출하는 최소 MCP 서버 (무의존, 순수 Node).
 *
 * ## 왜 만들었나
 * 기성 Notion MCP는 툴 42개를 노출한다. 2026-09-07 실측으로 스키마 2개가 약 13,000자였고,
 * 42개 전부면 약 27만 자로 추정된다 — 이 저장소의 상시 로드 총량(13,940자)의 약 20배다.
 * Claude Code 2.1.263은 이름만 싣고 스키마를 지연 로딩해 대부분을 막아 주지만,
 * **툴 응답 크기**만은 지연 로딩이 못 막는다. 여기서는 그것을 직접 통제한다(lib의 maxChars).
 *
 * ## 프로토콜 — 문서가 아니라 관측으로 정했다
 * MCP 스펙 2026-07-28은 `initialize`를 `server/discover`로 교체했다. 그대로 짰으면 틀렸다.
 * probe.js로 Claude Code 2.1.263이 실제로 보내는 바이트를 찍어 확인한 사실(2026-09-07):
 *
 *   - 프레이밍: **NDJSON** (개행 구분). Content-Length 헤더가 아니다.
 *   - 순서: `initialize` → `notifications/initialized` → `tools/list`
 *   - `params.protocolVersion` = "2025-11-25", clientInfo.name = "claude-code"
 *   - **한 chunk에 메시지가 2개 이상 붙어서 온다** → 버퍼링 후 개행으로 쪼개야 한다
 *   - `notifications/*` 는 id가 없다 → 응답하면 안 된다
 *
 * 재확인 방법: probe.js를 다시 등록하고 `claude mcp list` 후 .probe.log를 읽는다.
 *
 * ## 규칙
 * stdout은 JSON-RPC 전용이다. 로그는 전부 stderr로 보낸다 —
 * stdout에 한 글자라도 섞으면 파싱이 깨지고 서버가 조용히 죽는다.
 */

const fs = require("node:fs");
const path = require("node:path");
const notion = require("../../lib/notion-min.js");

const SERVER_INFO = { name: "notion-min", version: "1.0.0" };
const FALLBACK_PROTOCOL_VERSION = "2025-11-25"; // 관측값. 클라이언트가 말해 주면 그것을 쓴다.

function logErr(...args) {
  console.error("[notion-min]", ...args);
}

/**
 * 토큰을 읽는다. 환경변수 우선, 없으면 gitignore된 파일.
 * `.mcp.json`은 커밋되므로 거기에는 절대 넣지 않는다 (`.claude/context/sensitive-info.md`).
 */
function loadToken() {
  if (process.env.NOTION_TOKEN) return process.env.NOTION_TOKEN.trim();
  const file = path.join(__dirname, "..", "..", ".notion-token");
  try {
    const value = fs.readFileSync(file, "utf8").trim();
    return value || null;
  } catch {
    return null; // 없는 게 정상이다. 없으면 callTool이 설정 안내를 돌려준다.
  }
}

const TOKEN = loadToken();
logErr(TOKEN ? "토큰 로드됨" : "토큰 없음 — 툴 호출 시 설정 안내를 돌려줍니다");

function send(obj) {
  process.stdout.write(JSON.stringify(obj) + "\n");
}

function sendResult(id, result) {
  send({ jsonrpc: "2.0", id, result });
}

function sendError(id, code, message) {
  send({ jsonrpc: "2.0", id, error: { code, message } });
}

async function handle(msg) {
  const { id, method, params } = msg;
  const isNotification = id === undefined || id === null;

  switch (method) {
    case "initialize":
      sendResult(id, {
        // 클라이언트가 말한 버전을 그대로 되돌려준다. 우리가 고집하면 협상이 깨진다.
        protocolVersion: params?.protocolVersion || FALLBACK_PROTOCOL_VERSION,
        serverInfo: SERVER_INFO,
        capabilities: { tools: { listChanged: false } },
      });
      return;

    case "notifications/initialized":
    case "notifications/cancelled":
      return; // id가 없다. 응답하면 프로토콜 위반이다.

    case "tools/list":
      sendResult(id, { tools: notion.toolDefinitions() });
      return;

    case "tools/call": {
      const result = await notion.callTool(params?.name, params?.arguments ?? {}, {
        token: TOKEN,
      });
      sendResult(id, result);
      return;
    }

    // 이 서버는 리소스·프롬프트를 제공하지 않는다. 물어보면 빈 목록으로 답한다
    // (에러로 답하면 클라이언트가 서버를 고장난 것으로 취급할 수 있다).
    case "resources/list":
      sendResult(id, { resources: [] });
      return;
    case "prompts/list":
      sendResult(id, { prompts: [] });
      return;

    default:
      if (isNotification) return;
      logErr("모르는 메서드:", method);
      sendError(id, -32601, `Method not found: ${method}`);
  }
}

// --- NDJSON 읽기 루프 -------------------------------------------------------
// 한 chunk에 메시지가 여러 개 붙어 오고, 반대로 한 메시지가 여러 chunk에 걸쳐 올 수도 있다.
// 그래서 버퍼에 모아 두고 개행이 나올 때마다 꺼내 쓴다.
let buffer = "";

process.stdin.on("data", (chunk) => {
  buffer += chunk.toString("utf8");
  let nl;
  while ((nl = buffer.indexOf("\n")) !== -1) {
    const line = buffer.slice(0, nl).trim();
    buffer = buffer.slice(nl + 1);
    if (!line) continue;

    let msg;
    try {
      msg = JSON.parse(line);
    } catch (err) {
      logErr("JSON 파싱 실패:", err.message);
      continue; // 한 줄이 깨졌다고 서버를 죽이지 않는다
    }

    // handle은 async다. 실패해도 루프가 멈추지 않도록 여기서 삼킨다.
    Promise.resolve(handle(msg)).catch((err) => {
      logErr("처리 실패:", err?.message ?? err);
      if (msg?.id !== undefined && msg?.id !== null) {
        sendError(msg.id, -32603, "Internal error");
      }
    });
  }
});

process.stdin.on("end", () => process.exit(0));
