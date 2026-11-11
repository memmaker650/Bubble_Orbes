"""Zonas invisibles de enemigos en niveles altos, azules graduales desde el nivel 5 y
niveles 21-30 más grandes."""

import pytest

from bubblequest import settings as S
from bubblequest.level_generator import laser_count, level_rows
from bubblequest.levels import LEVELS, index_of
from bubblequest.world import World

DT = 1 / 60


def step(world, n, actions=()):
    for _ in range(n):
        world.update(DT, set(actions))


# --- tamaños ---

def test_levels_21_to_30_are_bigger_and_grow_faster_from_26():
    rows = {n: len(LEVELS[index_of(n)].rows) for n in range(20, 31)}
    assert all(rows[n] > rows[n - 1] for n in range(21, 31))
    assert rows[21] - rows[20] == 3 and rows[25] - rows[24] == 3      # 21-25: +3 por nivel
    assert rows[27] - rows[26] == 6 and rows[30] - rows[29] == 6      # 26-30: +6 por nivel
    assert rows[30] == level_rows(30) == 112


def test_enemy_density_of_new_levels_like_level_20():
    def density(n):
        lv = LEVELS[index_of(n)]
        return sum(row.count(c) for row in lv.rows for c in "EAN") / len(lv.rows)
    for n in range(21, 31):
        assert density(n) <= density(20) + 0.02, n


# --- azules (ojos rojos) graduales ---

def test_no_lasers_before_level_five_then_one_more_each_level():
    for lv in LEVELS:
        lasers = sum(row.count("A") for row in lv.rows)
        enemies = sum(row.count(c) for row in lv.rows for c in "EAN")
        if lv.tutorial:
            continue
        if lv.number < 5:
            assert lasers == 0, lv.number
        else:
            assert lasers == laser_count(enemies, lv.number) == min(lv.number - 4, enemies // 2)


def test_lasers_spread_through_the_level():
    rows = LEVELS[index_of(20)].rows
    laser_rows = [r for r, row in enumerate(rows) if "A" in row]
    assert min(laser_rows) < len(rows) // 3 and max(laser_rows) > 2 * len(rows) // 3


# --- zonas ---

def test_small_levels_have_no_zones():
    for n in (1, 2, 3):
        w = World(index_of(n), seed=1)
        assert w.zone_count == 1 and all(e.zone is None for e in w.enemies)


def test_tall_levels_are_split_in_zones_by_size():
    counts = [World(index_of(n), seed=1).zone_count for n in (4, 10, 20, 30)]
    assert counts == sorted(counts) and counts[0] >= 2 and counts[-1] == 112 // S.ZONE_ROWS


def test_every_enemy_starts_inside_its_zone_and_zones_cover_the_level():
    w = World(index_of(30), seed=1)
    bounds = [w.zone_bounds(i) for i in range(w.zone_count)]
    assert bounds[0][0] == S.BORDER and bounds[-1][1] == w.floor_y
    assert all(a[1] == b[0] for a, b in zip(bounds, bounds[1:]))     # contiguas
    for e in w.enemies:
        top, bottom = e.zone
        assert top <= e.rect.bottom + 8 <= bottom + 8


@pytest.mark.parametrize("number", [4, 14, 20, 30])
def test_enemies_never_leave_their_zone(number):
    w = World(index_of(number), seed=3)
    for _ in range(60 * 90):                      # minuto y medio sin el jugador estorbando
        w.player.invuln = 999
        step(w, 1)
    for e in w.enemies:
        if e.alive and e.state == "walk":
            top, bottom = e.zone
            assert top - 1 <= e.rect.bottom <= bottom + 1, (number, e.rect, e.zone)


def test_zones_prevent_crowding_on_level_14():
    """Sin zonas, a los 2 min se juntaban 18 enemigos en una pantalla; con zonas, como al
    empezar."""
    w = World(index_of(14), seed=0)

    def crowd():
        ys = sorted(e.rect.centery for e in w.enemies if e.alive)
        return max(sum(1 for z in ys[i:] if z - y < S.FIELD_H) for i, y in enumerate(ys))

    start = crowd()
    for _ in range(60 * 120):
        w.player.invuln = 999
        step(w, 1)
    assert crowd() <= start + 2


def test_enemy_turns_at_zone_edge_instead_of_falling():
    """En el borde de la última plataforma de su zona se da la vuelta (no cae a la de abajo,
    que es de otra zona); sin zona, sí cae."""
    from bubblequest.entities import TongueEnemy
    w = World(index_of(14), seed=1)
    lowest = max(p.top for p in w.oneway)               # plataforma más baja (suelo debajo)
    # Las plataformas son casillas de 40 px: se usa la casilla del extremo derecho de esa fila
    platform = max((p for p in w.oneway if p.top == lowest), key=lambda p: p.right)
    for zoned in (True, False):
        e = TongueEnemy(0, 0, 60, w.rng)
        e.place(platform.right - 30, platform.top - e.rect.height)
        e.direction, e.jump_cd, e.cooldown = 1, 99, 99
        e.zone = (platform.top - 200, platform.top + 1) if zoned else None   # acaba en sus pies
        w.enemies = [e]
        turns, lowest = 0, e.rect.bottom
        for _ in range(240):
            w.player.invuln = 999
            d = e.direction
            step(w, 1)
            turns += e.direction != d
            lowest = max(lowest, e.rect.bottom)
        if zoned:
            assert lowest == platform.top                  # nunca bajó de su plataforma...
            assert turns >= 1                              # ...porque se dio la vuelta
        else:
            assert lowest > platform.top                   # sin zona, se cae
