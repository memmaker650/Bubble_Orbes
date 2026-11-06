import pytest

from orbes import settings as S
from orbes.levels import LEVELS, parse_level
from orbes.world import World

DT = 1 / 60


def step(world, n, actions=()):
    for _ in range(n):
        world.update(DT, set(actions))


@pytest.mark.parametrize("i", range(len(LEVELS)))
def test_levels_parse(i):
    data = parse_level(LEVELS[i])
    assert data.player_spawn is not None
    assert len(data.enemy_spawns) >= 1


def test_player_stands_on_floor_and_jumps():
    w = World(0, seed=1)
    step(w, 30)
    assert w.player.coyote > 0
    y0 = w.player.rect.y
    step(w, 1, {"jump"})
    step(w, 8)
    assert w.player.rect.y < y0 - 40
    step(w, 120)
    assert abs(w.player.rect.y - y0) <= 1  # vuelve a aterrizar


def test_player_can_reach_first_platform():
    w = World(0, seed=1)
    p = w.player
    # En el suelo, justo bajo la plataforma de la fila 12 (columnas 1-2, x 40..120).
    p.place(60, (S.ROWS - 1) * S.TILE - p.rect.height)
    step(w, 10)
    assert p.rect.bottom == (S.ROWS - 1) * S.TILE
    step(w, 1, {"jump"})
    step(w, 80)
    # Atraviesa la plataforma desde abajo y aterriza encima de ella.
    assert p.rect.bottom == 12 * S.TILE


def test_bubble_traps_then_pop_scores():
    w = World(0, seed=1)
    e = w.enemies[0]
    p = w.player
    e.place(p.rect.x + 90, p.rect.y)
    e.direction = 1
    step(w, 3, {"bubble"})
    step(w, 40)
    assert e.state == "trapped"
    bubble = w.bubbles[0]
    assert bubble.captured is e

    step(w, 20)  # la burbuja ya está "armada"
    p.place(*bubble.rect.topleft)
    step(w, 1)
    assert not e.alive
    assert w.score >= S.POINTS_ENEMY


def test_trapped_enemy_escapes_angry():
    w = World(0, seed=1)
    e = w.enemies[0]
    e.place(w.player.rect.x + 90, w.player.rect.y)
    e.direction = 1
    step(w, 3, {"bubble"})
    step(w, 40)
    w.bubbles[0].life = 0.01
    step(w, 3)
    assert e.state == "walk" and e.angry and not w.bubbles


def test_enemy_contact_costs_life_then_game_over():
    w = World(0, lives=2, seed=1)
    e = w.enemies[0]
    e.place(*w.player.rect.topleft)
    step(w, 1)
    assert w.lives == 1 and w.player.invuln > 0
    w.player.invuln = 0
    e.place(*w.player.rect.topleft)
    step(w, 1)
    assert w.state == "lost"


def test_every_level_has_star():
    for rows in LEVELS:
        assert parse_level(rows).star_pos is not None


def test_clearing_enemies_alone_does_not_win():
    w = World(0, seed=1)
    for e in w.enemies:
        e.alive = False
    step(w, 1)
    assert w.state == "playing"
    assert not w.star.lit


def test_star_before_enemies_dead_shows_message():
    w = World(0, seed=1)
    w.player.place(*w.star.rect.topleft)
    step(w, 1)
    assert w.state == "playing"
    assert not w.star.lit
    assert w.message_timer > 0
    assert w.message == "star.kill_all"


def test_star_after_enemies_dead_wins_level():
    w = World(0, seed=1)
    for e in w.enemies:
        e.alive = False
    step(w, 30)
    w.player.place(*w.star.rect.topleft)
    step(w, 1)
    assert w.state == "won"
    assert w.star.lit
    assert w.score == S.POINTS_LEVEL
    assert w.level_points == S.POINTS_LEVEL
    assert w.elapsed > 0.4


def test_star_is_reachable_from_top_platform():
    w = World(0, seed=1)
    p = w.player
    for e in w.enemies:
        e.alive = False
    # De pie sobre la plataforma de la fila 3, bajo la estrella.
    p.place(w.star.rect.centerx - p.rect.width // 2, 3 * S.TILE - p.rect.height)
    step(w, 5)
    step(w, 1, {"jump"})
    step(w, 40)
    assert w.state == "won"
