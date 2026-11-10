"""Niveles 5 a 20, generados proceduralmente."""

import pytest

from bubblequest import settings as S
from bubblequest.level_generator import (FIRST_GENERATED, LAST_GENERATED, LAYOUTS, PATH_COLS,
                                   SAFE_ROWS, LevelGenerator, layout_for, set_layout)
from bubblequest.levels import LEVELS, index_of
from bubblequest.world import World

DT = 1 / 60
GENERATED = range(FIRST_GENERATED, LAST_GENERATED + 1)


def step(world, n, actions=()):
    for _ in range(n):
        world.update(DT, set(actions))


def _counts(rows):
    enemies = sum(r.count("E") + r.count("A") for r in rows)
    return len(rows), enemies, sum(r.count("A") for r in rows), sum(r.count("L") for r in rows)


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


def _settle(w):
    for _ in range(180):
        step(w, 1)
        if w.player.on_ground:
            return


def _climb(w, rows):
    """Sube plataforma a plataforma desde donde esté hasta la estrella (arriba)."""
    p = w.player
    _settle(w)
    start_row = (p.rect.bottom - S.BORDER) // S.TILE
    on_floor = p.rect.bottom == w.floor_y
    current = set(range(9)) if on_floor else _platform_cols(rows, start_row)
    plat_rows = sorted((r for r, row in enumerate(rows) if "=" in row and r < start_row),
                       reverse=True)
    for r in plat_rows:
        target = _platform_cols(rows, r)
        here = (p.rect.centerx - S.BORDER) // S.TILE

        def clear(c):                             # sin sólidos en el camino ni encima
            return all(rows[rr][c] not in "L#" for rr in range(r - 1, min(r + 3, len(rows))))

        shared = sorted((c for c in current & target if clear(c)), key=lambda c: abs(c - here))
        assert shared, (r, "no hay paso hacia la plataforma")
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
        _settle(w)
        assert p.rect.bottom == S.cell_pos(0, r)[1], (r, p.rect)
        current = target
    for _ in range(10):                           # bajo la estrella y salto doble
        if w.state == "won":
            break
        _walk_to(w, w.star.rect.centerx)
        _double_jump(w)
        step(w, 40)


def _descend(w):
    """Baja hasta el suelo: atraviesa las plataformas finas con la flecha abajo, se aparta
    de ladrillos/bloques si está encima de uno, y en el suelo va hasta la estrella."""
    p = w.player
    for _ in range(400):
        if w.state == "won":
            return
        _settle(w)
        if p.rect.bottom == w.floor_y:            # en el suelo: a por la estrella
            _walk_to(w, w.star.rect.centerx)
            step(w, 5)
            continue
        if p.on_oneway(w.solids, w.oneway):
            step(w, 1)
            step(w, 1, {"down"})
            continue
        # Encima de un ladrillo o bloque: caminar hasta caer de él (hasta que baje de altura;
        # on_ground parpadea fotograma a fotograma y no sirve para esto)
        d = {"left"} if p.rect.centerx > S.FIELD_W // 2 else {"right"}
        bottom = p.rect.bottom
        for _ in range(90):
            step(w, 1, d)
            if p.rect.bottom > bottom:
                break
        else:
            d = {"right"} if "left" in d else {"left"}   # bloqueado: probar al otro lado
            for _ in range(180):
                step(w, 1, d)
                if p.rect.bottom > bottom:
                    break


@pytest.mark.parametrize("number", list(GENERATED))
def test_generated_level_can_be_completed(number):
    """Con la física real, subiendo o bajando según la disposición del nivel. Funciona
    también con niveles retocados a mano."""
    w = World(index_of(number), seed=1)
    for e in w.enemies:
        e.alive = False
    w.player.invuln = 999
    rows = LEVELS[index_of(number)].rows
    star_row = next(r for r, row in enumerate(rows) if "S" in row)
    if star_row == 0:
        _climb(w, rows)
    else:
        _descend(w)
    assert w.state == "won", number


@pytest.mark.parametrize("number", list(GENERATED))
def test_start_and_star_follow_the_layout_rules(number):
    rows = LEVELS[index_of(number)].rows
    p_row = next(r for r, row in enumerate(rows) if "P" in row)
    s_row = next(r for r, row in enumerate(rows) if "S" in row)
    layout = layout_for(number)
    n = len(rows)
    if layout == "up":
        assert p_row == n - 1 and s_row == 0
    elif layout == "down":                        # empieza arriba: estrella abajo del todo
        assert p_row == 0 and s_row == n - 1
    else:                                         # a mitad: estrella arriba o abajo
        assert n // 4 < p_row < 3 * n // 4
        assert s_row == (0 if layout == "middle_up" else n - 1)
    # Nadie le ataca nada más empezar
    for r, row in enumerate(rows):
        if "E" in row or "A" in row:
            assert abs(r - p_row) > SAFE_ROWS, (number, r)


def test_every_layout_is_used():
    assert {layout_for(n) for n in GENERATED} == set(LAYOUTS)
    assert all(layout_for(n) == "up" for n in range(1, FIRST_GENERATED))


def test_set_layout_rejects_unknown_and_keeps_rest():
    rows = LevelGenerator().generated_map(5)
    with pytest.raises(ValueError):
        set_layout(rows, "sideways", 5)
    down = set_layout(rows, "down", 5)
    for ra, rb in zip(rows, down):
        for a, b in zip(ra, rb):
            if a != b:
                assert {a, b} <= set(" PSEA")
