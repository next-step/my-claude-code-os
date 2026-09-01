/**
 * dom-lite.js(경량 HTML/CSS 구조 검증 유틸)의 인수 테스트.
 *
 * UI 요구사항을 다루기 위한 인프라 자체도 이 저장소의 ATDD 관례(먼저 실패 →
 * 최소 구현)를 그대로 따라 만든다. jsdom 대신 이 경량 파서를 쓰는 이유는
 * OS.md의 "제로 디펜던시" 철학을 지키기 위함이며, 완전한 HTML/CSS 파서가
 * 아니라 AI가 생성하는 단순한 UI 구조를 검증하는 데 필요한 최소 기능만 갖는다.
 *
 * 테스트 이름의 `AC-<번호>` 접두사는 실패 원장 추적용이므로 임의로 바꾸지 않는다.
 *
 * 실행: node --test .claude/tests/
 */
const test = require("node:test");
const assert = require("node:assert/strict");

const {
  findElements,
  getText,
  hasClass,
  getCssPropertyForSelector,
  getInlineStyleProperty,
} = require("../lib/dom-lite.js");

test("AC-1: findElements는 태그로 단일 요소를 찾고 textContent를 채워 돌려준다", () => {
  const html = "<h1>설정</h1>";
  const found = findElements(html, "h1");
  assert.equal(found.length, 1);
  assert.equal(found[0].tag, "h1");
  assert.equal(found[0].textContent, "설정");
});

test("AC-2: findElements는 속성값으로 요소를 필터링한다", () => {
  const html = '<button id="save-btn">저장</button><button id="cancel-btn">취소</button>';
  const found = findElements(html, "button", { id: "save-btn" });
  assert.equal(found.length, 1);
  assert.equal(found[0].textContent, "저장");
});

test("AC-3: findElements의 class 필터는 여러 클래스 중 하나만 일치해도 매칭한다", () => {
  const html = '<button class="btn primary large">저장</button>';
  const found = findElements(html, "button", { class: "primary" });
  assert.equal(found.length, 1);

  const notFound = findElements(html, "button", { class: "danger" });
  assert.equal(notFound.length, 0);
});

test("AC-4: findElements는 중첩된 동일 태그에서도 바깥 요소의 textContent를 안쪽 태그까지 포함해 올바르게 잘라낸다", () => {
  const html = "<div>바깥<div>안쪽</div>텍스트</div>";
  const found = findElements(html, "div", {});
  assert.equal(found.length, 2, "바깥 div, 안쪽 div 둘 다 찾아야 한다");

  const outer = found.find((el) => el.textContent.includes("바깥"));
  assert.ok(outer, "바깥 div를 찾아야 한다");
  assert.equal(outer.innerHTML, "바깥<div>안쪽</div>텍스트");
});

test("AC-5: getText는 매칭된 요소의 텍스트를 태그 없이 트림해서 돌려준다", () => {
  const html = '<h1 class="title">  설정 화면  </h1>';
  const text = getText(html, "h1", { class: "title" });
  assert.equal(text, "설정 화면");
});

test("AC-6: getText는 매칭되는 요소가 없으면 undefined를 돌려주고 예외를 던지지 않는다", () => {
  const html = "<h1>설정</h1>";
  assert.equal(getText(html, "h2"), undefined);
});

test("AC-7: hasClass는 여러 클래스 중 하나로 존재해도 true를 돌려준다", () => {
  const html = '<button class="btn primary">저장</button>';
  assert.equal(hasClass(html, "button", "primary"), true);
});

test("AC-8: hasClass는 클래스가 없으면 false를 돌려준다", () => {
  const html = '<button class="btn primary">저장</button>';
  assert.equal(hasClass(html, "button", "danger"), false);
});

test("AC-9: getCssPropertyForSelector는 CSS 텍스트에서 선택자에 대응하는 속성값을 추출한다", () => {
  const css = `
    .save-btn {
      background-color: #2563eb;
      color: #ffffff;
    }
  `;
  assert.equal(getCssPropertyForSelector(css, ".save-btn", "background-color"), "#2563eb");
  assert.equal(getCssPropertyForSelector(css, ".save-btn", "color"), "#ffffff");
});

test("AC-10: getCssPropertyForSelector는 선택자나 속성이 없으면 undefined를 돌려준다", () => {
  const css = ".save-btn { color: #ffffff; }";
  assert.equal(getCssPropertyForSelector(css, ".missing", "color"), undefined);
  assert.equal(getCssPropertyForSelector(css, ".save-btn", "font-size"), undefined);
});

test("AC-11: getInlineStyleProperty는 인라인 style 속성 문자열에서 값을 추출한다", () => {
  const style = "background-color: #2563eb; padding: 8px 16px;";
  assert.equal(getInlineStyleProperty(style, "background-color"), "#2563eb");
  assert.equal(getInlineStyleProperty(style, "padding"), "8px 16px");
  assert.equal(getInlineStyleProperty(style, "color"), undefined);
});

test("AC-12: findElements는 닫는 태그가 없는 void 요소도 처리한다", () => {
  const html = '<div><input type="text" id="name" /><img src="a.png"></div>';
  const inputs = findElements(html, "input", { id: "name" });
  assert.equal(inputs.length, 1);
  assert.equal(inputs[0].attrs.type, "text");

  const imgs = findElements(html, "img");
  assert.equal(imgs.length, 1);
  assert.equal(imgs[0].attrs.src, "a.png");
});
