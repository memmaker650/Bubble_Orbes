"""Los enemigos saltan un ladrillo que les corta el paso, para no quedarse encajonados entre
una pared y un ladrillo (el jugador no podría matarlos y no terminaría el nivel)."""

import random

from bubblequest import settings as S
from bubblequest.entities import Enemy, KnifeEnemy, LaserEnemy, TongueEnemy
from bubblequest.levels import parse_level

DT = 1 / 60
EMPTY = " " * 9


def boxed(extra=None):
    """Enemigo en la esquina de abajo a la izquierda, con un ladrillo a su derecha.
    ``extra``: {fila: texto} para añadir más casillas al mapa."""
    rows = [EMPTY] * S.ROWS
    rows[0] = "    S    "
    rows[-1] = "EL  P    "
    for r, text in (extra or {}).items():
        rows[r] = text
    data = parse_level(rows)
    x, y, _ = data.enemy_spawns[0]
    return data, (x, y)


def run(cls, data, pos, frames=600, seed=1):
    e = cls(*pos, S.ENEMY_BASE_SPEED, random.Random(seed))
    e.direction = 1
    e.jump_cd = 1e9          # sin saltos al azar: solo cuenta el salto del ladrillo
    brick = data.bricks[0]
    escaped = False
    for _ in range(frames):
        e.update(DT, data.solids, data.oneway, bricks=data.bricks)
        assert not e.rect.colliderect(brick)
        if e.rect.left >= brick.right:
            escaped = True
            break
    return e, escaped


def test_enemy_hops_over_brick_next_to_wall():
    for cls in (Enemy, TongueEnemy, LaserEnemy, KnifeEnemy):
        data, pos = boxed()
        _, escaped = run(cls, data, pos)
        assert escaped, cls.__name__


def test_enemy_hops_brick_walking_left():
    rows_last = "    P LE "
    data, pos = boxed({S.ROWS - 1: rows_last})
    e = Enemy(*pos, S.ENEMY_BASE_SPEED, random.Random(3))
    e.direction = -1
    e.jump_cd = 1e9
    brick = data.bricks[0]
    for _ in range(600):
        e.update(DT, data.solids, data.oneway, bricks=data.bricks)
        if e.rect.right <= brick.left:
            break
    assert e.rect.right <= brick.left


def test_enemy_does_not_hop_two_stacked_bricks():
    data, pos = boxed({S.ROWS - 2: " L       "})
    e, escaped = run(Enemy, data, pos, frames=300)
    assert not escaped
    assert e.rect.right <= data.bricks[0].left + 1


def test_enemy_does_not_hop_without_headroom():
    data, pos = boxed({S.ROWS - 2: "#        "})   # bloque justo encima del enemigo
    e, escaped = run(Enemy, data, pos, frames=300)
    assert not escaped
    assert not e.hopping


def test_enemy_still_turns_at_plain_walls():
    """Contra un bloque normal (no ladrillo) sigue dándose la vuelta, como antes."""
    data, pos = boxed({S.ROWS - 1: "E#  P    "})
    e = Enemy(*pos, S.ENEMY_BASE_SPEED, random.Random(1))
    e.direction = 1
    e.jump_cd = 1e9
    for _ in range(120):
        e.update(DT, data.solids, data.oneway, bricks=data.bricks)
    assert not e.hopping
    assert e.rect.right <= S.cell_pos(1, 0)[0]
