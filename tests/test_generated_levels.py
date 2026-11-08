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


def test_generator_is_deterministic():
    # Los JSON se pueden retocar a mano (p. ej. el nivel 10), así que no se exige que
    # coincidan con el generador; sí que el generador dé siempre el mismo mapa.
    gen = LevelGenerator()
    for n in GENERATED:
        assert gen.generated_map(n) == gen.generated_map(n)


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


def _platform_cols(rows, r):
    return {c for c, ch in enumerate(rows[r]) if ch == "="}


def _double_jump(w):
    step(w, 1, {"jump"})
    step(w, 6)
    step(w, 1, {"jump"})


def _walk_to(w, x, limit=240):
    p = w.player
    for _ in range(limit):
        dx = x - p.rect.centerx
        if abs(dx) <= 3:
            return
        step(w, 1, {"right"} if dx > 0 else {"left"})


@pytest.mark.parametrize("number", list(GENERATED))
def test_generated_level_can_be_climbed_to_the_star(number):
    """Con la física real, plataforma a plataforma: en cada una busca una columna que
    comparta con la siguiente (3 filas más arriba), se coloca debajo y hace el salto doble.
    Funciona también con niveles retocados a mano."""
    w = World(index_of(number), seed=1)
    for e in w.enemies:
        e.alive = False
    p = w.player
    p.invuln = 999
    rows = LEVELS[index_of(number)].rows
    plat_rows = sorted((r for r, row in enumerate(rows) if "=" in row), reverse=True)
    step(w, 10)
    current = set(range(9))                       # en el suelo: cualquier columna
    for r in plat_rows:
        target = _platform_cols(rows, r)
        here = (p.rect.centerx - S.BORDER) // S.TILE

        def clear(c):                             # sin sólidos en el camino ni encima
            return all(rows[rr][c] not in "L#" for rr in range(r - 1, min(r + 3, len(rows))))

        shared = sorted((c for c in current & target if clear(c)), key=lambda c: abs(c - here))
        assert shared, (number, r, "no hay paso hacia la plataforma")
        col = shared[0]
        if current != set(range(9)):              # sobre una plataforma: ¿hay hueco en medio?
            lo, hi = sorted((here, col))
            if any(c not in current for c in range(lo, hi + 1)):
                d = {"right"} if col > here else {"left"}
                step(w, 1, {"jump"} | d)          # saltito para cruzar el hueco
                for _ in range(60):
                    step(w, 1, d)
                    if p.on_ground:
                        break
        _walk_to(w, S.cell_pos(col, 0)[0] + S.TILE // 2)
        _double_jump(w)
        for _ in range(120):
            step(w, 1)
            if p.on_ground:
                break
        assert p.rect.bottom == S.cell_pos(0, r)[1], (number, r, p.rect)
        current = target
    # En la plataforma de arriba: bajo la estrella y salto doble
    for _ in range(10):
        if w.state == "won":
            break
        _walk_to(w, w.star.rect.centerx)
        _double_jump(w)
        step(w, 40)
    assert w.state == "won", number
