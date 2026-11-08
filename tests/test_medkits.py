"""Botiquines: círculo blanco con cruz roja que recupera un corazón."""

import json

import pytest

from orbes import settings as S
from orbes.levels import LEVELS, index_of, parse_level
from orbes.world import World

DT = 1 / 60


def step(world, n, actions=()):
    for _ in range(n):
        world.update(DT, set(actions))


def _world_with_medkit(lives, level=5, difficulty="normal"):
    w = World(index_of(level), lives=lives, seed=1, difficulty=difficulty)
    for e in w.enemies:
        e.alive = False
    assert w.medkits
    return w, w.medkits[0]


def _touch(w, m):
    w.player.place(m.rect.x, m.rect.y)
    step(w, 1)


def test_medkits_only_from_level_five():
    for lv in LEVELS:
        count = sum(row.count("H") for row in lv.rows)
        if lv.number >= 5:
            assert count >= 1, lv.number
        else:
            assert count == 0, lv.number


def test_more_medkits_in_bigger_levels():
    counts = [sum(r.count("H") for r in LEVELS[index_of(n)].rows) for n in range(5, 21)]
    assert counts == sorted(counts) and counts[-1] > counts[0]


def test_medkit_recovers_one_heart():
    w, m = _world_with_medkit(lives=1)
    _touch(w, m)
    assert w.lives == 2 and m not in w.medkits


def test_medkit_recovers_one_heart_from_half():
    w, m = _world_with_medkit(lives=1.5)
    _touch(w, m)
    assert w.lives == 2.5


def test_medkit_never_exceeds_max():
    w, m = _world_with_medkit(lives=2.5)            # máximo en medio: 3
    _touch(w, m)
    assert w.lives == 3 and m not in w.medkits


def test_medkit_stays_when_health_is_full():
    w, m = _world_with_medkit(lives=3)
    _touch(w, m)
    assert w.lives == 3 and m in w.medkits          # no se gasta: queda para luego
    w.lives = 2
    step(w, 1)
    assert w.lives == 3 and m not in w.medkits      # al estar herido, ya sí


def test_medkit_max_depends_on_difficulty():
    w, m = _world_with_medkit(lives=4, difficulty="easy")
    _touch(w, m)
    assert w.lives == 5


def test_medkit_parsed_from_map():
    rows = ["         "] * 14 + ["   H     ", "    P    "]
    data = parse_level(rows)
    assert data.medkits == [S.cell_pos(3, 14)]


def test_taken_medkits_stay_taken_after_save():
    from orbes import savegame
    w = World(index_of(20), lives=1, seed=1)
    total = len(w.medkits)
    assert total >= 2
    taken = w.medkits[0]
    _touch(w, taken)
    data = json.loads(json.dumps(savegame.snapshot(w)))
    r = savegame.restore(data)
    assert len(r.medkits) == total - 1
    assert taken.cell not in [m.cell for m in r.medkits]


def test_medkit_is_reachable_on_a_platform():
    """Cada botiquín está justo encima de una plataforma (se puede llegar a él)."""
    for n in range(5, 21):
        rows = LEVELS[index_of(n)].rows
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                if ch == "H":
                    assert rows[r + 1][c] == "=", (n, r, c)
