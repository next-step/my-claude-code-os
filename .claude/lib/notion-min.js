/**
 * notion-min MCP 서버의 순수 로직.
 *
 * `.claude/context/code-vs-instruction.md`: "판정·집계·파싱은 전부 lib으로 뺀다.
 * lib 함수는 순수 함수로 쓰고 fs 접근은 옵션으로 주입받게 한다."
 * 여기서는 `fs` 대신 **`fetch`를 주입**한다 — 네트워크 없이 테스트하기 위해서다
 * (`context-map.js`의 `fsOverrides`, `session-board.js`와 같은 관례).
 *
 * 왜 이 파일이 있는가: 기성 Notion MCP는 툴 42개를 노출한다. 이 저장소가
 * 상시 로드에 쓰는 글자 수 전체보다 훨씬 큰 표면이다. 여기서는 툴 2개만 노출하고,
 * 무엇보다 **응답 길이를 직접 통제한다**(`maxChars`) — 지연 로딩이 해결해 주지 못하는
 * 유일한 비용 항목이 툴 응답 크기이기 때문이다.
 *
 * 서버 껍데기는 mcp-servers/notion-min/server.js 이고, 프로토콜 처리만 한다.
 */
"use strict";

const API_BASE = "https://api.notion.com/v1";

/**
 * Notion API 버전 헤더. 확인 시점 2026-09-07의 현재값이다
 * (developers.notion.com/reference/post-search).
 * Notion은 이 헤더가 없으면 요청을 거절하므로 생략할 수 없다.
 */
const NOTION_VERSION = "2026-03-11";

/** 툴 응답의 기본 길이 상한. 이 서버의 존재 이유이므로 기본값을 넉넉하지 않게 잡는다. */
const DEFAULT_MAX_CHARS = 4000;

/** 검색 결과 기본 개수. Notion의 기본값(100)을 그대로 쓰면 응답이 폭발한다. */
const DEFAULT_SEARCH_LIMIT = 10;

/**
 * 이 서버가 노출하는 툴 전부. 정확히 2개다.
 *
 * `description`은 모델이 어떤 툴을 부를지 정하는 유일한 근거라 짧게 깎지 않는다
 * (`docs/context-budget.md`의 "E. 스킬 description 압축을 하지 않은 이유"와 같은 판단).
 * 대신 개수 자체를 줄여서 비용을 통제한다.
 */
function toolDefinitions() {
  return [
    {
      name: "notion_search",
      title: "Notion 검색",
      description:
        "Notion 워크스페이스에서 제목으로 페이지를 검색한다. 페이지 제목과 ID, 마지막 수정 시각을 돌려준다. " +
        "본문 내용이 필요하면 여기서 얻은 ID로 notion_get_page를 부른다.",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string", description: "검색할 제목 키워드. 빈 문자열이면 최근 문서 목록." },
          limit: {
            type: "integer",
            description: `돌려받을 최대 개수 (기본 ${DEFAULT_SEARCH_LIMIT}, 최대 50)`,
            minimum: 1,
            maximum: 50,
          },
        },
        required: ["query"],
      },
    },
    {
      name: "notion_get_page",
      title: "Notion 페이지 읽기",
      description:
        "Notion 페이지 하나의 제목과 본문을 평문으로 읽는다. 페이지 ID 또는 Notion URL을 받는다. " +
        "본문이 길면 잘라내고 잘렸음을 표시한다 — 컨텍스트를 통째로 먹지 않기 위해서다.",
      inputSchema: {
        type: "object",
        properties: {
          page_id: { type: "string", description: "페이지 ID(하이픈 유무 무관) 또는 Notion 페이지 URL" },
          max_chars: {
            type: "integer",
            description: `본문 길이 상한 (기본 ${DEFAULT_MAX_CHARS})`,
            minimum: 200,
          },
        },
        required: ["page_id"],
      },
    },
  ];
}

/** Notion API 공통 헤더. 토큰은 호출부에서 주입받는다 — 이 모듈은 토큰을 저장하지 않는다. */
function apiHeaders(token) {
  return {
    Authorization: `Bearer ${token}`,
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
  };
}

/**
 * 페이지 ID를 정규화한다. 사용자는 보통 URL을 붙여넣지 순수 ID를 주지 않는다.
 *
 * 주의(2026-09-07 테스트가 잡은 결함): 문자열 **전체**에서 hex 문자를 긁어모으면
 * `?pvs=4` 의 `4` 같은 글자가 섞여 들어와 ID가 한 칸씩 밀린다. 그래서
 * (1) 쿼리스트링·프래그먼트를 먼저 떼고 (2) 하이픈 UUID를 우선 찾고
 * (3) 없으면 hex 덩어리 중 **마지막** 것을 쓴다 — Notion은 ID를 URL 끝에 붙인다.
 */
function normalizePageId(raw) {
  if (typeof raw !== "string") return null;
  const withoutQuery = raw.split(/[?#]/)[0];

  const dashed = withoutQuery.match(
    /[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/
  );
  if (dashed) return dashify(dashed[0].replace(/-/g, ""));

  const runs = withoutQuery.match(/[0-9a-fA-F]{32,}/g);
  if (!runs) return null;
  const last = runs[runs.length - 1];
  return dashify(last.slice(last.length - 32));
}

/** 32자리 hex → 8-4-4-4-12 형태. */
function dashify(hex) {
  const id = hex.toLowerCase();
  return `${id.slice(0, 8)}-${id.slice(8, 12)}-${id.slice(12, 16)}-${id.slice(16, 20)}-${id.slice(20)}`;
}

/**
 * limit을 안전한 값으로 죈다.
 *
 * 음수·0·NaN을 1로 죄지 않고 **기본값으로 되돌리는** 이유: 그것들은 잘못 넣은 값이다.
 * 조용히 1로 죄면 결과가 1건만 와서 "검색이 안 된다"로 오해하게 된다.
 */
function clampLimit(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 1) return DEFAULT_SEARCH_LIMIT;
  return Math.min(Math.floor(n), 50);
}

function buildSearchRequest({ query, limit, token }) {
  const pageSize = clampLimit(limit);
  return {
    url: `${API_BASE}/search`,
    method: "POST",
    headers: apiHeaders(token),
    body: JSON.stringify({
      query: typeof query === "string" ? query : "",
      page_size: pageSize,
      filter: { property: "object", value: "page" },
      sort: { direction: "descending", timestamp: "last_edited_time" },
    }),
  };
}

function buildPageRequest(pageId, { token }) {
  return { url: `${API_BASE}/pages/${pageId}`, method: "GET", headers: apiHeaders(token) };
}

function buildBlocksRequest(pageId, { token }) {
  return {
    url: `${API_BASE}/blocks/${pageId}/children?page_size=100`,
    method: "GET",
    headers: apiHeaders(token),
  };
}

/**
 * 페이지 객체에서 제목을 뽑는다.
 * 데이터베이스 안의 페이지는 제목 속성의 **이름이 워크스페이스마다 다르므로**
 * 이름으로 찾지 않고 `type === "title"` 인 속성을 찾는다.
 */
function pageTitle(page) {
  const props = page?.properties;
  if (props && typeof props === "object") {
    for (const value of Object.values(props)) {
      if (value?.type === "title" && Array.isArray(value.title)) {
        const text = value.title.map((t) => t?.plain_text ?? "").join("").trim();
        if (text) return text;
      }
    }
  }
  return "(제목 없음)";
}

function formatSearchResults(json, { limit } = {}) {
  const results = Array.isArray(json?.results) ? json.results : [];
  if (results.length === 0) return "검색 결과가 없습니다.";

  const shown = typeof limit === "number" ? results.slice(0, limit) : results;
  const lines = shown.map((page, i) => {
    const edited = page?.last_edited_time ? ` · 수정 ${page.last_edited_time.slice(0, 10)}` : "";
    return `${i + 1}. ${pageTitle(page)}\n   id: ${page?.id ?? "(id 없음)"}${edited}`;
  });

  if (json?.has_more) {
    lines.push(`\n(더 있음 — query를 좁히거나 limit을 올리세요)`);
  }
  return lines.join("\n");
}

/** 리치텍스트 배열 → 평문. */
function richText(arr) {
  if (!Array.isArray(arr)) return "";
  return arr.map((t) => t?.plain_text ?? "").join("");
}

/**
 * 블록 목록 → 평문. 지원하지 않는 블록 타입은 조용히 건너뛰지 않고
 * `[타입]` 으로 표시한다 — 조용히 빠지면 "내용이 없는 것"과 구별되지 않는다.
 */
function blocksToText(json, { maxChars = DEFAULT_MAX_CHARS } = {}) {
  const blocks = Array.isArray(json?.results) ? json.results : [];
  const out = [];

  for (const block of blocks) {
    const type = block?.type;
    const data = type ? block[type] : null;
    const text = richText(data?.rich_text);

    switch (type) {
      case "paragraph":
        out.push(text);
        break;
      case "heading_1":
        out.push(`# ${text}`);
        break;
      case "heading_2":
        out.push(`## ${text}`);
        break;
      case "heading_3":
        out.push(`### ${text}`);
        break;
      case "bulleted_list_item":
        out.push(`- ${text}`);
        break;
      case "numbered_list_item":
        out.push(`1. ${text}`);
        break;
      case "to_do":
        out.push(`- [${data?.checked ? "x" : " "}] ${text}`);
        break;
      case "quote":
        out.push(`> ${text}`);
        break;
      case "callout":
        out.push(`> ${text}`);
        break;
      case "code":
        out.push("```" + (data?.language ?? "") + "\n" + text + "\n```");
        break;
      case "divider":
        out.push("---");
        break;
      default:
        if (type) out.push(`[${type}]`);
    }
  }

  const joined = out.join("\n").trim();
  if (joined.length <= maxChars) return joined;
  return joined.slice(0, maxChars) + `\n\n…(${joined.length - maxChars}자 잘림 · max_chars를 올리면 더 볼 수 있습니다)`;
}

/**
 * 나가는 모든 텍스트에서 비밀을 가린다.
 *
 * 왜 한 곳에 모았나(2026-09-07 테스트가 잡은 결함): API 오류 메시지를 그대로 실어 나르면
 * 상대 서버가 되비춘 토큰이 그대로 응답에 실린다. 유출 경로마다 막으면 반드시 하나를 빠뜨리므로
 * `callTool`이 내보내는 **출구 한 곳**에서 가린다. `.claude/context/sensitive-info.md`.
 *
 * 한계: 완전한 비식별화가 아니다. 우리가 아는 토큰과 알려진 접두사 패턴만 가린다.
 */
function redact(text, token) {
  let out = typeof text === "string" ? text : String(text);
  if (token) out = out.split(token).join("***");
  return out.replace(/\b(ntn_|secret_|sk-|ghp_|AKIA)[A-Za-z0-9_-]{8,}/g, "$1***");
}

/** 응답이 실패일 때 Notion이 주는 message만 뽑는다. 토큰이 실릴 수 있는 헤더는 절대 싣지 않는다. */
function formatApiError(status, json) {
  const message = json?.message || json?.code || "알 수 없는 오류";
  return `Notion API 오류 (HTTP ${status}): ${message}`;
}

/**
 * 툴 호출 한 건을 처리한다.
 *
 * 왜 던지지 않고 텍스트를 돌려주는가: MCP 툴이 예외로 죽으면 모델은
 * "서버가 고장났다"만 알고 원인을 모른다. 사람이 읽을 수 있는 안내를 돌려주는 편이
 * 훨씬 빨리 고쳐진다. `.claude/context/explanation-style.md`("한계와 실패를 먼저 말한다")와 같은 방향.
 */
async function callTool(name, args = {}, { fetchImpl, token, maxChars } = {}) {
  // 이 함수의 모든 반환은 여기를 지난다 — 비밀을 가리는 단 하나의 출구다.
  const text = (t) => ({ content: [{ type: "text", text: redact(t, token) }] });

  if (!token) {
    return text(
      "NOTION_TOKEN이 설정되지 않았습니다.\n" +
        "notion.so/my-integrations 에서 internal integration 토큰을 만든 뒤\n" +
        "환경변수 NOTION_TOKEN 에 넣거나 .claude/.notion-token 파일에 저장하세요.\n" +
        "(대상 페이지를 그 integration에 'Connections'로 연결해야 검색에 잡힙니다)"
    );
  }

  const doFetch = fetchImpl || globalThis.fetch;
  const limit = clampLimit(args.limit);
  const cap = Math.max(Number(args.max_chars) || maxChars || DEFAULT_MAX_CHARS, 200);

  try {
    if (name === "notion_search") {
      const req = buildSearchRequest({ query: args.query, limit, token });
      const res = await doFetch(req.url, { method: req.method, headers: req.headers, body: req.body });
      const json = await res.json();
      if (!res.ok) return text(formatApiError(res.status, json));
      return text(formatSearchResults(json, { limit }));
    }

    if (name === "notion_get_page") {
      const pageId = normalizePageId(args.page_id);
      if (!pageId) return text(`페이지 ID를 해석하지 못했습니다: ${String(args.page_id)}`);

      const pageReq = buildPageRequest(pageId, { token });
      const pageRes = await doFetch(pageReq.url, { method: pageReq.method, headers: pageReq.headers });
      const pageJson = await pageRes.json();
      if (!pageRes.ok) return text(formatApiError(pageRes.status, pageJson));

      const blockReq = buildBlocksRequest(pageId, { token });
      const blockRes = await doFetch(blockReq.url, { method: blockReq.method, headers: blockReq.headers });
      const blockJson = await blockRes.json();
      if (!blockRes.ok) return text(formatApiError(blockRes.status, blockJson));

      const body = blocksToText(blockJson, { maxChars: cap });
      return text(`# ${pageTitle(pageJson)}\n(id: ${pageId})\n\n${body || "(본문 없음)"}`);
    }

    return text(`알 수 없는 툴: ${name}`);
  } catch (err) {
    // err.message에 URL은 들어갈 수 있어도 Authorization 헤더는 들어가지 않는다.
    return text(`요청 실패: ${err?.message ?? String(err)}`);
  }
}

module.exports = {
  API_BASE,
  NOTION_VERSION,
  DEFAULT_MAX_CHARS,
  DEFAULT_SEARCH_LIMIT,
  toolDefinitions,
  normalizePageId,
  clampLimit,
  redact,
  buildSearchRequest,
  buildPageRequest,
  buildBlocksRequest,
  pageTitle,
  formatSearchResults,
  blocksToText,
  formatApiError,
  callTool,
};
