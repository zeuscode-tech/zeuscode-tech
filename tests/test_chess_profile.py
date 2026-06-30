import copy
import importlib.util
import sys
import unittest
from pathlib import Path

import chess


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "chess_profile.py"
SPEC = importlib.util.spec_from_file_location("chess_profile", SCRIPT_PATH)
chess_profile = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = chess_profile
SPEC.loader.exec_module(chess_profile)


class ChessProfileTests(unittest.TestCase):
    def test_legal_move_updates_state(self):
        state = chess_profile.initial_state()

        result = chess_profile.apply_command(
            state, "chess|move|e2e4|0", "visitor", "zeuscode-tech"
        )

        self.assertTrue(result.changed)
        self.assertEqual(state["moves"][0]["uci"], "e2e4")
        self.assertEqual(chess.Board(state["fen"]).turn, chess.BLACK)

    def test_illegal_move_is_rejected_without_mutation(self):
        state = chess_profile.initial_state()
        original = copy.deepcopy(state)

        with self.assertRaises(chess_profile.ChessCommandError):
            chess_profile.apply_command(
                state, "chess|move|e2e5|0", "visitor", "zeuscode-tech"
            )

        self.assertEqual(state, original)

    def test_stale_link_is_rejected(self):
        state = chess_profile.initial_state()
        chess_profile.apply_command(
            state, "chess|move|e2e4|0", "visitor", "zeuscode-tech"
        )

        with self.assertRaisesRegex(chess_profile.ChessCommandError, "устарела"):
            chess_profile.apply_command(
                state, "chess|move|e7e5|0", "another", "zeuscode-tech"
            )

    def test_only_owner_can_reset_active_game(self):
        state = chess_profile.initial_state()

        with self.assertRaises(chess_profile.ChessCommandError):
            chess_profile.apply_command(
                state, "chess|new||0", "visitor", "zeuscode-tech"
            )

        result = chess_profile.apply_command(
            state, "chess|new||0", "zeuscode-tech", "zeuscode-tech"
        )
        self.assertTrue(result.changed)
        self.assertEqual(state["game_id"], 2)


if __name__ == "__main__":
    unittest.main()
