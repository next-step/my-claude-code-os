/**
 * "수도쿠 게임 만들기" UI 상태·렌더링.
 *
 * ATDD 06단계 산출물 — .claude/tests/sudoku-board-ui.test.js 의 AC-1~12를
 * 통과시키기 위한 구현이다. .claude/lib/sudoku.js(이미 검증된 순수 로직)를
 * 재구현하지 않고 그대로 감싸 쓴다.
 */
(function () {
  const SudokuLogic =
    typeof module !== "undefined" && module.exports ? require("../../sudoku.js") : window.SudokuLogic;

  const SIZE = 9;

  function createInitialState() {
    return { game: SudokuLogic.createGame(), lastError: null };
  }

  /** setCell은 거부 시 조용히 값을 유지하므로, 값이 실제로 바뀌었는지로 성공 여부를 판단한다. */
  function applyInput(state, row, col, value) {
    const next = SudokuLogic.setCell(state.game, row, col, value);
    const changed = next.board[row][col] === value;
    return { game: next, lastError: changed ? null : "입력이 거부되었습니다" };
  }

  function applyClear(state, row, col) {
    const next = SudokuLogic.clearCell(state.game, row, col);
    const changed = next.board[row][col] === 0;
    return { game: next, lastError: changed ? null : "지울 수 없는 셀입니다" };
  }

  function cellClasses(state, row, col) {
    const classes = ["cell"];
    if (state.game.fixed[row][col]) classes.push("fixed");
    if (col % 3 === 2 && col !== SIZE - 1) classes.push("box-right");
    if (row % 3 === 2 && row !== SIZE - 1) classes.push("box-bottom");
    return classes.join(" ");
  }

  function renderBoard(state) {
    let cellsHtml = "";
    for (let r = 0; r < SIZE; r++) {
      for (let c = 0; c < SIZE; c++) {
        const value = state.game.board[r][c];
        const text = value === 0 ? "" : String(value);
        cellsHtml += `<div class="${cellClasses(state, r, c)}" data-row="${r}" data-col="${c}">${text}</div>`;
      }
    }

    const errorHtml = state.lastError ? `<div class="cell-error" role="alert">${state.lastError}</div>` : "";
    const completeHtml = SudokuLogic.isComplete(state.game) ? `<div class="complete-banner">완료</div>` : "";

    return `<h1 class="difficulty">Svær</h1><div class="board">${cellsHtml}</div>${errorHtml}${completeHtml}`;
  }

  const SudokuBoard = { createInitialState, applyInput, applyClear, renderBoard };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = SudokuBoard;
  }
  if (typeof window !== "undefined") {
    window.SudokuBoard = SudokuBoard;
  }
})();
