/**
 * 스도쿠 게임 로직의 인수 테스트.
 *
 * ATDD 05단계 산출물 — 04단계에서 사람이 승인한 AC-1~12에 1:1로 대응한다.
 * 테스트 이름의 `AC-<번호>` 접두사는 실패 원장에서 어떤 인수기준이 깨졌는지
 * 바로 추적하기 위한 것이므로 임의로 바꾸지 않는다.
 *
 * 실행: node --test .claude/tests/
 */
const test = require("node:test");
const assert = require("node:assert/strict");

const {
  createGame,
  isValidSudoku,
  countSolutions,
  setCell,
  clearCell,
  isComplete,
} = require("../lib/sudoku.js");

/** board[row][col] 자리에 놓을 수 없는(이미 같은 행·열·3x3 박스에 있는) 값의 집합. */
function usedValues(board, row, col) {
  const used = new Set();
  for (let i = 0; i < 9; i++) {
    if (board[row][i]) used.add(board[row][i]);
    if (board[i][col]) used.add(board[i][col]);
  }
  const boxRow = Math.floor(row / 3) * 3;
  const boxCol = Math.floor(col / 3) * 3;
  for (let r = boxRow; r < boxRow + 3; r++) {
    for (let c = boxCol; c < boxCol + 3; c++) {
      if (board[r][c]) used.add(board[r][c]);
    }
  }
  return used;
}

/** 고정되지 않은(빈) 셀 좌표를 하나 찾는다. */
function findEmptyCell(game) {
  for (let r = 0; r < 9; r++) {
    for (let c = 0; c < 9; c++) {
      if (!game.fixed[r][c]) return { r, c };
    }
  }
  throw new Error("빈 셀을 찾지 못했습니다");
}

/** 고정된(힌트) 셀 좌표를 하나 찾는다. */
function findFixedCell(game) {
  for (let r = 0; r < 9; r++) {
    for (let c = 0; c < 9; c++) {
      if (game.fixed[r][c]) return { r, c };
    }
  }
  throw new Error("고정 셀을 찾지 못했습니다");
}

test("AC-1: 새 게임 보드는 9x9이고 각 셀은 0(빈칸) 또는 1~9여야 한다", () => {
  const game = createGame();
  assert.strictEqual(game.board.length, 9);
  for (const row of game.board) {
    assert.strictEqual(row.length, 9);
    for (const cell of row) {
      assert.ok(
        cell === 0 || (Number.isInteger(cell) && cell >= 1 && cell <= 9),
        `유효하지 않은 셀 값: ${cell}`
      );
    }
  }
});

test("AC-2: 생성된 보드의 완성 정답은 스도쿠 규칙(행/열/3x3 박스)을 만족해야 한다", () => {
  const game = createGame();
  for (const row of game.solution) {
    for (const cell of row) {
      assert.ok(cell >= 1 && cell <= 9, `완성 정답에 빈 칸이 있음: ${cell}`);
    }
  }
  assert.strictEqual(isValidSudoku(game.solution), true);
});

test("AC-3: 초기 보드는 일부는 힌트로 고정된 셀이고 나머지는 빈 셀이어야 한다", () => {
  const game = createGame();
  let fixedCount = 0;
  let emptyCount = 0;
  for (let r = 0; r < 9; r++) {
    for (let c = 0; c < 9; c++) {
      if (game.fixed[r][c]) {
        fixedCount++;
        assert.strictEqual(game.board[r][c], game.solution[r][c]);
      } else {
        emptyCount++;
        assert.strictEqual(game.board[r][c], 0);
      }
    }
  }
  assert.ok(fixedCount > 0, "고정된 힌트 셀이 하나도 없음");
  assert.ok(emptyCount > 0, "빈 셀이 하나도 없음");
});

test("AC-4: 초기 퍼즐 상태(힌트만 채워진 상태)는 해가 정확히 하나여야 한다", () => {
  const game = createGame();
  assert.strictEqual(countSolutions(game.board), 1);
});

test("AC-5: 힌트로 고정된 셀은 값 입력도 지우기도 거부되어야 한다", () => {
  const game = createGame();
  const { r, c } = findFixedCell(game);
  const original = game.board[r][c];

  const afterSet = setCell(game, r, c, original === 9 ? 1 : original + 1);
  assert.strictEqual(afterSet.board[r][c], original);

  const afterClear = clearCell(game, r, c);
  assert.strictEqual(afterClear.board[r][c], original);
});

test("AC-6: 빈 셀에 유효한 값을 입력하면 채워져야 한다", () => {
  const game = createGame();
  const { r, c } = findEmptyCell(game);
  const validValue = game.solution[r][c];

  const updated = setCell(game, r, c, validValue);
  assert.strictEqual(updated.board[r][c], validValue);
});

test("AC-7: 이미 값이 채워진 비고정 셀에 다른 유효한 값을 입력하면 덮어써져야 한다", () => {
  const game = createGame();
  let target = null;
  outer: for (let r = 0; r < 9; r++) {
    for (let c = 0; c < 9; c++) {
      if (game.fixed[r][c]) continue;
      const used = usedValues(game.board, r, c);
      const candidates = [];
      for (let v = 1; v <= 9; v++) if (!used.has(v)) candidates.push(v);
      if (candidates.length >= 2) {
        target = { r, c, candidates };
        break outer;
      }
    }
  }
  assert.ok(
    target,
    "덮어쓰기를 검증할, 유효 후보가 2개 이상인 빈 셀을 찾지 못했습니다"
  );

  const [first, second] = target.candidates;
  const afterFirst = setCell(game, target.r, target.c, first);
  assert.strictEqual(afterFirst.board[target.r][target.c], first);

  const afterSecond = setCell(afterFirst, target.r, target.c, second);
  assert.strictEqual(afterSecond.board[target.r][target.c], second);
});

test("AC-8: 같은 행·열·3x3 박스에 이미 존재하는 값을 입력하면 거부되어야 한다", () => {
  const game = createGame();
  let target = null;
  outer: for (let r = 0; r < 9; r++) {
    for (let c = 0; c < 9; c++) {
      if (game.fixed[r][c]) continue;
      const used = usedValues(game.board, r, c);
      if (used.size > 0) {
        target = { r, c, value: [...used][0] };
        break outer;
      }
    }
  }
  assert.ok(target, "중복 값 거부를 검증할 셀을 찾지 못했습니다");

  const before = game.board[target.r][target.c];
  const after = setCell(game, target.r, target.c, target.value);
  assert.strictEqual(after.board[target.r][target.c], before);
});

test("AC-9: 1~9 범위를 벗어난 값을 입력하면 거부되어야 한다", () => {
  const game = createGame();
  const { r, c } = findEmptyCell(game);

  for (const invalid of [0, 10, -1, "a", 3.5]) {
    const after = setCell(game, r, c, invalid);
    assert.strictEqual(after.board[r][c], 0, `값 ${invalid} 입력이 거부되지 않음`);
  }
});

test("AC-10: 사용자가 입력한 비고정 셀 값을 지우면 빈 칸으로 돌아가야 한다", () => {
  const game = createGame();
  const { r, c } = findEmptyCell(game);

  const filled = setCell(game, r, c, game.solution[r][c]);
  assert.notStrictEqual(filled.board[r][c], 0);

  const cleared = clearCell(filled, r, c);
  assert.strictEqual(cleared.board[r][c], 0);
});

test("AC-11: 81칸이 모두 채워지고 규칙을 만족하면 완료 상태여야 한다", () => {
  const game = createGame();
  const solvedGame = { ...game, board: game.solution.map((row) => [...row]) };
  assert.strictEqual(isComplete(solvedGame), true);
});

test("AC-12: 빈 셀이 남아 있으면 규칙 위반이 없어도 완료 상태가 아니어야 한다", () => {
  const game = createGame();
  assert.strictEqual(isComplete(game), false);
});
