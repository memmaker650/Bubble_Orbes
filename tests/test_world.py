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
    data = parse_level(LEVELS[i].rows)
    assert data.player_spawn is not None
    assert len(data.enemy_spawns) >= 1


def test_player_stands_on_floor_and_jumps():
    w = World(1, seed=1)
    step(w, 30)
    assert w.player.coyote > 0
    y0 = w.player.rect.y
    step(w, 1, {"jump"})
    step(w, 8)
    assert w.player.rect.y < y0 - 40
    step(w, 120)
    assert abs(w.player.rect.y - y0) <= 1  # vuelve a aterrizar


def test_player_can_reach_first_platform():
    w = World(1, seed=1)
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
    w = World(1, seed=1)
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
    w = World(1, seed=1)
    e = w.enemies[0]
    e.place(w.player.rect.x + 90, w.player.rect.y)
    e.direction = 1
    step(w, 3, {"bubble"})
    step(w, 40)
    w.bubbles[0].life = 0.01
    step(w, 3)
    assert e.state == "walk" and e.angry and not w.bubbles


def test_enemy_contact_costs_life_then_game_over():
    w = World(1, lives=2, seed=1)
    e = w.enemies[0]
    e.place(*w.player.rect.topleft)
    step(w, 1)
    assert w.lives == 1 and w.player.invuln > 0
    w.player.invuln = 0
    e.place(*w.player.rect.topleft)
    step(w, 1)
    assert w.state == "lost"


def test_every_level_has_star():
    for level in LEVELS:
        assert parse_level(level.rows).star_pos is not None


def test_clearing_enemies_alone_does_not_win():
    w = World(1, seed=1)
    for e in w.enemies:
        e.alive = False
    step(w, 1)
    assert w.state == "playing"
    assert not w.star.lit


def test_star_before_enemies_dead_shows_message():
    w = World(1, seed=1)
    w.player.place(*w.star.rect.topleft)
    step(w, 1)
    assert w.state == "playing"
    assert not w.star.lit
    assert w.message_timer > 0
    assert w.message == "star.kill_all"


def test_star_after_enemies_dead_wins_level():
    w = World(1, seed=1)
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
    w = World(1, seed=1)
    p = w.player
    for e in w.enemies:
        e.alive = False
    # De pie sobre la plataforma de la fila 3, bajo la estrella.
    p.place(w.star.rect.centerx - p.rect.width // 2, 3 * S.TILE - p.rect.height)
    step(w, 5)
    step(w, 1, {"jump"})
    step(w, 40)
    assert w.state == "won"


# --- tipos de enemigo ---
from orbes.entities import LaserEnemy, TongueEnemy  # noqa: E402

FLOOR_Y = (S.ROWS - 1) * S.TILE - 32


def _duel(cls, gap):
    """Mundo con un único enemigo en el suelo, a `gap` píxeles del jugador y mirándolo."""
    w = World(1, seed=1)
    w.enemies = [e for e in w.enemies if isinstance(e, cls)][:1]
    e, p = w.enemies[0], w.player
    p.place(60, FLOOR_Y)
    e.place(60 + 28 + gap, FLOOR_Y)
    e.direction = -1
    e.cooldown = 0.0
    e.jump_cd = 99
    e.coyote = S.COYOTE_TIME
    p.invuln = 0
    return w, e, p


def test_every_level_mixes_both_enemy_types():
    for i in range(len(LEVELS)):
        kinds = {e.kind for e in World(i, seed=1).enemies}
        assert kinds == {"tongue", "laser"}


def test_tongue_hits_player_at_range_without_touching():
    w, e, p = _duel(TongueEnemy, gap=80)
    lives = w.lives
    assert e.rect.left - p.rect.right == 80    # separados: solo llega la lengua
    step(w, 2)
    assert e.attack == "tongue"
    step(w, 15)
    assert w.lives == lives - 1


def test_tongue_does_not_attack_behind_or_far():
    w, e, p = _duel(TongueEnemy, gap=80)
    e.direction = 1          # mirando hacia el otro lado
    step(w, 1)
    assert e.attack is None
    w, e, p = _duel(TongueEnemy, gap=200)
    step(w, 1)
    assert e.attack is None


def test_laser_lasts_one_second_then_recharges_four():
    w, e, p = _duel(LaserEnemy, gap=200)
    p.invuln = 99            # observamos el ciclo sin perder vidas
    step(w, 1)
    assert e.attack == "windup"
    step(w, int(S.LASER_WINDUP * 60) + 1)
    assert e.attack == "fire"
    beam = e.attack_rect()
    assert beam.colliderect(p.rect) and beam.left <= S.TILE   # llega hasta el muro
    step(w, 50)              # ~0.85 s disparando: sigue activo
    assert e.attack == "fire"
    step(w, 12)              # pasado 1 s: se apaga
    assert e.attack is None and e.attack_rect() is None
    assert abs(e.cooldown - S.LASER_RECHARGE) < 0.1
    step(w, int(3.8 * 60))
    assert e.attack is None  # sigue recargando aunque vea al jugador
    step(w, 20)
    assert e.attack is not None


def test_laser_hits_player_across_room():
    w, e, p = _duel(LaserEnemy, gap=200)
    lives = w.lives
    step(w, int((S.LASER_WINDUP + 0.1) * 60))
    assert w.lives == lives - 1


def test_trapping_cancels_attack():
    w, e, p = _duel(LaserEnemy, gap=200)
    step(w, int((S.LASER_WINDUP + 0.1) * 60))
    e.trap()
    assert e.attack is None and e.attack_rect() is None


# --- dificultad ---

@pytest.mark.parametrize("name", S.DIFFICULTY_ORDER)
def test_difficulty_rules_are_applied(name):
    rules = S.DIFFICULTIES[name]
    w = World(1, seed=1, difficulty=name)
    base = World(1, seed=1)
    assert w.lives == rules["lives"]
    assert w.enemies[0].speed == pytest.approx(base.enemies[0].speed * rules["enemy_speed"])
    assert all(e.cooldown_factor == rules["cooldown"] for e in w.enemies)


def test_normal_difficulty_keeps_laser_one_second_four_recharge():
    w, e, p = _duel(LaserEnemy, gap=200)
    assert w.difficulty == "normal"
    p.invuln = 99
    step(w, int((S.LASER_WINDUP + S.LASER_DURATION) * 60) + 5)
    assert e.attack is None
    assert abs(e.cooldown - 4.0) < 0.1


def test_hard_recharges_faster_easy_slower():
    for name, expected in (("hard", 3.0), ("easy", 5.0)):
        w = World(1, seed=1, difficulty=name)
        e = next(e for e in w.enemies if isinstance(e, LaserEnemy))
        e._end_attack(S.LASER_RECHARGE)
        assert e.cooldown == pytest.approx(expected)


def test_unknown_difficulty_falls_back_to_normal():
    assert World(1, seed=1, difficulty="imposible").difficulty == "normal"
