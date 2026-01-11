from __future__ import annotations

from typing import Dict

from src.libraries.fishgame.fishgame import FishGame


fish_games: Dict[int, FishGame] = {}


def ensure_game(group_id: int | str) -> FishGame:
    """Return the cached FishGame instance for the group, creating it if needed."""
    gid = int(group_id)
    game = fish_games.get(gid)
    if game is None:
        game = FishGame(gid)
        fish_games[gid] = game
    return game
