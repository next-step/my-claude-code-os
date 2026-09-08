#!/usr/bin/env node
"use strict";
/**
 * MCP 프로토콜 도청기 (Part 0 — 일회성 조사 도구, 제품 코드 아님)
 *
 * 왜 있는가: MCP 스펙 2026-07-28이 `initialize`를 `server/discover`로 교체했다.
 * Claude Code 2.1.263이 둘 중 무엇을 말하는지 문서로 확인하지 못했다.
 * SDK 없이 직접 짜면 여기서 틀리는 순간 서버가 조용히 죽으므로,
 * 추측 대신 실제로 들어오는 바이트를 그대로 찍어 둔다.
 *
 * 관측하려는 것 3가지:
 *   1) 프레이밍 — 개행 구분(NDJSON)인가 Content-Length 헤더인가
 *   2) 첫 메서드 이름 — initialize 인가 server/discover 인가
 *   3) protocolVersion 문자열의 실제 값
 *
 * 그래서 이 서버는 "최대한 관대하게" 응답한다. 응답이 틀려서 클라이언트가
 * 일찍 끊어 버리면 tools/list 까지 못 보기 때문이다.
 */

const fs = require("fs");
const path = require("path");

const LOG = path.join(__dirname, ".probe.log");

function log(tag, data) {
  fs.appendFileSync(LOG, `\n===== ${tag} @ ${new Date().toISOString()} =====\n${data}\n`);
}

log("PROCESS START", `argv=${JSON.stringify(process.argv)}\ncwd=${process.cwd()}`);

// 서버가 노출한다고 주장할 툴 1개. tools/list 가 실제로 오는지 확인하는 미끼다.
const FAKE_TOOLS = [
  {
    name: "probe_echo",
    title: "Probe Echo",
    description: "프로토콜 도청용 더미 툴. 입력을 그대로 돌려준다.",
    inputSchema: {
      type: "object",
      properties: { text: { type: "string", description: "돌려받을 문자열" } },
      required: ["text"],
    },
  },
];

function send(obj) {
  const line = JSON.stringify(obj);
  log("SENT", line);
  process.stdout.write(line + "\n"); // NDJSON 가정. 안 먹으면 로그로 드러난다.
}

/** 어떤 리비전으로 물어보든 답이 되도록 결과를 합쳐서 돌려준다. */
function handle(msg) {
  const { id, method, params } = msg;
  if (id === undefined || id === null) return; // 알림(notification) — 응답 없음

  const clientVersion =
    params?.protocolVersion ||
    params?._meta?.["io.modelcontextprotocol/protocolVersion"] ||
    "2025-06-18";

  if (method === "initialize" || method === "server/discover") {
    send({
      jsonrpc: "2.0",
      id,
      result: {
        // 구 리비전용 필드
        protocolVersion: clientVersion, // 클라이언트가 말한 버전을 그대로 되돌려준다
        serverInfo: { name: "notion-min-probe", version: "0.0.1" },
        capabilities: { tools: { listChanged: false } },
        // 신 리비전용 필드
        resultType: "complete",
        supportedVersions: [clientVersion],
        _meta: {
          "io.modelcontextprotocol/serverInfo": { name: "notion-min-probe", version: "0.0.1" },
        },
      },
    });
    return;
  }

  if (method === "tools/list") {
    send({ jsonrpc: "2.0", id, result: { tools: FAKE_TOOLS, resultType: "complete" } });
    return;
  }

  if (method === "tools/call") {
    send({
      jsonrpc: "2.0",
      id,
      result: { content: [{ type: "text", text: "probe ok" }], resultType: "complete" },
    });
    return;
  }

  // 모르는 메서드 — 빈 결과로 넘긴다. 여기 뭐가 찍히는지가 관측 포인트다.
  log("UNKNOWN METHOD", method);
  send({ jsonrpc: "2.0", id, result: {} });
}

let buffer = "";
process.stdin.on("data", (chunk) => {
  const raw = chunk.toString("utf8");
  // 원본 바이트를 그대로 남긴다 — 프레이밍(개행 vs Content-Length)을 여기서 판별한다.
  log("RAW STDIN CHUNK", JSON.stringify(raw));
  buffer += raw;

  let nl;
  while ((nl = buffer.indexOf("\n")) !== -1) {
    const line = buffer.slice(0, nl).trim();
    buffer = buffer.slice(nl + 1);
    if (!line) continue;
    try {
      handle(JSON.parse(line));
    } catch (err) {
      log("PARSE FAIL", `${err.message}\nline=${JSON.stringify(line)}`);
    }
  }
});

process.stdin.on("end", () => log("STDIN END", ""));
process.on("exit", (code) => log("PROCESS EXIT", `code=${code}`));
