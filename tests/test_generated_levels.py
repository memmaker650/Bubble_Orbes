"""Niveles 5 a 20, generados proceduralmente."""

import pytest

from orbes import settings as S
from orbes.level_generator import FIRST_GENERATED, LAST_GENERATED, PATH_COLS, LevelGenerator
from orbes.levels import LEVELS, index_of
from orbes.world import World

DT = 1 / 60
GENERATED = range(FIRST_GENERATED, LAST_GENERATED + 1)


def step(world, n, actions=()):
    for _ in range(n):
        world.update(DT, set(actions))


def _counts(rows):
    enemies = sum(r.count("E") + r.count("B") for r in rows)
    return len(rows), enemies, sum(r.count("B") for r in rows), sum(r.count("L") for r in rows)


def test_generator_is_deterministic_and_matches_json():
    gen = LevelGenerator()
    for n in GENERATED:
        assert gen.generated_map(n) == gen.generated_map(n)
        assert LEVELS[index_of(n)].rows == gen.generated_map(n)


def test_size_and_enemies_grow_with_level():
    stats = [_counts(LEVELS[index_of(n)].rows) for n in GENERATED]
    heights = [s[0] for s in stats]
    enemies = [s[1] for s in stats]
    assert heights == sorted(heights) and heights[0] > 16 and heights[-1] >= 60
    assert enemies[-1] > enemies[0] * 2
    assert sum(s[2] for s in stats[-4:]) > sum(s[2] for s in stats[:4])   # más láseres al final


def test_brick_amount_varies_between_levels():
    bricks = [_counts(LEVELS[index_of(n)].rows)[3] for n in GENERATED]
    assert min(bricks) >= 1 and max(bricks) > 2 * min(bricks)


def test_path_columns_never_blocked_by_bricks():
    for n in GENERATED:
        for row in LEVELS[index_of(n)].rows:
            assert all(row[c] != "L" for c in PATH_COLS), (n, row)


def test_enemy_speed_is_capped():
    fast = World(index_of(20), seed=1).enemies[0].speed
    assert fast == World(index_of(7), seed=1).enemies[0].speed
    assert fast * S.DIFFICULTIES["hard"]["enemy_speed"] < S.PLAYER_SPEED


@pytest.mark.parametrize("number", list(GENERATED))
def test_generated_level_can_be_climbed_to_the_star(number):
    """Con la física real: doble salto por la columna 2 hasta arriba y tocar la estrella."""
    w = World(index_of(number), seed=1)
    for e in w.enemies:
        e.alive = False
    p = w.player
    p.invuln = 999
    p.place(S.cell_pos(2, 0)[0] + 6, w.floor_y - p.rect.height)
    step(w, 10)
    rows = LEVELS[index_of(number)].rows
    top = min(r for r, row in enumerate(rows) if "=" in row)
    top_y = S.cell_pos(0, top)[1]
    for _ in range(len(rows)):
        if p.rect.bottom == top_y:
            break
        step(w, 1, {"jump"})
        step(w, 6)
        step(w, 1, {"jump"})
        for _ in range(120):
            step(w, 1)
            if p.on_ground:
                break
    assert p.rect.bottom == top_y, (number, p.rect)
    for _ in range(600):
        if w.state == "won":
            break
        dx = w.star.rect.centerx - p.rect.centerx
        if abs(dx) > 4:
            step(w, 1, {"right"} if dx > 0 else {"left"})
        elif p.on_ground:
            step(w, 1, {"jump"})
            step(w, 6)
            step(w, 1, {"jump"})
        else:
            step(w, 1)
    assert w.state == "won", number
