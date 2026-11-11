"""Niveles más altos que la pantalla (scroll vertical) y ladrillos que sirven de parapeto."""

import pytest
from pygame import Rect

from bubblequest import settings as S
from bubblequest.entities import Bubble, LaserEnemy, TongueEnemy
from bubblequest.levels import LEVELS, index_of, parse_level
from bubblequest.world import World

DT = 1 / 60
TALL = index_of(4)


def step(world, n, actions=()):
    for _ in range(n):
        world.update(DT, set(actions))


def _empty_tall_world():
    w = World(TALL, seed=1)
    for e in w.enemies:
        e.alive = False
    w.player.invuln = 999
    return w


# --- scroll vertical ---

def test_tall_level_is_taller_than_screen():
    w = World(TALL, seed=1)
    assert len(LEVELS[TALL].rows) == 32
    assert w.scrolls and w.height == S.level_height(32) > S.FIELD_H
    assert w.floor_y == w.height - S.BORDER
    assert not World(1, seed=1).scrolls


def test_camera_starts_at_bottom_and_is_limited_to_level():
    w = _empty_tall_world()
    assert w.camera_y == w.height - S.FIELD_H         # empieza abajo, donde está el jugador
    w.player.place(S.cell_pos(4, 0)[0], S.BORDER)     # arriba del todo
    step(w, 120)
    assert w.camera_y == pytest.approx(0, abs=0.5)    # no sube más allá del techo
    w.player.place(S.cell_pos(4, 31)[0], w.floor_y - 32)
    step(w, 120)
    assert w.camera_y == pytest.approx(w.height - S.FIELD_H, abs=0.5)  # ni baja del suelo


def test_camera_follows_player_smoothly():
    w = _empty_tall_world()
    bottom = w.camera_y
    w.player.place(S.cell_pos(2, 15)[0], S.cell_pos(0, 15)[1])
    step(w, 1)
    assert bottom - 60 < w.camera_y < bottom          # se mueve poco a poco...
    step(w, 120)
    target = w.player.rect.centery - S.FIELD_H * S.CAMERA_ANCHOR
    assert w.camera_y == pytest.approx(target, abs=1)  # ...hasta centrarlo


def test_short_level_camera_never_moves():
    w = World(1, seed=1)
    for e in w.enemies:
        e.alive = False
    step(w, 1, {"jump"})
    step(w, 60)
    assert w.camera_y == 0


def test_tall_level_can_be_climbed_to_the_star():
    """Con la física real: saltando por la columna 2 se llega arriba y se toca la estrella."""
    w = _empty_tall_world()
    p = w.player
    p.place(S.cell_pos(2, 31)[0] + 6, w.floor_y - p.rect.height)
    step(w, 10)
    top_platform = S.cell_pos(0, 2)[1]
    for _ in range(20):                               # 10 plataformas: de sobra
        step(w, 1, {"jump"})                          # salto doble: pulsar...
        step(w, 6)
        step(w, 1, {"jump"})                          # ...y volver a pulsar en el aire
        for _ in range(120):
            step(w, 1)
            if p.on_ground:
                break
        if p.rect.bottom == top_platform:
            break
    assert p.rect.bottom == top_platform, p.rect      # en la plataforma más alta
    assert w.camera_y < 40                            # la cámara ha subido con él
    # Bajo la estrella hay un ladrillo: se sube a él saltando y desde ahí se toca la estrella
    for _ in range(600):                              # acotado: nunca se queda colgado
        if w.state == "won":
            break
        x = p.rect.x
        step(w, 1, {"right"} if p.rect.centerx < w.star.rect.centerx else {"left"})
        if p.rect.x == x and p.on_ground:             # bloqueado por el ladrillo: salta
            step(w, 1, {"jump", "right"})
            step(w, 6, {"right"})
            step(w, 1, {"jump", "right"})
        elif abs(p.rect.centerx - w.star.rect.centerx) < 6 and p.on_ground:
            step(w, 1, {"jump"})
    assert w.state == "won"


def test_ghost_disappears_above_the_camera_not_the_level_top():
    from bubblequest.entities import Ghost
    w = _empty_tall_world()
    e = w.enemies[-1]                                  # uno de abajo
    g = Ghost(e)
    w.ghosts.append(g)
    for _ in range(60 * 10):
        step(w, 1)
        if not w.ghosts:
            break
    assert not w.ghosts
    assert g.rect.bottom < w.camera_y - S.HUD_H        # ha salido por arriba de la pantalla
    assert g.rect.bottom > 0                           # ...aunque en el nivel aún queda altura


def test_save_and_restore_tall_level_keeps_camera_on_player():
    from bubblequest import savegame
    w = _empty_tall_world()
    w.player.place(S.cell_pos(2, 10)[0], S.cell_pos(0, 11)[1] - 32)
    step(w, 120)
    r = savegame.restore(savegame.snapshot(w))
    assert r.number == 4 and r.player.rect.topleft == w.player.rect.topleft
    assert r.camera_y == pytest.approx(w.camera_y, abs=1)


# --- ladrillos ---

ROWS16 = ["         "] * 15 + ["P        "]


def _brick_world(row, kind):
    """Nivel de 16 filas con el jugador a la izquierda, un ladrillo en medio y un enemigo
    a la derecha, todos en la fila del suelo; `row` es la fila 15 del mapa."""
    rows = list(ROWS16)
    rows[15] = row
    w = World(1, seed=1)
    data = parse_level(rows)
    w.solids, w.oneway, w.bricks = data.solids, data.oneway, data.bricks
    cls = TongueEnemy if kind == "E" else LaserEnemy
    x, y = data.enemy_spawns[0][:2]
    e = cls(x, y, 50, w.rng)
    w.enemies = [e]
    p = w.player
    p.place(data.player_spawn[0] + 6, data.player_spawn[1] + 8)
    e.direction, e.cooldown, e.jump_cd, e.coyote = -1, 0.0, 99, S.COYOTE_TIME
    p.invuln = 0
    return w, e, p


def test_bricks_are_parsed_and_solid():
    data = parse_level(["    L    "] + ROWS16[1:])
    assert len(data.bricks) == 1 and data.bricks[0] in data.solids


@pytest.mark.parametrize("kind", ["E", "A"])
def test_enemy_does_not_see_or_attack_through_brick(kind):
    # Enemigo dentro del alcance de cualquiera de los dos ataques; solo cambia el ladrillo
    w, e, p = _brick_world("P L" + kind + "     ", kind)   # P . L E
    step(w, 30)
    assert e.attack is None and w.lives == S.DIFFICULTIES["normal"]["lives"]
    # Sin el ladrillo, sí ataca
    w2, e2, p2 = _brick_world("P  " + kind + "     ", kind)
    p2.invuln = 99
    step(w2, 2)
    assert e2.attack is not None


def test_tongue_stops_at_brick():
    w, e, p = _brick_world("P   LE   ", "E")
    e.attack, e.attack_t = "tongue", S.TONGUE_OUT     # lengua estirada del todo
    e._measure_reach(w.solids)
    tongue = e.attack_rect()
    brick = w.bricks[0]
    assert tongue is None or tongue.left >= brick.right
    assert e.tongue_length <= e.rect.left - brick.right


def test_laser_beam_stops_at_brick():
    w, e, p = _brick_world("P  L  A  ", "A")
    e._start_attack(w.solids)
    e.attack = "fire"
    e._aim(w.solids)
    beam = e.attack_rect()
    assert beam.left == w.bricks[0].right and not beam.colliderect(p.rect)


def test_player_bubble_is_stopped_by_brick():
    w, e, p = _brick_world("P L  E   ", "E")
    e.direction = 1                                    # de espaldas: no ataca
    p.facing = 1
    w.player.invuln = 99
    step(w, 1)
    step(w, 1, {"bubble"})
    step(w, 40)
    assert e.state == "walk"                           # no lo ha atrapado
    assert all(b.rect.right <= w.bricks[0].right + S.BUBBLE_SIZE for b in w.bubbles)


def test_tall_level_has_bricks_and_both_enemy_types():
    w = World(TALL, seed=1)
    assert len(w.bricks) >= 6
    assert {e.kind for e in w.enemies} == {"tongue", "knife"}   # sin azules antes del 5
