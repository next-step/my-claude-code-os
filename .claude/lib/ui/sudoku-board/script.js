(function () {
  let state = window.SudokuBoard.createInitialState();
  let selected = null;

  function render() {
    document.getElementById("app").innerHTML = window.SudokuBoard.renderBoard(state);
    document.querySelectorAll(".cell").forEach((cell) => {
      cell.addEventListener("click", () => {
        selected = {
          row: Number(cell.getAttribute("data-row")),
          col: Number(cell.getAttribute("data-col")),
        };
      });
    });
  }

  document.addEventListener("keydown", (e) => {
    if (!selected) return;
    if (e.key >= "1" && e.key <= "9") {
      state = window.SudokuBoard.applyInput(state, selected.row, selected.col, Number(e.key));
      render();
    } else if (e.key === "Backspace" || e.key === "Delete") {
      state = window.SudokuBoard.applyClear(state, selected.row, selected.col);
      render();
    }
  });

  render();
})();
