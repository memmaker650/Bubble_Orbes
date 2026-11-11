"""Bombas: se encienden con una burbuja o con la acción encima, explotan a los 3 s y eliminan
a los enemigos a menos de BOMB_RADIUS en cualquier dirección."""

import json

import pytest

from bubblequest import settings as S
from bubblequest.entities import Bomb, Bubble
from bubblequest.levels import LEVELS, index_of, parse_level
from bubblequest.world import World

DT = 1 / 60
FLOOR_Y = S.FLOOR_Y - 32


def step(world, n, actions=()):
    for _ in range(n):
        world.update(DT, set(actions))


def _world_with_bomb(col=6):
    """Nivel 1 con una bomba en el suelo (fila 15, columna `col`) y sin daño al jugador."""
    w = World(1, seed=1)
    w.bombs = [Bomb(*S.cell_pos(col, 15))]
    w.player.invuln = 999
    return w, w.bombs[0]


# --- niveles ---

def test_bombs_only_from_level_ten_one_or_two_by_size():
    for lv in LEVELS:
        count = sum(row.count("B") for row in lv.rows)
        if lv.number < 10:
            assert count == 0, lv.number
        else:
            assert count == (1 if len(lv.rows) <= 45 else 2), lv.number


def test_bombs_sit_on_platforms_away_from_start_with_enemies_in_reach():
    reach2 = (S.BOMB_RADIUS / S.TILE) ** 2
    for n in range(10, 21):
        rows = LEVELS[index_of(n)].rows
        p_row = next(r for r, row in enumerate(rows) if "P" in row)
        enemies = [(r, c) for r, row in enumerate(rows) for c, ch in enumerate(row) if ch in "EAN"]
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                if ch == "B":
                    assert rows[r + 1][c] == "=", (n, r, c)
                    assert abs(r - p_row) > 6
                    assert any((er - r) ** 2 + (ec - c) ** 2 <= reach2 for er, ec in enemies)


def test_bomb_parsed_from_map():
    rows = ["         "] * 14 + ["   B     ", "    P    "]
    assert parse_level(rows).bombs == [S.cell_pos(3, 14)]


# --- encender ---

def test_bubble_hitting_bomb_lights_it():
    w, m = _world_with_bomb(col=4)
    p = w.player
    p.place(S.cell_pos(1, 15)[0] + 6, FLOOR_Y)
    p.facing = 1
    step(w, 2)
    step(w, 1, {"bubble"})
    for _ in range(30):
        step(w, 1)
        if m.lit:
            break
    assert m.lit and not w.bubbles                 # la burbuja se gasta al encenderla


def test_action_on_top_of_bomb_lights_it_instead_of_shooting():
    w, m = _world_with_bomb()
    w.player.place(m.rect.x, FLOOR_Y)
    step(w, 2)
    step(w, 1, {"bubble"})
    assert m.lit and not w.bubbles


def test_action_away_from_bomb_shoots_normally():
    w, m = _world_with_bomb(col=8)
    w.player.place(S.cell_pos(0, 15)[0] + 6, FLOOR_Y)
    w.player.facing = -1
    step(w, 2)
    step(w, 1, {"bubble"})
    assert not m.lit and w.bubbles


# --- explotar ---

def test_explodes_after_three_seconds():
    w, m = _world_with_bomb()
    m.light()
    step(w, int(S.BOMB_FUSE * 60) - 3)
    assert m in w.bombs and m.lit
    step(w, 5)
    assert m not in w.bombs and w.explosions
    step(w, int(S.EXPLOSION_TIME * 60) + 2)
    assert w.explosions                            # el fuego ya pasó, pero queda el humo
    step(w, int((S.SMOKE_TIME - S.EXPLOSION_TIME) * 60) + 2)
    assert not w.explosions                        # el humo se ha difuminado del todo


def test_explosion_kills_enemies_in_radius_in_any_direction():
    w, m = _world_with_bomb(col=4)
    cx, cy = m.rect.center
    near_side = w.enemies[0]
    near_up = w.enemies[1]
    far = w.enemies[2]
    near_side.rect.center = (cx + S.BOMB_RADIUS - 20, cy)       # al lado
    near_up.rect.center = (cx, cy - S.BOMB_RADIUS + 20)          # encima (en otra fila)
    far.rect.center = (cx, cy - S.BOMB_RADIUS - 40)              # fuera del radio
    score = w.score
    w.explode(m)
    assert not near_side.alive and not near_up.alive and far.alive
    assert w.score == score + 2 * S.POINTS_ENEMY
    assert len(w.ghosts) == 2 and len(w.popups) == 2


def test_explosion_also_kills_trapped_enemies_and_spares_player():
    w, m = _world_with_bomb(col=4)
    e = w.enemies[0]
    b = Bubble(*m.rect.center, 1)
    e.trap()
    b.captured = e
    b._to_float()
    w.bubbles = [b]
    lives = w.lives
    w.player.rect.center = m.rect.center                         # el jugador, encima
    w.explode(m)
    assert not e.alive and not w.bubbles
    assert w.lives == lives and w.state == "playing"             # al jugador no le hace daño


def test_chain_reaction_lights_nearby_bombs():
    w, m = _world_with_bomb(col=2)
    other = Bomb(*S.cell_pos(5, 15))
    far = Bomb(*S.cell_pos(4, 2))
    w.bombs += [other, far]
    w.explode(m)
    assert other.lit and not far.lit


def test_bomb_can_clear_the_level():
    w, m = _world_with_bomb(col=4)
    for e in w.enemies:
        e.place(m.rect.x, m.rect.y - 8)
    w.explode(m)
    assert w.enemies_left == 0


def test_bombs_survive_save_with_their_fuse():
    from bubblequest import savegame
    w = World(index_of(13), seed=1)
    assert len(w.bombs) == 2
    w.bombs[0].light()
    w.bombs[0].timer = 1.25
    w.explode(w.bombs[1])
    r = savegame.restore(json.loads(json.dumps(savegame.snapshot(w))))
    assert len(r.bombs) == 1
    assert r.bombs[0].lit and r.bombs[0].timer == pytest.approx(1.25)


def test_explosion_is_logged(caplog):
    import logging
    w, m = _world_with_bomb(col=4)
    cx, cy = m.rect.center
    w.enemies[0].rect.center = (cx + 40, cy)
    w.enemies[1].rect.center = (cx, cy - 300)                # fuera del radio
    other = Bomb(*S.cell_pos(6, 15))
    w.bombs.append(other)
    with caplog.at_level(logging.INFO, logger="bubblequest.world"):
        w.explode(m)
    msgs = [r.getMessage() for r in caplog.records if "Bomba explotada" in r.getMessage()]
    assert len(msgs) == 1
    msg = msgs[0]
    assert "nivel 1" in msg and "columna 4, fila 15" in msg
    assert "1 enemigos eliminados" in msg and "1 bombas encendidas en cadena" in msg
