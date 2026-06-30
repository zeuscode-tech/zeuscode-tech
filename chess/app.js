const DATA_URLS = [
  "https://raw.githubusercontent.com/zeuscode-tech/zeuscode-tech/main/chess/position.json",
  "position.json",
];
const PIECES = {
  P: "♙", N: "♘", B: "♗", R: "♖", Q: "♕", K: "♔",
  p: "♟", n: "♞", b: "♝", r: "♜", q: "♛", k: "♚",
};
const FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];
const RANKS = ["8", "7", "6", "5", "4", "3", "2", "1"];

const boardElement = document.querySelector("#board");
const hintElement = document.querySelector("#hint");
const statusElement = document.querySelector("#game-status");
const numberElement = document.querySelector("#game-number");
const newGameButton = document.querySelector("#new-game");
const promotionDialog = document.querySelector("#promotion-dialog");
const promotionOptions = document.querySelector("#promotion-options");

let position;
let selectedSquare = null;

function issueUrl(title) {
  const params = new URLSearchParams({
    title,
    body: "Ход выбран на интерактивной доске. Нажмите «Create new issue» — workflow проверит и применит его.",
  });
  return `https://github.com/${position.repository}/issues/new?${params.toString()}`;
}

function submitMove(move) {
  window.location.assign(issueUrl(`chess|move|${move.uci}|${position.revision}`));
}

function choosePromotion(moves) {
  promotionOptions.replaceChildren();
  const labels = { q: "♛", r: "♜", b: "♝", n: "♞" };
  for (const move of moves) {
    const promotion = move.uci.at(-1);
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = labels[promotion] ?? promotion.toUpperCase();
    button.setAttribute("aria-label", `Превратить пешку: ${move.san}`);
    button.addEventListener("click", () => {
      promotionDialog.close();
      submitMove(move);
    });
    promotionOptions.append(button);
  }
  promotionDialog.showModal();
}

function movesFrom(square) {
  return position.legalMoves.filter((move) => move.from === square);
}

function selectSquare(square) {
  const sourceMoves = movesFrom(square);
  if (selectedSquare) {
    const candidateMoves = movesFrom(selectedSquare).filter((move) => move.to === square);
    if (candidateMoves.length === 1) {
      submitMove(candidateMoves[0]);
      return;
    }
    if (candidateMoves.length > 1) {
      choosePromotion(candidateMoves);
      return;
    }
  }

  selectedSquare = sourceMoves.length > 0 && selectedSquare !== square ? square : null;
  renderBoard();
  hintElement.textContent = selectedSquare
    ? `Выбрана клетка ${selectedSquare.toUpperCase()}. Теперь нажми на подсвеченную клетку.`
    : "Выбери фигуру с голубой рамкой.";
}

function renderBoard() {
  boardElement.replaceChildren();
  const movableSquares = new Set(position.legalMoves.map((move) => move.from));
  const targets = new Set(selectedSquare ? movesFrom(selectedSquare).map((move) => move.to) : []);
  const lastSquares = new Set(position.lastMove ? [position.lastMove.slice(0, 2), position.lastMove.slice(2, 4)] : []);

  RANKS.forEach((rank, rankIndex) => {
    FILES.forEach((file, fileIndex) => {
      const square = `${file}${rank}`;
      const piece = position.pieces[square];
      const button = document.createElement("button");
      button.type = "button";
      button.className = `square ${(rankIndex + fileIndex) % 2 === 0 ? "light" : "dark"}`;
      button.setAttribute("role", "gridcell");
      button.setAttribute("aria-label", `${square.toUpperCase()}${piece ? `, ${PIECES[piece]}` : ""}`);
      if (lastSquares.has(square)) button.classList.add("last");
      if (movableSquares.has(square) && !selectedSquare) button.classList.add("movable");
      if (selectedSquare === square) button.classList.add("selected");
      if (targets.has(square)) button.classList.add("target");
      if (targets.has(square) && piece) button.classList.add("has-piece");
      if (piece) {
        const glyph = document.createElement("span");
        glyph.textContent = PIECES[piece];
        button.append(glyph);
      }
      button.addEventListener("click", () => selectSquare(square));
      boardElement.append(button);
    });
  });
}

async function loadPosition() {
  try {
    let lastError;
    for (const dataUrl of DATA_URLS) {
      try {
        const response = await fetch(`${dataUrl}?t=${Date.now()}`, { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        position = await response.json();
        break;
      } catch (error) {
        lastError = error;
      }
    }
    if (!position) throw lastError;
    statusElement.textContent = position.status;
    numberElement.textContent = `Партия #${position.gameId} · ходов ${position.revision}`;
    newGameButton.hidden = !position.gameOver;
    hintElement.textContent = position.gameOver
      ? "Партия завершена — можно начать новую."
      : "Выбери фигуру с голубой рамкой.";
    renderBoard();
  } catch (error) {
    statusElement.textContent = "Не удалось загрузить позицию";
    hintElement.textContent = "Обнови страницу через несколько секунд.";
    console.error(error);
  }
}

newGameButton.addEventListener("click", () => {
  window.location.assign(issueUrl(`chess|new||${position.revision}`));
});

loadPosition();
