/**
 * notion-min MCP 서버 순수 로직의 인수 테스트.
 *
 * `.claude/context/code-vs-instruction.md`의 관례대로 `lib` 파일 하나에 테스트 하나를 짝짓고,
 * 테스트 제목에 AC 번호를 달아 실패 원장에서 무엇이 깨졌는지 추적할 수 있게 한다.
 *
 * 네트워크를 타지 않는다 — `fetchImpl`에 가짜 함수를 주입해 검증한다.
 *
 * 실행: node --test .claude/tests/notion-min.test.js
 *      (`node --test .claude/tests/` 는 Node가 숨김 디렉터리를 탐색에서 빼서 실패한다)
 */
const test = require("node:test");
const assert = require("node:assert/strict");

const {
  NOTION_VERSION,
  DEFAULT_SEARCH_LIMIT,
  toolDefinitions,
  normalizePageId,
  buildSearchRequest,
  buildPageRequest,
  buildBlocksRequest,
  pageTitle,
  formatSearchResults,
  blocksToText,
  formatApiError,
  callTool,
} = require("../lib/notion-min.js");

const TOKEN = "ntn_secret_should_never_leak_1234567890";

/** 호출 순서대로 미리 준비한 응답을 돌려주는 가짜 fetch. 실제 요청도 기록한다. */
function fakeFetch(responses) {
  const calls = [];
  const queue = [...responses];
  const impl = async (url, init) => {
    calls.push({ url, init });
    const next = queue.shift();
    if (!next) throw new Error(`예상치 못한 추가 호출: ${url}`);
    return {
      ok: next.ok !== false,
      status: next.status ?? 200,
      json: async () => next.json,
    };
  };
  impl.calls = calls;
  return impl;
}

// ---------------------------------------------------------------- 툴 정의

test("AC-1: 노출하는 툴은 정확히 2개다 (기성 서버 42개 대비)", () => {
  const tools = toolDefinitions();
  assert.equal(tools.length, 2);
  assert.deepEqual(
    tools.map((t) => t.name).sort(),
    ["notion_get_page", "notion_search"]
  );
});

test("AC-2: 모든 툴이 name·description·inputSchema.required를 갖춘다", () => {
  for (const tool of toolDefinitions()) {
    assert.ok(tool.name, "name 누락");
    assert.ok(tool.description && tool.description.length > 20, `${tool.name}: description이 너무 짧다`);
    assert.equal(tool.inputSchema.type, "object");
    assert.ok(Array.isArray(tool.inputSchema.required) && tool.inputSchema.required.length > 0);
    for (const req of tool.inputSchema.required) {
      assert.ok(tool.inputSchema.properties[req], `${tool.name}: required '${req}'가 properties에 없다`);
    }
  }
});

// ---------------------------------------------------------------- 요청 조립

test("AC-3: 검색 요청이 올바른 URL·메서드·Notion-Version 헤더를 만든다", () => {
  const req = buildSearchRequest({ query: "회고", limit: 5, token: TOKEN });
  assert.equal(req.url, "https://api.notion.com/v1/search");
  assert.equal(req.method, "POST");
  assert.equal(req.headers["Notion-Version"], NOTION_VERSION);
  assert.equal(req.headers.Authorization, `Bearer ${TOKEN}`);
  assert.equal(req.headers["Content-Type"], "application/json");

  const body = JSON.parse(req.body);
  assert.equal(body.query, "회고");
  assert.equal(body.page_size, 5);
  assert.deepEqual(body.filter, { property: "object", value: "page" });
});

test("AC-4: limit이 없거나 범위를 벗어나면 안전한 값으로 죈다", () => {
  assert.equal(JSON.parse(buildSearchRequest({ query: "x", token: TOKEN }).body).page_size, DEFAULT_SEARCH_LIMIT);
  assert.equal(JSON.parse(buildSearchRequest({ query: "x", limit: 999, token: TOKEN }).body).page_size, 50);
  assert.equal(JSON.parse(buildSearchRequest({ query: "x", limit: 0, token: TOKEN }).body).page_size, DEFAULT_SEARCH_LIMIT);
  assert.equal(JSON.parse(buildSearchRequest({ query: "x", limit: -3, token: TOKEN }).body).page_size, DEFAULT_SEARCH_LIMIT);
});

test("AC-5: 페이지/블록 요청 URL이 올바르다", () => {
  const id = "195de922-1179-449f-ab80-75a27c979105";
  assert.equal(buildPageRequest(id, { token: TOKEN }).url, `https://api.notion.com/v1/pages/${id}`);
  assert.equal(buildBlocksRequest(id, { token: TOKEN }).url, `https://api.notion.com/v1/blocks/${id}/children?page_size=100`);
});

// ---------------------------------------------------------------- ID 정규화

test("AC-6: 페이지 ID를 URL·하이픈 유무 무관하게 정규화한다", () => {
  const expected = "195de922-1179-449f-ab80-75a27c979105";
  assert.equal(normalizePageId("195de9221179449fab8075a27c979105"), expected);
  assert.equal(normalizePageId(expected), expected);
  assert.equal(normalizePageId("https://www.notion.so/My-Page-195de9221179449fab8075a27c979105"), expected);
  assert.equal(normalizePageId("https://notion.so/x/195de9221179449fab8075a27c979105?pvs=4"), expected);
});

test("AC-7: 해석 불가능한 페이지 ID는 null이다 (조용히 잘못된 ID를 만들지 않는다)", () => {
  assert.equal(normalizePageId("짧다"), null);
  assert.equal(normalizePageId(""), null);
  assert.equal(normalizePageId(undefined), null);
  assert.equal(normalizePageId(12345), null);
});

// ---------------------------------------------------------------- 포맷팅

test("AC-8: 제목은 이름이 아니라 type==='title' 속성에서 뽑는다", () => {
  // 데이터베이스 페이지는 제목 속성의 이름이 워크스페이스마다 다르다.
  const page = { properties: { "이름아무거나": { type: "title", title: [{ plain_text: "회고 노트" }] } } };
  assert.equal(pageTitle(page), "회고 노트");
  assert.equal(pageTitle({ properties: {} }), "(제목 없음)");
  assert.equal(pageTitle({}), "(제목 없음)");
});

test("AC-9: 검색 결과가 비면 결과 없음을 말한다", () => {
  assert.match(formatSearchResults({ results: [] }), /검색 결과가 없습니다/);
  assert.match(formatSearchResults({}), /검색 결과가 없습니다/);
});

test("AC-10: 검색 결과에 제목·id가 실리고 has_more면 더 있음을 알린다", () => {
  const json = {
    results: [
      { id: "abc", last_edited_time: "2026-09-07T10:00:00.000Z", properties: { T: { type: "title", title: [{ plain_text: "첫 문서" }] } } },
    ],
    has_more: true,
  };
  const out = formatSearchResults(json);
  assert.match(out, /첫 문서/);
  assert.match(out, /id: abc/);
  assert.match(out, /2026-09-07/);
  assert.match(out, /더 있음/);
});

test("AC-11: 블록을 마크다운 평문으로 옮긴다", () => {
  const json = {
    results: [
      { type: "heading_1", heading_1: { rich_text: [{ plain_text: "제목" }] } },
      { type: "paragraph", paragraph: { rich_text: [{ plain_text: "본문" }] } },
      { type: "bulleted_list_item", bulleted_list_item: { rich_text: [{ plain_text: "항목" }] } },
      { type: "to_do", to_do: { rich_text: [{ plain_text: "할일" }], checked: true } },
      { type: "code", code: { rich_text: [{ plain_text: "x=1" }], language: "python" } },
      { type: "divider", divider: {} },
    ],
  };
  const out = blocksToText(json);
  assert.match(out, /^# 제목$/m);
  assert.match(out, /^본문$/m);
  assert.match(out, /^- 항목$/m);
  assert.match(out, /^- \[x\] 할일$/m);
  assert.match(out, /```python\nx=1\n```/);
  assert.match(out, /^---$/m);
});

test("AC-12: 모르는 블록 타입은 조용히 빠지지 않고 [타입]으로 표시된다", () => {
  // 조용히 빠지면 '내용이 없는 페이지'와 구별할 수 없다.
  const out = blocksToText({ results: [{ type: "table_of_contents", table_of_contents: {} }] });
  assert.equal(out, "[table_of_contents]");
});

test("AC-13: 본문이 maxChars를 넘으면 잘라내고 잘렸음을 표시한다", () => {
  const long = "가".repeat(5000);
  const json = { results: [{ type: "paragraph", paragraph: { rich_text: [{ plain_text: long }] } }] };

  const out = blocksToText(json, { maxChars: 100 });
  assert.ok(out.length < 300, `잘리지 않았다: ${out.length}자`);
  assert.match(out, /자 잘림/);
  assert.match(out, /max_chars/);

  // 상한 이하면 손대지 않는다.
  const short = blocksToText({ results: [{ type: "paragraph", paragraph: { rich_text: [{ plain_text: "짧음" }] } }] }, { maxChars: 100 });
  assert.equal(short, "짧음");
});

// ---------------------------------------------------------------- callTool 통합

test("AC-14: 토큰이 없으면 던지지 않고 설정 안내를 돌려준다", async () => {
  const res = await callTool("notion_search", { query: "x" }, { token: null });
  assert.equal(res.content[0].type, "text");
  assert.match(res.content[0].text, /NOTION_TOKEN/);
  assert.match(res.content[0].text, /my-integrations/);
});

test("AC-15: notion_search가 검색 결과를 텍스트로 돌려준다", async () => {
  const impl = fakeFetch([
    { json: { results: [{ id: "p1", properties: { T: { type: "title", title: [{ plain_text: "회고" }] } } }] } },
  ]);
  const res = await callTool("notion_search", { query: "회고" }, { fetchImpl: impl, token: TOKEN });
  assert.match(res.content[0].text, /회고/);
  assert.equal(impl.calls.length, 1);
  assert.equal(impl.calls[0].url, "https://api.notion.com/v1/search");
});

test("AC-16: notion_get_page가 페이지와 블록을 두 번 호출해 합친다", async () => {
  const impl = fakeFetch([
    { json: { properties: { T: { type: "title", title: [{ plain_text: "설계 노트" }] } } } },
    { json: { results: [{ type: "paragraph", paragraph: { rich_text: [{ plain_text: "내용입니다" }] } }] } },
  ]);
  const res = await callTool(
    "notion_get_page",
    { page_id: "195de9221179449fab8075a27c979105" },
    { fetchImpl: impl, token: TOKEN }
  );
  assert.match(res.content[0].text, /# 설계 노트/);
  assert.match(res.content[0].text, /내용입니다/);
  assert.equal(impl.calls.length, 2);
  assert.match(impl.calls[0].url, /\/pages\//);
  assert.match(impl.calls[1].url, /\/blocks\/.*\/children/);
});

test("AC-17: API 오류를 던지지 않고 상태코드·메시지로 설명한다", async () => {
  const impl = fakeFetch([{ ok: false, status: 401, json: { message: "API token is invalid." } }]);
  const res = await callTool("notion_search", { query: "x" }, { fetchImpl: impl, token: TOKEN });
  assert.match(res.content[0].text, /HTTP 401/);
  assert.match(res.content[0].text, /API token is invalid/);
});

test("AC-18: 네트워크 예외도 던지지 않고 텍스트로 돌려준다", async () => {
  const impl = async () => {
    throw new Error("getaddrinfo ENOTFOUND api.notion.com");
  };
  const res = await callTool("notion_search", { query: "x" }, { fetchImpl: impl, token: TOKEN });
  assert.match(res.content[0].text, /요청 실패/);
  assert.match(res.content[0].text, /ENOTFOUND/);
});

test("AC-19: 알 수 없는 툴 이름을 안전하게 거절한다", async () => {
  const res = await callTool("notion_delete_everything", {}, { token: TOKEN });
  assert.match(res.content[0].text, /알 수 없는 툴/);
});

// ------------------------------------------------- 민감정보 회귀 (sensitive-info.md)

test("AC-20: 어떤 경로로도 토큰이 툴 응답에 실리지 않는다", async () => {
  const cases = [
    // 정상
    () => callTool("notion_search", { query: "x" }, { fetchImpl: fakeFetch([{ json: { results: [] } }]), token: TOKEN }),
    // API 오류 — 오류 본문에 토큰을 되비추는 서버가 있어도 우리가 실어 나르면 안 된다
    () =>
      callTool(
        "notion_search",
        { query: "x" },
        { fetchImpl: fakeFetch([{ ok: false, status: 401, json: { message: `bad token ${TOKEN}` } }]), token: TOKEN }
      ),
    // 네트워크 예외
    () =>
      callTool("notion_search", { query: "x" }, {
        fetchImpl: async () => {
          throw new Error("boom");
        },
        token: TOKEN,
      }),
    // 잘못된 페이지 ID
    () => callTool("notion_get_page", { page_id: "??" }, { fetchImpl: fakeFetch([]), token: TOKEN }),
  ];

  for (const [i, run] of cases.entries()) {
    const res = await run();
    assert.ok(
      !JSON.stringify(res).includes(TOKEN),
      `케이스 ${i}: 토큰이 응답에 실렸다 — ${res.content[0].text}`
    );
  }
});

test("AC-21: 툴 정의 전체가 기성 서버 대비 작다 (이 서버의 존재 이유)", () => {
  // 기성 notion MCP는 툴 42개. 스키마 2개 표본이 약 13,000자였다(2026-09-07 실측).
  // 여기서는 툴 정의 전체가 그 표본 1개보다 작아야 의미가 있다.
  const chars = JSON.stringify(toolDefinitions()).length;
  assert.ok(chars < 3000, `툴 정의가 ${chars}자로 커졌다 — 툴을 늘렸거나 description이 길어졌다`);
});
