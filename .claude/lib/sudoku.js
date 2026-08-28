/**
 * 스도쿠 게임 로직.
 *
 * ATDD 06단계 산출물 — .claude/tests/sudoku.test.js 의 AC-1~12를 통과시키기 위한 구현이다.
 */

const BOX_SIZE = 3;
const SIZE = 9;

function shuffledDigits() {
  const digits = [1, 2, 3, 4, 5, 6, 7, 8, 9];
  for (let i = digits.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [digits[i], digits[j]] = [digits[j], digits[i]];
  }
  return digits;
}

function findEmptyCell(grid) {
  for (let r = 0; r < SIZE; r++) {
    for (let c = 0; c < SIZE; c++) {
      if (grid[r][c] === 0) return [r, c];
    }
  }
  return null;
}

function canPlaceOnGrid(grid, row, col, value) {
  for (let i = 0; i < SIZE; i++) {
    if (grid[row][i] === value) return false;
    if (grid[i][col] === value) return false;
  }
  const boxRow = Math.floor(row / BOX_SIZE) * BOX_SIZE;
  const boxCol = Math.floor(col / BOX_SIZE) * BOX_SIZE;
  for (let r = boxRow; r < boxRow + BOX_SIZE; r++) {
    for (let c = boxCol; c < boxCol + BOX_SIZE; c++) {
      if (grid[r][c] === value) return false;
    }
  }
  return true;
}

/** 완전히 채워진 유효한 스도쿠 정답 하나를 무작위로 생성한다. */
function generateSolvedGrid() {
  const grid = Array.from({ length: SIZE }, () => Array(SIZE).fill(0));

  function fill() {
    const empty = findEmptyCell(grid);
    if (!empty) return true;
    const [r, c] = empty;
    for (const value of shuffledDigits()) {
      if (canPlaceOnGrid(grid, r, c, value)) {
        grid[r][c] = value;
        if (fill()) return true;
        grid[r][c] = 0;
      }
    }
    return false;
  }

  fill();
  return grid;
}

/**
 * board(0=미정, 1~9=확정)를 스도쿠 규칙으로 풀었을 때 가능한 해의 개수를 센다.
 * limit에 도달하면 더 탐색하지 않고 멈춘다(유일해 여부 확인 목적이면 2로 충분).
 */
function countSolutions(board, limit = 2) {
  const grid = board.map((row) => [...row]);
  let count = 0;

  function backtrack() {
    if (count >= limit) return;
    const empty = findEmptyCell(grid);
    if (!empty) {
      count++;
      return;
    }
    const [r, c] = empty;
    for (let value = 1; value <= 9; value++) {
      if (canPlaceOnGrid(grid, r, c, value)) {
        grid[r][c] = value;
        backtrack();
        grid[r][c] = 0;
        if (count >= limit) return;
      }
    }
  }

  backtrack();
  return count;
}

/**
 * 완성된 정답에서 셀을 하나씩 무작위로 비워가며, 비운 뒤에도 해가 유일하게 유지되는 경우에만
 * 실제로 비운다. 최대 maxRemovals개까지 시도한다.
 */
function carvePuzzle(solution, maxRemovals) {
  const puzzle = solution.map((row) => [...row]);
  const fixed = Array.from({ length: SIZE }, () => Array(SIZE).fill(true));

  const cells = [];
  for (let r = 0; r < SIZE; r++) {
    for (let c = 0; c < SIZE; c++) cells.push([r, c]);
  }
  for (let i = cells.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [cells[i], cells[j]] = [cells[j], cells[i]];
  }

  let removed = 0;
  for (const [r, c] of cells) {
    if (removed >= maxRemovals) break;
    const backup = puzzle[r][c];
    puzzle[r][c] = 0;
    if (countSolutions(puzzle) === 1) {
      fixed[r][c] = false;
      removed++;
    } else {
      puzzle[r][c] = backup;
    }
  }

  return { puzzle, fixed };
}

function createGame() {
  const solution = generateSolvedGrid();
  const { puzzle, fixed } = carvePuzzle(solution, 45);
  return { board: puzzle, fixed, solution };
}

function isValidGroup(values) {
  if (values.length !== SIZE) return false;
  const seen = new Set();
  for (const value of values) {
    if (!Number.isInteger(value) || value < 1 || value > SIZE) return false;
    if (seen.has(value)) return false;
    seen.add(value);
  }
  return true;
}

function getRow(grid, r) {
  return grid[r];
}

function getCol(grid, c) {
  return grid.map((row) => row[c]);
}

function getBox(grid, boxIndex) {
  const boxRow = Math.floor(boxIndex / BOX_SIZE) * BOX_SIZE;
  const boxCol = (boxIndex % BOX_SIZE) * BOX_SIZE;
  const values = [];
  for (let r = boxRow; r < boxRow + BOX_SIZE; r++) {
    for (let c = boxCol; c < boxCol + BOX_SIZE; c++) {
      values.push(grid[r][c]);
    }
  }
  return values;
}

/** grid(9x9)가 스도쿠 규칙(모든 행·열·3x3 박스에 1~9가 정확히 한 번씩)을 만족하는지 검사한다. */
function isValidSudoku(grid) {
  for (let i = 0; i < SIZE; i++) {
    if (!isValidGroup(getRow(grid, i))) return false;
    if (!isValidGroup(getCol(grid, i))) return false;
    if (!isValidGroup(getBox(grid, i))) return false;
  }
  return true;
}

function isInRange(value) {
  return Number.isInteger(value) && value >= 1 && value <= 9;
}

/** (row, col) 자신을 제외한 같은 행·열·3x3 박스에 value가 이미 있는지 확인한다. */
function hasConflict(board, row, col, value) {
  for (let i = 0; i < SIZE; i++) {
    if (i !== col && board[row][i] === value) return true;
    if (i !== row && board[i][col] === value) return true;
  }
  const boxRow = Math.floor(row / BOX_SIZE) * BOX_SIZE;
  const boxCol = Math.floor(col / BOX_SIZE) * BOX_SIZE;
  for (let r = boxRow; r < boxRow + BOX_SIZE; r++) {
    for (let c = boxCol; c < boxCol + BOX_SIZE; c++) {
      if ((r !== row || c !== col) && board[r][c] === value) return true;
    }
  }
  return false;
}

function cloneGame(game) {
  return {
    board: game.board.map((row) => [...row]),
    fixed: game.fixed.map((row) => [...row]),
    solution: game.solution.map((row) => [...row]),
  };
}

/** 고정 셀이거나 범위를 벗어나거나 규칙을 위반하면 거부(변경 없음), 아니면 값을 채우거나 덮어쓴다. */
function setCell(game, row, col, value) {
  const next = cloneGame(game);
  if (game.fixed[row][col]) return next;
  if (!isInRange(value)) return next;
  if (hasConflict(game.board, row, col, value)) return next;
  next.board[row][col] = value;
  return next;
}

/** 고정 셀이면 거부(변경 없음), 아니면 빈 칸으로 되돌린다. */
function clearCell(game, row, col) {
  const next = cloneGame(game);
  if (game.fixed[row][col]) return next;
  next.board[row][col] = 0;
  return next;
}

/** 빈 칸이 하나도 없고 스도쿠 규칙을 만족하면 완료 상태다. */
function isComplete(game) {
  for (const row of game.board) {
    if (row.some((value) => value === 0)) return false;
  }
  return isValidSudoku(game.board);
}

const SudokuLogic = {
  createGame,
  isValidSudoku,
  countSolutions,
  setCell,
  clearCell,
  isComplete,
};

if (typeof module !== "undefined" && module.exports) {
  module.exports = SudokuLogic;
}
if (typeof window !== "undefined") {
  window.SudokuLogic = SudokuLogic;
}
