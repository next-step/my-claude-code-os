/**
 * 경량 HTML/CSS 구조 검증 유틸 (jsdom 대체).
 *
 * 완전한 HTML/CSS 파서가 아니다. AI가 생성하는 단순한 UI 구조(중첩이 깊지
 * 않고 문법이 유효한 HTML)를 정규식/문자열 스캔으로 검증하기 위한 최소
 * 기능만 제공한다. 잘못된 HTML(태그 미종료 등)에 대한 내성은 없다.
 */

const VOID_TAGS = new Set([
  "area", "base", "br", "col", "embed", "hr", "img",
  "input", "link", "meta", "source", "track", "wbr",
]);

function parseAttrs(attrString) {
  const attrs = {};
  const re = /([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*(?:=\s*("([^"]*)"|'([^']*)'|[^\s"'=<>`]+))?/g;
  let m;
  while ((m = re.exec(attrString)) !== null) {
    const name = m[1].toLowerCase();
    const value = m[3] !== undefined ? m[3] : m[4] !== undefined ? m[4] : m[2] !== undefined ? m[2] : "";
    attrs[name] = value;
  }
  return attrs;
}

function attrsMatch(attrs, filter) {
  for (const [key, expected] of Object.entries(filter || {})) {
    const actual = attrs[key];
    if (actual === undefined) return false;
    if (key === "class") {
      const tokens = actual.split(/\s+/).filter(Boolean);
      if (!tokens.includes(expected)) return false;
    } else if (actual !== expected) {
      return false;
    }
  }
  return true;
}

function stripTags(html) {
  return html.replace(/<[^>]*>/g, "");
}

/**
 * html 문자열에서 tag(대소문자 무시)를 찾아 attrsPartial과 일치하는
 * 요소들을 { tag, attrs, textContent, innerHTML } 배열로 돌려준다.
 */
function findElements(html, tag, attrsPartial = {}) {
  const lowerTag = tag.toLowerCase();
  const results = [];
  const isVoid = VOID_TAGS.has(lowerTag);

  const openRe = new RegExp(`<${lowerTag}((?:\\s+[^<>]*)?)\\s*(/?)>`, "gi");
  let m;
  while ((m = openRe.exec(html)) !== null) {
    const attrString = m[1] || "";
    const selfClosed = m[2] === "/";
    const attrs = parseAttrs(attrString);
    if (!attrsMatch(attrs, attrsPartial)) continue;

    if (isVoid || selfClosed) {
      results.push({ tag: lowerTag, attrs, textContent: "", innerHTML: "" });
      continue;
    }

    // 여는 태그 뒤부터, 같은 태그의 열림/닫힘 깊이를 세어 대응하는 닫는 태그를 찾는다.
    const afterOpenIndex = openRe.lastIndex;
    const pairRe = new RegExp(`<(/?)${lowerTag}(?:\\s[^<>]*)?>`, "gi");
    pairRe.lastIndex = afterOpenIndex;
    let depth = 1;
    let closeIndex = -1;
    let pm;
    while ((pm = pairRe.exec(html)) !== null) {
      if (pm[1] === "/") {
        depth -= 1;
        if (depth === 0) {
          closeIndex = pm.index;
          break;
        }
      } else {
        depth += 1;
      }
    }

    const innerHTML = closeIndex === -1 ? "" : html.slice(afterOpenIndex, closeIndex);
    results.push({
      tag: lowerTag,
      attrs,
      textContent: stripTags(innerHTML).trim(),
      innerHTML,
    });
  }

  return results;
}

/** findElements의 첫 매칭 요소의 textContent를 돌려준다. 매칭이 없으면 undefined. */
function getText(html, tag, attrsPartial = {}) {
  const found = findElements(html, tag, attrsPartial);
  return found.length === 0 ? undefined : found[0].textContent;
}

/** tag(+attrsPartial)로 찾은 요소 중 하나라도 class에 className을 포함하면 true. */
function hasClass(html, tag, className, attrsPartial = {}) {
  const found = findElements(html, tag, attrsPartial);
  return found.some((el) => {
    const classAttr = el.attrs.class || "";
    return classAttr.split(/\s+/).filter(Boolean).includes(className);
  });
}

/**
 * 중첩 없는 단순 CSS 텍스트에서 `selector { ... }` 블록을 찾아 property 값을 돌려준다.
 * 선택자나 속성이 없으면 undefined.
 */
function getCssPropertyForSelector(cssText, selector, property) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const blockRe = new RegExp(`${escaped}\\s*\\{([^}]*)\\}`);
  const blockMatch = cssText.match(blockRe);
  if (!blockMatch) return undefined;
  return getInlineStyleProperty(blockMatch[1], property);
}

/** "color: red; padding: 8px 16px;" 형태의 문자열에서 property 값을 돌려준다. */
function getInlineStyleProperty(styleText, property) {
  const escaped = property.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`(?:^|;)\\s*${escaped}\\s*:\\s*([^;]+?)\\s*(?:;|$)`, "i");
  const match = styleText.match(re);
  return match ? match[1].trim() : undefined;
}

module.exports = {
  findElements,
  getText,
  hasClass,
  getCssPropertyForSelector,
  getInlineStyleProperty,
};
