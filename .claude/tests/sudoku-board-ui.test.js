/**
 * "수도쿠 게임 만들기" UI(sudoku-board)의 인수 테스트.
 *
 * ATDD 05단계 산출물 — 04단계에서 사람이 승인한 AC-1~12에 1:1로 대응한다.
 * 테스트 이름의 `AC-<번호>` 접두사는 실패 원장 추적용이므로 임의로 바꾸지 않는다.
 *
 * 이 UI는 브라우저 클릭/키보드 이벤트를 실제로 일으킬 수단이 없으므로(jsdom
 * 미도입, claude-in-chrome은 06단계 시각 비교 전용), "게임 화면"과 "셀 선택 후
 * 입력"은 아래 계약을 통해 정직하게 검증 가능한 형태로 옮겼다:
 *
 *   .claude/lib/ui/sudoku-board/board.js (06단계에서 만들 예정, 아직 없음)
 *     - createInitialState()              → { game, lastError: null }
 *     - applyInput(state, row, col, value) → 값 입력을 시도한 새 state
 *     - applyClear(state, row, col)        → 지우기를 시도한 새 state
 *     - renderBoard(state)                 → 그 시점 화면의 HTML 문자열
 *   .claude/lib/ui/sudoku-board/style.css  → 격자 스타일(AC-8 검증 대상)
 *
 * "게임 화면을 연다"는 renderBoard(createInitialState())의 결과를, "셀을
 * 선택해 값을 입력한다"는 applyInput(state, row, col, value)의 결과를 검사하는
 * 것으로 옮겨 테스트한다. .claude/lib/sudoku.js(createGame/setCell/clearCell/
 * isComplete)는 이미 검증된 로직이므로 재구현하지 않고 board.js가 그대로
 * require해서 감싸 쓸 것으로 기대한다.
 *
 * 실행: node --test .claude/tests/
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const { findElements, getText, hasClass, getCssPropertyForSelector } = require("../lib/dom-lite.js");
const {
  createInitialState,
  applyInput,
  applyClear,
  renderBoard,
} = require("../lib/ui/sudoku-board/board.js");

const STYLE_PATH = path.join(__dirname, "../lib/ui/sudoku-board/style.css");

/**
 * 결정적인(무작위 아닌) 테스트용 게임 상태를 만든다.
 * - 유효한 완성 스도쿠 정답 패턴(표준 shift 패턴, 행/열/박스 모두 1~9 유일)을 기반으로,
 * - 0행만 힌트(고정)로 채워 넣고 나머지 72칸은 빈 칸으로 둔다.
 */
const SOLVED_GRID = [
  [1, 2, 3, 4, 5, 6, 7, 8, 9],
  [4, 5, 6, 7, 8, 9, 1, 2, 3],
  [7, 8, 9, 1, 2, 3, 4, 5, 6],
  [2, 3, 4, 5, 6, 7, 8, 9, 1],
  [5, 6, 7, 8, 9, 1, 2, 3, 4],
  [8, 9, 1, 2, 3, 4, 5, 6, 7],
  [3, 4, 5, 6, 7, 8, 9, 1, 2],
  [6, 7, 8, 9, 1, 2, 3, 4, 5],
  [9, 1, 2, 3, 4, 5, 6, 7, 8],
];

function buildInitialState() {
  const board = SOLVED_GRID.map((row) => row.map(() => 0));
  board[0] = [...SOLVED_GRID[0]];
  const fixed = SOLVED_GRID.map((_, r) => SOLVED_GRID[r].map(() => r === 0));
  const solution = SOLVED_GRID.map((row) => [...row]);
  return { game: { board, fixed, solution }, lastError: null };
}

function buildCompleteState() {
  const board = SOLVED_GRID.map((row) => [...row]);
  const fixed = SOLVED_GRID.map((row) => row.map(() => true));
  const solution = SOLVED_GRID.map((row) => [...row]);
  return { game: { board, fixed, solution }, lastError: null };
}

test("AC-1: 게임 화면을 열면 9x9=81개의 셀이 표시되어야 한다", () => {
  const html = renderBoard(createInitialState());
  const cells = findElements(html, "div", { class: "cell" });
  assert.equal(cells.length, 81);
});

test("AC-2: 힌트로 채워진 셀과 빈 셀이 서로 구별되어야 한다", () => {
  const state = buildInitialState();
  const html = renderBoard(state);

  assert.equal(hasClass(html, "div", "fixed", { "data-row": "0", "data-col": "0" }), true, "힌트 셀은 fixed 스타일이어야 한다");
  assert.equal(hasClass(html, "div", "fixed", { "data-row": "1", "data-col": "0" }), false, "빈 셀은 fixed 스타일이면 안 된다");
});

test("AC-3: 빈 셀에 1~9 사이 값을 입력하면 그 셀에 값이 표시되어야 한다", () => {
  const state = buildInitialState();
  const next = applyInput(state, 1, 0, 5);

  assert.equal(next.game.board[1][0], 5);
  const html = renderBoard(next);
  assert.equal(getText(html, "div", { "data-row": "1", "data-col": "0" }), "5");
});

test("AC-4: 힌트로 고정된 셀에 값을 입력하려고 하면 값이 변경되지 않아야 한다", () => {
  const state = buildInitialState();
  const next = applyInput(state, 0, 0, 9);

  assert.equal(next.game.board[0][0], 1, "고정 셀의 원래 값(1)이 유지되어야 한다");
  const html = renderBoard(next);
  assert.equal(getText(html, "div", { "data-row": "0", "data-col": "0" }), "1");
});

test("AC-5: 같은 행·열·박스에 이미 있는 값을 입력하면 거부되고 사용자에게 알려야 한다", () => {
  const state = buildInitialState();
  // (0,1)=2가 이미 힌트로 있음 → 같은 열(1)에 2를 입력하면 충돌.
  const next = applyInput(state, 1, 1, 2);

  assert.equal(next.game.board[1][1], 0, "충돌하는 입력은 반영되지 않아야 한다");
  assert.ok(next.lastError, "거부 사유가 상태에 남아야 한다");

  const html = renderBoard(next);
  const errorEls = findElements(html, "div", { class: "cell-error" });
  assert.equal(errorEls.length, 1, "사용자에게 알리는 요소가 화면에 있어야 한다");
});

test("AC-6: 사용자가 입력한(고정 아닌) 셀을 지우면 빈 칸으로 돌아가야 한다", () => {
  const state = buildInitialState();
  const filled = applyInput(state, 1, 0, 5);
  const cleared = applyClear(filled, 1, 0);

  assert.equal(cleared.game.board[1][0], 0);
  const html = renderBoard(cleared);
  assert.equal(getText(html, "div", { "data-row": "1", "data-col": "0" }), "");
});

test("AC-7: 81칸이 모두 규칙을 만족하며 채워지면 화면에 완료 상태가 표시되어야 한다", () => {
  const html = renderBoard(buildCompleteState());
  const banners = findElements(html, "div", { class: "complete-banner" });
  assert.equal(banners.length, 1);
});

test("AC-8: [UI] 격자는 3x3 박스로 나뉘고, 박스 경계선이 칸 경계선보다 굵어야 한다", () => {
  const css = fs.readFileSync(STYLE_PATH, "utf-8");
  const cellBorder = getCssPropertyForSelector(css, ".cell", "border-width");
  const boxBorder = getCssPropertyForSelector(css, ".box-right", "border-right-width");

  assert.ok(cellBorder, ".cell border-width가 정의되어 있어야 한다");
  assert.ok(boxBorder, ".box-right border-right-width가 정의되어 있어야 한다");

  const cellPx = parseFloat(cellBorder);
  const boxPx = parseFloat(boxBorder);
  assert.ok(boxPx > cellPx, `박스 경계(${boxPx}px)가 칸 경계(${cellPx}px)보다 굵어야 한다`);
});

test('AC-9: [UI] 화면 상단에 "Svær" 텍스트가 노출되어야 한다', () => {
  const html = renderBoard(buildInitialState());
  assert.equal(getText(html, "h1", { class: "difficulty" }), "Svær");
});

test("AC-10: 1~9 범위를 벗어난 값을 입력하면 거부되고 셀 값은 바뀌지 않아야 한다", () => {
  const state = buildInitialState();

  for (const invalid of [0, -1, 10, "a"]) {
    const next = applyInput(state, 1, 0, invalid);
    assert.equal(next.game.board[1][0], 0, `${invalid} 입력은 거부되어야 한다`);
  }
});

test("AC-11: 이미 값이 채워진 비고정 셀에 지우지 않고 다른 값을 입력하면 덮어써져야 한다", () => {
  const state = buildInitialState();
  const filled = applyInput(state, 1, 0, 5);
  const overwritten = applyInput(filled, 1, 0, 7);

  assert.equal(overwritten.game.board[1][0], 7);
});

test("AC-12: 힌트로 고정된 셀을 지우려고 하면 값이 지워지지 않아야 한다", () => {
  const state = buildInitialState();
  const next = applyClear(state, 0, 0);

  assert.equal(next.game.board[0][0], 1, "고정 셀은 지워지지 않아야 한다");
});
