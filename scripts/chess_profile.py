#!/usr/bin/env python3
"""Maintain an issue-driven chess game in a GitHub profile README."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import chess
import chess.svg


ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
CHESS_DIR = ROOT / "chess"
STATE_PATH = CHESS_DIR / "state.json"
BOARD_PATH = CHESS_DIR / "board.svg"
START_MARKER = "<!-- CHESS:START -->"
END_MARKER = "<!-- CHESS:END -->"
COMMAND_PATTERN = re.compile(r"^chess\|(move|new)\|([^|]*)\|(\d+)$", re.IGNORECASE)
POSITION_PATH = CHESS_DIR / "position.json"


class ChessCommandError(ValueError):
    """Raised when an issue contains an invalid or stale chess command."""


@dataclass(frozen=True)
class CommandResult:
    changed: bool
    message: str


def initial_state(game_id: int = 1) -> dict:
    return {
        "version": 1,
        "game_id": game_id,
        "fen": chess.STARTING_FEN,
        "moves": [],
    }


def load_state() -> dict:
    if not STATE_PATH.exists():
        return initial_state()
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    chess.Board(state["fen"])
    return state


def save_state(state: dict) -> None:
    CHESS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_command(title: str) -> tuple[str, str, int]:
    match = COMMAND_PATTERN.fullmatch(title.strip())
    if not match:
        raise ChessCommandError(
            "Команда не распознана. Используйте одну из ссылок под актуальной доской."
        )
    action, move, revision = match.groups()
    return action.lower(), move.lower(), int(revision)


def apply_command(state: dict, title: str, actor: str, owner: str) -> CommandResult:
    action, move_text, expected_revision = parse_command(title)
    current_revision = len(state["moves"])
    board = chess.Board(state["fen"])

    if expected_revision != current_revision:
        raise ChessCommandError(
            "Эта ссылка устарела: другой игрок уже сделал ход. Откройте профиль и выберите новый вариант."
        )

    if action == "new":
        if actor.casefold() != owner.casefold() and not board.is_game_over():
            raise ChessCommandError(
                "Начать новую партию может владелец профиля или любой игрок после завершения текущей."
            )
        game_id = int(state.get("game_id", 1)) + 1
        state.clear()
        state.update(initial_state(game_id))
        return CommandResult(True, f"Новая партия #{game_id} начата. Ход белых.")

    if board.is_game_over():
        raise ChessCommandError("Партия уже завершена. Начните новую игру по ссылке под доской.")

    try:
        move = chess.Move.from_uci(move_text)
    except ValueError as error:
        raise ChessCommandError("Некорректная запись хода.") from error

    if move not in board.legal_moves:
        raise ChessCommandError(
            "Этот ход нелегален или уже устарел. Выберите ход под актуальной доской."
        )

    san = board.san(move)
    board.push(move)
    state["fen"] = board.fen()
    state["moves"].append({"uci": move.uci(), "san": san, "actor": actor})

    if board.is_checkmate():
        winner = "белые" if board.turn == chess.BLACK else "черные"
        message = f"Ход {san} принят. Мат — победили {winner}!"
    elif board.is_game_over():
        message = f"Ход {san} принят. Партия завершилась вничью."
    elif board.is_check():
        message = f"Ход {san} принят. Шах!"
    else:
        side = "белых" if board.turn == chess.WHITE else "черных"
        message = f"Ход {san} принят. Теперь ход {side}."
    return CommandResult(True, message)


def issue_url(repository: str, title: str) -> str:
    body = "Ход подготовлен автоматически. Нажмите «Create new issue» — workflow проверит и применит его."
    return (
        f"https://github.com/{repository}/issues/new"
        f"?title={quote(title, safe='')}&body={quote(body, safe='')}"
    )


def game_status(board: chess.Board) -> str:
    if board.is_checkmate():
        winner = "Белые" if board.turn == chess.BLACK else "Черные"
        return f"🏆 Мат. {winner} победили."
    if board.is_stalemate():
        return "🤝 Пат. Партия завершилась вничью."
    if board.is_insufficient_material():
        return "🤝 Ничья: недостаточно материала."
    if board.is_game_over():
        return "🤝 Партия завершилась вничью."
    side = "белых" if board.turn == chess.WHITE else "черных"
    suffix = " — шах!" if board.is_check() else ""
    return f"Ход {side}{suffix}"


def position_payload(state: dict, repository: str) -> dict:
    board = chess.Board(state["fen"])
    legal_moves = [
        {
            "from": chess.square_name(move.from_square),
            "to": chess.square_name(move.to_square),
            "uci": move.uci(),
            "san": board.san(move),
        }
        for move in sorted(board.legal_moves, key=lambda item: item.uci())
    ]
    return {
        "version": 1,
        "repository": repository,
        "gameId": state["game_id"],
        "revision": len(state["moves"]),
        "fen": state["fen"],
        "turn": "white" if board.turn == chess.WHITE else "black",
        "status": game_status(board),
        "gameOver": board.is_game_over(),
        "lastMove": state["moves"][-1]["uci"] if state["moves"] else None,
        "pieces": {
            chess.square_name(square): piece.symbol()
            for square, piece in board.piece_map().items()
        },
        "legalMoves": legal_moves,
    }


def history_table(state: dict) -> str:
    moves = state["moves"][-6:]
    if not moves:
        return "_Партия только началась._"
    rows = ["| # | Ход | Игрок |", "|--:|:--:|:--|"]
    offset = len(state["moves"]) - len(moves)
    for index, move in enumerate(moves, start=offset + 1):
        actor = move["actor"]
        rows.append(f"| {index} | `{move['san']}` | [@{actor}](https://github.com/{actor}) |")
    return "\n".join(rows)


def render(state: dict, repository: str) -> None:
    board = chess.Board(state["fen"])
    last_move = None
    if state["moves"]:
        last_move = chess.Move.from_uci(state["moves"][-1]["uci"])

    CHESS_DIR.mkdir(parents=True, exist_ok=True)
    svg = chess.svg.board(
        board=board,
        lastmove=last_move,
        size=520,
        coordinates=True,
        colors={
            "square light": "#dbeafe",
            "square dark": "#2563eb",
            "square light lastmove": "#fde68a",
            "square dark lastmove": "#f59e0b",
        },
    )
    BOARD_PATH.write_text(svg, encoding="utf-8")
    POSITION_PATH.write_text(
        json.dumps(position_payload(state, repository), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    revision = len(state["moves"])
    board_url = (
        f"https://raw.githubusercontent.com/{repository}/main/chess/board.svg?move={revision}"
    )
    lines = [
        START_MARKER,
        '<p align="center">',
        '  <a href="https://zeuscode-tech.github.io/zeuscode-tech/chess/">',
        f'    <img width="520" src="{board_url}" alt="Текущая шахматная позиция" />',
        "  </a>",
        "</p>",
        "",
        f'<p align="center"><strong>{game_status(board)}</strong> · Партия #{state["game_id"]} · Ходов: {revision}</p>',
        "",
        '<p align="center"><a href="https://zeuscode-tech.github.io/zeuscode-tech/chess/"><strong>Нажмите на доску и сделайте ход →</strong></a></p>',
        "",
        "_В интерактивной доске: первый клик выбирает фигуру, второй — клетку назначения._",
        "",
    ]
    lines.extend(["", "<details>", "<summary>Последние ходы</summary>", "", history_table(state), "", "</details>", END_MARKER])
    block = "\n".join(lines)

    readme = README_PATH.read_text(encoding="utf-8")
    if START_MARKER not in readme or END_MARKER not in readme:
        raise RuntimeError("Chess markers are missing from README.md")
    prefix, remainder = readme.split(START_MARKER, 1)
    _, suffix = remainder.split(END_MARKER, 1)
    README_PATH.write_text(prefix + block + suffix, encoding="utf-8")


def write_github_output(result: CommandResult) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as output:
        output.write(f"changed={'true' if result.changed else 'false'}\n")
        output.write("message<<CHESS_MESSAGE\n")
        output.write(result.message + "\n")
        output.write("CHESS_MESSAGE\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("init", "play", "render"))
    parser.add_argument("--title", default="")
    parser.add_argument("--actor", default="")
    parser.add_argument("--repository", default="zeuscode-tech/zeuscode-tech")
    parser.add_argument("--owner", default="zeuscode-tech")
    args = parser.parse_args()

    state = load_state()
    if args.action == "init":
        save_state(state)
        render(state, args.repository)
        return 0
    if args.action == "render":
        render(state, args.repository)
        return 0

    try:
        result = apply_command(state, args.title, args.actor, args.owner)
    except ChessCommandError as error:
        result = CommandResult(False, f"❌ {error}")
        write_github_output(result)
        return 0

    save_state(state)
    render(state, args.repository)
    write_github_output(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
